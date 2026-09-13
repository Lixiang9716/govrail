#!/usr/bin/env python3
"""The decisions source: one loader, three consumers (#17/D32).

The decisions plane hardcoded ``docs/decisions.md`` — a project keeping
its table inside DESIGN.md got a vacuous green ("no decisions table")
while its notes referenced D1–D26. One loader now serves
verify-decisions, audit-notes, and recall:

- default source: ``docs/decisions.md`` (``sections`` format —
  ``## Dn — title`` headings, as govrail itself uses);
- configurable: ``.gov/decisions.json`` ``{"path": "DESIGN.md",
  "format": "table"}`` — ``table`` parses markdown-table rows whose
  first cell is ``Dn``; an alternatives column in the header satisfies
  the alternatives check for every row;
- ``dir`` format (#107/D40): one file per decision under e.g.
  ``.gov/decisions/`` (``D39-title.md``) — parallel branches each add a
  NEW file, so appends cannot textually conflict at merge time the way
  single-file appends do; numbering lives in the filenames;
- no source at all: the loader says so, and the consumers refuse the
  vacuous pass when notes reference D-refs into nothing.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

CONFIG = Path(".gov/decisions.json")
DEFAULT_PATH = Path("docs/decisions.md")
SECTION_RX = re.compile(r"(?m)^## (D\d+) — .*$")
ROW_RX = re.compile(r"(?m)^\|\s*(D\d+)\s*\|.*$")  # whole row line
DIR_FILE_RX = re.compile(r"^(D\d+)(?:[-_.].*)?\.md$", re.IGNORECASE)
ALT_RX = re.compile(r"被否|选项|否决|[Aa]lternatives")
FORMATS = ("sections", "table", "dir")


@dataclass
class Source:
    path: Path
    fmt: str  # sections | table | dir
    text: str

    def entries(self) -> list[tuple[str, str, str]]:
        """(D-number, title, body) in file order.

        sections: title is the full ``## Dn — title`` line, body the rest.
        table: title and body are both the row (a row is one line).
        dir: one file per decision, ordered by number; the title is the
        file's ``## Dn — title`` heading (its slug otherwise), body the
        whole file.
        """
        if self.fmt == "table":
            out = []
            for m in ROW_RX.finditer(self.text):
                row = m.group(0).strip()
                first_cell = row.strip("|").split("|")[0].strip()
                out.append((m.group(1), f"{m.group(1)} — {first_cell}", row))
            return out
        if self.fmt == "dir":
            out = []
            for num, p in self.dir_files():
                body = p.read_text(encoding="utf-8")
                m = SECTION_RX.search(body)
                title = (m.group(0).lstrip("# ").strip() if m
                         else f"{num} — {p.stem.split('-', 1)[-1]}")
                out.append((num, title, body))
            return out
        parts = SECTION_RX.split(self.text)
        # split yields [pre, id1, body1, id2, body2, ...] — the heading
        # text is the first line of the ORIGINAL section; recover it by
        # re-matching headings in order.
        headings = [m.group(0).lstrip("# ").strip() for m in
                    re.finditer(r"(?m)^## (D\d+) — .*$", self.text)]
        triples = []
        for i, idx in enumerate(range(1, len(parts) - 1, 2)):
            title = headings[i] if i < len(headings) else parts[idx]
            triples.append((parts[idx], title, parts[idx + 1]))
        return triples

    def dir_files(self) -> list[tuple[str, Path]]:
        """(D-number, path) for a dir-format source, ordered by number."""
        files: list[tuple[int, str, Path]] = []
        for p in sorted(self.path.glob("*.md")):
            m = DIR_FILE_RX.match(p.name)
            if m:
                files.append((int(m.group(1)[1:]), m.group(1).upper(), p))
        return [(num, p) for _, num, p in sorted(files)]

    def numbers(self) -> list[int]:
        return sorted(int(d[1:]) for d, _, _ in self.entries())

    def header_has_alternatives(self) -> bool:
        return bool(ALT_RX.search(self.text))


def configured_path_fmt() -> tuple[Path, str]:
    """The configured (or default) path+format, whether or not it exists.

    ``decision next/add`` and verify-decisions' ``--base`` check need the
    configuration even before (or without) the source itself.
    """
    path, fmt = DEFAULT_PATH, "sections"
    if CONFIG.is_file():
        try:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = {}
        p = cfg.get("path")
        if isinstance(p, str) and p:
            path = Path(p)
        f = cfg.get("format")
        if f is not None and f not in FORMATS:
            # rule 5: a typo'd format silently re-reads the source as
            # sections — refusing names the value instead
            import sys as _sys
            print(f"decisions: unknown format {f!r} in {CONFIG} — "
                  f"expected one of: {', '.join(FORMATS)}", file=_sys.stderr)
            raise SystemExit(2)
        if f in FORMATS:
            fmt = f
    return path, fmt


def load() -> Source | None:
    """The configured or default source; None when nothing exists."""
    path, fmt = configured_path_fmt()
    if fmt == "dir":
        if not path.is_dir():
            return None
        return Source(path=path, fmt=fmt, text="")
    if not path.is_file():
        return None
    return Source(path=path, fmt=fmt, text=path.read_text(encoding="utf-8"))


def numbers_in_rev(rev: str) -> set[int]:
    """Decision numbers as of a git revision (working config's path/format).

    File formats read the blob at ``rev``; the dir format lists tracked
    ``Dn*.md`` filenames via ls-tree. A bad revision raises
    CalledProcessError — callers fail loud with the ref's name.
    """
    path, fmt = configured_path_fmt()
    if fmt == "dir":
        out = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", rev, "--", str(path)],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if out.returncode != 0:
            raise subprocess.CalledProcessError(out.returncode, out.args,
                                                output=out.stdout,
                                                stderr=out.stderr)
        nums: set[int] = set()
        for line in out.stdout.splitlines():
            name = Path(line).name
            m = DIR_FILE_RX.match(name)
            if m:
                nums.add(int(m.group(1)[1:]))
        return nums
    out = subprocess.run(
        ["git", "show", f"{rev}:{path.as_posix()}"],
        capture_output=True, text=True,
        # #168: the blob is repo content (UTF-8 by convention) — decoding
        # with the locale codec crashed verify-decisions --base on non-UTF-8
        # locales (a GBK Windows died on the Chinese decisions table before
        # the number-collision check could fire).
        encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        raise subprocess.CalledProcessError(out.returncode, out.args,
                                            output=out.stdout,
                                            stderr=out.stderr)
    if fmt == "table":
        return {int(m.group(1)[1:]) for m in ROW_RX.finditer(out.stdout)}
    return {int(m.group(1)[1:]) for m in SECTION_RX.finditer(out.stdout)}
