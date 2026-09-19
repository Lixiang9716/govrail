#!/usr/bin/env python3
"""gov — the command dispatcher.

Every subcommand delegates to the module that owns it: adoption lives in
``plane.py`` (init/uninstall/update's machinery), the command vocabularies
live in ``commands.py`` (the one registry ``--help``, audit-notes, and the
exit-code contract test all read), and each family hub (note, decision,
lease, verify, task, preset, receipt, ...) forwards to its own module's
``main``. This module is argv grammar and routing — nothing else.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import (change_scope, decision,
               gates, gate, hookcmd, locks, recall, review, stats, surprise, task,
               verify_conflict_markers, verify_doc_sync, verify_plane)
from . import checks, commands, doctor, note, plane, presets, receipt, self_test, trend, whatsnew
from . import verify_rubric
from . import verify_translation_pairing
from . import __version__

_CD_FLAGS = ("-C", "--path")


def _resolved_target() -> str:
    """The directory gov is acting on: the git work-tree root when inside
    one (exactly what cd + root anchoring would resolve to), else cwd."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",  # git speaks UTF-8, not the locale codec (#168)
        )
    except OSError:
        proc = None
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return os.getcwd()


def _apply_cd_flags(argv: list[str]) -> list[str] | None:
    """Consume leading ``-C <path>`` / ``--path <path>`` flags (#121).

    A supervisor orchestrating several worktrees chdirs by value instead
    of bookkeeping: each path resolves against the previous one (git
    ``-C`` semantics, chainable), the chdir lands before the subcommand
    dispatches, and — because a wrong-tree invocation must be visible,
    not just valid — the resolved root is announced in the output header
    of every command run this way. A nonexistent path fails loud.
    """
    moved: list[str] = []
    while argv and argv[0] in _CD_FLAGS:
        if len(argv) < 2:
            print(f"gov: {argv[0]} requires a directory path", file=sys.stderr)
            return None
        target = Path(argv[1])
        if not target.is_dir():
            print(f"gov: {argv[0]} {argv[1]}: no such directory", file=sys.stderr)
            return None
        os.chdir(target)
        moved.append(argv[1])
        argv = argv[2:]
    if moved:
        print(f"gov: targeting {_resolved_target()} "
              f"(via -C {' -C '.join(moved)})", file=sys.stderr)
    return argv


def _usage() -> None:
    print("usage: gov [-C <path>] <command> [args]", file=sys.stderr)
    print("  -C, --path DIR   run <command> against DIR's repository "
          "(before the command;", file=sys.stderr)
    print("                   resolves the work-tree root and announces it)",
          file=sys.stderr)
    print("exit codes: 0 ok · 1 failure (gate red, findings, refused "
          "run) · 2 config/usage error · 3 lease busy (acquire)",
          file=sys.stderr)
    print("commands:", file=sys.stderr)
    for name, help_text in commands.COMMANDS.items():
        print(f"  {name:<16} {help_text}", file=sys.stderr)


def _command_help(cmd: str) -> None:
    """Per-command help for the hand-parsed trio (same shape as argparse's)."""
    flags = commands.COMMAND_FLAGS[cmd]
    print(f"usage: gov {cmd} [options]")
    print(commands.COMMANDS[cmd])
    print()
    print("options:")
    names = [name for name, _ in flags] + ["-h, --help"]
    width = max(len(n) for n in names)
    for name, desc in flags:
        print(f"  {name:<{width}}  {desc}")
    print(f"  {'-h, --help':<{width}}  show this help and exit")


def _parse_platforms(value: str) -> list[str] | None:
    """`--platforms` value → validated platform list (None = bad, named).

    Rule 5: an unknown or empty name aborts with the offender, never a
    silent skip; duplicates dedupe preserving order; 'all' selects every
    shipped platform.
    """
    names: list[str] = []
    for raw in value.split(","):
        name = raw.strip()
        if not name:
            print(f"gov init: --platforms has an empty name in '{value}' "
                  f"(known: {', '.join(plane.PLATFORM_TARGETS)}, all)",
                  file=sys.stderr)
            return None
        if name == "all":
            names.extend(p for p in plane.PLATFORM_TARGETS if p not in names)
            continue
        if name not in plane.PLATFORM_TARGETS:
            print(f"gov init: unknown platform '{name}' "
                  f"(known: {', '.join(plane.PLATFORM_TARGETS)}, all)",
                  file=sys.stderr)
            return None
        if name not in names:
            names.append(name)
    return names


