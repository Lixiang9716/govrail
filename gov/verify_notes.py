#!/usr/bin/env python3
"""Verify Agent Note format and placement.

An implemented note must carry the three required sections from D4 —
``## Problem``, ``## Decision``, ``## Alternatives considered`` — **in that
order** (the notes README's contract, now enforced). ``## Consequences``
is allowed but not required.

Placement is part of the format (D5's two-state lifecycle, closed class
set): a note lives at ``implemented/<class>/<file>.md`` where ``class`` is
one of feature, bug-fix, simplification, architecture, process, testing.
Anything else under ``implemented/`` is a violation, and an unknown
lifecycle directory under ``.agents/notes/`` (e.g. ``drafts/``) fails loud
(rule 5) instead of being silently ignored — verify-notes and recall must
agree on what a note is.

Archived notes are frozen (D5) and are not re-checked here.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    from root import anchor_to_git_root

NOTES_DIR = Path(".agents/notes")
NOTES_README = "README.md"
LIFECYCLES = ("implemented", "archived")
CLASSES = ("feature", "bug-fix", "simplification", "architecture", "process", "testing")
REQUIRED_SECTIONS = ("## Problem", "## Decision", "## Alternatives considered")


def check_note(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        errors.append("missing title heading (first line must start with '# ')")
        return errors
    header = lines[:6]
    status = ""
    for line in header:
        if line.startswith("Status:"):
            status = line[len("Status:"):].strip()
            break
    if status != "implemented":
        # The lifecycle is the directory (implemented/ vs archived/), never
        # this field — so the field has a closed set of exactly one value.
        errors.append(
            f"Status must be exactly 'implemented' (the lifecycle is the "
            f"directory; got {status!r})"
        )
    stripped = [line.strip() for line in lines]
    positions = []
    for section in REQUIRED_SECTIONS:
        try:
            positions.append(stripped.index(section))
        except ValueError:
            errors.append(f"missing required section '{section}'")
    if len(positions) == len(REQUIRED_SECTIONS) and positions != sorted(positions):
        errors.append(
            "required sections out of order — Problem, then Decision, "
            "then Alternatives considered"
        )
    return errors


def _check_placement(root: Path) -> tuple[list[str], list[Path]]:
    """Lifecycle dirs and class dirs must be the declared closed sets.

    Also returns the loose notes found sitting directly at the notes root:
    a file there used to be invisible to BOTH the placement check (which
    only flagged unknown directories) and the format scan (which only
    walked ``implemented/``) — a zero-cost bypass of the whole gate.
    """
    errors: list[str] = []
    loose: list[Path] = []
    for entry in sorted(root.iterdir()) if root.is_dir() else []:
        if entry.name == NOTES_README:
            continue
        if entry.is_dir():
            if entry.name not in LIFECYCLES:
                errors.append(
                    f"{entry}: unknown lifecycle '{entry.name}' "
                    f"(known: {', '.join(LIFECYCLES)}) — this is not a note, "
                    "move it or remove the directory"
                )
        elif entry.suffix == ".md":
            loose.append(entry)
            errors.append(
                f"{entry}: notes live at implemented/<class>/<file>.md, "
                f"not loose at the notes root (classes: {', '.join(CLASSES)})"
            )
    implemented = root / "implemented"
    for p in sorted(implemented.rglob("*.md")) if implemented.is_dir() else []:
        rel = p.relative_to(implemented)
        if len(rel.parts) != 2:
            errors.append(
                f"{p}: notes live at implemented/<class>/<file>.md "
                f"(classes: {', '.join(CLASSES)})"
            )
        elif rel.parts[0] not in CLASSES:
            errors.append(
                f"{p}: unknown class '{rel.parts[0]}' "
                f"(closed set: {', '.join(CLASSES)})"
            )
    return errors, loose


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("verify_notes")
    notes_root = NOTES_DIR / "implemented"
    notes = sorted(notes_root.rglob("*.md")) if notes_root.exists() else []
    try:
        errors, loose = _check_placement(NOTES_DIR)
        # Loose root notes get the format check too — placement is wrong,
        # but the content is still a note and still has to answer for it.
        for note in notes + loose:
            for err in check_note(note):
                errors.append(f"{note}: {err}")
    except (OSError, UnicodeDecodeError) as e:
        # A note that cannot be read is a broken prerequisite (exit 2):
        # a traceback (exit 1-shaped crash) is indistinguishable from a
        # violation report, and silently skipping it would pass garbage.
        print(f"verify_notes: cannot read a note file: {e}", file=sys.stderr)
        return 2
    if errors:
        for err in errors:
            print(err)
        print(f"verify_notes: {len(errors)} violation(s) in {len(notes)} note(s)")
        return 1
    print(f"verify_notes: {len(notes)} note(s) ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
