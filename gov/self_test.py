#!/usr/bin/env python3
"""Rejection cases for each governance gate (D3, D25).

Every case introduces a deliberate violation, runs the gate, and asserts the
gate FAILS — proving it can reject, not just pass. A green self-test means
each governance gate has demonstrated it catches the violation it claims to.

Two families, reported separately so they never blur:

- **tools**: the cases built into this file — the govrail gates' own proofs;
- **project**: every executable under ``.gov/rejections/`` in the project
  root (rule 6's last mile: a project-defined gate ships its rejection
  proof here, run with the repository root as cwd; exit 0 = the proof
  holds). ``README*`` files are skipped.

Cases run concurrently; the report order stays deterministic (tools in
CASES order, project sorted by path). ``--scope tools|project`` runs one
family. All failures are reported, not just the first.

Every FAIL is classified (#139/D47): a failing tools-family case is
replayed once in a minimal clean environment — a fresh copy of the
govrail package alone on ``PYTHONPATH`` with the host's ``PYTHON*``
configuration dropped. The replay passes → the failure is
**environment-suspect** (this host's site layer breaks the tool path;
check site-packages shadowing / ``PYTHONPATH``). It fails again →
**tool-defect** (the traceback stands). Boundary (D54): the package now
carries a compiled dependency (tree-sitter); it resolves from the
interpreter's site-packages in BOTH environments, so the replay stays
meaningful for it — but a dependency made importable only via
``PYTHONPATH`` promotion or user-site is NOT visible in the replay, and
a failure of that shape will be labeled tool-defect without the clean
run having proved much. Project cases
are arbitrary scripts: their failures carry a "reproduce by hand" hint
instead of an automatic replay. A classified FAIL still fails the run —
classification is a diagnosis, never a pass. ``--case NAME`` reruns one
tools-family case in isolation (the replay's own building block).
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

HERE = Path(__file__).resolve().parent
REJECTIONS_DIR = Path(".gov/rejections")
CONCURRENCY = 4
# A runaway rejection case must not hold a CI job hostage (D26): each
# project case gets a small budget — a rejection proof is small by nature.
REJECTION_TIMEOUT_S = 10


def _case_env() -> dict:
    """A hermetic environment for case subprocesses (#20/D32).

    A pre-push hook leaks GIT_DIR/GIT_WORK_TREE into everything it runs;
    with them inherited, git commands inside scratch repositories resolve
    the HOST repository instead of the scratch one — deterministic breakage
    specific to the hook context. Case subprocesses get the environment
    scrubbed of GIT_* so they resolve repositories by cwd, like the tools
    do when run by hand.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # Children speak UTF-8 regardless of the platform locale (#168): the
    # harness decodes their output as UTF-8, so both ends agree.
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# Portable gate-command fixtures (#168). The fixtures below used the Unix
# coreutils `true`/`false` and `sh -c` to say "a command that exits 0/1" —
# none of which exists on Windows, where every such gate came out MISSING
# and ten cases failed for fixture reasons, not tool reasons (the wheel is
# py3-none-any / OS Independent, so the tools' own proof must be too).
# Fixtures whose gates actually EXECUTE use these; config-error fixtures
# that exit 2 before any gate runs keep their `["true"]` placeholders.
_PASS_CMD = [sys.executable, "-c", "pass"]
_FAIL_CMD = [sys.executable, "-c", "raise SystemExit(1)"]


def _pass_cmd() -> list[str]:
    """A fresh portable always-exit-0 command (the Unix `true`)."""
    return list(_PASS_CMD)


def _fail_cmd() -> list[str]:
    """A fresh portable always-exit-1 command (the Unix `false`)."""
    return list(_FAIL_CMD)


def _pinned_env() -> dict:
    """Case env whose PYTHONPATH pins gov to the tested tree (#138).

    The naive pin — ``PYTHONPATH = str(HERE.parent)`` — backfires when gov
    is pip-installed: HERE.parent IS site-packages, and promoting it ahead
    of the stdlib lets any module living there hijack the interpreter. This
    machine shipped exactly that: a py2-era ``argparse==1.4.0`` backport in
    site-packages shadowed the stdlib inside every case subprocess and
    ``gov task`` died in a TypeError no case could get past. The stdlib dir
    goes FIRST so the interpreter's own modules stay the interpreter's; gov
    still resolves to the tested tree (the stdlib has no ``gov``), and any
    ambient PYTHONPATH follows.
    """
    env = _case_env()
    parts = [sysconfig.get_paths()["stdlib"], str(HERE.parent)]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _run(script: str, cwd: Path,
         extra: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HERE / script)] + (extra or []),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8", errors="replace",  # tools speak UTF-8 (#168)
        env=_case_env(),
    )


def _case(script: str, cwd: Path, expect: int, why: str) -> None:
    result = _run(script, cwd)
    assert result.returncode == expect, (
        f"{script} returned {result.returncode}, expected {expect}: {why}\n"
        f"{result.stdout}\n{result.stderr}"
    )


