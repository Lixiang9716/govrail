#!/usr/bin/env python3
"""Surprises gate: the third recurrence of a surprise is a process defect.

Rule 11's teeth. The surprise ledger (.gov/surprises.jsonl, written by
``gov surprise record``) collects expectation-vs-reality telemetry; this
gate reads it and enforces the escalation contract: when one signature
has three or more recorded surprises, a process note citing
``surprise:<sig>`` must exist in the notes corpus — a recurring surprise
means the process, not the person, needs to change, and the plane keeps
that change from being skipped the way every other skip is kept from
happening: by going red.

Also judged, fail loud (rule 5): a corrupt ledger line (counts drive the
threshold — a silent shrink would hide escalations), and a one-sided
entry (an expectation or reality left empty cannot be recognized next
time — the ledger's whole point). Below three, no note is owed: one or
two surprises are data, not yet a pattern. Exit codes follow D2: 0 ok,
1 escalation owed / one-sided entries, 2 corrupt ledger or usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LEDGER = Path(".gov/surprises.jsonl")
ESCALATION_AT = 3
NOTES_GLOBS = (".agents/notes/implemented/**/*.md",
               ".agents/notes/archived/**/*.md")


def load_ledger(root: Path) -> list[dict]:
    path = root / LEDGER
    if not path.exists():
        return []
    entries = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        print(f"surprises: cannot read ledger {path}: {e}", file=sys.stderr)
        raise SystemExit(2)
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"surprises: {path}:{i}: corrupt entry ({e}) — fix or "
                  f"revert the ledger; counts drive the escalation gate",
                  file=sys.stderr)
            raise SystemExit(2)
        if not isinstance(entry, dict) or not isinstance(entry.get("sig"), str):
            print(f"surprises: {path}:{i}: entry is not an object with a "
                  f"'sig' field", file=sys.stderr)
            raise SystemExit(2)
        entries.append(entry)
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_surprises")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root to judge (default: this checkout)")
    parser.add_argument("--threshold", type=int, default=ESCALATION_AT,
                        help="entries per signature that demand escalation")
    args = parser.parse_args(argv)
    if args.threshold < 1:
        print("surprises: --threshold must be a positive integer",
              file=sys.stderr)
        return 2
    root = Path(args.root)
    entries = load_ledger(root)

    problems = []
    for i, entry in enumerate(entries, 1):
        for field in ("expectation", "reality"):
            if not str(entry.get(field) or "").strip():
                problems.append(
                    f"{LEDGER}:{i}: one-sided surprise (empty '{field}') "
                    f"under sig '{entry['sig']}' — a surprise without both "
                    f"sides cannot be recognized next time")

    corpus = ""
    for pattern in NOTES_GLOBS:
        for note_path in root.glob(pattern):
            try:
                corpus += note_path.read_text(encoding="utf-8")
            except OSError as e:
                print(f"surprises: cannot read note {note_path}: {e}",
                      file=sys.stderr)
                raise SystemExit(2)

    counts: dict[str, int] = {}
    for entry in entries:
        sig = entry["sig"]
        counts[sig] = counts.get(sig, 0) + 1
    for sig, count in sorted(counts.items()):
        if count >= args.threshold and f"surprise:{sig}" not in corpus:
            problems.append(
                f"sig '{sig}' has {count} recorded surprises and no "
                f"linked process improvement — a recurring surprise is a "
                f"process defect, not bad luck; write a process note "
                f"citing surprise:{sig} (gov note new --class process)")

    if problems:
        for p in problems:
            print(f"surprises: {p}", file=sys.stderr)
        print(f"surprises: {len(problems)} violation(s) across "
              f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}",
              file=sys.stderr)
        return 1
    escalated = sum(1 for c in counts.values() if c >= args.threshold)
    print(f"surprises: {len(entries)} entr"
          f"{'y' if len(entries) == 1 else 'ies'}, {len(counts)} "
          f"signature(s), {escalated} escalated with linked improvement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
