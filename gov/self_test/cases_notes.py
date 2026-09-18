"""notes-family rejection cases: note verify/presence and the archive seal.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ._harness import (
    HERE,
    _GOOD_NOTE,
    _GOOD_NOTE_BODY,
    _case,
    _git_repo,
    _run,
    _write_note,
    case,
)




@case
def test_verify_notes_rejects_missing_section() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        notes = root / ".agents" / "notes" / "implemented"
        notes.mkdir(parents=True)
        (notes / "bad.md").write_text(
            "# Agent Note: bad\n\n"
            "Status: implemented\n\n"
            "## Problem\nx\n\n"
            "## Decision\ny\n",
            encoding="utf-8",
        )
        _case("verify_notes.py", root, 1, "a note missing Alternatives must fail")



@case
def test_verify_notes_rejects_hollow_skeleton() -> None:
    """D3: the `note new` scaffold's own output — placeholders and all —
    used to pass verify-notes AS WRITTEN, making the empty shell the
    path of least resistance. The gate now names every hollow section."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        notes = root / ".agents" / "notes" / "implemented"
        (notes / "bug-fix").mkdir(parents=True)
        try:
            from ..note import PLACEHOLDERS, SKELETON
        except ImportError:  # run as a script by the tools family
            from note import PLACEHOLDERS, SKELETON
        (notes / "bug-fix" / "2026-01-01-h.md").write_text(
            SKELETON.format(
                title="h", related="",
                ph_problem=PLACEHOLDERS["## Problem"],
                ph_decision=PLACEHOLDERS["## Decision"],
                ph_alternatives=PLACEHOLDERS["## Alternatives considered"]),
            encoding="utf-8")
        result = _run("verify_notes.py", root)
        assert result.returncode == 1, "the unfilled scaffold must fail"
        assert result.stdout.count("placeholder") == 3, result.stdout
        assert "'## Problem'" in result.stdout, result.stdout
        assert "'## Decision'" in result.stdout, result.stdout
        assert "'## Alternatives considered'" in result.stdout, result.stdout



