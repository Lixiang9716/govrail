"""Rejection-style tests for findings #15-#23 (D32)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent / "gov"

# POSIX-exec-inherent checks (see the #168 note's deferred rule-6
# decision): sh -n linting and shebang-script execution need a POSIX
# host; on Windows they are named skips, not failures.
needs_posix_exec = pytest.mark.skipif(
    sys.platform == "win32", reason="needs a POSIX shell / shebang execution")


def _repo(root, commit=True):
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True)
    if commit:
        (root / "seed.txt").write_text("x\n")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "base"],
                       cwd=root, check=True)


def test_15_doctor_worktree_hook(tmp_path, monkeypatch, capsys):
    main = tmp_path / "main"
    main.mkdir()
    _repo(main)
    hooks = main / ".git" / "hooks"
    (hooks / "pre-push").write_text("#!/bin/sh\n")
    (hooks / "pre-push").chmod(0o755)
    wt = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", str(wt)], cwd=main, check=True)
    monkeypatch.chdir(wt)
    from gov import doctor
    doctor.main([])
    out = capsys.readouterr().out
    assert "not a git repository" not in out  # #15 acceptance
    assert "pre-push is executable" in out


def test_16_bare_write_touches_only_stale(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from gov import verify_translation_pairing as vtp
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("m2-plan.md", "m2-plan.zh.md", "ok.md", "ok.zh.md"):
        (docs / name).write_text(f"# {name}\n")
    assert vtp.main(["--write", "m2-plan"]) == 0   # baseline both explicitly
    assert vtp.main(["--write", "ok"]) == 0
    green_before = (docs / "ok.i18n.yaml").read_bytes()
    (docs / "m2-plan.md").write_text("# m2-plan EDITED\n")  # one goes stale
    assert vtp.main([]) == 1                           # exactly it is red
    assert vtp.main(["--write"]) == 0                  # bare form fixes it...
    assert (docs / "ok.i18n.yaml").read_bytes() == green_before  # ...only it
    assert vtp.main(["--write"]) == 0                  # all-green: no-op
    assert "nothing out of sync" in capsys.readouterr().out


@needs_posix_exec
def test_18_ledger_credits_executed_undeclared(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gov").mkdir()
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": ["x"]}, "gates": [{"id": "x", "command": ["true"]}]}))
    rej = tmp_path / ".gov" / "rejections"
    rej.mkdir()
    legacy = rej / "source-limits-rejects.py"  # predates the convention
    legacy.write_text("#!/bin/sh\nexit 0\n")
    legacy.chmod(0o755)
    from gov import self_test as st
    assert st.main(["--scope", "project"]) == 0
    out = capsys.readouterr().out
    assert "x(NONE — rule 6)" in out
    assert "source-limits-rejects.py" in out  # the executed case is named
    assert "write one:" not in out  # never nag for a case that just ran


def test_19_doctor_names_version_drift(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    gov_dir = tmp_path / ".gov"
    gov_dir.mkdir()
    (gov_dir / "manifest.json").write_text(json.dumps({"version": "0.6.5"}))
    from gov import __version__, doctor
    doctor.main([])
    out = capsys.readouterr().out
    assert f"manifest initialized with govrail 0.6.5" in out
    assert f"this package is {__version__}" in out
    assert "gov init --upgrade" in out
    # match -> silent
    (gov_dir / "manifest.json").write_text(json.dumps({"version": __version__}))
    doctor.main([])
    assert "manifest initialized" not in capsys.readouterr().out


def test_20_self_test_scrubs_hook_environment(tmp_path, monkeypatch, capsys):
    """Hostile GIT_* (hook context) must not break the self-test."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    from gov import self_test as st
    assert st.main(["--scope", "project"]) == 0  # no cases: still sane
    out = capsys.readouterr().out
    assert "scrubbed repository-resolving" in out
    assert "GIT_DIR" in out


@needs_posix_exec
def test_22_hook_selects_by_push_range():
    hook = (HERE / "templates" / "pre-push").read_text()
    assert 'run --base "$base"' in hook
    assert "unset GIT_DIR" in hook
    # functional: feed push stdin, expect scoped invocation (dry: sh -n ok)
    assert subprocess.run(["sh", "-n", str(HERE / "templates" / "pre-push")]).returncode == 0


def test_21_scope_annotation(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": ["a"]},
         "gates": [{"id": "a", "command": ["true"], "paths": ["src/**"]}]}))
    from gov import gates
    assert gates.main([]) == 0
    out = capsys.readouterr().out
    assert "0 in change scope — nothing changed matches" in out  # clean tree
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("x = 1\n")
    assert gates.main([]) == 0
    assert "1 in change scope" in capsys.readouterr().out


def test_23_history_lands_in_main_checkout(tmp_path, monkeypatch):
    main = tmp_path / "main"
    main.mkdir()
    _repo(main)
    subprocess.run(["git", "worktree", "add", "-q", str(tmp_path / "wt")],
                   cwd=main, check=True)
    wt = tmp_path / "wt"
    (wt / "gates.json").write_text(json.dumps(
        {"gates": [{"id": "a", "command": ["true"]}]}))
    monkeypatch.chdir(wt)
    from gov import gates
    assert gates.main([]) == 0
    ledger = main / ".gov" / "history" / "gates.jsonl"
    assert ledger.is_file()  # recorded in the MAIN checkout, not the worktree
    assert "wt/.gov/history" not in str(ledger)


def test_17_table_format_and_refusal(tmp_path, monkeypatch, capsys):
    """The decisions source is configurable; no source + D-refs = REFUSED."""
    monkeypatch.chdir(tmp_path)
    from gov import verify_decisions as vd
    # no source, no refs -> benign
    assert vd.main([]) == 0
    # notes referencing D-refs with no source -> REFUSED, not vacuous ok
    notes = tmp_path / ".agents" / "notes" / "implemented" / "process"
    notes.mkdir(parents=True)
    (notes / "x.md").write_text(
        "# Agent Note: x\n\nStatus: implemented\n\n## Problem\np\n\n"
        "## Decision\nd\n\n## Alternatives considered\na\n\nLocked by D1.\n")
    assert vd.main([]) == 1
    assert "REFUSED" in capsys.readouterr().out
    # configure a table source
    design = tmp_path / "DESIGN.md"
    design.write_text(
        "# design\n\n| D | choice | alternatives |\n|---|---|---|\n"
        "| D1 | use tabs | spaces rejected: indent drift |\n"
        "| D2 | keep py39 | py310+: no need yet |\n")
    (tmp_path / ".gov").mkdir(exist_ok=True)
    (tmp_path / ".gov" / "decisions.json").write_text(
        json.dumps({"path": "DESIGN.md", "format": "table"}))
    assert vd.main([]) == 0  # header alternatives column covers rows
    out = capsys.readouterr().out
    assert "2 decision(s) ok" in out
    # audit-notes resolves D-refs through the same source
    from gov import audit_notes
    assert audit_notes.main([]) == 0
    # recall ranks table rows
    from gov import recall
    assert recall.main(["tabs"]) == 0
    assert "DESIGN.md#D1" in capsys.readouterr().out