def _init_uninstall_args(
    args: list[str], what: str
) -> tuple[Path, bool, bool, bool, bool] | None:
    """Parse --project (+ init's --hooks/--ci/--upgrade/--preset/
    --platforms, uninstall's --force)."""
    project = "."
    hooks = ci = force = upgrade = adopt = report_json = preview = pre_commit = False
    adopt_targets: list[str] = []
    adopt_new: str | None = None
    preset: str | None = None
    platforms: list[str] | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--project":
            if i + 1 >= len(args):
                print(f"gov {what}: --project requires a directory", file=sys.stderr)
                return None
            project = args[i + 1]
            i += 2
        elif what == "init" and a == "--hooks":
            hooks = True
            i += 1
        elif what == "init" and a == "--pre-commit":
            pre_commit = True
            i += 1
        elif what == "init" and a == "--ci":
            ci = True
            i += 1
        elif what == "init" and a == "--upgrade":
            upgrade = True
            i += 1
        elif what == "init" and a == "--json":
            report_json = True
            i += 1
        elif what == "init" and a == "--preview":
            preview = True
            i += 1
        elif what == "init" and a == "--preset":
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                print("gov init: --preset requires a preset name "
                      "(see `gov preset list`)", file=sys.stderr)
                return None
            preset = args[i + 1]
            i += 2
        elif what == "init" and a == "--platforms":
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                print("gov init: --platforms requires a comma-separated "
                      f"list (known: {', '.join(plane.PLATFORM_TARGETS)}, all)",
                      file=sys.stderr)
                return None
            platforms = _parse_platforms(args[i + 1])
            if platforms is None:
                return None
            i += 2
        elif what == "init" and a == "--adopt":
            adopt = True
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                adopt_targets.append(args[i])
                i += 1
        elif what == "init" and a == "--adopt-new":
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                print("gov init: --adopt-new requires a file "
                      "(currently: gates.json)", file=sys.stderr)
                return None
            adopt_new = args[i + 1]
            i += 2
        elif what == "uninstall" and a == "--force":
            force = True
            i += 1
        else:
            print(f"gov {what}: unexpected argument '{a}'", file=sys.stderr)
            _usage()
            return None
    return (Path(project), hooks, ci, force, upgrade,
            (adopt_targets if adopt else None), report_json, preview,
            adopt_new, pre_commit, preset, platforms)