def _run_text(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """A text-mode ``subprocess.run`` with the decode codec pinned (#172).

    ``text=True`` without ``encoding`` decodes the child's output with the
    LOCALE codec — on a zh-CN Windows that is GBK, and the first non-ASCII
    UTF-8 byte in a case's output (a Chinese rejection case, a 中文 decision
    line) raised ``UnicodeDecodeError`` inside ``subprocess._readerthread``
    — the ``buffer.append(fh.read())`` frame in #172's report. The
    traceback surfaced only through ``threading.excepthook``: it changed no
    exit code, so the case kept its emptied capture and still PASSED. The
    git-spawn wall #168 built for the runner continues here, over the
    harness's own spawns: every text subprocess in this module routes
    through this helper, and ``errors="replace"`` bounds legacy bytes to
    mojibake instead of a crash. Binary spawns keep plain
    ``subprocess.run`` — there is nothing to decode.
    """
    kw.setdefault("text", True)
    kw["encoding"] = "utf-8"
    kw["errors"] = "replace"
    return subprocess.run(cmd, **kw)


def _unpinned_text_spawns(src: str, where: str) -> list[str]:
    """``file:line`` of every text-mode subprocess call missing an encoding.

    The scanner behind ``test_text_subprocess_decodes_are_pinned``: a
    ``text=True``/``universal_newlines`` spawn without ``encoding=``
    decodes with the locale codec — the #172 crash class. Call bodies are
    captured by balanced-paren scan so multiline invocations read whole.
    """
    bad: list[str] = []
    for m in re.finditer(r"subprocess\.(?:run|Popen|check_output)\s*\(", src):
        start = m.end() - 1
        depth = 0
        i = start
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        call = src[start:i + 1]
        is_text = "text=True" in call or "universal_newlines" in call
        if is_text and "encoding=" not in call:
            bad.append(f"{where}:{src[:m.start()].count(chr(10)) + 1}")
    return bad


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


def test_gates_rejects_duplicate_id() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": ["true"]},
                        {"id": "a", "command": ["true"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "duplicate gate ids must fail loud")


def test_gates_rejects_cycle() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": ["true"], "needs": ["b"]},
                        {"id": "b", "command": ["true"], "needs": ["a"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "a needs cycle must fail loud")


def test_gates_rejects_unknown_needs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {"gates": [{"id": "a", "command": ["true"], "needs": ["ghost"]}]}
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "an unknown needs reference must fail loud")


def test_pairing_rejects_missing_record() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo.zh.md").write_text("# foo 中文\n", encoding="utf-8")
        _case(
            "verify_translation_pairing.py",
            root,
            1,
            "a pair with no .i18n.yaml record must fail",
        )


def test_gates_skips_transitively() -> None:
    """A gate whose need was skipped must itself skip, never pass."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "A", "command": _pass_cmd(), "needs": ["B"]},
                        {"id": "B", "command": _pass_cmd(), "needs": ["C"]},
                        {"id": "C", "command": _fail_cmd()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 1, "a blocking failure must exit 1"
        assert "SKIP B" in result.stdout, "B must be skipped when C fails"
        assert "SKIP A" in result.stdout, "A must be skipped when B is skipped"
        assert "PASS A" not in result.stdout, "A must never pass through a skipped need"


def test_gates_rejects_non_object_gate() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(json.dumps({"gates": [None]}), encoding="utf-8")
        _case("gates.py", root, 2, "a null gate must be a config error, not a crash")


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


def test_pairing_write_resolves_bare_stem_and_zh_side() -> None:
    """--write must resolve a bare stem and a .zh.md side to the source .md."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo.zh.md").write_text("# foo 中文\n", encoding="utf-8")
        for arg in ("foo", "docs/foo.zh.md"):
            result = _run_text(
                [sys.executable, str(HERE / "verify_translation_pairing.py"), "--write", arg],
                cwd=root,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"--write {arg} must exit 0: {result.stderr}"
        assert (docs / "foo.i18n.yaml").exists(), "--write must create the record"


def test_pairing_staged_rejects_stale_sidecar() -> None:
    """--staged (the optional pre-commit gate's check, #110) must reject a
    staged pair whose sidecar is stale — naming the scoped fix command —
    and stay quiet on an index with no paired files staged."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        docs = root / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("hello\n", encoding="utf-8")
        (docs / "a.zh.md").write_text("nihao\n", encoding="utf-8")
        script = str(HERE / "verify_translation_pairing.py")
        env = _fixture_env(root)
        wrote = subprocess.run(
            [sys.executable, script, "--write", "docs/a.md"], cwd=root,
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace",
        )
        assert wrote.returncode == 0, wrote.stderr
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "baseline"],
            cwd=root, check=True, env=env,
        )
        # An index with nothing paired staged: quiet pass (cheap gate).
        (root / "code.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "code.py"], cwd=root, check=True, env=env)
        quiet = subprocess.run(
            [sys.executable, script, "--staged"], cwd=root,
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace",
        )
        assert quiet.returncode == 0, quiet.stdout + quiet.stderr
        assert "no staged file belongs to a pair" in quiet.stdout
        # The issue's evidence: edit one side, stage it — drift must go red
        # with the scoped fix command inline.
        (docs / "a.zh.md").write_text("nihao v2\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs/a.zh.md"], cwd=root, check=True, env=env)
        bad = subprocess.run(
            [sys.executable, script, "--staged"], cwd=root,
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace",
        )
        assert bad.returncode == 1, "a stale sidecar passed --staged"
        assert "gov verify-pairing --write docs/a.md" in bad.stdout, bad.stdout


def test_gates_default_mode_scopes_run() -> None:
    """defaultMode must scope the no-flag run; gates outside it never run."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "modes": {"all": ["a"], "also": ["b"]},
                    "defaultMode": "all",
                    "gates": [
                        {"id": "a", "command": _pass_cmd()},
                        {"id": "b", "command": _fail_cmd()},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0, "a gate outside the default mode must not run"
        assert "PASS a" in result.stdout
        assert "FAIL b" not in result.stdout


def test_gates_rejects_unknown_default_mode() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "modes": {"all": ["a"]},
                    "defaultMode": "ghost",
                    "gates": [{"id": "a", "command": ["true"]}],
                }
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "a defaultMode naming no known mode must fail loud")


def test_gates_disabled_gate_never_runs() -> None:
    """enabled:false parks a gate visibly outside every run (P0 defect 1)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": _pass_cmd()},
                        {"id": "b", "command": _fail_cmd(), "enabled": False},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0, "a disabled gate must not affect the run"
        assert "DISABLED b" in result.stdout
        assert "FAIL b" not in result.stdout


def test_gates_advisory_failure_reports_without_blocking() -> None:
    """allowFailure must report the failure output yet keep exit code 0."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": _fail_cmd(), "allowFailure": True},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0, "an advisory gate must never block"
        assert "FAIL a" in result.stdout
        assert "advisory" in result.stdout, "an advisory failure must be visible"


