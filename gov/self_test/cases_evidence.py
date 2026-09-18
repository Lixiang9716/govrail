"""evidence rejection cases: task cards and run receipts.
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
    _case_env,
    _pinned_env,
    _receipt_repo,
    _run,
    _run_text,
    _task_project,
    case,
)





@case
def test_task_check_rejects_stale_rules_pin() -> None:
    """#125: after a governance adoption, a card pinning the OLD rule-set
    hash must fail loud — the whole point of drift detection."""
    with tempfile.TemporaryDirectory() as td:
        root = _task_project(Path(td))
        env = _pinned_env()
        made = subprocess.run(
            [sys.executable, "-m", "gov", "task", "new", "Brief me"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env)
        assert made.returncode == 0, made.stderr
        # the adoption: the rule set moves under the open card
        (root / ".gov" / "rules.md").write_text(
            (root / ".gov" / "rules.md").read_text(encoding="utf-8")
            + "\n## 8. New rule adopted mid-flight\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "gov", "task", "check"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env)
        assert result.returncode == 1, (
            "a card pinning a pre-adoption rules hash must fail check\n"
            f"{result.stdout}\n{result.stderr}")
        assert "STALE" in result.stdout, "the stale card must be named"
        assert "T-0001" in result.stderr, "the failure names the card id"



@case
def test_task_check_rejects_tampered_receipt() -> None:
    """#125: a done card whose receipt is not an all-green run against the
    pinned rules must fail check — the receipt is evidence, not prose."""
    with tempfile.TemporaryDirectory() as td:
        root = _task_project(Path(td))
        from .. import task as task_mod
        combined, _ = task_mod.rules_hash(root)
        card_path = root / ".gov" / "tasks" / "T-0001-done.json"
        card_path.write_text(json.dumps({
            "id": "T-0001",
            "title": "Done deed",
            "rules": {"hash": combined, "files": {}},
            "checklist": [],
            "status": "done",
            "receipt": {"ts": "2026-09-04T00:00:00+00:00", "mode": "quick",
                        "rules": combined, "green": True,
                        "gates": [{"gate": "notes", "outcome": "FAIL",
                                   "blocking": True, "duration_ms": 1,
                                   "detail": ""}]},
        }), encoding="utf-8")
        result = _run_text(
            [sys.executable, "-m", "gov", "task", "check"],
            cwd=root, capture_output=True, text=True,
            env=_pinned_env())
        assert result.returncode == 1, (
            "a done card with a red receipt must fail check\n"
            f"{result.stdout}\n{result.stderr}")
        assert "not all-green" in result.stderr



@case
def test_task_survives_pre37_argparse_shadow() -> None:
    """#138: govrail 0.21.x shipped `gov task` with
    `add_subparsers(required=True)` — legal stdlib argparse since 3.7, but a
    fossil `argparse==1.4.0` backport sitting beside an installed gov dies
    on it with `TypeError: _SubParsersAction.__init__() got an unexpected
    keyword argument 'required'` the moment PYTHONPATH promotes that dir.
    The reporter's exact environment. The subcommand-required rule is
    ours, not argparse's, so the happy path must survive the shadow."""
    with tempfile.TemporaryDirectory() as td:
        shadow = Path(td) / "shadow"
        shadow.mkdir()
        # A faithful-enough stand-in for the backport: real stdlib argparse
        # with pre-3.7 `add_subparsers` restored — `required` is refused.
        (shadow / "argparse.py").write_text(
            "import importlib.util, os, sysconfig\n"
            "_dir = os.path.dirname(os.path.abspath(__file__))\n"
            "_p = os.path.join(sysconfig.get_paths()['stdlib'], 'argparse.py')\n"
            "_s = importlib.util.spec_from_file_location('_stdlib_argparse', _p)\n"
            "_m = importlib.util.module_from_spec(_s)\n"
            "_s.loader.exec_module(_m)\n"
            "globals().update(vars(_m))\n"
            "__file__ = os.path.join(_dir, 'argparse.py')\n"
            "__name__ = 'argparse'\n"
            "_real = _m.ArgumentParser.add_subparsers\n"
            "def _old_add_subparsers(self, **kw):\n"
            "    if 'required' in kw:\n"
            "        raise TypeError(\"_SubParsersAction.__init__() got an \"\n"
            "                        \"unexpected keyword argument 'required'\")\n"
            "    return _real(self, **kw)\n"
            "ArgumentParser.add_subparsers = _old_add_subparsers\n",
            encoding="utf-8")
        # shadow first, then the tested tree: argparse MUST resolve to the
        # shadow, gov to HERE.parent (rule 6 — prove the trap can fire).
        env = {**_case_env(), "PYTHONPATH": os.pathsep.join(
            [str(shadow), str(HERE.parent)])}
        trap = subprocess.run(
            [sys.executable, "-c",
             "import argparse; "
             "argparse.ArgumentParser().add_subparsers(required=True)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace")
        assert trap.returncode != 0 and "'required'" in trap.stderr, (
            "the shadow must model the pre-3.7 backport first\n"
            f"{trap.stdout}\n{trap.stderr}")
        root = _task_project(Path(td) / "proj")
        made = subprocess.run(
            [sys.executable, "-m", "gov", "task", "new", "Brief me"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env)
        assert made.returncode == 0, made.stderr
        assert "obey rules@" in made.stdout, "the pin line is the brief"
        bare = subprocess.run(
            [sys.executable, "-m", "gov", "task"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", env=env)
        assert bare.returncode == 2, bare.stderr
        assert "subcommand is required" in bare.stderr, (
            "the hand-rolled rule names the choices, fail loud")



@case
def test_receipt_rejects_forged_record() -> None:
    """#124/D44: editing a receipt's content without re-signing must fail
    verification loudly — the evidence cannot be quietly rewritten."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        commit = _receipt_repo(root)
        result = _run("gates.py", root,
                      extra=["--every-gate", "--no-record", "--receipt"])
        assert result.returncode == 0, result.stderr
        ledger = root / ".gov" / "history" / "receipts.jsonl"
        record = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
        assert record["commit"] == commit
        # The forgery: claim a gate failed, keep the original signature.
        record["gates"][0]["outcome"] = "FAIL"
        ledger.write_text(
            json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")
        res = _run("receipt.py", root, extra=["verify", commit])
        assert res.returncode == 2 and "hash mismatch" in res.stderr, (
            "a forged receipt must break verification loudly")



@case
def test_receipt_rejects_partial_run_as_full_evidence() -> None:
    """#124/D44: a single-gate run's receipt must not verify as 'a full
    green run on this tree' — partial evidence is named, never accepted."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        commit = _receipt_repo(root, two_gates=True)
        result = _run("gates.py", root,
                      extra=["--gate", "ok", "--no-record", "--receipt"])
        assert result.returncode == 0, result.stderr
        res = _run("receipt.py", root, extra=["verify", commit])
        assert res.returncode == 1 and "partial run" in res.stderr, (
            "a partial run must never pass as a full green run")
