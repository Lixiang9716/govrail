#!/usr/bin/env python3
"""Postmortem structure gate: the practice's contract, enforced.

docs/postmortem/README.md defines the practice — four sections, and
"Guardrails added" that links the gates/tests/rules the failure
motivated. Until this gate existed that contract was prose only, and
the corpus sat empty for its first three months (the first postmortem
was written late, against already-landed guardrails). This gate makes
the README's structure machine-checked, so the practice cannot decay
back to story-telling:

- every entry (README pair excluded) carries all four sections — in one
  consistent vocabulary (English or Chinese headings, never mixed);
- every section is non-empty;
- "Guardrails added" names at least one pointer (a repo-relative path,
  a PR, or a D-reference) — a guardrail section with zero pointers is
  the story the README forbids — and every path pointer must resolve
  to an existing file.

Pairing (en+zh sides) is the pairing gate's job; numbering and narrative
quality stay human judgment. Exit codes follow D2: 0 intact, 1 named
violations, 2 usage error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

POSTMORTEM_DIR = Path("docs/postmortem")

VOCABULARIES: dict[str, tuple[str, str, str, str]] = {
    "en": ("Executive summary", "Timeline", "Root cause", "Guardrails added"),
    "zh": ("执行摘要", "时间线", "根因", "补上的护栏"),
}

SECTION_HEADING = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
BACKTICK_SPAN = re.compile(r"`([^`]+)`")
MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
PATH_LIKE = re.compile(r"[\\/]")
PR_REF = re.compile(r"#\d+\b")
D_REF = re.compile(r"\bD\d+\b")


def parse_sections(text: str) -> list[tuple[str, str]]:
    """(heading, body) pairs for each ## section, in file order."""
    headings = list(SECTION_HEADING.finditer(text))
    sections = []
    for i, m in enumerate(headings):
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        sections.append((m.group(1), text[start:end]))
    return sections


def check_entry(path: Path, root: Path) -> list[str]:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8")
    sections = parse_sections(text)
    names = [name for name, _ in sections]

    vocab = None
    if path.name.endswith(".zh.md"):
        vocab = "zh"
    elif path.name.endswith(".md"):
        vocab = "en"
    if vocab is None:
        return [f"{rel}: not a .md/.zh.md entry — name it per the README pair"]

    required = VOCABULARIES[vocab]
    missing = [s for s in required if s not in names]
    if missing:
        return [f"{rel}: missing section(s) {', '.join(missing)}"]
    foreign = VOCABULARIES["zh" if vocab == "en" else "en"]
    mixed = [s for s in foreign if s in names]
    if mixed:
        return [f"{rel}: mixed heading vocabularies ({', '.join(mixed)}); "
                f"write one language per file"]

    problems = []
    for wanted in required:
        body = next(body for name, body in sections if name == wanted)
        if not any(line.strip() for line in body.splitlines()):
            problems.append(f"{rel}: section '{wanted}' is empty")

    guard_body = next(body for name, body in sections
                      if name == required[3])
    pointers = (PR_REF.findall(guard_body) + D_REF.findall(guard_body)
                + MD_LINK.findall(guard_body))
    for span in BACKTICK_SPAN.findall(guard_body):
        if PATH_LIKE.search(span):
            pointers.append(span)
            if not (root / span).exists():
                problems.append(f"{rel}: guardrail pointer `{span}` "
                                f"resolves to no file")
    for target in MD_LINK.findall(guard_body):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if not (root / target).exists():
            problems.append(f"{rel}: guardrail link ({target}) "
                            f"resolves to no file")
    if not pointers:
        problems.append(f"{rel}: 'Guardrails added' names no pointer — "
                        f"a postmortem without a linked guardrail is a "
                        f"story (postmortem README)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_postmortems")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root to judge (default: this checkout)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    directory = root / POSTMORTEM_DIR
    if not directory.is_dir():
        print(f"postmortems: {POSTMORTEM_DIR} does not exist — nothing to "
              f"judge (the practice is defined by its README)", file=sys.stderr)
        return 0

    entries = sorted(p for p in directory.glob("*.md")
                     if not p.name.startswith("README"))
    problems = []
    for entry in entries:
        problems.extend(check_entry(entry, root))

    if problems:
        for p in problems:
            print(f"postmortems: {p}", file=sys.stderr)
        print(f"postmortems: {len(problems)} violation(s) across "
              f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}",
              file=sys.stderr)
        return 1
    print(f"postmortems: {len(entries)} entr"
          f"{'y' if len(entries) == 1 else 'ies'} intact — sections present, "
          f"guardrails pointed and resolvable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
