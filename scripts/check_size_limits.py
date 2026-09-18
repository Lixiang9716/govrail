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

    seen: set[Path] = set()
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
            count = len(f.read_text(encoding="utf-8").splitlines())
            limit = overrides.get(rel, default_limit)
            if count > limit:
                over = (" — raise this override in scripts/size-limits.json"
                        " as a reviewed diff, or split the module"
                        if rel in overrides else
                        " — split the module, or declare an override in"
                        " scripts/size-limits.json")
                problems.append(f"{rel}: {count} lines (limit {limit}{over})")

    if problems:
        for p in problems:
            print(f"size-limits: {p}", file=sys.stderr)
        print(f"size-limits: {len(problems)} file(s) over their declared limit",
              file=sys.stderr)
        return 1
    print(f"size-limits: {len(seen)} file(s) within limits "
          f"(default {default_limit}, {len(overrides)} override(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
