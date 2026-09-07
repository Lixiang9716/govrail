#!/usr/bin/env python3
"""gov doctor — environment self-check (D29, wish: no silent environment).

The plane's runners assume an environment; when the assumption breaks
(gov on an un-PATH'd ~/.local/bin, a hook that cannot exec, a gates.json
typo) the failure mode has been silence or a confusing crash. Doctor
names the problems, one per line, rule-5 style; exit 1 when any check
fails, 0 when the environment is sound.

Checks: CLI reachability from PATH (the hook's fast path), the Python
interpreter against the package requirement, git hook presence and
executability (both copies; the pre-commit hook is opt-in), gates.json
schema (strict keys), shipped-but-unadopted gates (#147 — a gate absent
from gates.json never runs and nothing prompts its adoption, so doctor
names the ones this govrail version ships that the project hasn't
wired), and — when a decisions table exists — that it parses.

``--json`` (#119): stdout carries exactly one JSON object —
``{version, status, checks, problems}`` where each check is
``{name, state, detail}`` (state: ok | note | problem) — and the human
report moves to stderr. The human format remains the default.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

from . import __version__

MIN_PYTHON = (3, 9)


def _check_gov_on_path(checks: list[dict]) -> None:
    if shutil.which("gov"):
        checks.append({"name": "gov-on-path", "state": "ok",
                       "detail": "gov resolves on PATH (hooks' fast path works)"})
    else:
        checks.append({
            "name": "gov-on-path", "state": "problem",
            "detail": "gov is not on PATH — hooks and rejection cases calling "
                      "`gov` will fail; export GOV_BIN, or ensure the install "
                      "bin dir (e.g. ~/.local/bin) is on PATH"})


def _check_python(checks: list[dict]) -> None:
    v = sys.version_info
    if v[:2] >= MIN_PYTHON:
        checks.append({"name": "python", "state": "ok",
                       "detail": f"python {v.major}.{v.minor} meets the required "
                                 f">= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"})
    else:
        checks.append({"name": "python", "state": "problem",
                       "detail": f"python {v.major}.{v.minor} is below the "
                                 f"required {MIN_PYTHON[0]}.{MIN_PYTHON[1]}"})


def _check_argparse_shadow(checks: list[dict]) -> None:
    """#138: a py2-era ``argparse`` backport (PyPI argparse 1.4.0) installed
    next to gov shadows the stdlib whenever PYTHONPATH promotes that dir —
    subcommand CLIs died in an unreadable ``TypeError`` about ``required``.
    The environment must say so (rule 5: fail loud) instead of leaving the
    crash to be rediscovered per command."""
    import os
    import sysconfig
    real = getattr(argparse, "__file__", None)
    if real is None:
        checks.append({"name": "argparse-shadow", "state": "note",
                       "detail": "argparse reports no source file — "
                                 "cannot verify it resolves to the stdlib"})
        return
    stdlib = sysconfig.get_paths()["stdlib"]
    if os.path.dirname(os.path.realpath(real)) == os.path.realpath(stdlib):
        checks.append({"name": "argparse-shadow", "state": "ok",
                       "detail": "argparse resolves to the stdlib"})
    else:
        checks.append({
            "name": "argparse-shadow", "state": "problem",
            "detail": f"argparse resolves to {real}, not the stdlib — an "
                      "installed argparse backport is shadowing it and "
                      "breaks CLI parsing; pip uninstall argparse"})


def _git_dir() -> str | None:
    """The git dir, worktree-aware (#15/D32): a linked worktree's .git is a
    FILE; git rev-parse --git-common-dir resolves the shared dir (hooks
    live there even from a linked worktree)."""
    proc = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return None
    import os
    return os.path.abspath(proc.stdout.strip()) or None


def _check_hook(checks: list[dict]) -> None:
    import os
    git_dir = _git_dir()
    if git_dir is None:
        checks.append({"name": "git-repo", "state": "note",
                       "detail": "not a git repository — hook checks skipped"})
        return
    # pre-push: the gate-DAG runner; pre-commit: the OPT-IN commit-stage
    # gates (#110) — its absence is a choice, not a problem.
    for name, how in (("pre-push", "gov init --hooks installs it"),
                      ("pre-commit",
                       "gov init --hooks --pre-commit installs it (opt-in)")):
        hook = os.path.join(git_dir, "hooks", name)
        for rel, what in ((hook, "the wired git hook"),
                          (f".gov/hooks/{name}", "the auditable copy")):
            if not os.path.exists(rel):
                checks.append({"name": f"hook:{rel}", "state": "note",
                               "detail": f"{rel} absent ({what}) — {how}"})
                continue
            if os.access(rel, os.X_OK):
                checks.append({"name": f"hook:{rel}", "state": "ok",
                               "detail": f"{rel} is executable"})
            else:
                checks.append({"name": f"hook:{rel}", "state": "problem",
                               "detail": f"{rel} is not executable — chmod +x it"})


def _check_version_drift(checks: list[dict]) -> None:
    """#19/D32: the environment self-check must see manifest drift."""
    import os
    manifest = ".gov/manifest.json"
    if not os.path.exists(manifest):
        return
    try:
        init_version = json.loads(
            open(manifest, encoding="utf-8").read()).get("version")
    except (OSError, ValueError):
        return
    if init_version and init_version != __version__:
        checks.append({
            "name": "manifest-drift", "state": "note",
            "detail": f"manifest initialized with govrail {init_version}, this "
                      f"package is {__version__} — gov init --upgrade shows "
                      "template drift; gov whatsnew --since "
                      f"{init_version} shows what arrived"})


def _check_gates(checks: list[dict]) -> None:
    import os
    if not os.path.exists("gates.json"):
        checks.append({"name": "gates.json", "state": "note",
                       "detail": "no gates.json — gov init creates one when missing"})
        return
    from . import gates as gates_mod
    try:
        _, gs, _, _ = gates_mod.load_config("gates.json")
        checks.append({"name": "gates.json", "state": "ok",
                       "detail": "gates.json passes the strict schema"})
        for g in gs:
            if g.command and not shutil.which(g.command[0]):
                checks.append({
                    "name": f"gate:{g.id}", "state": "problem",
                    "detail": f"gate '{g.id}': command '{g.command[0]}' not found on "
                              "PATH — the run would report MISSING"})
            elif g.command:
                checks.append({"name": f"gate:{g.id}", "state": "ok",
                               "detail": f"gate '{g.id}' command resolves ({g.command[0]})"})
    except gates_mod.ConfigError as e:
        checks.append({"name": "gates.json", "state": "problem",
                        "detail": f"gates.json: {e}"})


# Gate-shaped tools this govrail version ships that are NOT in the
# injection template: their paths/content are project-specific (D17/D28),
# so they are wired into a mode by hand rather than via --adopt-new.
# Discovery lives here because a gate absent from gates.json is invisible
# to every run — radiant ran parallel branches while the one gate that
# would have named the number collisions (verify-decisions) sat unadopted
# and nothing ever pointed at it (#147).
HAND_SHIPPED_GATES = {
    "rubric": ("verify-rubric", "review rubric structure"),
    "decisions": ("verify-decisions", "decisions table guard"),
    "doc-sync": ("verify-doc-sync", "CHANGELOG/HIGHLIGHTS pairing"),
}


def _check_gate_adoption(checks: list[dict]) -> None:
    """#147: name shipped gates the project never adopted.

    A note, never a problem: adoption is deliberate (D17/D28 — the plane
    is a floor, growth is event-driven), and a defined-but-unmoded gate
    is already a loud config error (D24). What was missing is the naming:
    a project whose gates.json predates a shipped gate had no prompt at
    all. Template gates have a mechanical adoption path (``gov init
    --adopt-new gates.json``, D39); the hand gates name the tool to wire.
    """
    import json
    import os
    if not os.path.exists("gates.json"):
        return  # the gates.json check above already speaks for a missing config
    from . import gates as gates_mod
    try:
        _, gs, _, _ = gates_mod.load_config("gates.json")
    except gates_mod.ConfigError:
        return  # the gates.json check already names this; nothing to scan
    by_id = {g.id for g in gs}
    tokens = {tok for g in gs for tok in (g.command or [])}

    def adopted(gid: str, tool_tokens: tuple[str, ...]) -> bool:
        return gid in by_id or all(t in tokens for t in tool_tokens)

    tpl_missing: list[str] = []
    hand_missing: list[str] = []
    try:
        from importlib.resources import files
        tpl = json.loads(files("gov.templates").joinpath("gates.json")
                         .read_text(encoding="utf-8"))
        for g in tpl.get("gates", []):
            tool = tuple(t for t in g.get("command", []) if t != "gov")
            if not adopted(g["id"], tool):
                tpl_missing.append(g["id"])
    except (OSError, ValueError, KeyError, AttributeError):
        checks.append({"name": "gate-adoption", "state": "note",
                       "detail": "cannot read the shipped gates template — "
                                 "adoption check skipped"})
        return
    for gid, (tool, what) in HAND_SHIPPED_GATES.items():
        if not adopted(gid, (tool,)):
            hand_missing.append(f"{gid} (`gov {tool}`, {what})")

    if not tpl_missing and not hand_missing:
        checks.append({"name": "gate-adoption", "state": "ok",
                       "detail": "every gate this govrail version ships is "
                                 "wired into gates.json (or deliberately "
                                 'parked via "enabled": false)'})
        return
    parts: list[str] = []
    if tpl_missing:
        parts.append(f"shipped gate(s) not adopted here: {', '.join(tpl_missing)}"
                     " — gov init --adopt-new gates.json lands them")
    if hand_missing:
        parts.append("shipped tool(s) with no gate: "
                     + ", ".join(hand_missing)
                     + " — wire one into a mode by hand (paths are "
                       "project-specific, so they are not in the template)")
    checks.append({"name": "gate-adoption", "state": "note",
                   "detail": "; ".join(parts)})


def _check_decisions(checks: list[dict]) -> None:
    import contextlib
    import io
    import os
    if not os.path.exists("docs/decisions.md"):
        return  # no table, nothing to check — not an environment problem
    from . import verify_decisions as vd
    # Capture the sub-run's stdout: in --json mode doctor's stdout must
    # carry exactly one JSON value (D26), never verify-decisions prose.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = vd.main([])
    if rc == 0:
        checks.append({"name": "decisions-table", "state": "ok",
                       "detail": "decisions table parses"})
    else:
        checks.append({"name": "decisions-table", "state": "problem",
                       "detail": "decisions table has violations — "
                                 "gov verify-decisions"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov doctor",
        description="Environment self-check: PATH, Python, hooks, gates schema.",
    )
    parser.add_argument("--json", action="store_true",
                        help="machine-readable: stdout is exactly one JSON "
                             "object {version, status, checks, problems}; "
                             "the human report moves to stderr")
    args = parser.parse_args(argv)

    def emit(text: str) -> None:
        if args.json:
            print(text, file=sys.stderr)
        else:
            print(text)

    checks: list[dict] = []
    _check_gov_on_path(checks)
    _check_python(checks)
    _check_argparse_shadow(checks)
    _check_version_drift(checks)
    _check_hook(checks)
    _check_gates(checks)
    _check_gate_adoption(checks)
    _check_decisions(checks)
    problems = [c for c in checks if c["state"] == "problem"]

    emit(f"gov doctor — govrail {__version__}")
    for c in checks:
        if c["state"] == "ok":
            emit(f"ok: {c['detail']}")
        elif c["state"] == "note":
            emit(f"note: {c['detail']}")
    if problems:
        emit("")
        for c in problems:
            emit(f"problem: {c['detail']}")
        emit(f"gov doctor: {len(problems)} problem(s)")
    else:
        emit("gov doctor: environment sound")

    if args.json:
        print(json.dumps(
            {"version": __version__,
             "status": "sound" if not problems else "problems",
             "checks": checks,
             "problems": [c["name"] for c in problems]},
            indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