def test_pairing_custom_counterpart_convention() -> None:
    """A .gov/pairing.json convention must be enforced, not ignored."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gov = root / ".gov"
        gov.mkdir()
        (gov / "pairing.json").write_text(
            json.dumps({"counterparts": ["{stem}_CN.md"]}), encoding="utf-8"
        )
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo_CN.md").write_text("# foo 中文\n", encoding="utf-8")
        _case(
            "verify_translation_pairing.py",
            root,
            1,
            "a custom-convention pair with no record must fail",
        )


def test_pairing_explicit_registration_sticks() -> None:
    """--write en:.. zh:.. registers any name; verification then pins it."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo_CN.md").write_text("# foo 中文\n", encoding="utf-8")
        register = subprocess.run(
            [
                sys.executable,
                str(HERE / "verify_translation_pairing.py"),
                "--write", "en:docs/foo.md", "zh:docs/foo_CN.md",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",
        )
        assert register.returncode == 0, f"explicit registration must exit 0: {register.stderr}"
        (docs / "foo_CN.md").write_text("# 单边修改\n", encoding="utf-8")
        _case(
            "verify_translation_pairing.py",
            root,
            1,
            "a one-sided edit of a registered pair must fail",
        )


def _fixture_env(root: Path) -> dict:
    """A scratch fixture's git environment (#24/D33): three walls.

    1. GIT_* scrubbed — an inherited GIT_DIR/GIT_INDEX_FILE resolves the
       HOST repository instead of the scratch (two production incidents).
    2. GIT_CEILING_DIRECTORIES pins discovery to the scratch parent —
       even a surprising cwd cannot walk up into the host.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    return env


def _git_repo(root: Path) -> None:
    env = _fixture_env(root)
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True, env=env)
    # The toplevel guard: BEFORE any config/add/commit, the scratch must
    # resolve to itself. If any path makes git resolve elsewhere, abort
    # loud rather than touch that repository (#24).
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=root,
        capture_output=True, text=True, env=env,
        encoding="utf-8", errors="replace",
    )
    resolved = Path(top.stdout.strip()).resolve() if top.returncode == 0 else None
    if resolved != root.resolve():
        raise AssertionError(
            f"self-test scratch fixture escaped: git in {root} resolves to "
            f"{resolved or '<no repository>'} — refusing to configure or "
            "commit into it (host-integrity guard, #24)"
        )
    for cmd in (
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(cmd, cwd=root, check=True, env=env)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "init"],
        cwd=root, check=True, env=env,
    )


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


def test_run_base_scopes_gates_by_paths() -> None:
    """--base must select gates by paths; out-of-scope gates never run."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        # docs-gate would PASS, code-gate would FAIL — only the in-scope one runs.
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "docs-gate", "command": _pass_cmd(), "paths": ["docs/**"]},
                        {"id": "code-gate", "command": _fail_cmd(), "paths": ["src/**"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "docs").mkdir()
        (root / "docs" / "a.md").write_text("x\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(HERE / "gates.py"), "--base", "HEAD"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, (
            "the failing gate is out of scope; the run must be green\n"
            f"{result.stdout}\n{result.stderr}"
        )
        assert "PASS docs-gate" in result.stdout
        assert "out of scope: code-gate" in result.stdout
        assert "FAIL code-gate" not in result.stdout


def test_run_failure_summary_and_gate_flag() -> None:
    """A blocking failure must end with a summary and a single-gate rerun hint."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "boom", "command": [sys.executable, "-c",
                                                   "import sys; print('boom', file=sys.stderr); raise SystemExit(3)"]},
                        {"id": "ok", "command": _pass_cmd()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 1
        assert "--- summary: 1 blocking failure(s) ---" in result.stdout
        assert "boom: boom" in result.stdout
        # #109: the failure line itself names the per-gate rerun command.
        assert "rerun: gov run --gate boom" in result.stdout
        single = subprocess.run(
            [sys.executable, str(HERE / "gates.py"), "--gate", "ok"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert single.returncode == 0
        assert "PASS boom" not in single.stdout


def test_change_scope_suggests_from_paths() -> None:
    """change-scope must read gate suggestions from gates.json paths, not prose."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "docs-gate", "command": ["true"], "paths": ["docs/**"]},
                        {"id": "code-gate", "command": ["true"], "paths": ["src/**"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "docs").mkdir()
        (root / "docs" / "a.md").write_text("x\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(HERE / "change_scope.py"), "--base", "HEAD"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert "gates.json paths" in result.stdout, result.stdout + result.stderr
        assert "docs-gate" in result.stdout
        assert "code-gate" not in result.stdout


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


def test_rubric_rejects_broken_structure() -> None:
    """verify-rubric must catch missing fields and bilingual id drift."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        good = (
            "### R1 — a\n\n"
            "- **Checks:** c\n- **Evidence:** e\n"
            "- **Anti-pattern:** a\n- **Gate candidate:** no — judgment\n"
        )
        (docs / "review-rubric.md").write_text(good, encoding="utf-8")
        (docs / "review-rubric.zh.md").write_text(
            good.replace("R1 — a", "R1 — 甲"), encoding="utf-8"
        )
        script = str(HERE / "verify_rubric.py")
        ok = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert ok.returncode == 0, ok.stderr
        (docs / "review-rubric.md").write_text(
            good.replace("- **Evidence:** e\n", ""), encoding="utf-8"
        )
        broken = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert broken.returncode == 1, "a rubric item missing a field must fail"
        assert "Evidence" in broken.stdout
        (docs / "review-rubric.md").write_text(good, encoding="utf-8")
        (docs / "review-rubric.zh.md").write_text(
            "### R2 — 乙\n\n- **查什么：** x\n", encoding="utf-8"
        )
        drift = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert drift.returncode == 1, "bilingual id drift must fail"
        assert "R2" in drift.stdout


def _write_note(root: Path, rel: str, body: str) -> None:
    p = root / ".agents" / "notes" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


_GOOD_NOTE = (
    "# Agent Note: t\n\nStatus: implemented\n\n"
    "## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n"
)
_GOOD_NOTE_BODY = (
    "## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n"
)


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


def test_verify_notes_rejects_unknown_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_note(root, "implemented/architecture/2026-01-01-x.md", _GOOD_NOTE)
        _write_note(root, "drafts/2026-01-01-x.md", _GOOD_NOTE)
        result = _run("verify_notes.py", root)
        assert result.returncode == 1, "an unknown lifecycle dir must fail loud (rule 5)"
        assert "unknown lifecycle 'drafts'" in result.stdout


def test_rubric_rejects_zero_items() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "review-rubric.md").write_text(
            "# Review rubric\n\ngarbage content, no items\n", encoding="utf-8"
        )
        _case(
            "verify_rubric.py",
            root,
            1,
            "a rubric with zero items is a vacuous pass (rule 6)",
        )


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


def test_gates_rejects_gate_in_no_mode() -> None:
    """D24: a gate parked by mode omission silently never runs — fail loud."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "modes": {"all": ["a"]},
                    "gates": [
                        {"id": "a", "command": ["true"]},
                        {"id": "stranded", "command": ["true"]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 2, "an enabled gate in no mode is a config error"
        assert "stranded" in result.stderr


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
        result = subprocess.run(
            [sys.executable, str(HERE / "self_test.py"), "--scope", "project"],
            cwd=root, capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 1, "a failing project case must fail self-test"
        assert "case-broken.sh" in result.stdout, "the case must be named"


def _ledger_output(root: Path) -> str:
    """The coverage ledger's stdout, run in process against ``root``.

    ``_coverage_report`` is a pure function of the tree it is run in, so
    the cases that pin its wording drive it directly: going through a
    self-test subprocess would add platform-dependent execution semantics
    (a POSIX shebang case cannot execute on Windows) that those cases are
    not about.
    """
    buf = io.StringIO()
    cwd = os.getcwd()
    os.chdir(root)
    try:
        with contextlib.redirect_stdout(buf):
            _coverage_report()
    finally:
        os.chdir(cwd)
    return buf.getvalue()


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


def test_verify_decisions_rejects_broken_table() -> None:
    """Wish 9: duplicate ids, gaps, and alternative-less decisions fail loud."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n\n## D1 — b\n\n- **选项**：x\n\n"
            "## D3 — c\n\n- **状态**：已决\n",
            encoding="utf-8",
        )
        result = _run("verify_decisions.py", root)
        assert result.returncode == 1, "a broken decisions table must fail"
        assert "duplicate" in result.stdout
        assert "missing: D2" in result.stdout
        assert "D3: records no options" in result.stdout


def test_verify_decisions_rejects_base_collision() -> None:
    """#107: --base must refuse a number two branches both allocated."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        env = _fixture_env(root)

        def git(*argv: str, check: bool = True):
            return subprocess.run(
                list(argv), cwd=root, check=check, capture_output=True,
                text=True, env=env,
                encoding="utf-8", errors="replace",
            )

        git("git", "branch", "-q", "-m", "main")
        docs = root / "docs"
        docs.mkdir()
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n", encoding="utf-8")
        git("git", "add", "-A")
        git("git", "-c", "commit.gpgsign=false", "commit", "-qm", "fork")
        git("git", "checkout", "-q", "-b", "topic")
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n\n## D2 — mine\n\n- **选项**：x\n",
            encoding="utf-8")
        git("git", "add", "-A")
        git("git", "-c", "commit.gpgsign=false", "commit", "-qm", "branch D2")
        git("git", "checkout", "-q", "main")
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n\n## D2 — theirs\n\n- **选项**：x\n",
            encoding="utf-8")
        git("git", "add", "-A")
        git("git", "-c", "commit.gpgsign=false", "commit", "-qm", "sibling")
        git("git", "checkout", "-q", "topic")
        result = _run("verify_decisions.py", root, ["--base", "main"])
        assert result.returncode == 1, \
            "a number both branches allocated must be a named collision"
        assert "D2: number collision" in result.stdout


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


def test_gates_rejects_unknown_keys() -> None:
    """D29: "enable": false is a typo'd park that silently parks nothing."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps({"gates": [{"id": "a", "command": ["true"],
                                   "enable": False}]}),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 2, "an unknown gate key must abort loud"
        assert "unknown key(s): enable" in result.stderr


def test_doc_sync_rejects_changelog_without_highlights() -> None:
    """D37: CHANGELOG gains a version, HIGHLIGHTS hasn't followed — red."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.14.0] (2026-09-04)\n\n### Features\n\n* x\n",
            encoding="utf-8",
        )
        gov = root / "gov"
        gov.mkdir()
        (gov / "HIGHLIGHTS.md").write_text(
            "## 0.13.0 — old\n\n- y\n", encoding="utf-8")
        _case(
            "verify_doc_sync.py",
            root,
            1,
            "a CHANGELOG version without a HIGHLIGHTS section must fail",
        )


def test_conflict_markers_rejects_marked_file() -> None:
    """#104/D38: a staged conflicted file must fail loud, naming file:line,
    while the escape hatch tolerates a deliberate literal."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        script = str(HERE / "verify_conflict_markers.py")
        conflicted = root / "doc.md"
        conflicted.write_text(
            "# doc\n\n"
            + "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 1, (
            "a file with conflict markers must fail the gate\n"
            f"{result.stdout}\n{result.stderr}"
        )
        assert "doc.md:3" in result.stdout, "the finding must name file and line"
        assert "doc.md:5" in result.stdout and "doc.md:7" in result.stdout, (
            "start, separator, and end markers are all named"
        )
        conflicted.write_text(
            "# doc\n\n"
            + "<<<<<<< HEAD " + "gov:ignore-marker" + "\n",
            encoding="utf-8",
        )
        clean = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert clean.returncode == 0, (
            "the ignore token must exempt a deliberate literal\n" + clean.stdout
        )


def test_conflict_markers_bare_separator_needs_sibling() -> None:
    """#104: a bare ======= alone (a Markdown H1 underline) must pass."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        (root / "README.md").write_text(
            "Title\n=======\n\nbody\n", encoding="utf-8")
        _case("verify_conflict_markers.py", root, 0,
              "a setext underline with no sibling marker must pass")


def test_passing_gate_output_stays_visible() -> None:
    """A pass that printed a warning must not be silenced (P1-2)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "warny", "command": [sys.executable, "-c",
                                                    "print('heads up')"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0
        assert "passed with output" in result.stdout
        assert "heads up" in result.stdout


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


def test_task_check_rejects_tampered_receipt() -> None:
    """#125: a done card whose receipt is not an all-green run against the
    pinned rules must fail check — the receipt is evidence, not prose."""
    with tempfile.TemporaryDirectory() as td:
        root = _task_project(Path(td))
        from . import task as task_mod
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


def _task_project(root: Path) -> Path:
    """A minimal gov-initialized project: rule set + empty tasks dir."""
    (root / ".gov" / "tasks").mkdir(parents=True, exist_ok=True)
    (root / ".gov" / "rules.md").write_text("# Rules\n", encoding="utf-8")
    (root / "gates.json").write_text(
        json.dumps({"gates": []}), encoding="utf-8")
    return root


def _receipt_repo(root: Path, two_gates: bool = False) -> str:
    """A committed scratch repo with passing gate(s); returns HEAD sha."""
    _git_repo(root)
    gate_ids = ["ok", "two"] if two_gates else ["ok"]
    config = {"gates": [{"id": gid, "command": _pass_cmd()} for gid in gate_ids]}
    (root / "gates.json").write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-qm", "gates"], cwd=root, check=True,
                   capture_output=True)
    return _run_text(["git", "rev-parse", "HEAD"], cwd=root,
                     check=True, capture_output=True, text=True).stdout.strip()


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


def test_run_merge_rejects_text_conflict() -> None:
    """D51: `gov run --merge` must catch a textual merge conflict before
    landing — the step fails loud, names the branch, the already-merged
    set, and the conflicted file, and keeps the scratch scene. A real,
    subprocess-reproducible failure (no fault injection, #24's lesson)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "host"
        root.mkdir()
        env = _fixture_env(root)

        def git(*argv: str, check: bool = True):
            return subprocess.run(["git", *argv], cwd=root, check=check,
                                  capture_output=True, text=True, env=env,
                                  encoding="utf-8", errors="replace")

        git("init", "-q", "-b", "main", ".")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (root / "gates.json").write_text(
            json.dumps({"gates": [{"id": "ok", "command": _pass_cmd()}]}),
            encoding="utf-8")
        (root / ".gitignore").write_text(".gov/history/\n", encoding="utf-8")
        (root / "f.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-qm", "base")
        for name, first in (("a", "A1"), ("b", "B1")):
            git("checkout", "-q", "-b", name)
            (root / "f.txt").write_text(f"{first}\ntwo\nthree\n",
                                        encoding="utf-8")
            git("commit", "-qam", name)
            git("checkout", "-q", "main")
        result = _run("gates.py", root,
                      extra=["--merge", "a", "b", "--base", "main"])
        assert result.returncode == 1, (
            "a textual conflict must fail the preflight\n"
            f"{result.stdout}\n{result.stderr}")
        assert ("branch 2 (b) conflicts with already-merged set (a)"
                in result.stdout), result.stdout
        assert "f.txt" in result.stdout, "the conflicted file must be named"
        kept = [l for l in result.stdout.splitlines()
                if "kept for inspection: " in l]
        assert kept, "the scratch scene must be kept for inspection"
        scene = Path(kept[0].split("kept for inspection: ", 1)[1].strip())
        assert scene.is_dir() and "<<<<<<<" in (scene / "f.txt").read_text(
            encoding="utf-8"), "the live conflict must be inspectable"
        # the scene is kept BY DESIGN; this case tidies it up
        subprocess.run(["git", "-C", str(root), "worktree", "remove",
                        "--force", str(scene)], capture_output=True)
        shutil.rmtree(scene, ignore_errors=True)
        subprocess.run(["git", "-C", str(root), "worktree", "prune"],
                       capture_output=True)


def test_failure_classifier_labels_tool_vs_environment() -> None:
    """#139/D47: a FAIL's label is earned from evidence, not guessed.

    A probe that genuinely breaks only under a polluted import path must
    replay green (environment-suspect); one that breaks everywhere must
    replay red (tool-defect). The probes double as ``--case`` fixtures.
    """
    # First prove the env-only probe's failure is real: under the shadow
    # path it reproduces; this is the #138 shape (a promoted site dir).
    saved = os.environ.get("PYTHONPATH")
    try:
        os.environ["PYTHONPATH"] = "/tmp/gov-selftest-shadow-probe/x"
        try:
            _probe_env_only_failure()
            raise AssertionError("the env-only probe failed to reproduce "
                                 "under a shadowed PYTHONPATH")
        except AssertionError as e:
            assert "shadowed PYTHONPATH" in str(e)
    finally:
        if saved is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = saved
    env_lines = _classify_tool_failure(_probe_env_only_failure)
    assert any("environment-suspect" in l for l in env_lines), env_lines
    tool_lines = _classify_tool_failure(_probe_always_fails)
    assert any("tool-defect" in l for l in tool_lines), tool_lines


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


def test_text_subprocess_decodes_are_pinned() -> None:
    """#172: every text-mode subprocess in the shipped package pins UTF-8.

    ``text=True`` without ``encoding`` decodes the child's output with the
    locale codec — on a zh-CN Windows that is GBK, and non-ASCII UTF-8 in
    a case's output crashed the reader thread while the case still PASSED.
    The package itself must stay on the wall #168 built for the runner's
    git decodes: this case re-runs that proof on every ``gov self-test``,
    wheel included.
    """
    bad: list[str] = []
    for p in sorted(HERE.rglob("*.py")):
        bad += _unpinned_text_spawns(p.read_text(encoding="utf-8"), p.name)
    assert not bad, (
        "text-mode subprocess calls decode with the locale codec unless "
        "encoding is pinned — on a GBK-locale Windows the first non-ASCII "
        f"UTF-8 byte crashes the reader thread (#172): {bad} — route them "
        "through _run_text()")


CASES = [
    test_verify_notes_rejects_missing_section,
    test_gates_rejects_duplicate_id,
    test_gates_rejects_cycle,
    test_gates_rejects_unknown_needs,
    test_gates_skips_transitively,
    test_gates_rejects_non_object_gate,
    test_cli_init_help_no_side_effect,
    test_pairing_rejects_missing_record,
    test_pairing_write_resolves_bare_stem_and_zh_side,
    test_gates_default_mode_scopes_run,
    test_gates_rejects_unknown_default_mode,
    test_gates_disabled_gate_never_runs,
    test_gates_advisory_failure_reports_without_blocking,
    test_pairing_custom_counterpart_convention,
    test_pairing_explicit_registration_sticks,
    test_note_presence_warns_then_strict_blocks,
    test_run_base_scopes_gates_by_paths,
    test_run_failure_summary_and_gate_flag,
    test_change_scope_suggests_from_paths,
    test_init_hooks_ci_roundtrip,
    test_rubric_rejects_broken_structure,
    test_verify_notes_rejects_wrong_section_order,
    test_verify_notes_rejects_unknown_lifecycle,
    test_rubric_rejects_zero_items,
    test_passing_gate_output_stays_visible,
    test_note_presence_auto_base_catches_committed_work,
    test_note_presence_task_receipts_and_manifest_exemptions,
    test_note_presence_rejects_ill_shaped_manifest,
    test_verify_notes_rejects_status_lying,
    test_archive_seal_detects_tampering_and_refuses_laundering,
    test_gates_rejects_gate_in_no_mode,
    test_self_test_adopts_project_rejection_cases,
    test_coverage_warning_names_the_marker_fix,
    test_verify_decisions_rejects_broken_table,
    test_verify_decisions_rejects_base_collision,
    test_skills_text_command_drift_is_named,
    test_registry_real_flags_are_not_drift,
    test_gates_rejects_unknown_keys,
    test_doc_sync_rejects_changelog_without_highlights,
    test_conflict_markers_rejects_marked_file,
    test_conflict_markers_bare_separator_needs_sibling,
    test_task_check_rejects_stale_rules_pin,
    test_task_check_rejects_tampered_receipt,
    test_task_survives_pre37_argparse_shadow,
    test_receipt_rejects_forged_record,
    test_receipt_rejects_partial_run_as_full_evidence,
    test_run_merge_rejects_text_conflict,
    test_failure_classifier_labels_tool_vs_environment,
    test_parse_layer_metrics_mean_what_they_claim,
    test_check_engine_mechanisms_are_real,
    test_preset_rejects_unknown_name,
    test_text_subprocess_decodes_are_pinned,
]


def _project_cases() -> list[Path]:
    if not REJECTIONS_DIR.is_dir():
        return []
    return [
        p
        for p in sorted(REJECTIONS_DIR.rglob("*"))
        if p.is_file() and not p.name.startswith("README")
    ]


def _run_project_case(p: Path) -> tuple[str, bool]:
    """(report line, ok) — exit 0 means the rejection proof holds."""
    if not os.access(p, os.X_OK):
        return f"FAIL {p} (not executable — chmod +x it)", False
    try:
        proc = _run_text(
            [str(p)], capture_output=True, text=True,
            timeout=REJECTION_TIMEOUT_S, cwd=str(Path.cwd()), env=_case_env(),
        )
    except subprocess.TimeoutExpired:
        return f"FAIL {p} (timed out after {REJECTION_TIMEOUT_S}s)", False
    except OSError as e:
        return f"FAIL {p} (cannot execute — missing shebang? {e.strerror})", False
    if proc.returncode == 0:
        return f"PASS {p}", True
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    why = f": {tail[0]}" if tail else ""
    return f"FAIL {p} (exit {proc.returncode}{why})", False


GATE_RX = re.compile(r"(?m)^#\s*gate:\s*([a-z][a-z0-9-]*)")


def _coverage_report() -> None:
    """Wish 4/D30: rule 6's ledger — which gates have rejection cases.

    A project case declares the gate it proves with a '# gate: <id>'
    comment in its first lines. Gates without any case are named; this is
    a reminder, not a failure (coverage ramps up).
    """
    import json as _json

    try:
        with open("gates.json", encoding="utf-8") as f:
            gate_ids = [g.get("id") for g in _json.load(f).get("gates", [])
                        if isinstance(g, dict) and g.get("id")]
    except (OSError, _json.JSONDecodeError):
        return  # no gates.json here (e.g. the tools' own scratch repos)
    covered: dict[str, int] = {}
    undeclared: list[str] = []
    for p in _project_cases():
        declared = GATE_RX.findall("\n".join(
            p.read_text(encoding="utf-8", errors="replace").splitlines()[:5]))
        for gid in declared:
            covered[gid] = covered.get(gid, 0) + 1
        if not declared:
            undeclared.append(str(p))
    lines = []
    for gid in gate_ids:
        n = covered.get(gid, 0)
        lines.append(f"{gid}({n})" if n else f"{gid}(NONE — rule 6)")
    stray = [g for g in covered if g not in gate_ids]
    print(f"coverage (gate x project rejection cases): {' '.join(lines)}")
    if undeclared:
        # #18/D32: a case that just RAN and PASSed but declares no gate —
        # name it; never nag about writing a case that exists.
        print("  executed case(s) without a '# gate: <id>' declaration "
              "(first five lines):")
        for p in undeclared:
            print(f"    {p}")
        # #167: naming the file was the whole message, and the two things
        # an adopter needs to fix it (the marker's syntax, its scan
        # window) had to be reverse-engineered. Print the remedy inline.
        print("  fix: add '# gate: <id>' within the first 5 lines to link "
              "the case to the gate it proves (a line inside the module "
              "docstring counts; keep the shebang on line 1)")
    if any("(NONE" in l for l in lines) and not undeclared:
        print("  write one: .gov/rejections/case-<gate-id>.sh, shebang on "
              "line 1, '# gate: <id>' within the first five lines")
    if stray:
        print(f"note: case names unknown gate(s): {', '.join(stray)}")


def _run_tool_case(case) -> tuple[str, bool]:
    try:
        case()
    except Exception as e:  # noqa: BLE001 — report, don't traceback
        # The evidence line: assertion messages that embed subprocess
        # output end with the real cause (the killer exception is the
        # last line), so quote the last non-empty line, not the header
        # (#139: the operator should not have to trace a traceback to
        # read the TypeError that killed the case).
        lines = [l for l in str(e).strip().splitlines() if l.strip()]
        why = f": {lines[-1].strip()}" if lines else ""
        return f"FAIL {case.__name__} ({type(e).__name__}{why})", False
    return f"PASS {case.__name__}", True


# --- failure classification: tool-defect vs environment-suspect (#139/D47)

# The clean replay's budget: the slowest single case recursively runs a
# nested self-test with its own 120s ceiling (D26's spirit — bounded, not
# unbounded); a replay that outlives this is reported unclassified.
CLEAN_REPLAY_TIMEOUT_S = 180

_CLEAN_STAGE: tempfile.TemporaryDirectory | None = None


def _clean_stage() -> Path:
    """A pristine copy of the running package, alone in a temp dir.

    The replayed case must import govrail without the host's site layer
    in the way: staging a copy lets ``PYTHONPATH`` point at a directory
    holding ONLY the package, so the stdlib resolves ahead of every
    site-packages entry and a stray backport (e.g. an ``argparse.py``
    installed there) cannot shadow it. Since D54 the package also has a
    compiled dependency (tree-sitter): it imports from the interpreter's
    site-packages in the replay too — the staged copy is complete for
    everything EXCEPT a dependency that was only ever importable via
    ``PYTHONPATH`` or user-site, which the replay drops. A failure with
    that shape is still labeled tool-defect; the label's evidence is
    weaker there, and the module docstring says so.
    """
    global _CLEAN_STAGE
    if _CLEAN_STAGE is None:
        _CLEAN_STAGE = tempfile.TemporaryDirectory(
            prefix="gov-selftest-clean-")
        shutil.copytree(
            HERE, Path(_CLEAN_STAGE.name) / HERE.name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    return Path(_CLEAN_STAGE.name)


def _clean_replay_env(stage: Path) -> dict:
    """The minimal environment for a clean replay (#139/D47).

    Everything ``PYTHON*`` from the host is dropped — ``PYTHONPATH`` is
    the promotion vector that put a site-packages backport ahead of the
    stdlib in the #138 incident — and the staged package is the only
    extra path entry. ``GIT_*`` stays scrubbed (D32), and the staged
    process re-establishes the git ceiling wall itself via ``main()``.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and not k.startswith("PYTHON")}
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONPATH"] = str(stage)
    return env


def _classify_tool_failure(case) -> list[str]:
    """Replay one failing tools-family case in the minimal env.

    Returns the indented verdict lines printed under the FAIL line:
    a replay that passes labels the failure environment-suspect, one
    that fails again confirms a tool-defect, and a replay that cannot
    run (timeout, interpreter failure) is reported unclassified with
    the hand-rerun command — never silently guessed.
    """
    stage = _clean_stage()
    try:
        proc = _run_text(
            [sys.executable, "-m", "gov.self_test", "--case", case.__name__],
            cwd=str(stage), env=_clean_replay_env(stage),
            capture_output=True, text=True,
            timeout=CLEAN_REPLAY_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return [f"    clean-env replay: TIMEOUT after "
                f"{CLEAN_REPLAY_TIMEOUT_S}s — unclassified; rerun by hand: "
                f"gov self-test --case {case.__name__}"]
    if proc.returncode not in (0, 1):
        # The replay itself failed to run (a case unknown to the staged
        # copy, an interpreter crash) — that classifies nothing.
        tail = [l for l in proc.stderr.splitlines() if l.strip()]
        why = f": {tail[-1].strip()}" if tail else ""
        return [f"    clean-env replay: not runnable (exit "
                f"{proc.returncode}{why}) — unclassified; rerun by hand: "
                f"gov self-test --case {case.__name__}"]
    if proc.returncode == 0:
        return ["    clean-env replay: PASS — environment-suspect: the same "
                "case passes with the host's PYTHON* layer removed (a clean "
                "copy of govrail; its compiled dependency resolves from this "
                "interpreter's site-packages either way, D54). Check this "
                "host's site-packages shadowing / PYTHON* environment; the "
                "traceback in the FAIL line is the environmental evidence."]
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    why = f": {lines[0].strip()}" if lines else f"exit {proc.returncode}"
    return [f"    clean-env replay: FAIL — tool-defect: fails in the "
            f"minimal env too ({why})"]


def _probe_env_only_failure() -> None:
    """Classifier probe (#139, never in CASES): the #138 miniature.

    Broken only when ``PYTHONPATH`` carries the probe's shadow directory
    — exactly how a promoted site-packages backport broke ``gov task``.
    """
    pp = os.environ.get("PYTHONPATH", "")
    assert "gov-selftest-shadow-probe" not in pp, (
        f"broken only under a shadowed PYTHONPATH: {pp}")


def _probe_always_fails() -> None:
    """Classifier probe (#139, never in CASES): broken everywhere."""
    raise AssertionError("broken in every environment")


_DIAGNOSTIC_PROBES = (_probe_env_only_failure, _probe_always_fails)


def _find_case(name: str):
    """Resolve a --case name against CASES, then the diagnostic probes."""
    for case in [*CASES, *_DIAGNOSTIC_PROBES]:
        if case.__name__ == name:
            return case
    return None


def _scrub_environment() -> None:
    """The process-boundary scrub (#20/D32, wall three of #24/D33).

    A pre-push hook leaks GIT_DIR/GIT_WORK_TREE into this process; the
    tools resolve repositories by cwd (D21), so inherited GIT_* only
    ever misleads — root anchoring in scratch repos would resolve the
    HOST repository. Scrub once, at the process boundary, and say so
    when it happened. The third wall pins GIT_CEILING_DIRECTORIES over
    the temp area so no case's git command can walk up out of it.
    """
    REPO_RESOLVING = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                      "GIT_QUARANTINE_PATH", "GIT_OBJECT_DIRECTORY",
                      "GIT_ALTERNATE_OBJECT_DIRECTORIES"}
    leaked = [k for k in os.environ if k.startswith("GIT_")]
    for k in leaked:
        del os.environ[k]  # benign ones too: cases are hermetic by contract
    os.environ["GIT_CEILING_DIRECTORIES"] = tempfile.gettempdir()
    dangerous = sorted(set(leaked) & REPO_RESOLVING)
    if dangerous:
        print(f"self-test: scrubbed repository-resolving variable(s) from the "
              f"environment ({', '.join(dangerous)}) — cases must resolve "
              "repositories by cwd (hook-context leak, #20)")


# Rule 5 / #172: a crash inside one of the harness's own threads — on
# Windows the subprocess reader threads are the residents — used to die in
# threading.excepthook, print a traceback, and leave the exit code
# untouched: the case kept its emptied capture and could still PASS. The
# default hook still runs (the traceback stays on stderr as evidence);
# the crash is ALSO recorded so the run itself fails loud.
_THREAD_CRASHES: list = []
_default_thread_excepthook = threading.excepthook


def _recording_thread_excepthook(args: threading.ExceptHookArgs) -> None:
    _default_thread_excepthook(args)
    _THREAD_CRASHES.append(args)


threading.excepthook = _recording_thread_excepthook


def _fail_if_thread_crashed() -> int:
    """1 when a harness thread crashed mid-run — never pass on that (#172).

    A crashed reader thread empties the capture it was filling, so PASS
    lines already printed may be blind. Prints one line per crash and
    clears the record so an in-process second run starts clean (pytest
    drives ``main`` repeatedly).
    """
    if not _THREAD_CRASHES:
        return 0
    for a in _THREAD_CRASHES:
        name = a.thread.name if a.thread is not None else "<thread>"
        print(f"HARNESS-ERROR thread {name!r} crashed: "
              f"{a.exc_type.__name__}: {a.exc_value}")
    n = len(_THREAD_CRASHES)
    _THREAD_CRASHES.clear()
    print(f"self-test: {n} harness thread crash(es) — a crashed reader "
          "thread empties a case's captured output, so PASS lines above "
          "may be blind (rule 5: fail loud, never silently skip)")
    return 1


def main(argv: list[str] | None = None) -> int:
    try:
        from .root import force_utf8_stdio
    except ImportError:  # direct-script execution (python gov/self_test.py)
        from root import force_utf8_stdio
    force_utf8_stdio()  # case reports leave as UTF-8 on every OS (#168)
    parser = argparse.ArgumentParser(
        prog="gov self-test",
        description="Run rejection cases: the tools' own plus the project's "
                    "under .gov/rejections/.",
        # #167: the declaration's syntax and scan window live in --help
        # too — the warning prints the fix, the help explains the ledger.
        epilog="A project case declares the gate it proves with a "
               "'# gate: <id>' comment within its first five lines (a line "
               "inside a module docstring counts; the id is lowercase "
               "letters, digits and dashes). The coverage ledger at the end "
               "of the run reads that declaration: uncovered gates read "
               "'NONE — rule 6'. The ledger is a reminder, never a failure.",
    )
    parser.add_argument("--scope", choices=("all", "tools", "project"),
                        default="all", help="which family of cases to run")
    parser.add_argument("--case", metavar="NAME",
                        help="run one tools-family case by name and exit — "
                             "the diagnostic building block of the clean-env "
                             "replay (#139); implies --scope tools")
    args = parser.parse_args(argv)

    if args.case:
        case = _find_case(args.case)
        if case is None:
            parser.error(f"unknown case '{args.case}' — not in CASES or the "
                         "diagnostic probes")
        _scrub_environment()
        line, ok = _run_tool_case(case)
        print(line)
        crash_rc = _fail_if_thread_crashed()
        return 0 if ok and not crash_rc else 1

    _scrub_environment()

    tool_jobs = [] if args.scope == "project" else list(CASES)
    project_jobs = [] if args.scope == "tools" else _project_cases()

    results: list[tuple[str, bool]] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        tool_futures = [pool.submit(_run_tool_case, c) for c in tool_jobs]
        project_futures = [pool.submit(_run_project_case, p) for p in project_jobs]
        for fut in tool_futures:
            results.append(fut.result())
        for fut in project_futures:
            results.append(fut.result())

    failures = [line for line, ok in results if not ok]
    # #139/D47: every FAIL is classified from evidence — a clean-env
    # replay verdict under each tools-family failure, a hand-repro hint
    # under project failures (their scripts may legitimately need this
    # environment; an automatic replay would prove nothing).
    counts = {"tool-defect": 0, "environment-suspect": 0, "unclassified": 0}
    for idx, (line, ok) in enumerate(results):
        print(line)
        if ok:
            continue
        if idx < len(tool_jobs):
            for verdict in _classify_tool_failure(tool_jobs[idx]):
                print(verdict)
                for kind in counts:
                    if kind in verdict:
                        counts[kind] += 1
                        break
                else:
                    counts["unclassified"] += 1
        else:
            print("    clean-env comparison not attempted — project cases "
                  "run arbitrary scripts; reproduce by hand in a minimal "
                  "environment.")
            counts["unclassified"] += 1
    _coverage_report()
    tools_n, project_n = len(tool_jobs), len(project_jobs)
    parts = [f"tools {tools_n}" if tools_n else "", f"project {project_n}" if project_n else ""]
    family = " + ".join(p for p in parts if p)
    crash_rc = _fail_if_thread_crashed()
    if failures or crash_rc:
        if failures:
            tally = ", ".join(f"{k} {v}" for k, v in counts.items())
            print(f"self-test: {len(failures)} failure(s) ({family}) — {tally}")
        return 1
    print(f"self-test: {family or 'no cases selected'} — all pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
