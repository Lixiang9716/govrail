#!/usr/bin/env python3
"""Verify the review rubric's structure (the meta-gate, D17).

The rubric carries the judgment criteria gates cannot check. This gate never
judges judgment: it checks the rubric *file* keeps the shape that makes it
gradeable —

- items are ``### Rn — title`` headings, numbered contiguously from R1 and
  unique;
- every item carries the four required fields — ``Checks``, ``Evidence``,
  ``Anti-pattern``, ``Gate candidate`` — each with content;
- a ``Gate candidate: yes`` names where the item graduates to;
- when a ``.zh.md`` sibling exists, it carries the same set of item ids
  (the ids are the contract across languages; the prose is the translator's).

Exit codes: 0 = structure ok; 1 = violations; 2 = unreadable rubric.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_PATH = Path("docs/review-rubric.md")
SECTION_RX = re.compile(r"^### (R\d+)\b.*$", re.MULTILINE)
REQUIRED_FIELDS = ("Checks", "Evidence", "Anti-pattern", "Gate candidate")


def _ids(text: str) -> list[str]:
    return SECTION_RX.findall(text)


def _sections(text: str) -> list[tuple[str, str]]:
    """(id, body) per heading, in file order."""
    parts = SECTION_RX.split(text)
    # split() yields [pre, id1, body1, id2, body2, ...]
    out: list[tuple[str, str]] = []
    for i in range(1, len(parts) - 1, 2):
        out.append((parts[i], parts[i + 1]))
    return out


def _check_side(name: str, text: str, full: bool) -> list[str]:
    errors: list[str] = []
    ids = _ids(text)
    if not ids:
        errors.append(
            f"{name}: the rubric has no items — a rubric with nothing to "
            "check is a vacuous pass (rule 6)"
        )
        return errors
    expected = [f"R{i}" for i in range(1, len(ids) + 1)]
    if ids != expected:
        errors.append(
            f"{name}: item ids must be unique and contiguous from R1 "
            f"(found: {', '.join(ids) or 'none'})"
        )
    if not full:
        return errors  # the translated side is checked for id parity only
    for item_id, body in _sections(text):
        for field in REQUIRED_FIELDS:
            if not re.search(rf"\*\*{field}:\*\*\s*\S", body):
                errors.append(f"{name}: item {item_id} is missing field '{field}'")
        m = re.search(r"\*\*Gate candidate:\*\*\s*yes\b\s*(.*)", body)
        if m and not m.group(1).strip("—- \t"):
            errors.append(
                f"{name}: item {item_id} says 'Gate candidate: yes' without "
                "naming where it graduates to"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    try:
        from .root import force_utf8_stdio
    except ImportError:  # direct-script execution (self-test scratch dirs)
        from root import force_utf8_stdio
    force_utf8_stdio()  # reports leave as UTF-8 on every OS (#168)
    parser = argparse.ArgumentParser(
        prog="gov verify-rubric",
        description="Check the review rubric's structure (ids, fields, parity).",
    )
    parser.add_argument("--path", default=str(DEFAULT_PATH),
                        help=f"rubric file (default: {DEFAULT_PATH})")
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"verify_rubric: cannot read rubric {path}: {e}", file=sys.stderr)
        return 2

    errors = _check_side(str(path), text, full=True)
    zh = path.with_name(path.stem + ".zh.md") if not path.name.endswith(".zh.md") else None
    if zh is not None and zh.exists():
        try:
            zh_text = zh.read_text(encoding="utf-8")
        except OSError as e:
            print(f"verify_rubric: cannot read {zh}: {e}", file=sys.stderr)
            return 2
        en_ids, zh_ids = _ids(text), _ids(zh_text)
        if en_ids != zh_ids:
            missing = [i for i in en_ids if i not in zh_ids]
            extra = [i for i in zh_ids if i not in en_ids]
            detail = ", ".join(
                [f"missing on zh side: {', '.join(missing)}" if missing else ""]
                + [f"extra on zh side: {', '.join(extra)}" if extra else ""]
            ).strip(", ")
            errors.append(f"{zh}: item ids diverge from {path} ({detail})")

    if errors:
        for e in errors:
            print(e)
        print(f"verify_rubric: {len(errors)} violation(s)")
        return 1
    pairs = " + zh" if zh is not None and zh.exists() else ""
    print(f"verify_rubric: {len(_ids(text))} item(s) ok{pairs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
