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

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="pyyaml (dev extra) parses workflows")

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
MAX_JOB_MINUTES = 45


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
    """The Docker matrix is the pipeline's critical path (~11 min): its
    budget must exceed the observed wall time but stay far below the
    default — a silently slowed matrix surfaces as a TIMEOUT, not as a
    three-hour hang."""
    timeout = _load("ci.yml")["jobs"]["docker-e2e"].get("timeout-minutes")
    assert 20 <= timeout <= MAX_JOB_MINUTES