def main(argv: list[str] | None = None) -> int:
    from .root import ensure_utf8_runtime, force_utf8_stdio
    if argv is None:  # a real process entry (console script / -m gov)
        ensure_utf8_runtime()
    force_utf8_stdio()  # every report leaves as UTF-8, on every OS (#168)
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        _usage()
        return 2
    argv = _apply_cd_flags(argv)
    if argv is None:
        return 2
    if not argv:
        _usage()
        return 2
    cmd, rest = argv[0], argv[1:]
    while cmd in commands.DEPRECATED_ALIASES:
        # D57 Wave 1: absorbed commands keep working — same behavior,
        # one deprecation line, and the alias dies after the window.
        # The line names no removal version (#316): the promised window
        # (0.40) passed five minors ago while the alias still works —
        # a deadline that lies once trains users to ignore the line.
        new = commands.DEPRECATED_ALIASES[cmd]
        print(f"gov: '{cmd}' is deprecated — use 'gov {' '.join(new)}' "
              "(the alias still works; it will be removed in a future "
              "release)", file=sys.stderr)
        cmd, rest = new[0], [*new[1:], *rest]

    if cmd in commands.HELP_FLAGS:
        _usage()
        return 0
    if cmd in commands.VERSION_FLAGS:
        print(f"gov {__version__}")
        return 0
    # Subcommand-level help/version: never execute the action as a side effect.
    if cmd in commands.NO_FORWARD:
        if any(a in commands.HELP_FLAGS for a in rest):
            _command_help(cmd)  # the real surface, not the terse global usage
            return 0
        if any(a in commands.VERSION_FLAGS for a in rest):
            print(f"gov {__version__}")
            return 0
    if cmd == "init":
        parsed = _init_uninstall_args(rest, "init")
        return 2 if parsed is None else plane.init(parsed[0], hooks=parsed[1], ci=parsed[2],
                                                   upgrade=parsed[4], adopt=parsed[5],
                                                   report_json=parsed[6],
                                                   preview=parsed[7],
                                                   adopt_new=parsed[8],
                                                   pre_commit=parsed[9],
                                                   preset=parsed[10],
                                                   platforms=parsed[11])
    if cmd == "uninstall":
        parsed = _init_uninstall_args(rest, "uninstall")
        return 2 if parsed is None else plane.uninstall(parsed[0], force=parsed[3])
    if cmd == "preset":
        return presets.main(rest)
    if cmd == "update":
        from . import update
        return update.main(rest)
    if cmd == "run":
        return gates.main(rest)
    if cmd == "gate":
        return gate.main(rest)
    if cmd == "receipt":
        return receipt.main(rest)
    if cmd == "self-test":
        return self_test.main(rest)
    if cmd == "verify":
        hub = {"pairing": verify_translation_pairing,
               "rubric": verify_rubric,
               "conflict-markers": verify_conflict_markers,
               "doc-sync": verify_doc_sync}
        sub = rest[0] if rest else ""
        if sub in ("-h", "--help"):
            print("usage: gov verify <target> [flags]")
            print("content gates without a family hub:")
            for name, help_text in (
                    ("pairing", "bilingual pairing (--write re-confirms; "
                     "--staged checks the index; --explain prints the schema)"),
                    ("rubric", "review rubric structure (--path)"),
                    ("conflict-markers", "conflict markers "
                     "(--base, --staged)"),
                    ("doc-sync", "CHANGELOG ↔ HIGHLIGHTS pairing (--write)")):
                print(f"  {name:<20} {help_text}")
            return 0
        if sub not in hub:
            # bare invocation AND unknown target are both usage errors:
            # siblings (note/decision/lease) exit 2 on a missing/unknown
            # subcommand — this hub must not be the quiet one (P2)
            print("usage: gov verify <target> [flags]", file=sys.stderr)
            print(f"gov verify: unknown target '{sub or '(bare)'}' (known: "
                  f"{', '.join(sorted(hub))})", file=sys.stderr)
            return 2
        return hub[sub].main(rest[1:])
    if cmd == "decision":
        return decision.main(rest)
    if cmd == "review":
        return review.main(rest)
    if cmd == "trend":
        return trend.main(rest)
    if cmd == "stats":
        return stats.main(rest)
    if cmd == "check":
        return checks.main(rest)
    if cmd == "parse":
        return stats.parse_main(rest)
    if cmd == "doctor":
        return doctor.main(rest)
    if cmd == "note":
        return note.main(rest)
    if cmd == "whatsnew":
        return whatsnew.main(rest)
    if cmd == "recall":
        return recall.main(rest)
    if cmd == "surprise":
        return surprise.main(rest)
    if cmd == "lease":
        sub = rest[0] if rest else ""
        if sub in ("-h", "--help"):
            print("usage: gov lease <subcommand> [flags]")
            print("lease locks for parallel agents (busy exits 3):")
            print("  acquire  take a lease on a resource "
                  "(--agent ID --ttl DUR --wait S)")
            print("  release  release a lease you hold (--agent ID)")
            print("  list     list current lease locks (diagnostic)")
            return 0
        if sub not in ("acquire", "release", "list"):
            print(f"gov lease: unknown subcommand '{sub}' "
                  "(known: acquire, release, list)", file=sys.stderr)
            return 2
        mapped = "locks" if sub == "list" else sub
        return locks.main([mapped, *rest[1:]])
    if cmd == "change-scope":
        return change_scope.main(rest)
    if cmd == "task":
        return task.main(rest)
    if cmd == "hooks":
        return hookcmd.main(rest)
    if cmd == "agent-hooks":
        from . import agent_hooks
        return agent_hooks.main(rest)
    if cmd == "verify-plane":
        return verify_plane.main(rest)
    print(f"gov: unknown command '{cmd}'", file=sys.stderr)
    _usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
