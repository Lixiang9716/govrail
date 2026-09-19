#!/usr/bin/env python3
"""Recall decisions, notes, and postmortems — the read side of memory.

The notes tree is write-disciplined memory (every non-trivial change
carries a note); this command is its read side: deterministic,
structure-aware retrieval over the planes that carry memory —

- ``.agents/notes/`` (implemented and archived Agent Notes),
- the decisions source (default ``docs/decisions.md``; each ``## Dn —
  title`` section is one entry — same loader as verify-decisions, D32),
- ``docs/postmortem/`` entries (everything but the README pair).

All query terms must appear, case-insensitively. Where they appear ranks
the hit: title > section heading > body. No index, no semantics, no
dependencies — this memory is small and versioned; grep with structure is
the honest tool (working memory belongs to the session layer, semantic
recall to tooling that may depend on things).

Every invocation states the corpus it searched on stderr (per-class
counts: notes, decisions, postmortems — issue #148), so "no match" is
interpretable instead of opaque. On a miss the per-term hit counts name
which term of the AND failed — "the corpus lacks this term" is now
distinguishable from "one term alone would hit". ``--any`` relaxes the
AND: entries matching some terms are ranked by terms matched (then by
where they hit) instead of the query being refused; the strict AND stays
the default (D18) and an empty --any result still fails loud.

Exit codes: 0 = hits (or partial hits under --any); 1 = no match, or an
empty corpus (fail loud — never reason from an empty recall); 2 = usage
error.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    from root import anchor_to_git_root

NOTES = Path(".agents/notes")
POSTMORTEM = Path("docs/postmortem")

WHERE = {3: "title", 2: "headings", 1: "body"}

# --fuzzy (#319): word-level edit-distance tolerance for Latin-script
# terms, CJK bigram overlap for Chinese terms. The literal AND stays the
# default (D18: grep with structure is the honest tool); --fuzzy is the
# opt-in widening for when the corpus vocabulary and the query disagree.
CJK_RX = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]+")
WORD_RX = re.compile(r"[a-z0-9]+")


def _is_cjk(term: str) -> bool:
    return bool(CJK_RX.search(term))


def _bigrams(text: str) -> set[str]:
    out: set[str] = set()
    for run in CJK_RX.findall(text.lower()):
        if len(run) == 1:
            out.add(run)
            continue
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


def _edit_distance_at_most(a: str, b: str, limit: int) -> bool:
    """True when levenshtein(a, b) <= limit (banded DP, small inputs)."""
    if abs(len(a) - len(b)) > limit:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            best = min(best, v)
        if best > limit:
            return False
        prev = cur
    return prev[-1] <= limit


def _fuzzy_hits_text(term: str, text: str) -> bool:
    """Does ``text`` contain something close enough to ``term``?"""
    lowered = text.lower()
    if term in lowered:
        return True
    if _is_cjk(term):
        # CJK: no word boundaries for substring AND to bite on — the
        # bigram overlap ratio is the honest cheap proxy.
        term_bigrams = _bigrams(term)
        if not term_bigrams:
            return False
        text_bigrams = _bigrams(lowered)
        overlap = sum(1 for bg in term_bigrams if bg in text_bigrams)
        return overlap / len(term_bigrams) >= 0.7
    # Latin script: word-level edit distance ≤ 2 (words shorter than 4
    # characters stay literal — short-word fuzzing is pure noise).
    if len(term) < 4:
        return False
    for word in WORD_RX.findall(lowered):
        if len(word) >= len(term) - 2 and _edit_distance_at_most(
                term, word, 2):
            return True
    return False


@dataclass
class Entry:
    source: str  # display path (docs/decisions.md#D14 for decision sections)
    title: str
    headings: list[str]
    body: str


@dataclass
class Corpus:
    """What recall searched — the entries plus the per-class counts (#148)."""

    implemented: int  # note files
    archived: int  # note files
    postmortems: int  # files
    decisions: int  # entries (Dn sections / table rows / dir files)
    decisions_path: str  # "" when no decisions source exists
    entries: list[Entry]

    def statement(self) -> str:
        notes = self.implemented + self.archived
        if self.decisions_path:
            decisions = f"decisions {self.decisions} ({self.decisions_path})"
        else:
            decisions = "decisions 0 (no source)"
        return (f"corpus — notes {notes} "
                f"(implemented {self.implemented}, archived {self.archived}), "
                f"{decisions}, postmortems {self.postmortems} "
                f"({POSTMORTEM.as_posix()}/)")


def _title_of(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _headings_of(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def _corpus() -> Corpus:
    out: list[Entry] = []
    implemented = archived = postmortems = decisions = 0
    decisions_path = ""
    # Notes are the two lifecycle states (D5) — the same definition
    # verify-notes enforces; anything else under .agents/notes/ is not a
    # note and stays unrecalled.
    for lifecycle in ("implemented", "archived"):
        root = NOTES / lifecycle
        if not root.is_dir():
            continue
        files = sorted(root.rglob("*.md"))
        for p in files:
            text = p.read_text(encoding="utf-8-sig")
            out.append(Entry(p.as_posix(), _title_of(text), _headings_of(text), text))
        if lifecycle == "implemented":
            implemented = len(files)
        else:
            archived = len(files)
    from . import decisions as dec
    src = dec.load()
    if src is not None:
        decisions_path = src.path.as_posix()
        triples = src.entries()
        for did, title, body in triples:
            out.append(
                Entry(source=f"{src.path.as_posix()}#{did}", title=title,
                      headings=[], body=body)
            )
        decisions = len(triples)
    if POSTMORTEM.is_dir():
        files = [p for p in sorted(POSTMORTEM.glob("*.md"))
                 if not p.name.startswith("README")]
        for p in files:
            text = p.read_text(encoding="utf-8-sig")
            out.append(Entry(p.as_posix(), _title_of(text), _headings_of(text), text))
        postmortems = len(files)
    return Corpus(implemented, archived, postmortems, decisions,
                  decisions_path, out)


def _entries() -> list[Entry]:
    """All searchable entries (consumed by `gov review` too)."""
    return _corpus().entries


def _score(entry: Entry, terms: list[str],
           fuzzy: bool = False) -> tuple[int, str] | None:
    """(rank, where) when every term appears; None when it does not.

    ``fuzzy`` widens "appears" to --fuzzy's tolerance (#319): the AND
    still requires every term in the SAME field — only the term match
    loosens."""
    if fuzzy:
        if all(_fuzzy_hits_text(t, entry.title) for t in terms):
            return 3, "title"
        for h in entry.headings:
            if all(_fuzzy_hits_text(t, h) for t in terms):
                return 2, f"section '{h}'"
        if all(_fuzzy_hits_text(t, entry.body) for t in terms):
            return 1, "body"
        return None
    lowered = [t.lower() for t in terms]
    if all(t in entry.title.lower() for t in lowered):
        return 3, "title"
    for h in entry.headings:
        if all(t in h.lower() for t in lowered):
            return 2, f"section '{h}'"
    if all(t in entry.body.lower() for t in lowered):
        return 1, "body"
    return None


def _presence(entry: Entry, term: str, fuzzy: bool = False) -> int:
    """Where one term appears: 3 title, 2 a heading, 1 body, 0 nowhere."""
    if fuzzy:
        if _fuzzy_hits_text(term, entry.title):
            return 3
        if any(_fuzzy_hits_text(term, h) for h in entry.headings):
            return 2
        if _fuzzy_hits_text(term, entry.body):
            return 1
        return 0
    t = term.lower()
    if t in entry.title.lower():
        return 3
    if any(t in h.lower() for h in entry.headings):
        return 2
    if t in entry.body.lower():
        return 1
    return 0


def _snippet(e: Entry, terms: list[str]) -> str:
    """The first line (title, headings, then body) containing any term —
    trimmed to a readable width."""
    lowered = [t.lower() for t in terms]
    for line in [e.title, *e.headings, *e.body.splitlines()]:
        low = line.lower()
        if any(t in low for t in lowered):
            text = line.strip()
            return (text[:100] + " …") if len(text) > 100 else text
    return ""


def _per_term(entries: list[Entry], terms: list[str],
              fuzzy: bool = False) -> list[int]:
    """Entries containing each term anywhere — the miss diagnostics (#148)."""
    return [sum(1 for e in entries if _presence(e, t, fuzzy))
            for t in terms]


def _print_miss(entries: list[Entry], terms: list[str],
                fuzzy: bool = False) -> int:
    counts = _per_term(entries, terms, fuzzy)
    per_term = " / ".join(f"{t}: {c}" for t, c in zip(terms, counts))
    print(f"recall: no match for {' '.join(terms)!r}")
    print(f"  per-term hits: {per_term}")
    if len(terms) > 1 and any(counts):
        print("  (strict AND — every term in one entry; "
              "retry with --any to rank partial matches)")
    return 1


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("recall")
    parser = argparse.ArgumentParser(
        prog="gov recall",
        description="Retrieve notes, decisions, and postmortems (all terms, ranked by where they hit).",
    )
    parser.add_argument("query", nargs="+", help="literal terms; all must appear")
    parser.add_argument("--any", action="store_true",
                        help="rank partial matches (entries containing some "
                             "terms, by terms matched) instead of requiring "
                             "every term; the strict AND stays the default")
    parser.add_argument("--fuzzy", action="store_true",
                        help="widen term matching (#319): word-level edit "
                             "distance <= 2 for Latin terms, CJK bigram "
                             "overlap of 70 percent for Chinese terms; "
                             "the AND semantics (and --any) still apply")
    parser.add_argument("--snippet", action="store_true",
                        help="print the first matched line under each hit — "
                             "the evidence inline, not just the address")
    args = parser.parse_args(argv)

    corpus = _corpus()
    # What was searched, every invocation (#148): context on stderr so the
    # ranked hits on stdout stay the first thing a caller reads.
    print(f"recall: {corpus.statement()}", file=sys.stderr)
    entries = corpus.entries
    if not entries:
        # An empty corpus is "no match, fail loud" (exit 1) — the same
        # verdict as a miss over a populated corpus ("never reason from an
        # empty recall"); exit 2 stays reserved for usage errors.
        print(
            "recall: no memory sources found (.agents/notes/, docs/decisions.md, "
            "docs/postmortem/) — is this a project root?",
            file=sys.stderr,
        )
        return 1

    if args.any:
        scored: list[tuple[int, int, str, str, Entry]] = []
        for e in entries:
            matched = [(t, p) for t, p in
                       ((t, _presence(e, t, args.fuzzy))
                        for t in args.query) if p]
            if matched:
                where = ", ".join(f"{t} in {WHERE[p]}" for t, p in matched)
                scored.append((len(matched), max(p for _, p in matched),
                               e.source, where, e))
        if not scored:
            return _print_miss(entries, args.query, args.fuzzy)
        # Full AND matches first, then more terms beat fewer; ties: where
        # they hit, then current authority over frozen evidence, then path
        # (F4).
        scored.sort(key=lambda s: (-s[0], -s[1], "/archived/" in s[2], s[2]))
        for k, _best, source, where, e in scored:
            print(f"{source} — matched {k}/{len(args.query)} terms ({where})")
            if args.snippet:
                line = _snippet(e, [t for t, _p in
                                    ((t, _presence(e, t, args.fuzzy))
                                     for t in args.query)
                                    if _p])
                if line:
                    print(f"    {line}")
        print(f"recall: {len(scored)} partial hit(s) for "
              f"{' '.join(args.query)!r} (--any: ranked by terms matched)")
        return 0

    hits: list[tuple[int, str, str]] = []
    for e in entries:
        scored = _score(e, args.query, args.fuzzy)
        if scored:
            rank, where = scored
            hits.append((rank, e.source, where))
    if not hits:
        return _print_miss(entries, args.query, args.fuzzy)

    # Equal ranks: current authority (implemented/) outranks frozen
    # evidence (archived/), then path order (F4).
    hits.sort(key=lambda h: (-h[0], "/archived/" in h[1], h[1]))
    by_source = {e.source: e for e in entries}
    for rank, source, where in hits:
        print(f"{source} — matched in {where}")
        if args.snippet and (e := by_source.get(source)):
            line = _snippet(e, args.query)
            if line:
                print(f"    {line}")
    print(f"recall: {len(hits)} hit(s) for {' '.join(args.query)!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
