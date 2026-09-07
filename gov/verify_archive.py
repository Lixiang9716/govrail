#!/usr/bin/env python3
"""Verify the archived-notes seal (D5): the freeze now has a detector.

The seal's promise — "the manifest pins each file's content hash so any
later edit is detectable" — was a promise without a reader (F7): the
manifest had only a writer, tampering with an archived note was caught by
no tool, and re-running ``gov archive-notes`` re-sealed the tampered
content, laundering the violation permanently.

This gate checks both directions: every archived file matches its pinned
sha256, and every seal entry still has its file. ``gov archive-notes``
refuses to re-seal over a drift on its own (``--rebaseline`` is explicit,
loudly-printed consent).

Exit codes: 0 = sealed and intact (or nothing archived); 1 = violations;
2 = unreadable seal.
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

ARCHIVED = Path(".agents/notes/archived")
MANIFEST = ARCHIVED / "manifest.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("verify_archive")
    parser = argparse.ArgumentParser(
        prog="gov verify-archive",
        description="Verify the archived-notes seal (pinned sha256 per file).",
    )
    parser.parse_args(argv)

    if not ARCHIVED.is_dir():
        print("verify_archive: nothing archived — nothing to seal")
        return 0
    # as_posix: seal keys are posix on every OS (#168)
    files = {p.relative_to(ARCHIVED).as_posix(): p for p in sorted(ARCHIVED.rglob("*.md"))}
    if not MANIFEST.is_file():
        if not files:
            print("verify_archive: nothing archived — nothing to seal")
            return 0
        print(f"verify_archive: {len(files)} archived file(s) with no seal — run gov archive-notes")
        for rel in sorted(files):
            print(f"  {rel}")
        return 1

    try:
        sealed = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", {})
    except (json.JSONDecodeError, OSError) as e:
        print(f"verify_archive: cannot read the seal {MANIFEST}: {e}", file=sys.stderr)
        return 2

    violations: list[str] = []
    for rel, p in files.items():
        entry = sealed.get(rel)
        if entry is None:
            violations.append(f"{rel}: not in the seal — run gov archive-notes")
        elif _sha256(p) != entry.get("sha256"):
            violations.append(
                f"{rel}: differs from its seal — restore it (git checkout) or "
                "re-baseline explicitly (gov archive-notes --rebaseline)"
            )
    for rel in sealed:
        if rel not in files:
            violations.append(f"{rel}: sealed but the file is gone")

    if violations:
        for v in violations:
            print(v)
        print(f"verify_archive: {len(violations)} violation(s)")
        return 1
    print(f"verify_archive: {len(files)} archived file(s) sealed and intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
