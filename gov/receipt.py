#!/usr/bin/env python3
"""Verifiable run receipts (issue #124 / D42).

A receipt binds one ``gov run`` to the exact tree it verified:

    {v, id, ts, commit, dirty, tag, selection, gates, prev, hash}

Every field except ``hash`` is canonically serialized (sorted keys,
compact separators) and sha256'd; the record's ``prev`` carries the
``hash`` of the previous receipt (``GENESIS`` for the first), so the
ledger at ``.gov/history/receipts.jsonl`` is a hash chain: editing or
deleting any historical line breaks every later link, loudly (rules 5/6
— tamper with the evidence and verification fails, it never silently
coasts). A receipt cited on its own (e.g. copy-pasted into a PR body)
still self-verifies: its ``hash`` covers its own content.

What a receipt proves — and what it deliberately does not: the chain is
keyless (the issue's explicit trade: tamper-evidence now, signatures
later), so it proves *internal consistency and binding* — "this record
says a full green run happened on this commit sha and has not been
edited since" — not authorship. Fabricating a whole chain from scratch
remains possible until real signatures land; see D42's 被否.

``gov receipt verify <commit>`` walks the chain (or checks one record
via ``--record``/stdin) and answers: was a **full, clean, green** run
recorded against exactly this tree?  Green means every gate PASS with no
blocking failure; full means every enabled gate ran (selection kind
``all``); clean means the worktree had no uncommitted changes. Exit 0 =
yes (the receipt ids are printed, PR-ready); exit 1 = no (each near-miss
is named); exit 2 = broken evidence (chain mismatch, malformed record).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "GENESIS"
RECEIPT_VERSION = 1
GREEN_OUTCOMES = ("PASS",)
# Only these fields feed the hash; ``hash`` itself is the digest.
_HASHED = ("v", "id", "ts", "commit", "tree", "dirty", "tag",
           "selection", "gates", "prev")


class ReceiptError(Exception):
    """The receipt ledger or a cited record is broken — exit 2, loudly."""


def canonical(record: dict) -> str:
    """The exact byte string a receipt hashes: sorted keys, compact."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def compute_hash(record: dict) -> str:
    core = {k: record[k] for k in _HASHED}
    return hashlib.sha256(canonical(core).encode("utf-8")).hexdigest()


def _receipt_path() -> Path:
    """Same anchoring as gates history (#23/D32): a linked worktree's
    receipts belong to the main checkout's .gov/history, not per-worktree."""
    try:
        proc = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode == 0 and proc.stdout.strip():
            root = Path(proc.stdout.strip()).resolve().parent
            return root / ".gov" / "history" / "receipts.jsonl"
    except OSError:
        pass
    return Path(".gov/history/receipts.jsonl")


def tree_state() -> tuple[str | None, str | None, bool]:
    """(HEAD commit sha, HEAD tree sha, dirty?) — best effort; outside
    git all three degrade.

    ``tree`` is the commit's content sha: a squash-merged PR lands with a
    NEW commit sha but the SAME tree, so verification matches on the tree
    when the commit sha moved — a receipt says "this exact content", not
    "this exact commit line".

    ``dirty`` means tracked content differs from the commit (staged or
    unstaged modifications); untracked files do not dirty a receipt —
    they are not part of the commit's tree, and the plane's own ledgers
    under .gov/history are untracked by nature. An *edited* tracked file
    absolutely changes what the gates just tested, hence the flag.
    """
    commit = tree = None
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            commit = proc.stdout.strip() or None
        treep = subprocess.run(["git", "rev-parse", "HEAD^{tree}"],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if treep.returncode == 0:
            tree = treep.stdout.strip() or None
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        return commit, tree, bool(dirty.returncode == 0 and dirty.stdout.strip())
    except OSError:
        return commit, tree, False


def build_receipt(gates_records: list[dict], tag: str,
                  selection: dict) -> dict:
    """Assemble one receipt from a run's per-gate records.

    ``gates_records`` is the run's JSON record list (same shape as the
    gates.jsonl entry / ``gov run --json`` output). Disabled gates ride
    along as ``DISABLED`` lines — verification counts them as not-green,
    because a parked gate did not just pass on this tree.
    """
    commit, tree, dirty = tree_state()
    record = {
        "v": RECEIPT_VERSION,
        "id": "",  # filled once the hash exists — id derives from it
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
        "tree": tree,
        "dirty": dirty,
        "tag": tag,
        "selection": selection,
        "gates": [
            {"gate": r.get("gate", ""), "outcome": r.get("outcome", ""),
             "blocking": bool(r.get("blocking", False))}
            for r in gates_records
        ],
        "prev": GENESIS,
    }
    record["prev"] = _last_hash(_receipt_path())
    record["hash"] = compute_hash(record)
    record["id"] = "r-" + record["hash"][:12]
    # id rides inside the hashed core, so recompute once with it set.
    record["hash"] = compute_hash(record)
    return record


def _last_hash(path: Path) -> str:
    """The chain head: the hash of the ledger's last valid line."""
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]
    except FileNotFoundError:
        return GENESIS
    if not lines:
        return GENESIS
    record = _parse_line(lines[-1], len(lines))
    return record["hash"]


def _parse_line(line: str, lineno: int) -> dict:
    try:
        record = json.loads(line)
    except json.JSONDecodeError as e:
        raise ReceiptError(f"receipts line {lineno}: not valid JSON: {e}")
    if not isinstance(record, dict):
        raise ReceiptError(f"receipts line {lineno}: record must be an object")
    missing = [k for k in _HASHED if k not in record] + (["hash"] if "hash" not in record else [])
    if missing:
        raise ReceiptError(
            f"receipts line {lineno}: missing field(s): {', '.join(missing)}")
    if compute_hash(record) != record["hash"]:
        raise ReceiptError(
            f"receipts line {lineno} ({record.get('id', '?')}): "
            "hash mismatch — record was edited after signing")
    return record


