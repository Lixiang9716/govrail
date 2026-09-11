"""End-to-end lifecycle tests: the plane driven as an adopter drives it.

These are the black-box, whole-product scenarios — every act spins up a
fresh git project and speaks to ``gov`` ONLY through the CLI (exit codes
and printed output), the way the release wheel is experienced. The
unit/feature suites pin internals; this file pins the JOURNEY:

- Act 1 — adopt and govern: init, doctor, pairing baseline + drift,
  notes, note-presence, the full template gate DAG, conflict markers,
  decisions, the archive seal, the task lifecycle with its receipt,
  run receipts, trend, stats, check, whatsnew, and the uninstall
  roundtrip.
- Act 2 — parallel agents: lease locks (busy, wrong-holder, takeover),
  the task-claim race, and ``run --merge`` preflighting a clean union
  and catching a conflicting one.
- Act 3 — presets and upgrades: preset discovery/application
  (idempotent, additive), a governance-mode run over the adopted gate,
  and ``init --upgrade`` machine-readable drift.

Everything here is portable by construction (git + the interpreter,
nothing POSIX-exec-inherent); hook EXECUTION is covered by the
dedicated hook tests, so it is only asserted as wiring here.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PASS_CMD_ARGS = ["-c", "pass"]


def _gov_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PYTHONPATH"] = str(REPO)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def gov(*args, cwd=None, expect=0, timeout=300):
    """One CLI invocation, asserted against its expected exit code."""
    cwd = cwd or REPO  # a real directory on every platform
    r = subprocess.run(
        [sys.executable, "-m", "gov", *args], cwd=cwd,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=_gov_env(), timeout=timeout)
    assert r.returncode == expect, (
        f"gov {' '.join(args)} -> {r.returncode}, expected {expect}\n"
        f"--- stdout\n{r.stdout}\n--- stderr\n{r.stderr}")
    return r


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=check)


def commit_all(cwd, msg):
    git("add", "-A", cwd=cwd)
    git("-c", "commit.gpgsign=false", "commit", "-qm", msg, cwd=cwd)


def branch_name(cwd) -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd).stdout.strip()


@pytest.fixture()
def project(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    git("init", "-q", ".", cwd=p)
    git("config", "user.email", "t@t", cwd=p)
    git("config", "user.name", "t", cwd=p)
    (p / "README.md").write_text("# demo project\n", encoding="utf-8")
    (p / "README.zh.md").write_text("# 演示项目\n", encoding="utf-8")
    commit_all(p, "init")
    return p


# --------------------------------------------------------------------------
# Act 1 — adopt and govern
# --------------------------------------------------------------------------

def test_act1_adopt_and_govern(project):
    # --- adoption ---------------------------------------------------------
    gov("init", cwd=project)
    assert (project / ".gov" / "rules.md").exists()
    assert (project / "gates.json").exists()
    assert (project / ".agents" / "notes" / "README.md").exists()
    r = gov("init", cwd=project)  # second init is a no-op, announced
    assert "already initialized" in r.stdout
    r = gov("doctor", cwd=project)
    assert "environment sound" in r.stdout
    assert "parse layer ok" in r.stdout  # D54: the parse layer is reported

    # --- pairing: baseline, then drift is red and the fix closes it ------
    docs = project / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("the english guide\n", encoding="utf-8")
    (docs / "guide.zh.md").write_text("中文指南\n", encoding="utf-8")
    gov("verify-pairing", "--write", cwd=project)
    commit_all(project, "docs pair + baseline")
    (docs / "guide.zh.md").write_text("改过的中文\n", encoding="utf-8")
    gov("verify-pairing", cwd=project, expect=1)  # drift is red
    gov("verify-pairing", "--write", cwd=project)  # the scoped fix
    gov("verify-pairing", cwd=project)  # and the pair is green again

    # --- notes: scaffold, fill, format gate ------------------------------
    r = gov("note", "new", "--class", "bug-fix", "the first note",
            cwd=project)
    note = next((project / ".agents" / "notes" / "implemented" / "bug-fix")
                .glob("*.md"))
    note.write_text(
        "# Agent Note: the first note\n\nStatus: implemented\n\n"
        "## Problem\nthe demo needed a note\n\n"
        "## Decision\nwrote one\n\n"
        "## Alternatives considered\nnot writing one — rejected\n",
        encoding="utf-8")
    gov("verify-notes", cwd=project)
    commit_all(project, "the first note")

    # --- note-presence: the advisory warns, the note closes it ----------
    (project / "app.py").write_text("value = 1\n", encoding="utf-8")
    commit_all(project, "code change without a note")
    r = gov("verify-note-presence", cwd=project)  # advisory: never blocks
    assert "app.py" in r.stdout
    note_dir = project / ".agents" / "notes" / "implemented" / "bug-fix"
    (note_dir / "2026-01-01-covers-the-change.md").write_text(
        "# Agent Note: covers the change\n\nStatus: implemented\n\n"
        "## Problem\np\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")
    commit_all(project, "the note arrives")
    gov("verify-note-presence", cwd=project)

    # --- the full template DAG is green ----------------------------------
    r = gov("run", cwd=project)
    assert "7 gates" in r.stdout and "7 pass" in r.stdout

    # --- conflict markers: red with file:line, then resolved -------------
    (project / "tangled.md").write_text(
        "intro\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n",
        encoding="utf-8")
    r = gov("run", "--base", "HEAD", cwd=project, expect=1)
    assert "tangled.md" in r.stdout
    (project / "tangled.md").write_text("resolved by hand\n",
                                        encoding="utf-8")
    gov("run", "--base", "HEAD", cwd=project)

    # --- decisions: next number and the table guard ----------------------
    (project / "docs" / "decisions.md").write_text(
        "## D1 — adopt the plane\n\n- **选项**：gov init\n\n"
        "- **状态**：已决\n", encoding="utf-8")
    (project / "docs" / "decisions.zh.md").write_text(
        "## D1 — 采用本平面\n\n- **选项**：gov init\n\n"
        "- **状态**：已决\n", encoding="utf-8")
    gov("verify-pairing", "--write", cwd=project)  # the new pair baselines
    r = gov("decision", "next", cwd=project)
    assert "D2" in r.stdout
    gov("verify-decisions", cwd=project)

    # --- the archive seal -------------------------------------------------
    arch = project / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    frozen = arch / "2026-01-01-old-decision.md"
    frozen.write_text("# Agent Note: old decision\n\nStatus: archived\n",
                      encoding="utf-8")
    gov("archive-notes", cwd=project)
    gov("verify-archive", cwd=project)
    frozen.write_text("# Agent Note: old decision — TAMPERED\n",
                      encoding="utf-8")
    gov("verify-archive", cwd=project, expect=1)  # a drift cannot hide
    frozen.write_text("# Agent Note: old decision\n\nStatus: archived\n",
                      encoding="utf-8")
    gov("archive-notes", cwd=project)  # re-seal the honest content

    # --- the task lifecycle: claim, race, close with a receipt -----------
    gov("task", "new", "Write the demo feature", cwd=project)
    r = gov("task", "list", cwd=project)
    assert "T-0001" in r.stdout
    gov("task", "claim", "T-0001", "--agent", "worker-1", cwd=project)
    gov("task", "claim", "T-0001", "--agent", "worker-2", cwd=project,
        expect=3)  # busy: two workers cannot take one card
    gov("task", "release", "T-0001", "--agent", "worker-1", cwd=project)
    commit_all(project, "task card in tree")
    gov("task", "close", "T-0001", cwd=project)  # runs the DAG; green = done
    r = gov("task", "check", cwd=project)
    assert "done" in r.stdout and "T-0001" in r.stdout, \
        "the closed card reads done, never STALE"

    # --- run receipts: "an agent verified this" becomes checkable --------
    commit_all(project, "settled tree")
    gov("run", "--receipt", "--tag", "e2e", cwd=project)
    ledger = project / ".gov" / "history" / "receipts.jsonl"
    assert ledger.exists()
    gov("receipt", "verify", "HEAD", cwd=project)

    # --- trend, stats, check, whatsnew ------------------------------------
    r = gov("trend", cwd=project)
    assert "run(s) in" in r.stdout
    (project / "lib.py").write_text("def usable():\n    return 1\n",
                                    encoding="utf-8")
    r = gov("stats", "--json", "--lang", "python", cwd=project)
    value = json.loads(r.stdout)
    assert value["languages"]["python"]["symbols"]["functions"] >= 1
    gov("check", cwd=project)  # clean: the parse layer's checks pass
    # in a governed project the default `since` is the manifest's init
    # version — ask for an older one to see the sections an upgrade brings
    r = gov("whatsnew", "--since", "0.1.0", cwd=project)
    assert "## 0.30.0" in r.stdout

    # --- uninstall reverses exactly ---------------------------------------
    gov("uninstall", "--force", cwd=project)
    assert not (project / "gates.json").exists()
    assert not (project / ".gov").exists()
    assert not (project / "AGENTS.md").exists()
    assert (project / "README.md").exists()  # the project's own file stays


# --------------------------------------------------------------------------
# Act 2 — parallel agents
# --------------------------------------------------------------------------

def test_act2_locks_and_merge_preflight(project):
    gov("init", cwd=project)
    commit_all(project, "adopted")

    # --- lease locks: busy, wrong-holder, takeover ------------------------
    gov("acquire", "res/e2e", "--agent", "a1", cwd=project)
    gov("acquire", "res/e2e", "--agent", "a2", cwd=project, expect=3)
    r = gov("locks", cwd=project)
    assert "e2e" in r.stdout
    gov("release", "res/e2e", "--agent", "a2", cwd=project, expect=2)
    gov("release", "res/e2e", "--agent", "a1", cwd=project)
    gov("acquire", "res/ttl", "--agent", "a1", "--ttl", "1", cwd=project)
    time.sleep(1.3)
    gov("acquire", "res/ttl", "--agent", "a2", cwd=project)  # lazy takeover
    gov("release", "res/ttl", "--agent", "a2", cwd=project)

    # --- the claim race, one card, two workers ----------------------------
    gov("task", "new", "Racy work", cwd=project)
    gov("task", "claim", "T-0001", "--agent", "w1", cwd=project)
    gov("task", "claim", "T-0001", "--agent", "w2", cwd=project, expect=3)
    gov("task", "release", "T-0001", "--agent", "w1", cwd=project)

    # --- run --merge: a clean union lands, a conflict keeps the scene ----
    base = branch_name(project)
    (project / "gates.json").write_text(json.dumps(
        {"gates": [{"id": "ok",
                    "command": [sys.executable, *PASS_CMD_ARGS]}]}),
        encoding="utf-8")
    commit_all(project, "one green gate")
    git("checkout", "-q", "-b", "branch-a", cwd=project)
    (project / "left.txt").write_text("left\n", encoding="utf-8")
    commit_all(project, "a")
    git("checkout", "-q", base, cwd=project)
    git("checkout", "-q", "-b", "branch-b", cwd=project)
    (project / "right.txt").write_text("right\n", encoding="utf-8")
    commit_all(project, "b")
    git("checkout", "-q", base, cwd=project)
    gov("run", "--merge", "branch-a", "branch-b", "--base", base,
        cwd=project)

    git("checkout", "-q", "-b", "branch-c", base, cwd=project)
    (project / "shared.txt").write_text("c version\n", encoding="utf-8")
    commit_all(project, "c")
    git("checkout", "-q", "-b", "branch-d", base, cwd=project)
    (project / "shared.txt").write_text("d version\n", encoding="utf-8")
    commit_all(project, "d")
    git("checkout", "-q", base, cwd=project)
    r = gov("run", "--merge", "branch-c", "branch-d", "--base", base,
            cwd=project, expect=1)
    assert "conflicts with already-merged set" in r.stdout
    kept = [line for line in r.stdout.splitlines()
            if "kept for inspection" in line]
    assert kept, "a conflicted preflight keeps its scene"
    scene = Path(kept[0].split("kept for inspection:", 1)[1].strip())
    try:
        assert scene.is_dir()
        assert "<<<<<<<" in (scene / "shared.txt").read_text(encoding="utf-8")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force",
                        str(scene)], cwd=project, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=project,
                       capture_output=True)


# --------------------------------------------------------------------------
# Act 3 — presets and upgrades
# --------------------------------------------------------------------------

def test_act3_presets_and_upgrades(project):
    r = gov("preset", "list")
    assert "agent-heavy" in r.stdout
    r = gov("preset", "show", "agent-heavy")
    assert "parallel-workers" in r.stdout
    # applying into an uninitialized project is refused, named
    r = gov("preset", "apply", "agent-heavy", "--project", ".",
            cwd=project, expect=2)
    assert "initialized" in (r.stderr + r.stdout)

    gov("init", cwd=project)
    r = gov("preset", "apply", "agent-heavy", cwd=project)
    gates = json.loads((project / "gates.json").read_text(encoding="utf-8"))
    assert "verify-decisions" in gates["modes"]["governance"]
    skill = project / ".agents" / "skills" / "parallel-workers" / "SKILL.md"
    assert skill.exists()
    manifest = json.loads((project / ".gov" / "manifest.json")
                          .read_text(encoding="utf-8"))
    assert manifest.get("note_presence_exempt") == [".gov/tasks/**"]
    # idempotent: re-apply adopts nothing and writes nothing
    r = gov("preset", "apply", "agent-heavy", cwd=project)
    assert "already adopted" in r.stdout

    # a governance-mode run over the adopted surface
    (project / "docs").mkdir(exist_ok=True)
    (project / "docs" / "decisions.md").write_text(
        "## D1 — adopt\n\n- **选项**：the plane\n\n- **状态**：已决\n",
        encoding="utf-8")
    commit_all(project, "preset adopted")
    gov("run", "--mode", "governance", cwd=project)

    # upgrades are read-only and machine-readable
    r = gov("init", "--upgrade", cwd=project)
    assert "matches the shipped template" in r.stdout or "DIFFERS" in \
        r.stdout
    r = gov("init", "--upgrade", "--json", cwd=project)
    value = json.loads(r.stdout)  # exactly one JSON value
    assert "files" in value and "package" in value
