#!/usr/bin/env python3
"""gov stats — structural facts per language, from the parse layer (D54).

Lines (with the counting rule echoed), symbols, and nesting depth — one
parse pass per file, every metric a consumer of the same tree. These are
FACTS, not verdicts: nothing here gates, nothing here fails a change. The
one loud failure is upstream of the numbers: a language pack that names a
node kind its grammar does not define refuses to load (rule 5), because a
wrong kind silently zeroes its metric — and a plausible zero is the worst
kind of lie a metrics command can tell.

Counting rules are declared per pack and echoed in the output, because an
undeclared rule makes the number unverifiable (two conventions, two
numbers, no way to tell which one you got):

- code line: has a non-whitespace byte OUTSIDE a comment node — so a
  line inside a multi-line string is CODE (a Python docstring is a
  string, not a comment);
- depth:   how many pack-declared block nodes wrap a point in the tree;
           a function's depth is measured INSIDE its body, from zero —
           how deeply nested the function itself is does not count;
- nesting membership is per language (Go's switch/case, Python's match,
  arrow functions) and lives in the pack, never in this module.

--record appends one JSON line to .gov/history/stats.jsonl (same anchoring
as the run ledger, D32) so gov trend can see whether complexity is
accumulating. Metrics, not evidence: nothing in the stats ledger is
verified, so nothing in it can count as evidence (D44's line).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import parse
from .anchor import history_path
from .root import anchor_to_git_root

STATS_VERSION = 1


class _Metrics:
    """One file's metrics, from a single walk of the parse tree."""

    __slots__ = ("total", "blank", "comment", "code", "functions",
                 "classes", "public", "error_nodes", "depths", "deepest",
                 "comment_spans")

    def __init__(self) -> None:
        self.total = self.blank = self.comment = self.code = 0
        self.functions = self.classes = self.public = 0
        self.error_nodes = 0
        self.depths: list[int] = []
        self.deepest: list[tuple[str, int, int]] = []
        self.comment_spans: list[tuple[int, int]] = []

    def absorb(self, per: "_Metrics", path: str | None = None) -> None:
        for key in ("total", "blank", "comment", "code", "functions",
                    "classes", "public", "error_nodes"):
            setattr(self, key, getattr(self, key) + getattr(per, key))
        self.depths.extend(per.depths)
        if path is not None:
            self.deepest.extend((n, d, f"{path}:{ln}")
                                for n, d, ln in per.deepest)
        else:
            self.deepest.extend(per.deepest)


def _walk_metrics(src: bytes, root, pack) -> _Metrics:
    m = _Metrics()

    def visit(node, depth: int) -> int:
        """Walk once; return the deepest nesting level in this subtree."""
        if node.type == "ERROR" or node.is_missing:
            m.error_nodes += 1
        if node.type in pack.comment:
            m.comment_spans.append((node.start_byte, node.end_byte))
        if node.type in pack.functions:
            m.functions += 1
            name_node = node.child_by_field_name("name")
            name = (src[name_node.start_byte:name_node.end_byte].decode()
                    if name_node is not None else node.type)
            if not name.startswith("_"):
                m.public += 1
            # The body is measured from zero: the count is nesting LEVELS
            # INSIDE the function, not how deeply the function itself is
            # nested (the prototype shipped this wrong once and every
            # number looked plausible — the known-answer fixture exists
            # to catch exactly this).
            inner = 0
            for c in node.children:
                inner = max(inner, visit(c, 0))
            m.depths.append(inner)
            m.deepest.append((name, inner, node.start_point[0] + 1))
            return inner
        if node.type in pack.classes:
            m.classes += 1
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = src[name_node.start_byte:name_node.end_byte].decode()
                if not name.startswith("_"):
                    m.public += 1
        nxt = depth + (1 if node.type in pack.nesting else 0)
        deepest = nxt
        for c in node.children:
            deepest = max(deepest, visit(c, nxt))
        return deepest

    visit(root, 0)

    # Line classification: bisect comment spans by each line's first
    # non-whitespace byte. A scan-per-line was O(lines x comments) and
    # cost 2x the parse on this repo.
    spans = sorted(m.comment_spans)
    m.comment_spans = []
    starts = [a for a, _ in spans]
    from bisect import bisect_right
    offset = 0
    for raw in src.splitlines():
        start = offset
        offset = start + len(raw) + 1
        m.total += 1
        stripped = raw.strip()
        if not stripped:
            m.blank += 1
            continue
        first = start + (len(raw) - len(raw.lstrip()))
        i = bisect_right(starts, first) - 1
        if i >= 0 and spans[i][0] <= first < spans[i][1]:
            m.comment += 1
        else:
            m.code += 1
    return m


def _percentile(sorted_values: list[int], q: float) -> int:
    if not sorted_values:
        return 0
    return sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * q))]


