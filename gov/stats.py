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
                 "comment_spans", "function_spans", "max_depth")

    def __init__(self) -> None:
        self.total = self.blank = self.comment = self.code = 0
        self.functions = self.classes = self.public = 0
        self.error_nodes = 0
        self.depths: list[int] = []
        self.deepest: list[tuple[str, int, int]] = []
        self.comment_spans: list[tuple[int, int]] = []
        # #265: per-function spans for `gov parse` — the size/complexity
        # gate primitive (name, first line, last line, inner depth).
        self.function_spans: list[tuple[str, int, int, int]] = []
        self.max_depth = 0

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
            name = (src[name_node.start_byte:name_node.end_byte]
                    .decode("utf-8", errors="replace")
                    if name_node is not None else node.type)
            # errors="replace", matching checks.py's node_text: a GBK or
            # Latin-1 identifier must cost a mangled NAME, not the whole
            # `gov stats` run (strict decode crashed the command on
            # non-UTF-8 sources).
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
            m.function_spans.append((name, node.start_point[0] + 1,
                                     node.end_point[0] + 1, inner))
            m.max_depth = max(m.max_depth, inner)
        if node.type in pack.classes:
            m.classes += 1
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = src[name_node.start_byte:name_node.end_byte]\
                    .decode("utf-8", errors="replace")
                if not name.startswith("_"):
                    m.public += 1
        nxt = depth + (1 if node.type in pack.nesting else 0)
        deepest = nxt
        for c in node.children:
            deepest = max(deepest, visit(c, nxt))
        return deepest

    visit(root, 0)

    # Line classification: bisect comment spans by each line's first
    # non-whitespace byte. Line boundaries are located by FINDING the \n
    # bytes, not by assuming one terminator byte per line — CRLF files
    # (Windows checkouts, text-mode writes) consume two, and an assumed
    # +1 drifts every later line's offset into the previous spans,
    # misclassifying code lines as comments (caught by the Windows CI
    # job on this code's first run).
    spans = sorted(m.comment_spans)
    m.comment_spans = []
    starts = [a for a, _ in spans]
    from bisect import bisect_right
    data = src
    pos = 0
    while pos < len(data):
        nl = data.find(b"\n", pos)
        if nl == -1:
            raw, start, pos_next = data[pos:], pos, len(data)
        else:
            raw, start, pos_next = data[pos:nl], pos, nl + 1
        pos = pos_next
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
        m = _Metrics()
        files: list[dict] = []
        for path, src in parse.iter_files(root, pack):
            parser = parse.parser_for(pack, path)
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
            "kind": "stats",
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




# ── #265: `gov parse` — the parse layer as a first-class primitive ──

def _pack_for(path: Path, names: list[str]):
    """The language pack whose globs match this file, or None."""
    import fnmatch
    from . import parse
    for name in names:
        pack = parse.load_pack(name)
        if any(fnmatch.fnmatch(path.as_posix(), pat) or
               fnmatch.fnmatch(path.name, pat) for pat in pack.globs):
            return name, pack
    return None, None


def _file_report(path: Path, src: bytes, name: str, pack) -> dict:
    """One file's structure facts: spans, depths, line counts — the
    declaration a size/complexity gate needs, no project-side parser."""
    from . import parse
    parser = parse.parser_for(pack, path)
    per = _walk_metrics(src, parser.parse(src).root_node, pack)
    cwd = Path.cwd()
    rel = (path.relative_to(cwd).as_posix()
           if path.is_absolute() and path.is_relative_to(cwd)
           else path.as_posix())
    return {
        "path": rel,
        "language": name,
        "lines": {"total": per.total, "code": per.code,
                  "comment": per.comment, "blank": per.blank},
        "functions": [{"name": n, "start": s, "end": e, "depth": d}
                      for n, s, e, d in per.function_spans],
        "max_depth": per.max_depth,
        "parse_errors": per.error_nodes,
    }


def _uncovered(target: Path, claimed: set[Path],
               excludes: set[str]) -> list[Path]:
    """Walkable files under ``target`` that no grammar claimed — the
    honest complement of the parse walk. Same traversal contract as
    parse._walk: excluded directory names pruned, symlinks never
    followed, and the caller's claimed set subtracted."""
    import os
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(target):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            if p not in claimed:
                out.append(p)
    return out


