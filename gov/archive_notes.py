#!/usr/bin/env python3
"""Seal the archived-notes manifest: recompute sha256 for every archived note.

Archived notes are frozen (D5); the manifest pins each file's content hash
so any later edit is detectable — ``gov verify-archive`` is the detector.
Run this after moving a note into ``archived/``.

Re-sealing refuses to launder a drift (F7): when the existing seal says a
file changed, sealing aborts loud unless ``--rebaseline`` gives explicit
consent (and says what it re-baselined). Sealing nothing is reported,
never written — an empty manifest is a vacuous seal. Unknown arguments
abort (rule 5).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    from root import anchor_to_git_root

NOTES_ROOT = Path(".agents/notes")
ARCHIVED = NOTES_ROOT / "archived"
MANIFEST = ARCHIVED / "manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("archive_notes")
    parser = argparse.ArgumentParser(
        prog="gov archive-notes",
        description="Seal the archived-notes manifest (recompute every sha256).",
    )
    parser.add_argument(
        "--rebaseline",
        action="store_true",
        help="re-seal entries that differ from the current seal (explicit, "
             "loudly-printed consent — not for restoring tampering)",
    )
    args = parser.parse_args(argv)  # unknown args abort with exit 2

    if not NOTES_ROOT.is_dir():
        print(
            f"archive_notes: {NOTES_ROOT} not found — run in a governed project root",
            file=sys.stderr,
        )
        return 2

    files: dict[str, dict[str, str]] = {}
    for p in sorted(ARCHIVED.rglob("*.md")):
        # as_posix: the seal must be byte-stable across operating systems —
        # a manifest sealed on Linux must verify on Windows (#168).
        rel = p.relative_to(ARCHIVED).as_posix()
        files[rel] = {"sha256": _sha256(p)}
    if not files:
        print("archive_notes: nothing to seal (no notes under archived/)")
        return 0

    drifted: list[str] = []
    if MANIFEST.is_file():
        try:
            previous = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", {})
        except (json.JSONDecodeError, OSError) as e:
            print(f"archive_notes: cannot read the current seal {MANIFEST}: {e}",
                  file=sys.stderr)
            return 2
        drifted = sorted(
            rel for rel, meta in previous.items()
            if rel in files and files[rel]["sha256"] != meta.get("sha256")
        )
        if drifted and not args.rebaseline:
            print("archive_notes: refusing to re-seal — file(s) differ from the current seal:")
            for rel in drifted:
                print(f"  {rel}")
            print(
                "restore them (git checkout) or pass --rebaseline to accept the "
                "new content",
                file=sys.stderr,
            )
            return 1

    ARCHIVED.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps({"files": files}, indent=2) + "\n", encoding="utf-8"
    )
    if drifted:
        print(f"archive_notes: RE-BASELINED {len(drifted)} drifted file(s): "
              + ", ".join(drifted))
    print(f"archive_notes: sealed {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