def compute(root: Path, packs: list) -> dict:
    """Aggregate metrics over every pack's declared file set under root."""
    agg: dict = {}
    for pack in packs:
        parser = parse.load_parser(pack)
        m = _Metrics()
        files: list[dict] = []
        for path, src in parse.iter_files(root, pack):
            per = _walk_metrics(src, parser.parse(src).root_node, pack)
            rel = path.relative_to(root).as_posix() if path.is_absolute() \
                else path.as_posix()
            m.absorb(per, rel)
            files.append({
                "path": rel,
                "errors": per.error_nodes,
                **{k: getattr(per, k) for k in ("total", "code", "comment",
                                                "blank", "functions",
                                                "classes", "public")},
                "deepest": [{"name": n, "depth": d, "line": ln}
                            for n, d, ln in
                            sorted(per.deepest, key=lambda w: -w[1])[:1]],
            })
        depths = sorted(m.depths)
        outliers = sorted(
            ((n, d, ln) for n, d, ln in m.deepest),
            key=lambda w: -w[1])[:5]
        agg[pack.name] = {
            "files": len(files),
            "lines": {"total": m.total, "code": m.code, "comment": m.comment,
                      "blank": m.blank},
            "symbols": {"functions": m.functions, "classes": m.classes,
                        "public": m.public},
            "depth": {"p50": _percentile(depths, 0.5),
                      "p95": _percentile(depths, 0.95),
                      "max": depths[-1] if depths else 0,
                      "outliers": [{"name": n, "depth": d, "line": ln}
                                   for n, d, ln in outliers]},
            "parse_errors": m.error_nodes,
            "rule": {
                "code_line": "a non-whitespace byte outside a comment node "
                             "(multi-line strings count as CODE)",
                "nesting": sorted(pack.nesting),
                "grammar": pack.grammar,
                "grammar_version": parse.grammar_version(pack),
            },
            "files_detail": files if m.error_nodes else [],
        }
    return agg


def _render(agg: dict) -> None:
    for lang, a in agg.items():
        print(f"--- {lang}: {a['files']} file(s)")
        l = a["lines"]
        print(f"    lines   total={l['total']} code={l['code']} "
              f"comment={l['comment']} blank={l['blank']}")
        s = a["symbols"]
        print(f"    symbols functions={s['functions']} classes={s['classes']} "
              f"public={s['public']}")
        d = a["depth"]
        print(f"    depth   p50={d['p50']} p95={d['p95']} max={d['max']}")
        if d["outliers"]:
            top = ", ".join(f"{o['name']}@{o['line']}(d{o['depth']})"
                            for o in d["outliers"][:3])
            print(f"    deepest {top}")
        r = a["rule"]
        print(f"    rule    nesting = {', '.join(r['nesting']) or '(none)'}")
        print(f"            code line: {r['code_line']}")
        print(f"            grammar {r['grammar']} {r['grammar_version'] or '?'}")
        if a["parse_errors"]:
            print(f"    PARSE   {a['parse_errors']} ERROR/missing node(s) — "
                  "named in --json output", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("stats")
    parser = argparse.ArgumentParser(
        prog="gov stats",
        description="Structural facts per language (lines, symbols, nesting "
                    "depth) from the tree-sitter parse layer — facts, not "
                    "verdicts: nothing here gates.",
    )
    parser.add_argument("--lang", action="append", dest="langs",
                        metavar="LANG",
                        help="only this language pack (repeatable; default: "
                             "every installed pack)")
    parser.add_argument("--record", action="store_true",
                        help="append this snapshot to "
                             ".gov/history/stats.jsonl (metrics, not "
                             "evidence — the run ledger's rule, D44)")
    parser.add_argument("--json", action="store_true",
                        help="one JSON value on stdout; the human report "
                             "moves to stderr")
    args = parser.parse_args(argv)

    names = args.langs or parse.available()
    if not names:
        print("gov stats: no language packs installed — the parse layer is "
              "part of the govrail dependency set; reinstall with "
              "`pip install govrail`", file=sys.stderr)
        return 2
    try:
        packs = [parse.load_pack(n) for n in names]
    except parse.ParseUnavailable as e:
        print(f"gov stats: {e}", file=sys.stderr)
        return 2

    root = Path.cwd()
    agg = compute(root, packs)

    if args.json:
        print(json.dumps({
            "v": STATS_VERSION,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "root": root.resolve().as_posix(),
            "languages": agg,
        }, indent=2))
    else:
        _render(agg)

    if args.record:
        path = history_path("stats.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "v": STATS_VERSION,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "languages": {
                name: {k: a[k] for k in ("files", "lines", "symbols",
                                         "depth", "parse_errors")}
                for name, a in agg.items()
            },
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
        print(f"gov stats: recorded to {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
