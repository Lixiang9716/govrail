#!/usr/bin/env python3
"""Doc budgets: standing prose stays within declared ceilings.

Every standing document in this repo is read by a human or an agent on
a cadence — the README on adoption, the constitution before every
change, the router skill at every session start. Prose grows one
"while we're here" paragraph at a time until the reading cost is paid
forever; no gate noticed (the DSH comparison found the same gap here
that doc-budgets closed there). This gate reads declared per-file
character ceilings from ``scripts/doc-budgets.json`` and names every
over-budget doc.

Characters, not words: this repo's docs are bilingual pairs and a
Chinese "word" is not a space-separated token — a character count is
the language-neutral, monotonic measure both sides can share. And the
measure judges curated prose: a document's generated regions (the
README's gov:commands block) are stripped before counting — they are
derived truth, they grow with the product's command count, and they
have their own pinning test; charging them to the doc's ceiling would
make every new command a docs violation. Ledgers are deliberately
absent: ``docs/decisions.md`` and ``CHANGELOG.md`` grow forever by
design (append-only logs), so they get no ceiling.

Raising a ceiling is a diff a reviewer sees — the budgets were set at
roughly +25% over the counts on adoption day, and the culture is that
they ratchet down. A declared doc that vanishes is a stale row: red
(rule 5). A file outside the config is unjudged; adding a standing doc
means editing the config, which is the point. Exit codes follow D2:
0 ok, 1 over-budget or stale rows, 2 config/usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / "doc-budgets.json"

# Generated regions are stripped before measuring: a budget judges the
# curated prose a human owns. The README's command block is derived
# truth (it grows with the product's command count and has its own
# pinning test); charging it to the README's ceiling would make every
# new command a docs violation.
GENERATED_REGION = re.compile(
    r"<!-- gov:commands BEGIN.*?<!-- gov:commands END -->", re.DOTALL)


def load_config(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"doc-budgets: unreadable config {path}: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(raw, dict) or not isinstance(raw.get("limits"), dict):
        print(f"doc-budgets: {path} must be an object with a 'limits' "
              f"object", file=sys.stderr)
        raise SystemExit(2)
    unknown = set(raw) - {"limits"}
    if unknown:
        # rule 5: a misspelled key would silently stop meaning anything.
        print(f"doc-budgets: {path}: unknown key(s) "
              f"{', '.join(sorted(unknown))}", file=sys.stderr)
        raise SystemExit(2)
    limits = raw["limits"]
    if not limits or not all(
            isinstance(k, str) and isinstance(v, int) and v > 0
            for k, v in limits.items()):
        print(f"doc-budgets: {path}: 'limits' must map doc paths to "
              f"positive integer character ceilings", file=sys.stderr)
        raise SystemExit(2)
    return limits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_doc_budgets")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root to judge (default: this checkout)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    root = Path(args.root)
    limits = load_config(Path(args.config))

    problems = []
    judged = 0
    for rel, budget in sorted(limits.items()):
        doc = root / rel
        if not doc.is_file():
            problems.append(f"{rel}: declared in the budget config but "
                            f"missing — remove the row or restore the doc")
            continue
        judged += 1
        text = doc.read_text(encoding="utf-8")
        size = len(GENERATED_REGION.sub("", text))
        if size > budget:
            problems.append(
                f"{rel}: {size} characters (budget {budget}) — tighten "
                f"the prose, or raise this ceiling in "
                f"scripts/doc-budgets.json as a reviewed diff")

    if problems:
        for p in problems:
            print(f"doc-budgets: {p}", file=sys.stderr)
        print(f"doc-budgets: {len(problems)} violation(s) across "
              f"{judged} judged doc(s)", file=sys.stderr)
        return 1
    print(f"doc-budgets: {judged} doc(s) within their declared ceilings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