def parse_report(paths: list[Path],
                 lang: str | None = None) -> tuple[list[dict], list[dict]]:
    """Per-file structure facts for every supported file under/being
    ``paths``, PLUS the honest complement (#270): files the walk saw but
    no grammar claims, returned as ``skipped`` — a size gate must be
    able to tell "parsed clean" from "never parsed at all"."""
    from . import parse
    # #335: the parsed set is every installed PACK, the same set
    # `gov stats` walks — not the rules-bearing set the check gate
    # judges. A size gate reads structure facts and must see a language
    # whose grammar shipped even when no `gov/checks/<lang>.json` rules
    # exist for it (Swift and Kotlin land exactly that way: grammar
    # first, rules only when they can be honest).
    names = [lang] if lang else parse.available()
    reports: list[dict] = []
    skipped: list[dict] = []

    for target in paths:
        target = Path(target)
        if target.is_dir():
            claimed: set[Path] = set()
            excludes: set[str] = set()
            for name in names:
                pack = parse.load_pack(name)
                excludes.update(pack.exclude)
                for path, src_bytes in parse.iter_files(target, pack):
                    claimed.add(path)
                    reports.append(_file_report(path, src_bytes, name, pack))
            cwd = Path.cwd()
            for walked in sorted(_uncovered(target, claimed, excludes)):
                rel = (walked.relative_to(cwd).as_posix()
                       if walked.is_absolute() and walked.is_relative_to(cwd)
                       else walked.as_posix())
                suffix = walked.suffix or "(no extension)"
                skipped.append({
                    "path": rel,
                    "reason": f"no grammar for {suffix}",
                })
            continue
        if not target.is_file():
            skipped.append({"path": target.as_posix(),
                            "reason": "no such file"})
            continue
        name, pack = _pack_for(target, names)
        if pack is None:
            skipped.append({"path": target.as_posix(),
                            "reason": "no shipped grammar matches"})
            continue
        reports.append(_file_report(target, target.read_bytes(), name, pack))
    return reports, skipped


def parse_main(argv: list[str] | None = None) -> int:
    """`gov parse <path>... [--json] [--lang L]` — per-file structure
    facts from the same walk `gov stats` aggregates. Facts, not
    verdicts (D44): a size/complexity gate declares its limits and
    reads these numbers; the plane does not judge them."""
    from .root import anchor_to_git_root
    anchor_to_git_root("parse")
    try:
        from . import parse as parse_layer
        parse_unavailable = parse_layer.ParseUnavailable
    except ImportError:  # direct script execution
        import parse as parse_layer
    names = parse_layer.available()
    parser = argparse.ArgumentParser(
        prog="gov parse",
        description="Per-file structure facts from the parse layer "
                    "(function spans, line counts, nesting depth) — "
                    "the primitive a size/complexity gate declares its "
                    "limits against. Facts, not verdicts. "
                    f"Shipped grammars: {', '.join(names)}.")
    parser.add_argument("paths", nargs="+", metavar="PATH",
                        help="files or directories (directories walk "
                             "every shipped grammar's file set)")
    parser.add_argument("--lang", metavar="LANG",
                        help="only this language (directories); shipped: "
                             f"{', '.join(names)}")
    parser.add_argument("--json", action="store_true",
                        help="one JSON object on stdout (files + skipped); "
                             "the human report moves to stderr")
    args = parser.parse_args(argv)

    # U-6: an explicit path that does not exist is a caller error
    # (named, exit 2) — rc 0 with empty facts is reserved for real
    # zero-match scopes, never for "your arguments pointed nowhere".
    missing = [p for p in args.paths if not Path(p).exists()]
    if missing:
        for m in missing:
            print(f"gov parse: no such file or directory: {m}",
                  file=sys.stderr)
        return 2

    # U-4: an unknown --lang or a missing grammar is a named exit 2 —
    # a traceback exiting 1 would read as "gate red" in CI.
    try:
        reports, skipped = parse_report([Path(p) for p in args.paths],
                                        lang=args.lang)
    except parse_unavailable.ParseUnavailable as e:
        print(f"gov parse: {e}", file=sys.stderr)
        return 2

    def emit(text: str) -> None:
        print(text, file=sys.stderr if args.json else sys.stdout)

    if skipped:
        # #270: "never parsed at all" must be distinguishable from
        # "parsed clean" — in JSON as per-file entries, in the human
        # report as a coverage line. Silence is the one wrong answer.
        emit(f"gov parse: {len(skipped)} file(s) not parsed — no shipped "
             "grammar matches their type")
        for note in skipped:
            emit(f"gov parse: skipped {note['path']}: {note['reason']}")
    if args.json:
        print(json.dumps({"files": reports, "skipped": skipped}, indent=2))
        return 0
    for r in reports:
        emit(f"--- {r['path']} ({r['language']}): "
             f"{r['lines']['total']} lines (code {r['lines']['code']}), "
             f"{len(r['functions'])} function(s), max depth "
             f"{r['max_depth']}"
             + (f", {r['parse_errors']} parse error(s)"
                if r["parse_errors"] else ""))
        for n, s, e, d in r["functions"]:
            emit(f"    {n}  {s}-{e}  depth {d}")
    if not reports:
        emit("gov parse: nothing matched a shipped grammar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
