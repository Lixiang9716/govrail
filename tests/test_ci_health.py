"""CI health invariants — the workflow files are themselves gated.

Every CI incident this repository has had left a scar that a test could
have caught BEFORE the push:

- a step name with a colon-space broke YAML parsing and every workflow
  run died at 0s across two pushes (found live, 2026-09-16);
- jobs had no timeout-minutes, so a hung subprocess burned GitHub's
  6-hour default instead of failing in minutes;
- ``on: push`` with no branch filter ran the whole matrix twice per
  change (branch push + PR event), doubling cost and noise;
- no concurrency group let successive pushes interleave stale runs;
- renaming the required check (the host matrix) BLOCKED every merge,
  because branch protection pins the check by exact name.

These tests parse the workflow files on every host run so the next
violation is a local red, not a 0-second GitHub failure.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml (dev extra) parses workflows")

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
MAX_JOB_MINUTES = 60


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_every_workflow_file_parses():
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert files, "no workflow files found — CI has been moved or deleted"
    for f in files:
        assert isinstance(_load(f.name), dict), f"{f.name} is not valid YAML"


def test_ci_every_job_has_a_bounded_timeout():
    """A job without timeout-minutes hangs for GitHub's 6-hour default."""
    for name, workflow in _load("ci.yml")["jobs"].items():
        timeout = workflow.get("timeout-minutes")
        assert isinstance(timeout, int) and 0 < timeout <= MAX_JOB_MINUTES, (
            f"ci.yml job {name!r} has no bounded timeout-minutes — a hang "
            f"burns hours; give it a budget of 1..{MAX_JOB_MINUTES}")
    for name, workflow in _load("release-please.yml")["jobs"].items():
        assert isinstance(workflow.get("timeout-minutes"), int), (
            f"release-please.yml job {name!r} needs a timeout-minutes")


def test_ci_runs_once_per_change():
    """`on: push` with no branch filter + the PR event ran every matrix
    twice per change (branch push AND PR), doubling cost and noise.
    Branch coverage belongs to the PR event; master pushes self-verify."""
    ci = _load("ci.yml")
    on = ci.get(True) or ci.get("on")  # YAML 1.1: bare `on` parses as True
    push = on.get("push")
    assert push is not None, "push trigger removed entirely?"
    branches = push.get("branches") if isinstance(push, dict) else None
    assert branches == ["master"], (
        f"push trigger must be pinned to master (got {branches!r}) — an "
        "unfiltered push hook runs the whole matrix twice per change")
    assert "pull_request" in on, (
        "branch coverage belongs to the pull_request event — a bare "
        "`pull_request:` key is enough (its value parses as null)")


def test_ci_cancels_superseded_runs():
    """Successive pushes to one branch must not interleave stale runs."""
    ci = _load("ci.yml")
    concurrency = ci.get("concurrency") or {}
    assert concurrency.get("group"), "concurrency group missing"
    assert concurrency.get("cancel-in-progress") is True, (
        "cancel-in-progress missing — superseded runs keep burning runners "
        "and their late verdicts read as the branch's state")


def test_required_check_name_stays_stable():
    """Branch protection requires the check `gates` by exact name. The
    host matrix renamed its checks per cell (`gates (3.10)`…), which
    made the required name unsatisfiable and BLOCKED every merge
    (#192 needed an admin bypass). The matrix job must stay
    `gates-cell`, and a `gates` job must exist as the stable summary."""
    jobs = _load("ci.yml")["jobs"]
    assert "gates-cell" in jobs, (
        "the matrix job must stay named 'gates-cell' — renaming it renames "
        "every cell check and un-satisfies the required 'gates' check")
    gates = jobs.get("gates")
    assert gates is not None, (
        "the stable required check 'gates' is gone — branch protection "
        "requires it by exact name and every merge BLOCKS without it")
    assert "gates-cell" in (gates.get("needs") or []), (
        "the 'gates' summary must depend on gates-cell, or it reports "
        "green without the matrix having run")