@case
def test_verify_notes_rejects_unknown_argument() -> None:
    """verify-notes is flagless; it used to ignore argv entirely and
    answer a mistyped invocation with a GREEN verdict — the exit-code
    contract's probe caught it (31/32 commands refuse unknown flags).
    A refusal is named and exits 2, never a silent pass."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        notes = root / ".agents" / "notes" / "implemented"
        notes.mkdir(parents=True)
        result = _run("verify_notes.py", root, extra=["--json"])
        assert result.returncode == 2, "an unknown flag must be refused"
        assert "unexpected argument" in result.stderr, result.stderr



@case
def test_note_presence_warns_then_strict_blocks() -> None:
    """Rule 2's presence half must be checkable: warn by default, block on --strict."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        (root / "app.py").write_text("x = 1\n", encoding="utf-8")
        script = str(HERE / "verify_note_presence.py")
        warn = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert warn.returncode == 0, "advisory mode must not block (D3)"
        assert ".gov/rules.md rule 2" in warn.stdout, "the warning must name its rule"
        strict = subprocess.run(
            [sys.executable, script, "--strict"], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert strict.returncode == 1, "--strict must catch the missing note"



@case
def test_verify_notes_rejects_wrong_section_order() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_note(
            root,
            "implemented/architecture/2026-01-01-x.md",
            "# Agent Note: t\n\nStatus: implemented\n\n"
            "## Decision\nd\n\n## Problem\np\n\n## Alternatives considered\na\n",
        )
        _case(
            "verify_notes.py",
            root,
            1,
            "sections out of the promised order must fail (notes README contract)",
        )



@case
def test_verify_notes_rejects_unknown_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_note(root, "implemented/architecture/2026-01-01-x.md", _GOOD_NOTE)
        _write_note(root, "drafts/2026-01-01-x.md", _GOOD_NOTE)
        result = _run("verify_notes.py", root)
        assert result.returncode == 1, "an unknown lifecycle dir must fail loud (rule 5)"
        assert "unknown lifecycle 'drafts'" in result.stdout



@case
def test_note_presence_auto_base_catches_committed_work() -> None:
    """F1: a clean tree with committed no-note work must not pass silently."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        (root / "app.py").write_text("v1\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "one"],
            cwd=root, check=True,
        )
        (root / "app.py").write_text("v2\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "two"],
            cwd=root, check=True,
        )  # clean tree, committed, no upstream
        script = str(HERE / "verify_note_presence.py")
        warn = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert warn.returncode == 0, warn.stderr
        assert "app.py" in warn.stdout, "the pushed work must be reviewed, not an empty diff"
        strict = subprocess.run(
            [sys.executable, script, "--strict"], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert strict.returncode == 1, "--strict must catch the committed no-note change"



@case
def test_note_presence_task_receipts_and_manifest_exemptions() -> None:
    """#149: routine bookkeeping never cries wolf; the repo rules where a
    note is expected via note_presence_exempt in .gov/manifest.json."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        tasks = root / ".gov" / "tasks"
        tasks.mkdir(parents=True)
        (tasks / "T-0001-x.json").write_text("{}\n", encoding="utf-8")
        script = str(HERE / "verify_note_presence.py")
        receipt = subprocess.run(
            [sys.executable, script, "--strict"], cwd=root,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert receipt.returncode == 0, (
            "a task receipt is machine bookkeeping; it must not warn (#149)\n"
            + receipt.stdout)
        (root / "src").mkdir()
        (root / "src" / "gen.py").write_text("x = 1\n", encoding="utf-8")
        (root / ".gov" / "manifest.json").write_text(
            json.dumps({"note_presence_exempt": ["src/**"]}), encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "exempt"],
            cwd=root, check=True,
        )  # the declaration lands first, like a real repo's would
        (root / "src" / "gen.py").write_text("x = 2\n", encoding="utf-8")
        exempt = subprocess.run(
            [sys.executable, script, "--strict"], cwd=root,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert exempt.returncode == 0, (
            "a repo-declared exemption must silence its paths (#149)\n"
            + exempt.stdout)
        (root / ".gov" / "manifest.json").write_text(
            json.dumps({"version": "0.0.0"}), encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "bare"],
            cwd=root, check=True,
        )
        (root / "src" / "gen.py").write_text("x = 3\n", encoding="utf-8")
        bare = subprocess.run(
            [sys.executable, script, "--strict"], cwd=root,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert bare.returncode == 1, (
            "without the exemption the warning must still fire\n" + bare.stdout)



@case
def test_note_presence_rejects_ill_shaped_manifest() -> None:
    """Rule 5: a manifest that exists but cannot serve must exit 2, named."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        (root / ".gov").mkdir()
        (root / ".gov" / "manifest.json").write_text(
            json.dumps({"note_presence_exempt": "src/**"}), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(HERE / "verify_note_presence.py")], cwd=root,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 2, (
            "an ill-shaped note_presence_exempt must fail loud (rule 5)\n"
            + result.stdout + result.stderr)
        assert "note_presence_exempt" in result.stderr



@case
def test_verify_notes_rejects_status_lying() -> None:
    """The lifecycle is the directory; the Status field must not improvise."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_note(
            root,
            "implemented/architecture/2026-01-01-s.md",
            "# Agent Note: s\n\nStatus: banana\n\n" + _GOOD_NOTE_BODY,
        )
        result = _run("verify_notes.py", root)
        assert result.returncode == 1, "Status: banana must fail loud"
        assert "banana" in result.stdout



@case
def test_archive_seal_detects_tampering_and_refuses_laundering() -> None:
    """F7: the seal has a detector, and re-sealing cannot wash a drift."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        arch = root / ".agents" / "notes" / "archived" / "process"
        arch.mkdir(parents=True)
        note = arch / "2026-01-01-x.md"
        note.write_text("# Agent Note: x\n", encoding="utf-8")
        seal = subprocess.run(
            [sys.executable, str(HERE / "archive_notes.py")],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert seal.returncode == 0, seal.stderr
        note.write_text("# Agent Note: x  # tampered\n", encoding="utf-8")
        _case("verify_archive.py", root, 1,
              "a tampered archived note must fail the seal check")
        refused = subprocess.run(
            [sys.executable, str(HERE / "archive_notes.py")],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert refused.returncode == 1, "re-sealing a drift must refuse (no laundering)"
        assert "refusing to re-seal" in refused.stdout
