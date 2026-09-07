#!/usr/bin/env python3
"""Verify the decisions table — the governance spine gets a guard (D28).

``docs/decisions.md`` is every adopter's spine (govrail's own D0–D27), yet
it was pure prose: D numbering uniqueness/contiguity, the presence of a
rejected-alternatives section, and orphan decisions were all unchecked.
This gate is the verify-rubric pattern applied to decisions:

- D numbers are unique and contiguous from the table's first entry
  (``D0`` or ``D1`` starts are both legal);
- every D records its options or rejected alternatives (a decision without
  what it beat is the notes rule-3 violation wearing a different hat);
- orphan decisions — defined but never D-referenced by any note — are
  reported as information, not violations (a decision may simply predate
  the notes that would cite it);
- ``--base REF`` (#107/D40) adds the parallel-branch check: numbers this
  branch added that a sibling ALSO added on REF since the fork point are
  a named collision (a duplicate in the merged history — refuse before
  the merge, with the fix in the message); a numbering gap that merely
  pre-partitions numbers still landing on sibling branches stays
  informational.

Exit codes: 0 = table intact (orphans allowed); 1 = violations; 2 =
unreadable table or bad ``--path``/``--base``.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

try:  # package context (`gov ...`)
    from . import decisions as dec
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    import decisions as dec
    from root import anchor_to_git_root

DEFAULT_PATH = Path("docs/decisions.md")
NOTES = Path(".agents/notes")
D_SECTION_RX = re.compile(r"(?m)^## (D\d+) — .*$")
# A decision must record what it beat — zh tables say 选项/被否, en tables
# say alternatives.
ALT_RX = re.compile(r"被否|选项|[Aa]lternatives")
D_REF_RX = re.compile(r"\bD(\d+)\b")
EXTERNAL_D_RX = re.compile(r"govrail:D\d+")  # D34: the tool's own table


def _sections(text: str) -> list[tuple[str, str]]:
    parts = D_SECTION_RX.split(text)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def _note_refs() -> set[str]:
    refs: set[str] = set()
    if not NOTES.is_dir():
        return refs
    for lifecycle in ("implemented", "archived"):
        root = NOTES / lifecycle
        if not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            text = EXTERNAL_D_RX.sub("", p.read_text(encoding="utf-8"))
            refs.update(f"D{d}" for d in D_REF_RX.findall(text))
    return refs


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("verify_decisions")
    parser = argparse.ArgumentParser(
        prog="gov verify-decisions",
        description="Verify the decisions table: numbering, alternatives, orphans.",
    )
    parser.add_argument("--path", default=str(DEFAULT_PATH),
                        help=f"decisions table (default: {DEFAULT_PATH})")
    parser.add_argument("--base", metavar="REF", default=None,
                        help="also check parallel-branch number collisions: "
                             "numbers added both here and on REF since the "
                             "merge-base are named and refused (#107)")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable: stdout is exactly one JSON "
                             "object {source, decisions, violations, orphans, "
                             "overdue, status}; the human report moves to stderr")
    args = parser.parse_args(argv)

    def emit(text: str) -> None:
        # #119/D26: in json mode stdout carries exactly one JSON value;
        # the human report (and violation prose) moves to stderr.
        print(text, file=sys.stderr if args.json else sys.stdout)

    def report(payload: dict, rc: int) -> int:
        if args.json:
            print(json.dumps(payload, indent=2))
        return rc

    src = dec.load()
    if src is None:
        refs = _note_refs()
        if refs:
            shown = ", ".join(sorted(refs)[:5]) + ("…" if len(refs) > 5 else "")
            emit(f"verify_decisions: REFUSED — notes reference {shown} "
                 "but no decisions source exists (docs/decisions.md missing; "
                 "configure .gov/decisions.json with "
                 '{"path": ..., "format": "sections"|"table"} '
                 "if the table lives elsewhere)")
            return report({"source": None, "decisions": 0,
                           "violations": ["no decisions source while notes "
                                          "carry D-refs"],
                           "orphans": [], "overdue": [],
                           "status": "refused"}, 1)
        emit("verify_decisions: no decisions table and no D-refs — nothing to verify")
        return report({"source": None, "decisions": 0, "violations": [],
                       "orphans": [], "overdue": [], "status": "ok"}, 0)
    path = src.path
    text = src.text
    sections = dec.Source.entries(src)  # (id, title, body)
    if not sections:
        print(f"verify_decisions: {path} has no decision entries; check its "
              "format (sections: '## Dn — ' headings; table: '| Dn | ...' rows; "
              "or fix .gov/decisions.json)", file=sys.stderr)
        return 2

    violations: list[str] = []
    ids = [d for d, _, _ in sections]
    seen: set[str] = set()
    for d in ids:
        if d in seen:
            violations.append(f"{d}: duplicate decision entry")
        seen.add(d)
    numbers = sorted(int(d[1:]) for d in set(ids))
    expected = list(range(numbers[0], numbers[0] + len(numbers)))
    if numbers != expected:
        gaps = [f"D{n}" for n in expected if n not in numbers]
        violations.append(
            f"numbering must be contiguous from D{numbers[0]} (missing: {', '.join(gaps)})"
        )
    header_alt = src.header_has_alternatives() and src.fmt == "table"
    for d, _, body in sections:
        if header_alt:
            break  # a table-level alternatives column covers every row
        if not ALT_RX.search(body):
            violations.append(
                f"{d}: records no options or rejected alternatives (被否/选项) — "
                "a decision without what it beat invites re-litigation"
            )

    orphans = sorted(set(ids) - _note_refs(), key=lambda d: int(d[1:]))

    # Wish 3/D30: decisions may declare a half-life ("review-by: 2026-09-01")
    # — a passed date is a prompt to re-read, reported like orphans.
    overdue: list[str] = []
    for d, _, body in sections:
        m = re.search(r"(?m)^-\s*\*\*review-by\*\*:?\s*(\S+)", body)
        if not m:
            continue
        try:
            due = date.fromisoformat(m.group(1))
        except ValueError:
            violations.append(f"{d}: unparseable review-by date {m.group(1)!r}")
            continue
        if due < date.today():
            overdue.append(f"{d} (review-by {m.group(1)})")

    # #107/D40: parallel-branch numbering — loud, named collision before
    # the merge; pre-partitioned gaps (numbers landing on siblings) stay
    # informational like orphans.
    if args.base:
        fork = subprocess.run(
            ["git", "merge-base", "HEAD", args.base],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if fork.returncode != 0:
            print(f"verify_decisions: cannot resolve --base '{args.base}' "
                  f"or merge-base with it — {(fork.stderr or '').strip()}",
                  file=sys.stderr)
            return 2
        try:
            base_nums = dec.numbers_in_rev(args.base)
            fork_nums = dec.numbers_in_rev(fork.stdout.strip())
        except subprocess.CalledProcessError as e:
            print(f"verify_decisions: cannot read the decisions source at "
                  f"'{args.base}' or its merge-base — "
                  f"{(e.stderr or '').strip()}", file=sys.stderr)
            return 2
        local_nums = set(numbers)
        branch_new = local_nums - fork_nums
        base_new = base_nums - fork_nums
        for n in sorted(branch_new & base_new):
            violations.append(
                f"D{n}: number collision — added both here and on "
                f"'{args.base}' since the fork point; merged history would "
                f"carry it twice. Renumber this branch to "
                f"D{max(local_nums | base_nums) + 1} "
                f"(gov decision next --base {args.base})"
            )
        if branch_new:
            floor = max(fork_nums) + 1 if fork_nums else min(branch_new)
            top = max(branch_new)
            # Numbers neither side has: a gap in the eventual merged
            # history unless a third sibling lands them — report, don't
            # block (pre-partitioning across branches is a legal workflow).
            missing = [f"D{n}" for n in range(floor, top)
                       if n not in local_nums and n not in base_nums]
            if missing:
                emit(f"note: branch numbering not contiguous with "
                     f"'{args.base}' (allocated elsewhere?): "
                     f"{', '.join(missing)}")

    for v in violations:
        emit(v)
    if orphans:
        emit(f"note: referenced by no note: {', '.join(orphans)} (informational)")
    if overdue:
        emit(f"note: review due — context may have drifted: {', '.join(overdue)}")
    status = "violations" if violations else "ok"
    if violations:
        emit(f"verify_decisions: {len(violations)} violation(s) in {len(sections)} decision(s)")
        return report({"source": str(path), "decisions": len(sections),
                       "violations": violations, "orphans": orphans,
                       "overdue": overdue, "status": status}, 1)
    emit(f"verify_decisions: {len(sections)} decision(s) ok"
         + (f", {len(orphans)} orphan(s)" if orphans else "")
         + (f", {len(overdue)} review-due" if overdue else ""))
    return report({"source": str(path), "decisions": len(sections),
                   "violations": [], "orphans": orphans,
                   "overdue": overdue, "status": status}, 0)


if __name__ == "__main__":
    raise SystemExit(main())
