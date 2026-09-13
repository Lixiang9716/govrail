#!/usr/bin/env python3
"""gov check — syntax-class static checks over the parse layer (D54/D57).

A rule finds something in the syntax tree; the engine never names a
language. Two rule kinds:

- ``parse-errors`` — one finding per ERROR/missing node. This is the
  editor-level syntax check: it says the file does not PARSE, never that
  it would not COMPILE (tree-sitter's tolerance differs from the
  compiler's; compile truth stays with the language's own compiler).
- ``query`` — a tree-sitter query whose matches are findings. Negation
  ("X present but Y absent") is expressed as TWO queries: ``query``
  finds the nodes, ``absent_query`` runs INSIDE each candidate node's
  row span — any match there discharges the candidate. tree-sitter
  queries cannot say "not", so the difference is how absence is claimed;
  a rule without ``absent_query`` finds presence only.

Suppression: a comment containing ``gov:ignore-check <rule-id>`` on the
finding's start line, or inside the finding node's row span, discharges
that finding. Suppressions are COUNTED and, with --record, written to
the stats ledger — exemptions growing is a trend someone should see (no
other tool accounts for its own suppressions).

Verdicts live here, so rule 6 applies in full: every shipped rule needs
a rejection proof (the file goes red when the violation exists), and the
engine's own machinery — difference, suppression, severity — is pinned
by known-answer fixtures in the self-test.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:  # package context (`gov ...`)
    from importlib.resources import files as _res_files
    _BUILTINS = _res_files("gov").joinpath("checks")
except Exception:  # direct-module execution (self-test scratch dirs)
    _BUILTINS = Path(__file__).resolve().parent / "checks"

PROJECT_DIR = Path(".gov/checks")
IGNORE_RX = re.compile(r"gov:ignore-check[:\s]+([A-Za-z0-9/_.-]+)")
QUERY_NODE_RX = re.compile(r"\(([_a-zA-Z][_a-zA-Z0-9]*)")
RULE_KINDS = ("parse-errors", "query")
SEVERITIES = ("error", "warning")
RULE_KEYS = {"id", "kind", "severity", "message", "query", "absent_query",
             "node"}
LEDGER_VERSION = 1


class CheckError(Exception):
    """A rule file or rule cannot serve (rule 5: abort, named)."""


@dataclass
class Rule:
    id: str
    kind: str
    severity: str
    message: str
    query: str | None = None
    absent_query: tuple[str, ...] = ()  # any match inside discharges
    node: str = "gov-node"


@dataclass
class Finding:
    rule_id: str
    severity: str
    message: str
    path: str
    row: int  # zero-based, like tree-sitter
    suppressed: bool = False
    span: tuple[int, int] | None = None  # inclusive row span of the node

    def line(self) -> int:
        return self.row + 1


@dataclass
class FileReport:
    path: str
    findings: list[Finding] = field(default_factory=list)


def _load_rule_file(path: Path, source: str) -> list[Rule]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise CheckError(f"{source}: not found") from e
    except json.JSONDecodeError as e:
        raise CheckError(f"{source}: not valid JSON: {e}") from e
    if not isinstance(raw, dict) or set(raw) != {"rules"} \
            or not isinstance(raw["rules"], list):
        raise CheckError(f"{source}: must be an object with a 'rules' array")
    rules: list[Rule] = []
    for i, r in enumerate(raw["rules"]):
        if not isinstance(r, dict):
            raise CheckError(f"{source}: rules[{i}] must be an object")
        unknown = sorted(set(r) - RULE_KEYS)
        if unknown:
            raise CheckError(
                f"{source}: rules[{i}]: unknown key(s): {', '.join(unknown)} "
                f"(known: {', '.join(sorted(RULE_KEYS))})")
        rid = r.get("id")
        if not rid or not isinstance(rid, str):
            raise CheckError(f"{source}: rules[{i}]: 'id' is required")
        kind = r.get("kind")
        if kind not in RULE_KINDS:
            raise CheckError(
                f"{source}: rule {rid!r}: kind must be one of "
                f"{', '.join(RULE_KINDS)}")
        severity = r.get("severity", "error")
        if severity not in SEVERITIES:
            raise CheckError(
                f"{source}: rule {rid!r}: severity must be one of "
                f"{', '.join(SEVERITIES)}")
        if kind == "query" and not isinstance(r.get("query"), str):
            raise CheckError(
                f"{source}: rule {rid!r}: query rules need a 'query' string")
        absent = r.get("absent_query")
        if absent is not None:
            if isinstance(absent, str):
                absent = [absent]
            if not isinstance(absent, list) \
                    or not all(isinstance(qx, str) for qx in absent):
                raise CheckError(
                    f"{source}: rule {rid!r}: 'absent_query' must be a "
                    "query string or an array of query strings")
        rules.append(Rule(
            id=rid, kind=kind, severity=severity,
            message=r.get("message") or f"matched {rid}",
            query=r.get("query"),
            absent_query=tuple(absent or ()),
            node=(r.get("node") or "gov-node").lstrip("@."),
        ))
    return rules


def load_rules(lang: str, include_project: bool = True) -> list[Rule]:
    """Shipped rules for a language, then the project's additions.

    Project files (``.gov/checks/<lang>.json``) may ADD rules; a project
    rule re-using a shipped id is refused rather than silently overriding
    it — an override that flips a shipped rule's meaning must be loud
    (rule 5). ``include_project=False`` loads the shipped set alone — the
    self-test's shipped proofs use it so a host project's rule files can
    never perturb the product's own rejection cases.
    """
    shipped_path = Path(_BUILTINS) / f"{lang}.json"
    rules: list[Rule] = []
    ids: set[str] = set()
    if shipped_path.exists():
        for r in _load_rule_file(shipped_path, f"shipped checks ({lang})"):
            rules.append(r)
            ids.add(r.id)
    if not include_project:
        return rules
    project_path = PROJECT_DIR / f"{lang}.json"
    if project_path.exists():
        for r in _load_rule_file(project_path, f".gov/checks/{lang}.json"):
            if r.id in ids:
                raise CheckError(
                    f".gov/checks/{lang}.json: rule id {r.id!r} duplicates a "
                    "shipped rule — project checks are additive; pick a "
                    "distinct id (rule 5)")
            rules.append(r)
            ids.add(r.id)
    return rules


_query_cache: dict[tuple[str, str, str, str], tuple] = {}
_pack_cache: dict[str, object] = {}


def _compiled(lang: str, rule: Rule):
    """(query, absent_query | None), compiled once per (lang, rule)."""
    cache_key = (lang, rule.id, rule.query or "",
                 tuple(rule.absent_query))
    cached = _query_cache.get(cache_key)
    if cached is not None:
        return cached
    from tree_sitter import Language, Query
    import importlib
    pack = _pack_cache.get(lang)
    if pack is None:
        from . import parse
        pack = parse.load_pack(lang)  # ParseUnavailable names the remedy
        _pack_cache[lang] = pack
    mod = importlib.import_module(pack.grammar)
    factory = (getattr(mod, "language", None)
               or getattr(mod, "language_typescript", None)
               or getattr(mod, "language_tsx"))
    language = Language(factory())
    try:
        q = Query(language, rule.query)
        aqs = [Query(language, qx) for qx in rule.absent_query]
    except Exception as e:
        raise CheckError(f"rule {rule.id!r}: query does not compile: {e}") from e
    # The query compiler ACCEPTS unknown node kinds — they silently match
    # nothing, the rule quietly zeroes, and a plausible green hides a rule
    # that never ran (D54's wrong-kind lesson, rule layer). Validate every
    # node symbol against the grammar's kind table; the `_` wildcard is
    # the one legal non-kind.
    kinds = pack.kind_ids
    # String literals are blanked first: a predicate's regex argument
    # ("^(text|...)$") contains parens and would otherwise yield phantom
    # node tokens.
    def node_tokens(query: str) -> list[str]:
        return QUERY_NODE_RX.findall(re.sub(r'"[^"]*"', '""', query))
    for token in node_tokens(rule.query) + \
            [tok for qx in rule.absent_query for tok in node_tokens(qx)]:
        if token == "_" or token in kinds:
            continue
        raise CheckError(
            f"rule {rule.id!r}: node kind {token!r} does not exist in "
            f"grammar {pack.grammar!r} — it would silently match nothing "
            "(rule 5)")
    _query_cache[cache_key] = (q, aqs)
    return q, aqs


def _collect_comments(root, comment_kinds: frozenset) -> list:
    out: list = []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in comment_kinds:
            out.append(n)
        stack.extend(n.children)
    return out


def check_tree(src: bytes, tree, comments: list, lang: str,
               rules: list[Rule]) -> list[Finding]:
    """Run every rule over one parsed file; apply suppressions."""
    from tree_sitter import QueryCursor
    findings: list[Finding] = []

    def node_text(n) -> str:
        return src[n.start_byte:n.end_byte].decode("utf-8", "replace")

    markers: list[tuple[int, str]] = []  # (row, rule_id)
    for c in comments:
        for m in IGNORE_RX.finditer(node_text(c)):
            markers.append((c.start_point[0], m.group(1)))

    def suppressed(row: int, rid: str, span: tuple[int, int] | None) -> bool:
        for mrow, mid in markers:
            if mid != rid:
                continue
            if mrow == row:
                return True
            if span is not None and span[0] <= mrow <= span[1]:
                return True
        return False

    for rule in rules:
        if rule.kind == "parse-errors":
            stack = [tree.root_node]
            while stack:
                n = stack.pop()
                if n.type == "ERROR" or n.is_missing:
                    findings.append(Finding(
                        rule_id=rule.id, severity=rule.severity,
                        message=f"{rule.message} ({n.type} node)",
                        path="", row=n.start_point[0]))
                stack.extend(n.children)
            continue

        q, aqs = _compiled(lang, rule)
        cursor = QueryCursor(q)

        def as_list(v):
            return v if isinstance(v, list) else [v]

        for _pat, caps in cursor.matches(tree.root_node):
            target = caps.get(rule.node)
            if target is None:  # fall back to the first named capture
                named = [v[0] for v in caps.values() if v]
                target = named[0] if named else None
            if target is None:
                continue
            node = as_list(target)[0]
            span = (node.start_point[0], node.end_point[0])
            if any(list(QueryCursor(aq).matches(node)) for aq in aqs):
                continue  # an "absent" thing is present — discharged
            findings.append(Finding(
                rule_id=rule.id, severity=rule.severity,
                message=rule.message, path="", row=node.start_point[0],
                span=span))

    for f in findings:
        f.suppressed = suppressed(f.row, f.rule_id, f.span)
    return findings


def run_lang(root: Path, lang: str, rules: list[Rule]) -> list[FileReport]:
    """Check every file of the language's declared set under root."""
    from . import parse
    pack = parse.load_pack(lang)
    _pack_cache[lang] = pack
    parser = parse.load_parser(pack)
    reports: list[FileReport] = []
    for path, src in parse.iter_files(root, pack):
        rel = path.relative_to(root).as_posix() if path.is_absolute() \
            else path.as_posix()
        tree = parser.parse(src)
        comments = _collect_comments(tree.root_node, pack.comment)
        rep = FileReport(path=rel)
        for f in check_tree(src, tree, comments, lang, rules):
            f.path = rel
            rep.findings.append(f)
        if rep.findings:
            reports.append(rep)
    return reports


