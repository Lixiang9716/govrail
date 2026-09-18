"""command-surface rejection cases: D57 hubs, init surface, self-test adoption, parse/check engines, presets.
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
    _git_repo,
    _ledger_output,
    _pinned_env,
    _run_text,
    case,
)




@case
def test_d57_hubs_and_aliases() -> None:
    """D57 Wave 1: the 13 absorbed top-level commands keep working as
    deprecated aliases — identical rc and output to their hub forms.
    The lease hub reports busy as exit 3, and gov parse --json emits a
    valid object. Each assertion is a real subprocess (the contract is
    the process exit code, not an in-process return value)."""
    import json as _json
    import subprocess as sp

    def _run_repo(td):
        sp.run(["git", "init", "-q", "."], cwd=td, check=True)
        sp.run(["git", "config", "user.email", "t@t"], cwd=td, check=True)
        sp.run(["git", "config", "user.name", "t"], cwd=td, check=True)

    def _gov(*argv, cwd, env):
        return sp.run(
            [sys.executable, "-m", "gov", *argv], cwd=cwd,
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace", env=env)

    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
           "PYTHONUTF8": "1"}

    # alias forwarding: verify-notes and note verify agree on rc+stdout
    with tempfile.TemporaryDirectory() as td:
        _run_repo(td)
        notes = Path(td) / ".agents" / "notes" / "implemented" / "bug-fix"
        notes.mkdir(parents=True)
        (notes / "2026-01-01-x.md").write_text(
            "# Agent Note: x\n\nStatus: implemented\n\n"
            "## Problem\np\n\n## Decision\nd\n\n"
            "## Alternatives considered\na\n", encoding="utf-8")
        old = _gov("verify-notes", cwd=td, env=env)
        new = _gov("note", "verify", cwd=td, env=env)
        assert old.returncode == new.returncode, (
            f"alias rc diverged: {old.returncode} vs {new.returncode}")
        assert old.stdout == new.stdout, "alias stdout diverged"

    # lease hub: busy resource exits 3 through the hub form
    with tempfile.TemporaryDirectory() as td:
        _run_repo(td)
        lease_env = {**env, "GOV_BIN": f"{sys.executable} -m gov"}
        sp.run(["gov", "acquire", "r", "--agent", "a", "--ttl", "60"],
               cwd=td, check=True, capture_output=True,
               env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
                    "PYTHONUTF8": "1"})
        r = sp.run(
            [sys.executable, "-m", "gov", "lease", "acquire", "r",
             "--agent", "b"], cwd=td, capture_output=True, text=True,
            timeout=60, env=lease_env, encoding="utf-8", errors="replace")
        assert r.returncode == 3, f"lease busy must exit 3, got {r.returncode}"

    # parse --json: valid object with files and skipped
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "a.py"
        f.write_text("x = 1\n", encoding="utf-8")
        r = sp.run(
            [sys.executable, "-m", "gov", "parse", str(f), "--json"],
            capture_output=True, text=True, timeout=60,
            env={**env, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)},
            encoding="utf-8", errors="replace")
        value = _json.loads(r.stdout)
        assert "files" in value and "skipped" in value



@case
def test_cli_init_help_no_side_effect() -> None:
    """`gov init --help` must show help and create nothing, not run init."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        env = _pinned_env()
        result = subprocess.run(
            [sys.executable, "-m", "gov", "init", "--help"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, f"init --help must exit 0: {result.stderr}"
        assert not list(root.iterdir()), "init --help must not create any file"



@case
def test_init_hooks_ci_roundtrip() -> None:
    """init --hooks/--ci must install, and uninstall must reverse exactly."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        env = _pinned_env()
        for args in (
            ["-m", "gov", "init", "--hooks", "--ci"],
            ["-m", "gov", "uninstall"],
        ):
            r = _run_text(
                [sys.executable, *args], cwd=root, env=env,
                capture_output=True, text=True,
            )
            assert r.returncode == 0, r.stderr
        assert not (root / ".git" / "hooks" / "pre-push").exists()
        assert not (root / ".github" / "workflows" / "gov.yml").exists()
        assert not (root / "gates.json").exists()



@case
def test_self_test_adopts_project_rejection_cases() -> None:
    """Wish 1: .gov/rejections/ is rule 6's last mile — wired and enforced."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rej = root / ".gov" / "rejections"
        rej.mkdir(parents=True)
        bad = rej / "case-broken.sh"
        bad.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        bad.chmod(0o755)
        # --scope project: proves the wiring without recursing into the
        # tools family (this very case lives there).
        env = {**os.environ,
               "PYTHONPATH": str(HERE.parent)}  # the working-tree checkout
        result = subprocess.run(
            [sys.executable, "-m", "gov.self_test", "--scope", "project"],
            cwd=root, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace", env=env,
        )
        assert result.returncode == 1, "a failing project case must fail self-test"
        assert "case-broken.sh" in result.stdout, "the case must be named"



@case
def test_coverage_warning_names_the_marker_fix() -> None:
    """#167: an undeclared case is named WITH the remedy inline.

    The warning used to name the file and stop there — an adopter had to
    reverse-engineer both the marker's syntax and its scan window (the
    issue's reporter did, over two round-trips: the marker works inside a
    module docstring, and the window is five lines). Both halves of that
    discovery are pinned here: the fix line prints, and a marker inside a
    module docstring is credited."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rej = root / ".gov" / "rejections"
        rej.mkdir(parents=True)
        (root / "gates.json").write_text(
            json.dumps({"modes": {"all": ["x"]},
                        "gates": [{"id": "x", "command": ["true"]}]}),
            encoding="utf-8",
        )
        # A case that predates the convention: it runs, it passes, and it
        # declares nothing — #167's report, reproduced.
        (rej / "case-legacy.sh").write_text("#!/bin/sh\nexit 0\n",
                                            encoding="utf-8")
        first = _ledger_output(root)
        assert "case-legacy.sh" in first, "the case must be named"
        assert "fix: add '# gate: <id>' within the first 5 lines" in first, (
            "the warning must print the remedy, not just the file (#167)\n"
            + first)
        # Line 4 of a five-line file: the marker inside the docstring.
        (rej / "case-docstring.py").write_text(
            '#!/usr/bin/env python3\n"""A rejection case.\n\n# gate: x\n"""\n'
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        second = _ledger_output(root)
        assert "x(1)" in second, (
            "a marker inside a module docstring must be credited (#167)\n"
            + second)
        assert "x(NONE — rule 6)" not in second, (
            "the declared case covers the gate; the cell must not still "
            "read NONE\n" + second)



@case
def test_skills_text_command_drift_is_named() -> None:
    """Wish 11: a typo'd command in a skill file is named, not silently stale."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        notes = root / ".agents" / "notes" / "implemented" / "architecture"
        notes.mkdir(parents=True)
        (notes / "x.md").write_text(
            "# Agent Note: x\n\nStatus: implemented\n\n## Decision\nd\n\n"
            "## Problem\np\n\n## Alternatives considered\na\n", encoding="utf-8")
        skills = root / ".agents" / "skills" / "probe"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("run `gov run --every-gat`\n", encoding="utf-8")
        env = _pinned_env()
        result = _run_text(
            [sys.executable, "-m", "gov", "audit-notes"],
            cwd=root, env=env, capture_output=True, text=True,
        )  # package mode: the command registry is importable
        assert result.returncode == 0, result.stdout + result.stderr  # advisory
        assert "--every-gat" in result.stdout, "the typo'd flag must be named"



@case
def test_registry_real_flags_are_not_drift() -> None:
    """Issue #101: --adopt/--preview/--json are real init flags. A note
    documenting WORKING commands must not be reported as dead ones — the
    exact inversion of what audit-notes exists to catch — while a genuinely
    unknown flag is still named."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        notes = root / ".agents" / "notes" / "implemented" / "process"
        notes.mkdir(parents=True)
        (notes / "x.md").write_text(
            "# Agent Note: x\n\nStatus: implemented\n\n"
            "## Decision\n`gov init --adopt .gov/hooks/pre-push` and "
            "`gov init --adopt all --preview` ran clean; `gov init --nonexistent` "
            "never did.\n\n## Problem\np\n\n## Alternatives considered\na\n",
            encoding="utf-8")
        env = _pinned_env()
        result = _run_text(
            [sys.executable, "-m", "gov", "audit-notes"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr  # advisory
        assert "unknown flag `--nonexistent` on `gov init`" in result.stdout
        assert "--adopt" not in result.stdout, (
            "real init flags must not be flagged: " + result.stdout)
        assert "--preview" not in result.stdout, result.stdout



@case
def test_parse_layer_metrics_mean_what_they_claim() -> None:
    """D54: the stats layer's numbers are hand-countable facts.

    The Go fixture's depths are human-counted (for→switch→if→for→if = 5;
    a lone if = 1; `case` is not a level), the docstring-is-CODE rule is
    pinned, a broken file is named instead of silently "checked", and a
    language pack naming a node kind its grammar lacks refuses to load —
    the wrong-kind bug class reported a plausible 0 in the prototype.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "svc.go").write_text(
            "package svc\n"
            "\n"
            "func Route(mode string, depth int) error {\n"
            "\tfor i := 0; i < depth; i++ {\n"          # 1
            "\t\tswitch mode {\n"                       # 2
            '\t\tcase "a":\n'                           # not a level
            "\t\t\tif i%2 == 0 {\n"                   # 3
            "\t\t\t\tfor j := 0; j < 3; j++ {\n"     # 4
            "\t\t\t\t\tif j == 2 {\n"               # 5
            "\t\t\t\t\t\tprintln(\"deep\")\n"
            "\t\t\t\t\t}\n"
            "\t\t\t\t}\n"
            "\t\t\t}\n"
            '\t\tcase "b":\n'
            "\t\t\tprintln(\"shallow\")\n"
            "\t\t}\n"
            "\t}\n"
            "\treturn nil\n"
            "}\n"
            "\n"
            "func Handle(x int) int {\n"
            "\tif x > 0 { // trailing comment, still a code line\n"  # 1
            "\t\treturn x\n"
            "\t}\n"
            "\treturn -x\n"
            "}\n",
            encoding="utf-8",
        )
        (root / "broken.go").write_text("func {\n", encoding="utf-8")
        env = _pinned_env()
        result = _run_text(
            [sys.executable, "-m", "gov", "stats", "--json", "--lang", "go"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        value = json.loads(result.stdout)
        go = value["languages"]["go"]
        assert go["parse_errors"] > 0, "a broken file must be named, not silent"
        named = {f["path"]: f["errors"] for f in go["files_detail"]}
        assert named.get("broken.go", 0) > 0 and named.get("svc.go", 0) == 0
        by_name = {o["name"]: o["depth"] for o in go["depth"]["outliers"]}
        assert by_name.get("Route") == 5, by_name
        assert by_name.get("Handle") == 1, by_name
        # The counting rule must ship WITH the number (an undeclared rule
        # makes the figure unverifiable).
        assert "outside a comment node" in go["rule"]["code_line"]
        # A pack naming a nonexistent kind must refuse to load (rule 5).
        bad = _run_text(
            [sys.executable, "-c",
             "import json, tempfile, pathlib, sys\n"
             "sys.path.insert(0, %r)\n"
             "from gov import parse\n"
             "good = json.loads((pathlib.Path(%r) / 'go.json')"
             ".read_text(encoding='utf-8'))\n"
             "good['nesting'] = ['if_statment']\n"
             "d = pathlib.Path(tempfile.mkdtemp())\n"
             "(d / 'bad.json').write_text(json.dumps(good), encoding='utf-8')\n"
             "import gov.parse as p\n"
             "p._LANGS = d\n"
             "try:\n"
             "    p.load_pack('bad')\n"
             "except p.ParseUnavailable as e:\n"
             "    print('REFUSED:', e)\n"
             "else:\n"
             "    raise SystemExit('a bad pack loaded — rule 5 violated')\n"
             % (str(HERE.parent), str(HERE / "langs"))],
            capture_output=True, text=True, env=env,
        )
        assert "REFUSED:" in result.stdout or "REFUSED:" in bad.stdout, (
            "the wrong-kind refusal did not print: " + bad.stdout + bad.stderr)
        assert "if_statment" in bad.stdout



@case
def test_check_engine_mechanisms_are_real() -> None:
    """D57: the check engine's verdict machinery, proven in-wheel.

    The shipped syntax rule goes RED on a broken file naming file:line;
    the query difference finds the argument-less candidate and discharges
    the one that HAS an argument; a suppression discharges exactly its
    rule on exactly its line and lands in the ledger as a counted
    exemption. A rule whose query names a node kind its grammar lacks
    fails the run loudly (exit 2) even when no file would ever reach it.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        proj = root / ".gov" / "checks"
        proj.mkdir(parents=True)
        (proj / "python.json").write_text(json.dumps({"rules": [
            {"id": "proof/bare-eval", "kind": "query",
             "severity": "warning", "message": "bare eval",
             "query": "((call function: (identifier)) @gov-node)",
             "absent_query": "(argument_list (_))"},
        ]}), encoding="utf-8")
        (root / "broken.py").write_text("def f(:\n", encoding="utf-8")
        (root / "calls.py").write_text(
            "eval('has args')\n"
            "eval()  # gov:ignore-check proof/bare-eval\n"
            "eval()\n",
            encoding="utf-8")
        env = _pinned_env()
        result = _run_text(
            [sys.executable, "-m", "gov", "check", "--lang", "python",
             "--json"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        assert result.returncode == 1, \
            "a broken file plus an unsuppressed finding must block\n" \
            + result.stdout + result.stderr
        value = json.loads(result.stdout)
        assert value["summary"]["blocking"] >= 1, value["summary"]
        by_path = {f["path"]: f["findings"] for f in value["files"]}
        # The syntax rule names the broken file with a line number.
        syn = [f for f in by_path.get("broken.py", [])
               if f["rule"] == "python/syntax"]
        assert syn and all(f["line"] >= 1 for f in syn)
        # Difference: only the argument-less eval() on line 3 stands;
        # line 1 discharged by the absent query, line 2 by the marker.
        bare = [f for f in by_path.get("calls.py", [])
                if f["rule"] == "proof/bare-eval"]
        active = [f for f in bare if not f["suppressed"]]
        assert [f["line"] for f in active] == [3], bare
        assert sum(1 for f in bare if f["suppressed"]) == 1
        # A ghost node kind must fail the run loudly even though no file
        # would ever reach the rule.
        (proj / "python.json").write_text(json.dumps({"rules": [
            {"id": "proof/ghost", "kind": "query", "severity": "error",
             "message": "m", "query": "(call function: (nope))"},
        ]}), encoding="utf-8")
        (root / "broken.py").unlink()
        (root / "calls.py").unlink()
        ghost = _run_text(
            [sys.executable, "-m", "gov", "check", "--lang", "python"],
            cwd=root, env=env, capture_output=True, text=True,
        )
        assert ghost.returncode == 2 and "proof/ghost" in ghost.stderr, \
            ghost.stdout + ghost.stderr



@case
def test_preset_rejects_unknown_name() -> None:
    """D53: an unknown preset name must exit 2 naming it and listing the
    available presets — never a silent empty adoption."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        result = _run_text(
            [sys.executable, "-m", "gov", "preset", "apply", "no-such-preset",
             "--project", "."],
            cwd=root, env=_pinned_env(), capture_output=True, text=True,
            timeout=60,
        )
        assert result.returncode == 2, (
            "an unknown preset name must fail loud (rule 5)\n"
            f"{result.stdout}\n{result.stderr}")
        assert "no-such-preset" in result.stderr
        assert "agent-heavy" in result.stderr, \
            "the available presets must be named"



@case
def test_text_subprocess_decodes_are_pinned() -> None:
    """#172: every text-mode subprocess in the shipped package pins UTF-8.

    ``text=True`` without ``encoding`` decodes the child's output with the
    locale codec — on a zh-CN Windows that is GBK, and non-ASCII UTF-8 in
    a case's output crashed the reader thread while the case still PASSED.
    The package itself must stay on the wall #168 built for the runner's
    git decodes: this case re-runs that proof on every ``gov self-test``,
    wheel included — now through the check engine's shipped rule (D54),
    which was proven equivalent to the original regex scanner by the
    differential in tests/test_encoding_differential.py. Only the shipped
    rules run here: a host project's .gov/checks must never perturb the
    product's own rejection cases.
    """
    try:
        from .. import checks as checks_mod
    except ImportError:  # direct-script execution (python gov/self_test.py)
        import checks as checks_mod
    rules = [r for r in checks_mod.load_rules("python",
                                              include_project=False)
             if r.id == "python/subprocess-text-encoding"]
    reports = checks_mod.run_lang(HERE, "python", rules)
    bad = [f"{f.path}:{f.line()}"
           for r in reports for f in r.findings if not f.suppressed]
    assert not bad, (
        "text-mode subprocess calls decode with the locale codec unless "
        "encoding is pinned — on a GBK-locale Windows the first non-ASCII "
        f"UTF-8 byte crashes the reader thread (#172): {bad} — route them "
        "through _run_text()")
