#!/usr/bin/env python3
"""Render README.md's command reference from `gov --help` — one truth.

The README block between the BEGIN/END markers is GENERATED from the
CLI's own help output (pinned to COLUMNS=80 so the render is identical
on every machine and in CI). Edit the CLI's descriptions in
gov/commands.py, then run this script; never edit the block by hand. The
consistency test (tests/test_docs_cli_consistency.py) turns a stale
block red in CI.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
# The marker TEXT may evolve (it names the generator/regenerator/verifier),
# so matching is by the STABLE PREFIX, and every block found is collapsed
# into one at the first position — a marker-text change must never orphan
# an old block and grow a duplicate (the derive bot accumulated four on
# master exactly this way before the fix; recorded in the surprise
# ledger as generated-marker-drift).
BEGIN_PREFIX = "<!-- gov:commands BEGIN"
END = "<!-- gov:commands END -->"
BLOCK_RX = re.compile(
    re.escape(BEGIN_PREFIX) + r"(?:(?!" + re.escape(END) + r").)*"
    + re.escape(END) + r"\n?", re.DOTALL)


def render_help() -> str:
    """The `gov --help` commands section, deterministically widthed."""
    env = {**os.environ, "COLUMNS": "80", "PYTHONPATH": str(REPO)}
    proc = subprocess.run(
        [sys.executable, "-m", "gov", "--help"],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    if proc.returncode != 0 or not proc.stderr:
        raise SystemExit(f"gov --help failed: {proc.stderr or 'no output'}")
    out = proc.stderr  # the bare `gov --help` usage prints to stderr
    i = out.find("commands:")
    if i < 0:
        raise SystemExit("gov --help printed no commands section")
    return out[i:].strip()


def render_marker() -> str:
    return (f"{BEGIN_PREFIX} — generated from `gov --help` by "
            "scripts/update_readme_commands.py (regenerate: python3 "
            "scripts/derive_all.py); never edit by hand — drift is "
            "caught by tests/test_docs_cli_consistency.py -->")


def main() -> int:
    body = render_help()
    block = (f"{render_marker()}\n```text\n{body}\n```\n{END}\n")
    text = README.read_text(encoding="utf-8")
    found = BLOCK_RX.findall(text)
    if found:
        # Collapse EVERY existing block (any marker-era text) and put
        # exactly one, current-marker block where the first one sat.
        first = BLOCK_RX.search(text)
        text = BLOCK_RX.sub("", text)
        insert_at = first.start()
        text = text[:insert_at] + block + text[insert_at:]
        action = f"replaced {len(found)} block(s)"
    else:
        anchor = "`init` is non-invasive and idempotent"
        assert anchor in text, "README anchor for the block moved"
        text = text.replace(
            anchor,
            f"The full command surface, verbatim from `gov --help`:\n\n"
            f"{block}\n\n{anchor}", 1)
        action = "inserted"
    README.write_text(text, encoding="utf-8")
    print(f"update-readme-commands: {action} in README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
