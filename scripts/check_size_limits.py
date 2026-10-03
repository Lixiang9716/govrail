#!/usr/bin/env python3
"""Module size gate: declared line limits, judged per file.

The plane grows event-driven ("Growing the plane", docs/architecture.md)
— but growth lands in review-visible numbers, not in a monolith nobody
noticed until it was 2300 lines (the self_test.py that this gate's
creation promptly split). This gate reads declared limits from
``scripts/size-limits.json`` and names every file over its budget.

Limits are data, not code (#265's shape: a size gate = declared limits +
facts from the tree). The scan set is a closed glob list — a file outside
the globs is unjudged, so adding a code tree means editing the config,
which is the point. Raising a limit is a diff a reviewer sees; the
default budget is generous on purpose — this gate catches runaway
monoliths, not style. Exit codes follow D2: 0 ok, 1 over-limit files
(each named with its count), 2 config/usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / "size-limits.json"


def load_config(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"size-limits: unreadable config {path}: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(raw, dict) or "default" not in raw:
        print(f"size-limits: {path} must be an object with a 'default' limit",
              file=sys.stderr)
        raise SystemExit(2)
    unknown = set(raw) - {"default", "overrides", "scan"}
    if unknown:
        # rule 5: a misspelled key would silently stop meaning anything.
        print(f"size-limits: {path}: unknown key(s) "
              f"{', '.join(sorted(unknown))}", file=sys.stderr)
        raise SystemExit(2)
    limits = raw.get("overrides", {})
    if not isinstance(limits, dict):
        print(f"size-limits: {path}: 'overrides' must be an object", file=sys.stderr)
        raise SystemExit(2)
    for k, v in {**{"default": raw["default"]}, **limits}.items():
        if not isinstance(v, int) or v <= 0:
            print(f"size-limits: {path}: limit '{k}' must be a positive "
                  f"integer, got {v!r}", file=sys.stderr)
            raise SystemExit(2)
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_size_limits")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root to scan (default: this checkout)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--only", action="append", default=None,
                        metavar="PATH_OR_GLOB",
                        help="judge only files matching this literal path "
                             "or glob (#414: a parallel worker gets a "
                             "verdict for ITS files without paying the "
                             "whole-tree scan; whole-tree stays the "
                             "default and the CI mode). Repeatable; a "
                             "slash-less pattern also matches a basename. "
                             "A filter matching nothing is a typo, not a "
                             "pass — exit 2 names it")
    args = parser.parse_args(argv)

    root = Path(args.root)
    cfg = load_config(Path(args.config))
    default_limit = cfg["default"]
    overrides = cfg.get("overrides", {})
    scan = cfg.get("scan")
    if not isinstance(scan, list) or not scan:
        print("size-limits: config 'scan' must be a non-empty glob array",
              file=sys.stderr)
        raise SystemExit(2)

    # #414: the same pathmatch grammar the plane's path-scoped gates use
    # (one glob language, not a second one) — a slash-less filter also
    # matches a basename, mirroring `gov run --only-paths`.
    try:
        from gov.pathmatch import glob_to_regex
    except ImportError:  # direct-script execution from scripts/
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from gov.pathmatch import glob_to_regex
    filters = [(f, glob_to_regex(f)) for f in (args.only or [])]

    def _wanted(rel: str) -> bool:
        if not filters:
            return True
        parts = rel.replace("\\", "/").split("/")
        for literal, rx in filters:
            if rx.match(rel) or ("/" not in literal and rx.match(parts[-1])):
                return True
        return False

    seen: set[Path] = set()
    judged: int = 0
    problems: list[str] = []
    for pattern in scan:
        matches = sorted(root.glob(pattern))
        if not matches and "*" not in pattern:
            print(f"size-limits: scan glob '{pattern}' matched nothing",
                  file=sys.stderr)
            raise SystemExit(2)
        for f in matches:
            if not f.is_file() or f.resolve() in seen:
                continue
            seen.add(f.resolve())
            rel = f.relative_to(root).as_posix()
            if not _wanted(rel):
                continue
            judged += 1
            count = len(f.read_text(encoding="utf-8").splitlines())
            limit = overrides.get(rel, default_limit)
            if count > limit:
                over = (" — raise this override in scripts/size-limits.json"
                        " as a reviewed diff, or split the module"
                        if rel in overrides else
                        " — split the module, or declare an override in"
                        " scripts/size-limits.json")
                problems.append(f"{rel}: {count} lines (limit {limit}{over})")

    if filters and judged == 0:
        # Rule 5: a filtered run that judges nothing is a caller typo —
        # the same contract `gov run --only-paths` holds.
        print("size-limits: --only matched none of the "
              f"{len(seen)} scanned file(s): {', '.join(f for f, _ in filters)}",
              file=sys.stderr)
        raise SystemExit(2)

    if problems:
        for p in problems:
            print(f"size-limits: {p}", file=sys.stderr)
        print(f"size-limits: {len(problems)} file(s) over their declared limit",
              file=sys.stderr)
        return 1
    scope = (f" (--only: {judged} of {len(seen)} file(s) judged)"
             if filters else
             f" (default {default_limit}, {len(overrides)} override(s))")
    print(f"size-limits: {judged} file(s) within limits{scope}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
