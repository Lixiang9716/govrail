"""The four-state exit contract, mechanically pinned (D56's revision).

``0 ok · 1 failure · 2 config/usage · 3 lease busy`` is written into
``gov --help``. A contract that lives in prose without a pin test goes
stale exactly like the README's hand-copied help and the 0.12-era flag
registry did — this module is the pin:

- **leg 2, universal**: every command in ``cli._COMMANDS`` refuses an
  unknown flag with exit 2 — the registry is the command table itself,
  so a new command is covered the moment it exists (the probe for this
  leg caught ``verify-notes`` swallowing an unknown flag and answering
  a mistyped invocation with a green verdict);
- **leg 1, registry**: failure-capable commands declare a pinned red
  invocation; a new command must join this registry or the declared
  complement — undeclared, the coverage test below goes red, which is
  "new commands comply from day one" made mechanical;
- **leg 3**: acquire busy;
- **polarity**: without ``--json``, stdout carries the human report and
  errors stay on stderr; with it, stdout is exactly one machine value.

The complement set's members do have red paths — they are pinned in the
self-test's rejection cases (rule 6's ledger) rather than duplicated
here; the declaration says where each lives.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gov import cli

PASS = [sys.executable, "-c", "pass"]
FAIL = [sys.executable, "-c", "raise SystemExit(1)"]


def _repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path,
                   check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path,
                   check=True)


def _commit(tmp_path: Path, msg: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", msg],
        cwd=tmp_path, check=True)


REPO = Path(__file__).resolve().parent.parent


def _invoke(argv: list[str], cwd: Path, stdin: str | None = None) -> int:
    """Every leg runs through a REAL subprocess: the contract under test
    is the process exit code, not an in-process return value."""
    env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONUTF8": "1"}
    try:
        return subprocess.run(
            [sys.executable, "-m", "gov", *argv], cwd=cwd, check=False,
            input=stdin, capture_output=True, text=True, timeout=300,
            env=env, encoding="utf-8", errors="replace").returncode
    except SystemExit as e:  # argparse's error path exits instead of returning
        return e.code


# --- leg 2: unknown flags are usage errors, everywhere -----------------

@pytest.mark.parametrize("command", sorted(cli._COMMANDS))
def test_usage_error_is_two(command, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = _invoke([command, "--surely-not-a-flag-xyz"], tmp_path)
    assert rc == 2, f"`gov {command}` must answer an unknown flag with 2"


# --- leg 1: the failure registry ---------------------------------------
# Each entry prepares a deterministic red state and returns the argv that
# must exit 1. A command whose red path is pinned elsewhere (self-test's
# rejection cases) lives in NEVER_ONE_HERE instead — the union of both
# sets must be every command (the coverage test below).

def _red_run(tmp_path):
    (tmp_path / "gates.json").write_text(json.dumps(
        {"gates": [{"id": "a", "command": FAIL}]}), encoding="utf-8")
    _repo(tmp_path)
    _commit(tmp_path, "x")
    return ["run"]


def _red_verify_notes(tmp_path):
    d = tmp_path / ".agents" / "notes" / "implemented" / "bug-fix"
    d.mkdir(parents=True)
    (d / "2026-01-01-b.md").write_text("no title, no sections\n",
                                       encoding="utf-8")
    return ["note", "verify"]


def _red_verify_note_presence(tmp_path):
    _repo(tmp_path)
    (tmp_path / "app.py").write_text("v1\n", encoding="utf-8")
    _commit(tmp_path, "x")
    (tmp_path / "app.py").write_text("v2\n", encoding="utf-8")
    return ["note", "presence", "--strict"]


def _red_verify_rubric(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    (docs / "review-rubric.md").write_text("not a rubric\n", encoding="utf-8")
    return ["verify", "rubric"]


def _red_verify_decisions(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)
    (docs / "decisions.md").write_text(
        "## D1 — a\n\n- **选项**：x\n\n## D1 — b\n\n- **选项**：y\n",
        encoding="utf-8")
    return ["decision", "verify"]


def _red_verify_doc_sync(tmp_path):
    (tmp_path / "gov").mkdir()
    (tmp_path / ".gov").mkdir()
    (tmp_path / "gov" / "HIGHLIGHTS.md").write_text("", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [9.9.9] — x\n\nnothing\n",
                                           encoding="utf-8")
    (tmp_path / ".gov" / "docsync.json").write_text(
        json.dumps({"highlights": "gov/HIGHLIGHTS.md"}), encoding="utf-8")
    return ["verify", "doc-sync"]


def _red_verify_conflict_markers(tmp_path):
    _repo(tmp_path)
    (tmp_path / "tangled.md").write_text(
        "intro\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n",
        encoding="utf-8")
    return ["verify", "conflict-markers"]


def _red_check(tmp_path):
    (tmp_path / "bad.py").write_text(
        "import subprocess\n"
        'subprocess.run(["ls"], capture_output=True, text=True)\n',
        encoding="utf-8")
    return ["check", "--all"]


def _red_review(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    item = ("- **Checks:** `feature.txt` reviewed\n"
            "- **Evidence:** reviewed above\n"
            "- **Anti-pattern:** rubber stamp\n"
            "- **Gate candidate:** no — judgment\n")
    (docs / "review-rubric.md").write_text(
        "# Review rubric\n\n### R1 — a thing\n\n" + item + "\n",
        encoding="utf-8")
    _repo(tmp_path)
    (tmp_path / "feature.txt").write_text("the feature\n", encoding="utf-8")
    return ["review", "--base", "HEAD", "--grade"], "q\n"


def _red_receipt(tmp_path):
    _repo(tmp_path)
    (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")
    _commit(tmp_path, "i")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          check=True).stdout.strip()
    return ["receipt", "verify", head]


def _red_task(tmp_path):
    assert cli.init(tmp_path) == 0
    from gov import task
    combined, _ = task.rules_hash(tmp_path)
    cards = tmp_path / ".gov" / "tasks"
    cards.mkdir(parents=True, exist_ok=True)
    (cards / "T-0001-x.json").write_text(json.dumps({
        "id": "T-0001", "title": "x", "rules": {"hash": combined},
        "checklist": [], "status": "done", "receipt": None,
    }), encoding="utf-8")
    return ["task", "check"]


def _red_uninstall(tmp_path):
    assert cli.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    rules.write_text(
        rules.read_text(encoding="utf-8") + "\ncustom\n", encoding="utf-8")
    return ["uninstall"]


def _red_doctor(tmp_path):
    (tmp_path / "gates.json").write_text(
        json.dumps({"gates": [{"id": "a"}]}), encoding="utf-8")
    return ["doctor"]


def _red_verify_plane(tmp_path):
    assert cli.init(tmp_path) == 0
    gates = tmp_path / "gates.json"
    gates.write_text(
        json.dumps({"modes": {}, "gates": []}), encoding="utf-8")
    return ["verify-plane"]


def _red_recall(tmp_path):
    return ["recall", "anything"]


def _red_note(tmp_path):
    d = tmp_path / ".agents" / "notes" / "implemented" / "bug-fix"
    d.mkdir(parents=True)
    (d / "2026-01-01-b.md").write_text("garbage\n", encoding="utf-8")
    return ["note", "check"]


FAILURE_LEGS = {
    "run": _red_run,
    "note": _red_verify_notes,          # gov note verify
    "verify": _red_verify_conflict_markers,
    "decision": _red_verify_decisions,  # gov decision verify
    "check": _red_check,
    "review": _red_review,
    "receipt": _red_receipt,
    "task": _red_task,
    "uninstall": _red_uninstall,
    "doctor": _red_doctor,
    "verify-plane": _red_verify_plane,
    "recall": _red_recall,
}

# Their red paths are pinned in the self-test's rejection cases and
# verdict-free/read-only surfaces (0/2/3 only) — each named, so a new
# command cannot silently land here. `lease` is deliberately 0/2/3: a
# busy lease is 3, refusals are 2, and it has no failure verdict.
NEVER_ONE_HERE = {
    "init", "self-test", "hooks", "agent-hooks", "lease", "trend", "stats",
    "whatsnew", "change-scope", "preset", "parse", "update",
}


def test_every_command_declares_its_failure_leg():
    """The declaration IS the day-one enforcement: a new command missing
    from both registries turns this red until it states its contract."""
    assert set(FAILURE_LEGS) | NEVER_ONE_HERE == set(cli._COMMANDS)
    assert not set(FAILURE_LEGS) & NEVER_ONE_HERE


@pytest.mark.parametrize("command", sorted(FAILURE_LEGS))
def test_failure_legs_are_one(command, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entry = FAILURE_LEGS[command](tmp_path)
    argv, stdin = entry if isinstance(entry, tuple) else (entry, None)
    rc = _invoke(argv, tmp_path, stdin=stdin)
    assert rc == 1, f"`gov {' '.join(argv)}` must report failure with 1"


# --- leg 3: lease busy --------------------------------------------------

def test_lease_busy_is_three(tmp_path, monkeypatch):
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["acquire", "res", "--agent", "holder",
                     "--ttl", "60"]) == 0
    assert cli.main(["acquire", "res", "--agent", "waiter"]) == 3


# --- polarity: the machine stream never carries prose -------------------

def _run_proc(tmp_path, argv):
    env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-m", "gov", *argv], cwd=tmp_path, check=False,
        capture_output=True, text=True, timeout=300, env=env,
        encoding="utf-8", errors="replace")


def test_run_default_polarity_is_the_human_report(tmp_path, monkeypatch):
    _repo(tmp_path)
    assert cli.init(tmp_path) == 0
    monkeypatch.chdir(tmp_path)
    proc = _run_proc(tmp_path, ["run"])
    assert proc.returncode == 0
    assert "gates:" in proc.stdout and "PASS" in proc.stdout
    assert "PASS" not in proc.stderr


def test_run_json_polarity_is_one_machine_value(tmp_path, monkeypatch):
    _repo(tmp_path)
    assert cli.init(tmp_path) == 0
    monkeypatch.chdir(tmp_path)
    proc = _run_proc(tmp_path, ["run", "--json"])
    assert proc.returncode == 0
    value = json.loads(proc.stdout)  # exactly one JSON value (prose would break this)
    assert isinstance(value, list) and value
    assert "gates:" not in proc.stdout  # the prose summary moved to stderr
    assert "gates:" in proc.stderr


# --- the help side of the contract ---------------------------------------

def test_help_names_the_contract(capsys):
    """Moved here from test_flag_registry: the usage line is the
    contract's home, and this file is the contract's pin."""
    assert cli.main([]) == 2
    err = capsys.readouterr().err
    assert "exit codes:" in err
    for token in ("0 ok", "1 failure", "2 config", "3 lease busy"):
        assert token in err, token
