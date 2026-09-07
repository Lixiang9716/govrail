#!/usr/bin/env python3
"""Report what a change touches, and suggest the smallest gate set.

This is the "check only what changed" hint (rule 1). It does not run gates;
it maps the touched files to the gates that cover them so a developer picks
the smallest sufficient set instead of reflexively running everything.

Suggestions come from two sources, most specific first (D25):

1. ``.gov/surfaces.json`` — optional project mapping of path globs to a
   surface name and the gates that cover it (``"eval/**": {"surface":
   "experiments", "gates": ["source-limits"]}``); a matched file reports
   that surface and suggests exactly those gates;
2. each gate's ``paths`` globs in ``gates.json`` (unpathed gates are
   always suggested); a legacy surface fallback applies without them.

It also reminds whether the diff carries an Agent Note (rule 2) — the
same check ``gov verify-note-presence`` gates.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:  # package context (`gov change-scope`)
    from .gates import _glob_regex
    from .verify_note_presence import (_is_exempt, _is_trivially_scoped,
                                       _load_exempt_globs)
except ImportError:  # direct script execution (self-test runs files by path)
    from gates import _glob_regex
    from verify_note_presence import (_is_exempt, _is_trivially_scoped,
                                      _load_exempt_globs)

# Fallback when gates.json declares no per-gate paths (legacy configs).
SURFACE_GATES = {
    "governance": ["self-test"],
    "notes": ["notes"],
    "docs": ["pairing"],
    "config": ["self-test"],
}
NOTES_DIR = ".agents/notes/implemented"
SURFACES_CONFIG = Path(".gov/surfaces.json")


def _load_surfaces() -> dict[str, dict] | None:
    """The optional path-pattern → {surface, gates} mapping; None = absent."""
    if not SURFACES_CONFIG.is_file():
        return None
    try:
        raw = json.loads(SURFACES_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"change_scope: cannot read {SURFACES_CONFIG}: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(raw, dict):
        print(f"change_scope: {SURFACES_CONFIG} must be an object", file=sys.stderr)
        raise SystemExit(2)
    for pattern, value in raw.items():
        if not isinstance(value, dict) or not isinstance(value.get("surface"), str) \
                or not isinstance(value.get("gates"), list) \
                or not all(isinstance(g, str) for g in value["gates"]):
            print(
                f"change_scope: '{pattern}' in {SURFACES_CONFIG} must map to "
                '{"surface": "<name>", "gates": ["<id>", ...]}',
                file=sys.stderr,
            )
            raise SystemExit(2)
    return raw


def _classify(path: str, surfaces: dict[str, dict] | None) -> str:
    if surfaces:
        for pattern, value in surfaces.items():
            if _glob_regex(pattern).match(path):
                return value["surface"]
    if path.startswith(".agents/notes/"):
        return "notes"
    if path.endswith(".md"):
        return "docs"
    if path in ("gates.json",) or path.startswith(("gov/", "tests/")):
        return "governance"
    return "code"


def _changed(base: str) -> tuple[list[str], str | None]:
    files: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only", base],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            return [], proc.stderr.strip()
        files.update(f for f in proc.stdout.splitlines() if f)
    return sorted(files), None


def _configured_gates(path: str, surfaces: dict[str, dict] | None) -> list[str] | None:
    if not surfaces:
        return None
    for pattern, value in surfaces.items():
        if _glob_regex(pattern).match(path):
            return list(value["gates"])
    return None


def _suggest_gates(files: list[str], surfaces: dict[str, dict] | None) -> tuple[list[str], bool]:
    """Gate ids covering the change; True when sourced from gates.json paths."""
    matched: set[str] = set()
    rest: list[str] = []
    for f in files:
        via_config = _configured_gates(f, surfaces)
        if via_config is not None:
            matched.update(via_config)
        else:
            rest.append(f)
    try:
        with open("gates.json", encoding="utf-8") as f:
            cfg = json.load(f)
        gates = cfg.get("gates", [])
    except (OSError, json.JSONDecodeError):
        gates = []
    if any(g.get("paths") for g in gates if isinstance(g, dict)):
        suggested = [
            g["id"]
            for g in gates
            if isinstance(g, dict) and "id" in g
            and (not g.get("paths")
                 or any(_glob_regex(p).match(f) for p in g["paths"] for f in rest))
        ]
        return sorted(matched | set(suggested)), True
    fallback_surfaces = {_classify(f, surfaces) for f in rest}
    fallback = {g for s in fallback_surfaces for g in SURFACE_GATES.get(s, [])}
    return sorted(matched | fallback), False


def main(argv: list[str] | None = None) -> int:
    try:
        from .root import force_utf8_stdio
    except ImportError:  # direct-script execution (self-test scratch dirs)
        from root import force_utf8_stdio
    force_utf8_stdio()  # reports leave as UTF-8 on every OS (#168)
    parser = argparse.ArgumentParser(
        prog="gov change-scope",
        description="Report touched surfaces since a base ref.",
    )
    parser.add_argument("--base", default="HEAD~1", help="git ref to diff against")
    args = parser.parse_args(argv)

    surfaces = _load_surfaces()
    files, err = _changed(args.base)
    if err is not None:
        print(f"change_scope: git diff failed: {err}", file=sys.stderr)
        return 2
    if not files:
        print(f"change_scope: no changes since {args.base}")
        return 0

    names = sorted({_classify(f, surfaces) for f in files})
    print(f"touched surfaces: {', '.join(names)}")
    for s in names:
        changed = [f for f in files if _classify(f, surfaces) == s]
        print(f"  {s}: {len(changed)} file(s)")

    suggested, from_paths = _suggest_gates(files, surfaces)
    source = "gates.json paths" if from_paths else "surface fallback"
    if surfaces:
        source += " + .gov/surfaces.json"
    print(f"suggested gates ({source}): {', '.join(suggested) or 'code gates (project toolchain)'}")
    print("run them: gov run --base " + args.base + "  (or: gov run --gate <id>)")

    # The reminder gates the same surface verify-note-presence does (#149):
    # bookkeeping (task receipts) and repo-declared exemptions are shared,
    # so the two tools never disagree about what deserves a note. Root .md
    # files other than README/CHANGELOG-class are behavior-bearing (D20).
    exempt_globs, err = _load_exempt_globs()
    if err is not None:
        print(f"change_scope: {err}", file=sys.stderr)
        return 2
    non_trivial = [f for f in files
                   if not _is_trivially_scoped(f)
                   and not _is_exempt(f, exempt_globs)]
    has_note = any(f.startswith(NOTES_DIR) for f in files)
    if non_trivial and not has_note:
        print("note: no Agent Note in this change — if it is non-trivial, add one "
              "(.gov/rules.md rule 2; gov verify-note-presence checks it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
