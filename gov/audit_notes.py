#!/usr/bin/env python3
"""Audit implemented notes for mechanical staleness signals.

The note contract says implemented notes are kept current with the shipped
facts; drift is silent. This audit reports mechanical signals only —
references the world no longer satisfies:

- backticked ``gov <subcommand>`` mentions that this CLI does not know,
  and flags those mentions carry that the subcommand does not accept
  (against a registry pinned to each command's ``--help`` options —
  tests/test_flag_registry.py);
- ``Dn`` references with no ``## Dn —`` entry in ``docs/decisions.md``
  (checked only when that file exists);
- backticked repo paths (directory separator plus extension, no globs,
  no obvious placeholders) that do not resolve from the project root.

Archived notes are frozen (D5) and exempt by design. Findings are evidence
for the archive-agent-notes skill's judgment, not a verdict: exit 0 with or
without findings, exit 2 only when the tree cannot be read. Package mode
only (`gov audit-notes`) — the command signal needs the CLI's own registry.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    from root import anchor_to_git_root

IMPLEMENTED = Path(".agents/notes/implemented")
DECISIONS = Path("docs/decisions.md")
GOV_CMD_RX = re.compile(r"`gov ([a-z][a-z0-9-]*)((?: [^`]*?)?)`")  # cmd + args
D_REF_RX = re.compile(r"\bD(\d+)\b")
# External decision references — the tool's own decisions table. The only
# sanctioned cross-project namespace (D34): radiant citing govrail:D24 is
# a reference INTO govrail's table, never into the local one.
EXTERNAL_D_RX = re.compile(r"govrail:D\d+")
PATH_RX = re.compile(r"`([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-/]*\.[A-Za-z0-9]+)`")
PLACEHOLDER_PARTS = {"foo", "bar", "baz", "example", "examples", "xx", "x", "demo", "path"}
SKILLS_DIR = Path(".agents/skills")
# Universal flags every command answers (cli handles them uniformly).
UNIVERSAL_FLAGS = {"-h", "--help", "-v", "--version"}

# Flag registry for the skills-drift check (wish 11/D28). The command set
# is cli._COMMANDS (single source); flags are declared here because the
# argparse parsers are built inside main() at run time. D28 rejected
# deriving this table from argparse at run time — the deal was "static
# table, pinned by tests". The pin is tests/test_flag_registry.py: for
# every command, `gov <cmd> --help` must list exactly these flags. When a
# flag moves, move it here and in the command's help (issue #101: init
# gained --adopt/--preview/--json and the registry silently lagged, so
# notes documenting working runs read as dead commands).
FLAGS: dict[str, set[str]] = {
    "init": {"--project", "--hooks", "--pre-commit", "--ci", "--upgrade",
             "--json", "--adopt", "--adopt-new", "--preview", "--preset"},
    "uninstall": {"--project", "--force"},
    "run": {"--config", "--mode", "--base", "--gate", "--every-gate",
            "--merge", "--tag", "--no-record", "--receipt", "--json",
            "--fail-fast", "--verbose", "--cost"},
    "self-test": {"--scope", "--case"},
    "receipt": {"--record", "--commit"},
    "verify-notes": set(),
    "verify-pairing": {"--write", "--staged", "--explain"},
    "verify-note-presence": {"--base", "--strict", "--staged"},
    "verify-rubric": {"--path"},
    "verify-archive": set(),
    "verify-decisions": {"--path", "--base", "--json"},
    "decision": {"--count", "--base", "--against", "--from", "--id",
                 "--dry-run"},  # --against aliases --base (#147)
    "verify-doc-sync": {"--write"},
    "verify-conflict-markers": {"--base", "--staged"},
    "review": {"--base", "--hits", "--grade"},
    "trend": {"--last", "--gate", "--base", "--by-tag", "--cost"},
    "stats": {"--lang", "--record", "--json"},
    "check": {"--lang", "--strict", "--record", "--json"},
    "doctor": {"--json"},
    "note": {"--class", "--ref"},  # on the `new` subcommand
    "whatsnew": {"--since"},
    "recall": {"--any"},
    "audit-notes": {"--json"},
    "change-scope": {"--base"},
    "archive-notes": {"--rebaseline"},
    "task": {"--check", "--rules", "--mode", "--timeout",
             "--agent", "--ttl", "--wait", "--json"},  # across subcommands
    "preset": {"--project"},  # on the `apply` subcommand (list/show are flagless)
    "acquire": {"--agent", "--ttl", "--wait"},
    "release": {"--agent"},
    "locks": set(),
}


def _known_commands() -> set[str] | None:
    try:
        from . import cli
    except ImportError:
        return None
    return set(cli._COMMANDS)


def _known_decisions() -> set[str] | None:
    """D-numbers in the decisions source (loader: config or default).

    None = no source; an EMPTY set = a source exists but parses to zero
    entries (format mismatch) — two states the summary must not confuse.
    Callers treat an empty set as "unchecked", same as None.
    """
    from . import decisions as dec
    src = dec.load()
    if src is None:
        return None
    found = {d for d, _, _ in src.entries()}
    if not found:
        # A decisions file that parses to zero entries means a format
        # mismatch — treating it as "no decisions" would flag every D-ref
        # as missing. Say so and leave D-refs unchecked instead.
        print(
            f"audit_notes: {DECISIONS} has no '## Dn — ' sections; "
            "check its format (D-refs left unchecked)",
            file=sys.stderr,
        )
        return set()
    return found


def _drift(text: str, commands: set[str]) -> list[str]:
    """Unknown `gov <cmd>` mentions and unknown flags, per mention."""
    found: list[str] = []
    for cmd, rest in sorted(set(GOV_CMD_RX.findall(text))):
        if cmd not in commands:
            found.append(f"unknown command `gov {cmd}`")
            continue
        # Registry coverage is enforced in main() (commands == set(FLAGS)),
        # so every known command has an entry — possibly empty.
        known_flags = FLAGS[cmd]
        for flag in sorted(set(re.findall(r"(?<!\w)(?:--[a-z][a-z0-9-]*|-h|-v)", rest))):
            if flag in UNIVERSAL_FLAGS:
                continue  # every command answers these (cli handles them)
            if flag not in known_flags:
                found.append(f"unknown flag `{flag}` on `gov {cmd}`")
    return found


def _flags_note(text: str, commands: set[str] | None,
                decisions: set[str] | None) -> list[str]:
    found: list[str] = []
    if commands is not None:
        found.extend(_drift(text, commands))
    if decisions:  # non-empty: the set to check against
        local_text = EXTERNAL_D_RX.sub("", text)  # govrail:D24 != local D24
        for d in sorted(set(D_REF_RX.findall(local_text)), key=int):
            if f"D{d}" not in decisions:
                found.append(f"references D{d}, not in the decisions source")
    for raw in sorted(set(PATH_RX.findall(text))):
        if "*" in raw or "{" in raw:
            continue
        parts = Path(raw).parts
        names = set(parts) | {Path(part).stem for part in parts}
        if names & PLACEHOLDER_PARTS:
            continue
        if not Path(raw).exists():
            found.append(f"unresolved path `{raw}` (may be illustrative)")
    return found


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("audit_notes")
    parser = argparse.ArgumentParser(
        prog="gov audit-notes",
        description="Report mechanical staleness signals in implemented notes.",
    )
    parser.add_argument("--json", action="store_true",
                        help="machine-readable: stdout is exactly one JSON "
                             "object {notes, skills, decisions_source, "
                             "findings, state}; the human report moves to stderr")
    args = parser.parse_args(argv)

    def emit(text: str) -> None:
        # #119/D26: in json mode stdout carries exactly one JSON value.
        print(text, file=sys.stderr if args.json else sys.stdout)

    commands = _known_commands()
    if commands is None:
        print("audit_notes: needs package mode — run as `gov audit-notes`", file=sys.stderr)
        return 2
    # Rule 5: a registry that lags cli._COMMANDS would silently skip flag
    # checks for the missing command (or flag-check a phantom one). That is
    # a defect in this tool, not a finding in the tree — name it and abort.
    missing = commands - set(FLAGS)
    phantom = set(FLAGS) - commands
    if missing or phantom:
        for name in sorted(missing):
            print(f"audit_notes: flag registry is missing '{name}' "
                  "(registry lagged cli._COMMANDS — file a govrail bug)", file=sys.stderr)
        for name in sorted(phantom):
            print(f"audit_notes: flag registry knows '{name}' but the CLI does not",
                  file=sys.stderr)
        return 2
    if not IMPLEMENTED.is_dir():
        print(f"audit_notes: {IMPLEMENTED} not found — is this a project root?", file=sys.stderr)
        return 2
    decisions = _known_decisions()

    findings: list[dict] = []
    notes = 0
    for p in sorted(IMPLEMENTED.rglob("*.md")):
        notes += 1
        text = p.read_text(encoding="utf-8")
        for flag in _flags_note(text, commands, decisions):
            emit(f"{p}: {flag}")
            findings.append({"file": str(p), "signal": flag})

    # Wish 11/D28: skills are the manual agents read most literally —
    # a renamed command or flag silently expires them.
    skills = 0
    if SKILLS_DIR.is_dir():
        for p in sorted(SKILLS_DIR.rglob("*.md")):
            skills += 1
            for flag in _drift(p.read_text(encoding="utf-8"), commands):
                emit(f"{p}: {flag}")
                findings.append({"file": str(p), "signal": flag})
    human_state = "clean" if not findings else f"{len(findings)} signal(s)"
    state = "clean" if not findings else "dirty"
    if decisions is None:
        extra = " (no decisions source; D-refs unchecked)"
    elif not decisions:
        extra = f" ({DECISIONS} has no '## Dn — ' sections; D-refs unchecked)"
    else:
        extra = ""
    emit(f"audit_notes: {notes} implemented note(s), {skills} skill file(s), "
         f"{human_state}{extra}")
    if args.json:
        print(json.dumps(
            {"notes": notes, "skills": skills,
             "decisions_source": bool(decisions),
             "findings": findings, "state": state},
            indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