def available_langs() -> list[str]:
    """Languages this installation ships rules for."""
    try:
        return sorted(p.name[:-5] for p in Path(_BUILTINS).iterdir()
                      if p.name.endswith(".json"))
    except (FileNotFoundError, NotADirectoryError, TypeError):
        return []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gov check",
        description="Syntax-class static checks over the parse layer: "
                    "rules find patterns in the tree; suppressions are "
                    "counted, never invisible.",
    )
    parser.add_argument("--lang", action="append", dest="lang",
                        metavar="LANG",
                        help="only this language (repeatable; default: "
                             "every language with shipped rules)")
    parser.add_argument("--strict", action="store_true",
                        help="warnings block too (default: only severity "
                             "error blocks)")
    parser.add_argument("--record", action="store_true",
                        help="append finding/suppression counts to "
                             ".gov/history/stats.jsonl")
    parser.add_argument("--json", action="store_true",
                        help="one JSON value on stdout; the human report "
                             "moves to stderr")
    return parser


def _record(reports: list[FileReport]) -> Path:
    from .anchor import history_path
    path = history_path("stats.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    per_rule: dict[str, dict[str, int]] = {}
    for r in reports:
        for f in r.findings:
            slot = per_rule.setdefault(f.rule_id, {"findings": 0,
                                                   "suppressed": 0})
            slot["suppressed" if f.suppressed else "findings"] += 1
    record = {
        "v": LEDGER_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "check",
        "checks": per_rule,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    from .root import anchor_to_git_root
    anchor_to_git_root("check")
    args = build_parser().parse_args(argv)

    langs = args.lang or available_langs()
    if not langs:
        print("gov check: no languages ship rules in this installation — "
              "reinstall govrail", file=sys.stderr)
        return 2
    all_rules: list[tuple[str, list[Rule]]] = []
    try:
        for lang in langs:
            rules = load_rules(lang)
            if rules:
                all_rules.append((lang, rules))
        # Eager validation: a rule whose query names a node kind its
        # grammar lacks must fail the run NOW, not on the first file that
        # reaches it — a directory with no matching files would otherwise
        # never validate at all, and the rule would sit there silently
        # matching nothing (rule 5: fail before the work, not mid-way).
        for lang, rules in all_rules:
            for rule in rules:
                if rule.kind == "query":
                    _compiled(lang, rule)
    except CheckError as e:
        print(f"gov check: {e}", file=sys.stderr)
        return 2
    if not all_rules:
        print(f"gov check: no rules for {', '.join(langs)} — add "
              ".gov/checks/<lang>.json (project rules are additive, "
              "distinct ids)", file=sys.stderr)
        return 2

    from . import parse
    root = Path.cwd()
    reports: list[FileReport] = []
    for lang, rules in all_rules:
        try:
            reports.extend(run_lang(root, lang, rules))
        except parse.ParseUnavailable as e:
            print(f"gov check: {e}", file=sys.stderr)
            return 2

    active = [f for r in reports for f in r.findings if not f.suppressed]
    suppressed_n = sum(1 for r in reports for f in r.findings if f.suppressed)
    blocking = [f for f in active if f.severity == "error"]

    # --json's own help text promises "the human report moves to
    # stderr" — stdout stays exactly one JSON value, and a human
    # watching the terminal still gets the summary.
    def emit(text: str) -> None:
        print(text, file=sys.stderr if args.json else sys.stdout)

    for r in reports:
        for f in r.findings:
            mark = " (suppressed)" if f.suppressed else ""
            emit(f"{r.path}:{f.line()}: [{f.rule_id}] {f.message}{mark}")
    if active or suppressed_n:
        emit(f"gov check: {len(active)} finding(s) "
             f"({len(blocking)} blocking), {suppressed_n} suppressed")
    else:
        emit("gov check: clean")

    if args.json:
        print(json.dumps({
            "v": LEDGER_VERSION,
            "languages": [l for l, _ in all_rules],
            "files": [
                {"path": r.path,
                 "findings": [{"rule": f.rule_id, "severity": f.severity,
                               "line": f.line(), "message": f.message,
                               "suppressed": f.suppressed}
                              for f in r.findings]}
                for r in reports
            ],
            "summary": {"findings": len(active),
                        "suppressed": suppressed_n,
                        "blocking": len(blocking)},
        }, indent=2))

    if args.record:
        path = _record(reports)
        print(f"gov check: recorded to {path}", file=sys.stderr)

    if blocking or (args.strict and active):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
