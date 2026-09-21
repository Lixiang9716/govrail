#!/usr/bin/env python3
"""Rejection cases for each governance gate (D3, D25).

Every case introduces a deliberate violation, runs the gate, and asserts the
gate FAILS — proving it can reject, not just pass. A green self-test means
each governance gate has demonstrated it catches the violation it claims to.

Two families, reported separately so they never blur:

- **tools**: the cases built into this package — the govrail gates' own
  proofs, one family module per plane surface (registration is the
  ``@case`` decorator; a new case is defined, never also listed);
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
import json  # noqa: F401 — tests read st.json (historical surface)
import os
import subprocess  # noqa: F401 — tests read st.subprocess (historical surface)
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Family modules register their cases at import time (order = report
# order); the imports are deliberate side effects, never name loads.
from . import (  # noqa: F401
    cases_notes,  # noqa: F401
    cases_gates,  # noqa: F401
    cases_knowledge,  # noqa: F401
    cases_surface,  # noqa: F401
    cases_evidence,  # noqa: F401
)
from ._harness import (
    CASES,  # noqa: F401
    CONCURRENCY,  # noqa: F401
    HERE,  # noqa: F401
    REJECTIONS_DIR,  # noqa: F401
    REJECTION_TIMEOUT_S,  # noqa: F401
    _DIAGNOSTIC_PROBES,  # noqa: F401
    _case_env,  # noqa: F401
    _classify_tool_failure,  # noqa: F401
    _coverage_report,  # noqa: F401
    _git_repo,  # noqa: F401
    _probe_always_fails,  # noqa: F401
    _probe_env_only_failure,  # noqa: F401
    _project_cases,  # noqa: F401
    _run_project_case,  # noqa: F401
    _run_text,  # noqa: F401
)  # noqa: F401 — the closing-paren noqa cannot cover per-alias diagnostics




# The clean replay's budget: the slowest single case recursively runs a
# nested self-test with its own 120s ceiling (D26's spirit — bounded, not
# unbounded); a replay that outlives this is reported unclassified.




# Rule 5 / #172: a crash inside one of the harness's own threads — on
# Windows the subprocess reader threads are the residents — used to die in
# threading.excepthook, print a traceback, and leave the exit code
# untouched: the case kept its emptied capture and could still PASS. The
# default hook still runs (the traceback stays on stderr as evidence);
# the crash is ALSO recorded so the run itself fails loud.
_THREAD_CRASHES: list = []
_default_thread_excepthook = threading.excepthook


CASE_TIMEOUT_S = float(os.environ.get("GOV_SELFTEST_TIMEOUT", "300"))










def _run_with_timeout_guarded(case) -> tuple[str, bool]:
    """Pool path: arm the subprocess watchdog around the direct runner.

    The watchdog's subprocess IS the --case replay, which prints its own
    PASS/FAIL line; on success this wrapper re-runs direct to produce
    the caller's (line, ok) tuple from the same evidence. On timeout or
    child failure it returns a loud FAIL line naming the case."""
    import sys as _sys
    if _watchdog_env_marked() or "--case" in (
            _sys.argv[1:3] if len(_sys.argv) > 1 else []):
        return _run_tool_case_direct(case)
    if not any(c is case for c in CASES):
        return _run_tool_case_direct(case)
    import subprocess as _sp
    # The child must import the SAME govrail this process is running:
    # from a scratch cwd, `python -m gov.self_test` resolves the pip-
    # installed govrail (possibly versions behind the working tree —
    # found live: the newly registered case exited 2 "unknown case").
    # package layout: __init__.py is gov/self_test/ — two levels up is
    # the checkout root the working-tree gov/ resolves from
    pkg_root = str(Path(__file__).resolve().parent.parent.parent)
    env = {**os.environ, "GOV_SELFTEST_WATCHDOG": "1",
           "PYTHONPATH": os.pathsep.join(
               [pkg_root] + ([os.environ["PYTHONPATH"]]
                             if os.environ.get("PYTHONPATH") else []))}
    proc = _sp.Popen(
        [_sys.executable, "-m", "gov.self_test", "--case", case.__name__],
        stdout=_sp.PIPE, stderr=_sp.PIPE, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    try:
        out, err = proc.communicate(timeout=CASE_TIMEOUT_S)
    except _sp.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return (f"FAIL {case.__name__} (exceeded {CASE_TIMEOUT_S}s — "
                "killed by the case watchdog)", False)
    # the child reported its own verdict; mirror it
    verdict_ok = proc.returncode == 0
    if out:
        print(out, end="", flush=True)
    if not verdict_ok and err:
        print(err, end="", file=sys.stderr, flush=True)
    line = f"{'PASS' if verdict_ok else 'FAIL'} {case.__name__}"
    if not verdict_ok:
        lines = [l for l in (out or "").strip().splitlines() if l.strip()]
        if lines:
            line += f" ({lines[-1].strip()})"
    return line, verdict_ok



def _run_tool_case_direct(case) -> tuple[str, bool]:
    """Run one case in-process (the --case replay path): no watchdog —
    this IS the innermost execution the pool's guard forks into."""
    try:
        case()
    except Exception as e:  # noqa: BLE001 — report, don't traceback
        # The evidence line: assertion messages that embed subprocess
        # output end with the real cause (the killer exception is the
        # last line), so quote the last non-empty line, not the header
        # (#139: the operator should not have to trace a traceback to
        # read the TypeError that killed the case). Quoting the last
        # line DISCARDS the rest — a flake whose traceback lived only
        # in the assert message is unreadable after the fact — so a
        # multi-line message also lands WHOLE in a file the FAIL line
        # names.
        text = str(e)
        lines = [l for l in text.strip().splitlines() if l.strip()]
        why = f": {lines[-1].strip()}" if lines else ""
        dump = ""
        if len(lines) > 1:
            dump = f"; full output: {_dump_case_failure(case.__name__, text)}"
        return f"FAIL {case.__name__} ({type(e).__name__}{why}){dump}", False
    return f"PASS {case.__name__}", True