def load_chain(path: Path) -> list[dict]:
    """Parse and hash-check every line; then check the prev links."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    records = [
        _parse_line(ln, i)
        for i, ln in enumerate(text.splitlines(), start=1)
        if ln
    ]
    expected_prev = GENESIS
    for i, record in enumerate(records, start=1):
        if record["prev"] != expected_prev:
            raise ReceiptError(
                f"receipts line {i} ({record.get('id', '?')}): chain broken — "
                f"prev is {record['prev'][:16]}… but the previous record "
                f"hashes to {expected_prev[:16]}… "
                "(edited, deleted, or reordered history)")
        expected_prev = record["hash"]
    return records


def _is_green_full(record: dict) -> tuple[bool, str]:
    """(green-and-full?, why-not) — the exact bar `verify` demands.

    Selection kind is judged BEFORE the outcome list: a narrowed run's
    record also carries NOT_SELECTED/SKIPPED entries (per-gate outcomes,
    #119), and "not full by construction" is the root reason — the
    not-green entries are its consequence, not the news.
    """
    gates = record.get("gates", [])
    if not gates:
        return False, "no gates ran"
    selection = record.get("selection") or {}
    if selection.get("kind") != "all":
        return False, (f"partial run (selection: {selection.get('kind')}"
                       f"{':' + selection['value'] if selection.get('value') else ''})")
    not_pass = [g["gate"] for g in gates if g.get("outcome") not in GREEN_OUTCOMES]
    if not_pass:
        return False, f"not all green: {', '.join(not_pass)}"
    if record.get("dirty"):
        return False, "worktree was dirty (run not against the commit's tree)"
    if not record.get("commit"):
        return False, "no commit recorded (outside a git repository?)"
    return True, ""


def _sha(rev: str) -> str | None:
    try:
        proc = subprocess.run(["git", "rev-parse", rev],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            return proc.stdout.strip() or None
    except OSError:
        pass
    return None


def _resolve_commit(commit: str) -> str | None:
    if commit == "HEAD":
        return _sha("HEAD")
    return commit


def _commit_matches(record: dict, commit: str) -> bool:
    """Direct commit-sha match, or the commit's TREE matches the receipt's
    tree sha (the squash-merge case: new commit, identical content)."""
    rc = record.get("commit")
    if rc and rc.startswith(commit):
        return True
    rt = record.get("tree")
    if rt:
        arg_tree = _sha(f"{commit}^{{tree}}")
        if arg_tree and arg_tree == rt:
            return True
    return False


def verify(commit: str, records: list[dict]) -> int:
    """Exit 0 iff some receipt is green, full, clean, and bound to commit."""
    commit = _resolve_commit(commit) or commit
    matches = [r for r in records if _commit_matches(r, commit)]
    if not matches:
        print(f"receipt verify: no receipt recorded against {commit}",
              file=sys.stderr)
        return 1
    greens = []
    for r in matches:
        ok, why = _is_green_full(r)
        if ok:
            greens.append(r)
        else:
            print(f"receipt verify: {r.get('id', '?')} ({r.get('ts', '?')}): {why}",
                  file=sys.stderr)
    if not greens:
        print(f"receipt verify: receipt(s) exist for {commit} but none is a "
              "full clean green run", file=sys.stderr)
        return 1
    for r in greens:
        tag = f" tag={r['tag']}" if r.get("tag") else ""
        print(f"receipt verify: {r['id']} {commit}{tag} — "
              f"{len(r['gates'])} gate(s) all PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov receipt",
        description="Verifiable run receipts: bind a green gov run to the "
                    "exact tree it verified (issue #124/D42).")
    # #138: no `required=True` — a shadowed pre-3.7 argparse backport
    # rejects the kwarg; the rule is enforced by hand below instead.
    sub = parser.add_subparsers(dest="cmd")

    p_verify = sub.add_parser(
        "verify", help="was a full green run recorded against this tree?")
    p_verify.add_argument("commit", help="commit sha (prefix ok, or HEAD)")
    p_verify.add_argument("--record", default=None,
                          help="verify this single receipt record (a JSON "
                               "line, e.g. cited in a PR body) instead of "
                               "the local ledger; '-' reads stdin")

    p_show = sub.add_parser(
        "show", help="print receipt records (JSON lines), newest last")
    p_show.add_argument("--commit", default=None,
                        help="only receipts bound to this commit")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.error("a subcommand is required (verify|show)")

    if args.cmd == "verify":
        try:
            if args.record:
                raw = (sys.stdin.read() if args.record == "-" else args.record)
                lines = [ln for ln in raw.splitlines() if ln.strip()]
                records = [_parse_line(ln, i)
                           for i, ln in enumerate(lines, start=1)]
            else:
                records = load_chain(_receipt_path())
        except ReceiptError as e:
            print(f"receipt verify: {e}", file=sys.stderr)
            return 2
        return verify(args.commit, records)

    if args.cmd == "show":
        try:
            records = load_chain(_receipt_path())
        except ReceiptError as e:
            print(f"receipt show: {e}", file=sys.stderr)
            return 2
        shown = 0
        for r in records:
            if args.commit and not _commit_matches(r, args.commit):
                continue
            print(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
            shown += 1
        if args.commit and not shown:
            print(f"receipt show: no receipts for {args.commit}", file=sys.stderr)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