def test_docker_e2e_is_the_long_pole_and_bounded():
    """The Docker matrix is the pipeline's critical path: its budget must
    exceed the observed wall time but stay far below the default — a
    silently slowed cell surfaces as a TIMEOUT, not a three-hour hang."""
    timeout = _load("ci.yml")["jobs"]["e2e-docker"].get("timeout-minutes")
    assert 20 <= timeout <= MAX_JOB_MINUTES


def test_docker_cells_are_individually_rerunnable():
    """The monolith split (orthogony): one job per docker cell, so a red
    cell is named and rerunnable without re-running the whole matrix —
    and the hostile-locale + nonroot cells are pinned into it."""
    matrix = (_load("ci.yml")["jobs"]["e2e-docker"]["strategy"]
              ["matrix"]["cell"])
    for cell in ("gbk", "nonroot", "3.10-slim", "3.13-slim",
                 "3.12-alpine", "cross"):
        assert cell in matrix, f"docker cell {cell!r} left the matrix"


def test_macos_is_a_first_class_platform():
    assert "macos" in _load("ci.yml")["jobs"], (
        "macos is a declared platform (pyproject classifiers) — the host "
        "suite must run there, not only on linux and windows")


def test_nightly_scale_tier_never_runs_on_prs():
    """The 10k/20k-file perf tier is nightly-only: an `if` guarding on
    the schedule event keeps it off every PR's critical path."""
    nightly = _load("ci.yml")["jobs"]["nightly"]
    assert nightly.get("if") and "schedule" in nightly["if"], (
        "nightly must be schedule-gated")


def test_governance_dogfooding_runs_once_not_per_version():
    """The rejection cases + full DAG are version-agnostic: they run
    once in the governance job, not four times across the matrix."""
    governance = _load("ci.yml")["jobs"]["governance"]
    steps = " ".join(s.get("name", "") + " " + s.get("run", "")
                     for s in governance.get("steps", []))
    assert "self-test" in steps and "gov run" in steps
    cell = _load("ci.yml")["jobs"]["gates-cell"]
    cell_steps = " ".join(s.get("name", "") + " " + s.get("run", "")
                          for s in cell.get("steps", []))
    assert "self-test" not in cell_steps and "gov run" not in cell_steps, (
        "the version matrix must stay orthogonal to the governance DAG")


def test_release_pr_carries_the_highlights_draft_in_its_commit():
    """The release race (found live on the 0.31.0 release): the PR's
    creation fired CI on a pre-draft SHA and the late drafting push
    could not heal a bot-PR's action_required run. The drafting step
    must AMEND the draft into the release commit, and superseded
    pending runs must be cancelled so only the complete SHA is
    approvable."""
    rp = _load("release-please.yml")
    jobs = rp["jobs"]
    assert "highlights" in jobs, "the drafting job disappeared"
    run_text = " ".join(
        s.get("run", "") for s in jobs["highlights"].get("steps", []))
    assert "--amend" in run_text, (
        "the HIGHLIGHTS draft must join the release commit itself "
        "(--amend), not ride a late follow-up commit")
    assert "action_required" in run_text and "/cancel" in run_text, (
        "superseded pending runs on the pre-draft SHA must be cancelled "
        "— approving one re-runs the race")
    assert rp.get("permissions", {}).get("actions") == "write", (
        "cancelling workflow runs needs actions: write")


def test_release_automation_is_end_to_end():
    """The 0.31.0 postmortem, structural half: the release chain must be
    closable without a human in the loop. RELEASE_PAT (falling back to
    the default token so nothing breaks while the secret is unset)
    pushes as a user identity — its CI run starts instead of sitting in
    action_required; the arming step lets GitHub squash-merge the PR the
    moment the required checks pass."""
    rp = _load("release-please.yml")
    jobs = rp["jobs"]
    release_steps = jobs["release"]["steps"]
    uses = [s.get("uses", "") for s in release_steps]
    assert any("release-please-action" in u for u in uses)
    token = " ".join(s.get("with", {}).get("github-token", "")
                     for s in release_steps if "with" in s)
    assert "secrets.RELEASE_PAT" in token and "github.token" in token, (
        "the release action must run under RELEASE_PAT with a fallback "
        "token — the fallback alone re-introduces the action_required "
        "human gate")
    hl_text = " ".join(s.get("name", "") for s in
                       jobs["highlights"].get("steps", []))
    assert "auto-merge" in hl_text.lower(), (
        "the release PR must be armed for auto-merge — CI green should "
        "merge, tag, and publish without a human")


