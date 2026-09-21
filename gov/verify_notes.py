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
    from .note import PLACEHOLDERS
except ImportError:  # direct script execution (self-test runs files by path)
    from root import anchor_to_git_root
    from note import PLACEHOLDERS

NOTES_DIR = Path(".agents/notes")
NOTES_README = "README.md"
LIFECYCLES = ("implemented", "archived")
CLASSES = ("feature", "bug-fix", "simplification", "architecture", "process", "testing")
REQUIRED_SECTIONS = ("## Problem", "## Decision", "## Alternatives considered")
# #310: below this word count a section states a verdict, not a reason —
# exactly the "template note passes the gate" laundering the issue names.
# Advisory only: the format gate judges structure; thinness is a signal
# for the human (and the note audit), never a new way to go red.
THIN_SECTION_WORDS = 12


def _thin_section_advisories(path: Path) -> list[str]:
    """Advisory signals for notes that are structurally valid but
    information-free (#310): any required section under the word floor."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    stripped = [line.strip() for line in lines]
    positions = []
    for section in REQUIRED_SECTIONS:
        try:
            positions.append(stripped.index(section))
        except ValueError:
            return []  # placement/format errors already report this
    out: list[str] = []
    bounds = sorted(positions) + [len(lines)]
    for section, start, end in zip(REQUIRED_SECTIONS, bounds, bounds[1:]):
        body = "\n".join(lines[start + 1:end]).strip()
        if len(body.split()) < THIN_SECTION_WORDS:
            out.append(f"{path}: '{section}' is thin "
                       f"({len(body.split())} words) — a note this short "
                       "records a verdict, not a reason; recall can only "
                       "retrieve what was written")
    return out


def superseded_by(path: Path) -> str:
    """The note this one names as its replacement ('' when none).

    #364: the optional forward pointer. `gov recall` marks such notes
    and ranks them below current ones; `verify_notes` prints the pair.
    """
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()[:8]
    except (OSError, UnicodeDecodeError):
        return ""
    for line in lines:
        if line.startswith("Superseded by:"):
            return line[len("Superseded by:"):].strip()
    return ""


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
    # #364: `Superseded by: <note>` is OPTIONAL and additive — rule 4
    # requires the NEW note to link back, and nothing made the old note
    # point forward, so a reader (or gov recall) could act on retired
    # guidance with no signal. An EMPTY marker is worse than none: it
    # reads as "someone started the ritual and stopped".
    for line in header:
        if line.startswith("Superseded by:"):
            if not line[len("Superseded by:"):].strip():
                errors.append(
                    "'Superseded by:' is present but names nothing — write "
                    "the note that replaces this one, or drop the line")
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
    elif len(positions) == len(REQUIRED_SECTIONS):
        # D3, hollow notes: a section that is empty or still carries the
        # `gov note new` placeholder satisfies the format and proves
        # nothing. The scaffold's own output used to pass this gate AS
        # WRITTEN, making the empty shell the path of least resistance.
        bounds = sorted(positions) + [len(lines)]
        for section, start, end in zip(REQUIRED_SECTIONS, bounds, bounds[1:]):
            body = "\n".join(lines[start + 1:end]).strip()
            if not body:
                errors.append(
                    f"'{section}' section is empty — a note must state "
                    "its content, not just carry the heading")
            elif body == PLACEHOLDERS[section]:
                errors.append(
                    f"'{section}' section still carries the `gov note new` "
                    "placeholder — fill it in or delete the note")
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
        elif entry.suffix.lower() == ".md":
            # Case-insensitive: BYPASS.MD is a note too (a macOS/exFAT
            # checkout or a sloppy hand-edit must not buy a format-check
            # exemption from the extension's case).
            loose.append(entry)
            errors.append(
                f"{entry}: notes live at implemented/<class>/<file>.md, "
                f"not loose at the notes root (classes: {', '.join(CLASSES)})"
            )
    implemented = root / "implemented"
    for p in sorted(implemented.rglob("*")) if implemented.is_dir() else []:
        if not p.is_file() or p.suffix.lower() != ".md":
            # Only notes are judged here; but a note is a note whatever
            # case its extension wears — .MD gets the same checks.
            continue
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
    argv = list(sys.argv[1:]) if argv is None else argv
    if argv:
        # This command is flagless. It used to ignore argv entirely and
        # answer a mistyped invocation with a GREEN verdict — 31 of 32
        # commands refuse unknown flags with exit 2; this was the one
        # that did not (found by the exit-code contract's probe).
        print(f"verify_notes: unexpected argument '{argv[0]}' — this "
              "command takes no flags", file=sys.stderr)
        return 2
    notes_root = NOTES_DIR / "implemented"
    notes = ([p for p in sorted(notes_root.rglob("*"))
              if p.is_file() and p.suffix.lower() == ".md"]
             if notes_root.exists() else [])
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
    # #310: structurally valid but information-free notes pass this gate
    # — the format check cannot judge substance. Named as advisories so
    # the boilerplate shortcut stays visible without a new red state.
    advisories: list[str] = []
    for note in notes:
        advisories.extend(_thin_section_advisories(note))
    # #364 informational half: a superseded note is still valid here (the
    # lifecycle is the directory); naming the pointer keeps the pair
    # visible in the gate that reads every note anyway.
    for note in notes + loose:
        target = superseded_by(note)
        if target:
            print(f"note: {note} is superseded by {target}")
    for line in advisories:
        print(f"advisory: {line}")
    verdict = f"verify_notes: {len(notes)} note(s) ok"
    if advisories:
        verdict += f" ({len(advisories)} advisory)"
    print(verdict)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
