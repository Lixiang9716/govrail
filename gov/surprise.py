#!/usr/bin/env python3
"""The surprise ledger — expectation-vs-reality, recorded and counted.

A surprise is the moment reality differs from what you expected: a gate
failed for a reason you didn't predict, a file wasn't where you thought,
a register said something the tree contradicts. Surprises are not bug
reports — they are telemetry about where the mental model and the
process disagree. This command is the write and read side of that
telemetry (rule 11):

- ``gov surprise record "<expectation>" --reality "<what happened>"``
  appends one entry to the tracked, append-only ledger
  ``.gov/surprises.jsonl`` (a ``sig`` slug groups recurrences of the
  same kind; one is derived from the expectation when omitted) and, at
  the moment of recording, shows similar earlier surprises — the
  "have I seen this before?" lookup happens when it is cheapest, before
  the human picks the signature.
- ``gov surprise list [--sig SLUG] [--json]`` counts surprises per
  signature, newest last.

Enforcement lives in the ``surprises`` gate (scripts/check_surprises.py):
when one signature reaches three recorded surprises, the gate stays red
until a process note citing ``surprise:<sig>`` ships — a recurring
surprise is a process defect, not bad luck. Recording never blocks on
that: data first, verdict in the gate (facts vs. verdicts, #265's
shape). Exit codes follow D2: 0 ok, 2 usage/config error — a surprise
ledger has no failure verdict, so it is 0/2-only in the contract
(tests/test_exit_code_contract.py).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path(".gov/surprises.jsonl")
ESCALATION_AT = 3


def _load(root: Path) -> list[dict]:
    path = root / LEDGER
    if not path.exists():
        return []
    entries = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        print(f"surprise: cannot read ledger {path}: {e}", file=sys.stderr)
        raise SystemExit(2)
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            # rule 5: a corrupt line would silently shrink the counts
            # that the escalation threshold depends on.
            print(f"surprise: {path}:{i}: corrupt entry ({e}) — fix or "
                  f"revert the ledger; counts drive the escalation gate",
                  file=sys.stderr)
            raise SystemExit(2)
        if not isinstance(entry, dict) or not isinstance(entry.get("sig"), str):
            print(f"surprise: {path}:{i}: entry is not an object with a "
                  f"'sig' field", file=sys.stderr)
            raise SystemExit(2)
        entries.append(entry)
    return entries


def _slugify(text: str) -> str:
    words = [w for w in re.sub(r"[^a-z0-9\s-]", "", text.lower()).split()
             if len(w) > 2]
    return "-".join(words[:4]) or "unfiled"


def _terms(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}


def _counts(entries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["sig"]] = counts.get(entry["sig"], 0) + 1
    return counts


def _cmd_record(args: argparse.Namespace) -> int:
    root = Path.cwd()
    entries = _load(root)
    expectation, reality = args.expectation.strip(), (args.reality or "").strip()
    if not expectation or not reality:
        print("surprise: both the expectation and the reality are "
              "required — a one-sided surprise cannot be recognized "
              "later", file=sys.stderr)
        return 2
    sig = (args.sig or _slugify(expectation)).strip()
    surface = (args.surface or "").strip() or None
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sig": sig,
        "expectation": expectation,
        "reality": reality,
        "surface": surface,
    }
    path = root / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    counts = _counts(entries + [entry])
    print(f"surprise: recorded under sig '{sig}' "
          f"({counts[sig]} entr{'y' if counts[sig] == 1 else 'ies'} so far)")
    others = [e for e in entries
              if e["sig"] != sig
              and _terms(expectation + " " + reality) & _terms(
                  e["expectation"] + " " + e["reality"])]
    if others:
        print("surprise: similar earlier surprise(s) — same kind? "
              "reuse its sig next time:")
        for e in others[-3:]:
            print(f"  [{e['sig']}] {e['expectation'][:72]}")
    if counts[sig] >= ESCALATION_AT:
        print(f"surprise: ESCALATION OWED — sig '{sig}' now has "
              f"{counts[sig]} surprises; a recurring surprise is a "
              f"process defect, not bad luck. The surprises gate stays "
              f"red until a process note citing surprise:{sig} ships "
              f"(gov note new --class process).", file=sys.stderr)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    entries = _load(Path.cwd())
    if args.sig:
        entries = [e for e in entries if e["sig"] == args.sig]
    if args.json:
        print(json.dumps(
            [{"sig": e["sig"], "ts": e["ts"],
              "expectation": e["expectation"], "reality": e["reality"],
              "surface": e.get("surface")} for e in entries],
            ensure_ascii=False, indent=2))
        return 0
    if not entries:
        print("surprise: no surprises recorded — either the process is "
              "aligned with reality, or surprises are evaporating "
              "unrecorded")
        return 0
    counts = _counts(entries)
    for sig in sorted(counts, key=lambda s: (-counts[s], s)):
        latest = max((e for e in entries if e["sig"] == sig),
                     key=lambda e: e["ts"])
        owed = " — ESCALATION OWED" if counts[sig] >= ESCALATION_AT else ""
        print(f"{counts[sig]:2d}  {sig}{owed}")
        print(f"    latest: {latest['expectation'][:72]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov surprise",
        description="The surprise ledger: expectation-vs-reality, "
                    "recorded and counted (rule 11)")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    p_record = sub.add_parser(
        "record", help="append one surprise to .gov/surprises.jsonl")
    p_record.add_argument("expectation", help="what you expected")
    p_record.add_argument("--reality", required=True,
                          help="what actually happened")
    p_record.add_argument("--sig",
                          help="signature grouping recurrences of the "
                               "same kind (derived from the expectation "
                               "when omitted)")
    p_record.add_argument("--surface",
                          help="where it happened: a path, gate id, or "
                               "command")
    p_list = sub.add_parser(
        "list", help="count surprises per signature")
    p_list.add_argument("--sig", help="only this signature")
    p_list.add_argument("--json", action="store_true",
                        help="exactly one machine-readable JSON value")
    args = parser.parse_args(argv)
    return _cmd_record(args) if args.subcommand == "record" else _cmd_list(args)


if __name__ == "__main__":
    raise SystemExit(main())