def test_pytest_runs_are_parallelized():
    """The suite is subprocess-heavy (gov invocations, scratch repos):
    xdist workers overlap the waits instead of paying them serially.
    Serial was 53s; -n 4 is 20s. A new pytest step without -n re-pays
    the serial cost on every PR."""
    import re
    ci = _load("ci.yml")
    offenders = []
    for name, job in ci["jobs"].items():
        for step in job.get("steps", []):
            run = step.get("run", "")
            if "pip install" in run:
                continue
            for line in run.splitlines():
                if re.match(r"^\s*(python -m )?pytest\b", line) \
                        and re.search(r"-n\s", line) is None:
                    offenders.append(f"{name}: {line.strip()}")
    assert not offenders, (
        "pytest invoked without -n (xdist) — the suite is "
        "subprocess-heavy and loses ~2.5x wall clock serially:\n"
        + "\n".join(offenders))


def test_derived_truths_regenerate_in_ci():
    """The register's derived rows are CI-enforced, not memory-enforced:
    the derive job runs scripts/derive_all.py (--check on PRs — drift
    goes red naming the command), regenerates and COMMITS on master
    merge pushes (the PAT identity, so the push re-triggers CI), and
    carries a loop guard (a derivation commit that still drifts stops
    the job instead of push-cycling)."""
    ci = _load("ci.yml")
    jobs = ci["jobs"]
    assert "derive" in jobs, "the derive job disappeared — derived "
    "truths are back to memory-enforced"
    steps = " ".join(s.get("run", "") + s.get("name", "")
                     for s in jobs["derive"].get("steps", []))
    assert "derive_all.py --check" in steps, (
        "PR-side must be a drift probe (--check)")
    assert "derive_all.py" in steps and "git push" in steps, (
        "master-side must regenerate and push")
    assert "loop guard" in steps or "derivation commit" in steps, (
        "the auto-push needs its loop guard")
    needs = ci["jobs"]["gates"].get("needs", [])
    assert "derive" in needs, (
        "derive must feed the required gates summary — drift that "
        "cannot block a merge is advisory drift")


def test_ci_is_path_aware():
    """Docs-only changes (nothing the wheel or e2e image ships) run the
    doc-facing set, not the world: the platform suites, hostile locale,
    shadow install, and ten docker cells skip; ONE pytest cell (3.12)
    stays unconditional so the required `gates` summary can never
    starve — the #193 lesson holds under path-awareness."""
    ci = _load("ci.yml")
    jobs = ci["jobs"]
    assert "changes" in jobs, "the path classifier job disappeared"
    classify = json.dumps(jobs["changes"])
    assert "dorny/paths-filter" in classify and "gov/**" in classify, (
        "the classifier must name the wheel/e2e path set")
    # heavy jobs skip on docs-only
    for job in ("backport-shadow", "windows", "macos", "gbk-locale",
                "e2e-docker"):
        cond = jobs[job].get("if", "")
        assert "docs_only" in cond, (
            f"{job} runs unconditionally — a prose edit pays its full "
            "price; gate it on the classifier")
    # one pytest cell always runs
    cell = jobs["gates-cell"]
    cond = cell.get("if", "")
    assert "docs_only" in cond and "'3.12'" in cond, (
        "gates-cell must keep one unconditional cell (3.12) — the "
        "required summary starves otherwise")
    for job in ("lint", "derive", "governance"):
        assert "docs_only" not in jobs[job].get("if", "none"), (
            f"{job} is doc-relevant by design; do not skip it for "
            "docs-only changes")
