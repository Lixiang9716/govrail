"""Shared fixtures and step helpers for the rejection-case families.

Everything here is mechanism, not a case: scratch environments, git
seeding, subprocess plumbing, and the ``@case`` registry the families
import. Runner machinery that never feeds a case module stays in
``__init__``.
"""
from __future__ import annotations

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
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # the gov/ package root (the monolith's parent)
REJECTIONS_DIR = Path(".gov/rejections")
CONCURRENCY = 4
# A runaway rejection case must not hold a CI job hostage (D26): each
# project case gets a small budget — a rejection proof is small by nature.
REJECTION_TIMEOUT_S = 10

# The case registry. Family modules register via the decorator at import
# time — definition order within a module, module import order in
# ``__init__`` across families — replacing the hand-maintained CASES list
# the monolith required (define here AND remember to append there).
CASES: list = []


def case(fn):
    """Register a rejection case. Order = definition order."""
    CASES.append(fn)
    return fn


# Portable gate-command fixtures (#168). The fixtures below used the Unix
# coreutils `true`/`false` and `sh -c` to say "a command that exits 0/1" —
# none of which exists on Windows, where every such gate came out MISSING
# and ten cases failed for fixture reasons, not tool reasons (the wheel is
# py3-none-any / OS Independent, so the tools' own proof must be too).
# Fixtures whose gates actually EXECUTE use these; config-error fixtures
# that exit 2 before any gate runs keep their `["true"]` placeholders.
_PASS_CMD = [sys.executable, "-c", "pass"]
_FAIL_CMD = [sys.executable, "-c", "raise SystemExit(1)"]


_GOOD_NOTE = (
    "# Agent Note: t\n\nStatus: implemented\n\n"
    "## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n"
)
_GOOD_NOTE_BODY = (
    "## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n"
)



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



def _write_note(root: Path, rel: str, body: str) -> None:
    p = root / ".agents" / "notes" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")



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
    if root.resolve() != Path(cwd).resolve():
        os.chdir(root)
        try:
            with contextlib.redirect_stdout(buf):
                _coverage_report()
        finally:
            os.chdir(cwd)
    else:
        with contextlib.redirect_stdout(buf):
            _coverage_report()
    return buf.getvalue()



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



_CLEAN_STAGE: tempfile.TemporaryDirectory | None = None


CLEAN_REPLAY_TIMEOUT_S = 180


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



def _probe_always_fails() -> None:
    """Classifier probe (#139, never in CASES): broken everywhere."""
    raise AssertionError("broken in every environment")



def _probe_env_only_failure() -> None:
    """Classifier probe (#139, never in CASES): the #138 miniature.

    Broken only when ``PYTHONPATH`` carries the probe's shadow directory
    — exactly how a promoted site-packages backport broke ``gov task``.
    """
    pp = os.environ.get("PYTHONPATH", "")
    assert "gov-selftest-shadow-probe" not in pp, (
        f"broken only under a shadowed PYTHONPATH: {pp}")


_DIAGNOSTIC_PROBES = (_probe_env_only_failure, _probe_always_fails)


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


GATE_RX = re.compile(r"(?m)^#\s*gate:\s*([a-z][a-z0-9-]*)")


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


def _project_cases() -> list[Path]:
    if not REJECTIONS_DIR.is_dir():
        return []
    return [
        p
        for p in sorted(REJECTIONS_DIR.rglob("*"))
        if p.is_file() and not p.name.startswith("README")
    ]

