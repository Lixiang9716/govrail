#!/usr/bin/env python3
"""gov whatsnew — what arrived since your init version, and how to use it.

Adopters learned about new capabilities from changelog lines, if at all —
three shipped features were re-requested as wishes (D31's evidence that
discoverability, not capability, was the bottleneck). This command prints
the package's usage-oriented highlights (gov/HIGHLIGHTS.md) from a given
version onward. The default "since" in a governed project is the
manifest's init version — the last moment the project touched the plane;
outside one, the newest section prints.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import __version__ as _pkg_version

try:  # package context (`gov ...`)
    from importlib.resources import files
    _HIGHLIGHTS = files("gov").joinpath("HIGHLIGHTS.md")
except Exception:  # direct script execution
    _HIGHLIGHTS = Path(__file__).resolve().parent / "HIGHLIGHTS.md"

MANIFEST = Path(".gov/manifest.json")


def _version_tuple(v: str) -> tuple:
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3])


def _manifest_version() -> str | None:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov whatsnew",
        description="Usage-oriented highlights since a version (default: "
                    "your manifest's init version).",
    )
    parser.add_argument("--since", default=None,
                        help="print sections newer than this version "
                             "(e.g. 0.10.0; default: manifest init version, "
                             "else the newest section)")
    args = parser.parse_args(argv)

    text = _HIGHLIGHTS.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)[1:]
    since = args.since or _manifest_version()

    installed = _version_tuple(_pkg_version)
    installed_str = _pkg_version
    if since:
        print(f"gov whatsnew — govrail {installed_str} installed; "
              f"highlights since {since}")
        threshold = _version_tuple(since)
        printed = 0
        for section in sections:
            header = section.splitlines()[0]
            version = header.split()[0]
            if _version_tuple(version) > threshold:
                print("\n## " + section.rstrip())
                printed += 1
        if not printed:
            print("  (nothing newer than " + since + ")")
        _mapping_note(sections, installed, installed_str)
        return 0

    print(f"gov whatsnew — govrail {installed_str} installed; newest section "
          "(no governed project here; --since to range)")
    print("\n## " + sections[0].rstrip())
    _mapping_note(sections, installed, installed_str)
    return 0


def _mapping_note(sections, installed: tuple, installed_str: str) -> None:
    """#92's wheel-lag residual, said out loud: a section added after its
    release ships in the NEXT wheel (docs-only commits cut no wheel), so
    the installed wheel can legitimately carry no section for itself."""
    newest = None
    for section in sections:
        v = _version_tuple(section.split()[0])
        if newest is None or v > newest:
            newest = v
    if newest is not None and newest < installed:
        print(f"  note: wheel {installed_str} has no dedicated highlights "
              f"section (docs-only release or section ships in the next "
              "wheel); newest above is what this wheel carries")


if __name__ == "__main__":
    raise SystemExit(main())