def _dump_case_failure(name: str, text: str) -> str:
    """Persist the whole failure output; the one-line report quotes only
    the killer exception, and the traceback above it used to vanish with
    the print. Tempdir semantics: the OS cleans it up, the operator
    reads it first."""
    import tempfile
    fd, path = tempfile.mkstemp(prefix=f"gov-selftest-{name}-", suffix=".log")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")
    return path


# Alias kept for the tests that drive the direct runner by its
# historical name.
_run_tool_case = _run_tool_case_direct







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



def _recording_thread_excepthook(args: threading.ExceptHookArgs) -> None:
    _default_thread_excepthook(args)
    _THREAD_CRASHES.append(args)



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



def _watchdog_env_marked() -> bool:
    """True when this process is already a watchdog child.

    The --case replay path IS the innermost execution: a watchdog that
    forks `--case` from inside `_run_tool_case` forks ITSELF
    recursively (found live — the suite hung in self-fork). The guard
    arms only in the pool-runner process; the replayed child runs the
    function directly.
    """
    return os.environ.get("GOV_SELFTEST_WATCHDOG") == "1"



def main(argv: list[str] | None = None) -> int:
    try:
        from ..root import anchor_to_git_root
    except ImportError:  # direct-script execution (scratch installs)
        from root import anchor_to_git_root
    anchor_to_git_root("self-test")
    try:
        from ..root import force_utf8_stdio
    except ImportError:  # non-package execution (kept for parity with the other fallbacks)
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
    parser.add_argument("--explain", action="store_true",
                        help="print the full rule-6 coverage ledger: the "
                             "per-gate case list and the case-authoring "
                             "remedy (the default reports coverage counts "
                             "only, #337)")
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
        # --case is the innermost single-case execution (the pool's
        # watchdog forked this very process to reach here): run direct
        line, ok = _run_tool_case_direct(case)
        print(line)
        crash_rc = _fail_if_thread_crashed()
        return 0 if ok and not crash_rc else 1

    _scrub_environment()

    tool_jobs = [] if args.scope == "project" else list(CASES)
    project_jobs = [] if args.scope == "tools" else _project_cases()

    results: list[tuple[str, bool]] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        tool_futures = [
            pool.submit(lambda c=c: _run_with_timeout_guarded(c)) 
            for c in tool_jobs]
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
    _coverage_report(explain=getattr(args, "explain", False))
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
