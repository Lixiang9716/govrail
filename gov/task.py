#!/usr/bin/env python3
"""Task cards for subagent briefs — a versioned rules pin, not pasted prose.

Orchestrators hand subagents briefs that re-embed the repo's governance
rules by hand: half a page of restated discipline per brief, drift-prone
(a rule adoption silently outdates every template still being pasted) and
unverifiable. A task card replaces the boilerplate with a one-line pin
(``obey rules@<hash>``) plus the task's acceptance checklist, and closes
with a verifiable receipt (issue #125):

- ``gov task new "Title" --check "..."`` writes ``.gov/tasks/T-0001-*.json``
  referencing the CURRENT rule set by content hash (``.gov/rules.md`` +
  ``gates.json``, note conventions included — they live inside rules.md);
  the printed brief line replaces the boilerplate;
- ``gov task check`` recomputes the hash and names every card whose pin is
  stale after a governance adoption (also a gate, scoped to
  ``.gov/tasks/**``), and re-verifies closed cards' receipts;
- ``gov task close T-0001`` runs the gate DAG now and, only on an all-green
  run, records the receipt (outcomes + rules hash + timestamp) in the card.

Claim semantics (D52 applied to cards): ``gov task claim T-0001 --agent W1``
takes a LEASE on the card — resource name ``task/<id>`` — through the
``gov/locks.py`` machinery unchanged (O_EXCL create, lazy takeover of an
expired lease, guard-flocked critical section, holder-verified release).
Two parallel workers cannot both hold one card: the loser gets exit 3
naming the holder and expiry. The claim lives ONLY in the runtime domain
(``<git-common-dir>/gov-locks/``) — it never touches the card JSON, whose
integrity D43 pins (the card is the rules@hash brief + receipt; claim
state is runtime, not record). ``gov task list`` reads the lease files to
display a claim column / ``claim`` JSON field; an expired lease reads as
unclaimed. ``gov task close`` best-effort clears the card's own lease on
success — holder-aware: a lease naming the closer goes, a lease naming
another live worker stays (only ``--force``, a knowing steal, removes
it).

Fail loud throughout (rule 5): missing rule files, malformed cards, and
ambiguous id prefixes abort with the offending name.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:  # package context (`gov ...`)
    from . import atomicio, locks, lockfile
    from .root import anchor_to_git_root
except ImportError:  # direct script execution
    import atomicio, lockfile, locks
    from root import anchor_to_git_root

TASKS_DIR = Path(".gov/tasks")
# The rule set a brief pins: rules.md (which embeds the note conventions,
# rule 3/4) plus the gate DAG that enforces them. Sorted for a stable hash.
RULE_FILES = (".gov/rules.md", "gates.json")
ID_RE = re.compile(r"^T-\d{4}$")
CARD_RE = re.compile(r"^(T-\d{4})(?:-(.+))?\.json$")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rules_hash(root: Path | None = None) -> tuple[str, dict[str, str]]:
    """(combined hash, per-file hashes) over the current rule set.

    Missing rule files abort loud: a hash over a half-absent rule set would
    pin something the project never agreed to.
    """
    root = root or Path.cwd()
    parts: list[str] = []
    files: dict[str, str] = {}
    for rel in RULE_FILES:
        path = root / rel
        if not path.is_file():
            print(f"task: rule-set file {rel} not found — is this a "
                  "gov-initialized project?", file=sys.stderr)
            raise SystemExit(2)
        digest = _sha256_file(path)
        files[rel] = digest
        parts.append(f"{rel}:{digest}")
    combined = hashlib.sha256("\n".join(parts).encode()).hexdigest()
    return combined, files


def brief_line(combined: str) -> str:
    """The one line a brief carries instead of the boilerplate."""
    return f"obey rules@{combined[:12]}"


def _load_cards() -> list[tuple[str, Path, dict]]:
    """(id, path, card) sorted by id; malformed cards abort loud."""
    if not TASKS_DIR.is_dir():
        return []
    cards: list[tuple[str, Path, dict]] = []
    for p in sorted(TASKS_DIR.glob("*.json")):
        m = CARD_RE.match(p.name)
        if not m:
            print(f"task: {p.name}: card filenames must be "
                  "T-<4 digits>-<slug>.json", file=sys.stderr)
            raise SystemExit(2)
        try:
            card = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"task: {p.name}: malformed JSON ({e})", file=sys.stderr)
            raise SystemExit(2)
        if not isinstance(card, dict) or "id" not in card or "rules" not in card:
            print(f"task: {p.name}: card needs 'id' and 'rules' fields",
                  file=sys.stderr)
            raise SystemExit(2)
        cards.append((card["id"], p, card))
    return cards


def _history_ids(root: Path) -> set[str]:
    """Card ids that EVER existed under .gov/tasks/ per git history
    (#327): a deleted card's file still shows in the log, so its id is
    retired even though the tree no longer carries it. Empty outside a
    repository (fresh scratch projects; nothing was ever committed, so
    nothing can be cited against history)."""
    proc = subprocess.run(
        ["git", "-C", str(root), "log", "--name-only", "--format=",
         "--", ".gov/tasks/"],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    ids: set[str] = set()
    for line in (proc.stdout or "").splitlines():
        m = re.fullmatch(r"\.gov/tasks/(T-\d{4,})-.*\.json", line.strip())
        if m:
            ids.add(m.group(1))
    return ids


def _next_id(cards: list[tuple[str, Path, dict]], root: Path | None = None,
             history: set[str] | None = None) -> str:
    """High-water allocation (#327): ids are ADDRESSES, like decision
    numbers — a freed slot is never reused, because every historical
    citation of T-n would silently re-point at a different brief. Seen
    ids = current cards plus every id git history ever recorded under
    .gov/tasks/; the next id is strictly beyond the high-water mark."""
    used = {cid for cid, _, _ in cards}
    if root is not None:
        used |= _history_ids(root)
    if history:
        used |= history
    n = 1
    while f"T-{n:04d}" in used:
        n += 1
    return f"T-{n:04d}"


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "task"


TICK_PREFIX = "[x] "
# A done-marker the gate does not read (#334): `[X]`, `[✓]`, `[y]` … —
# a hand edit that LOOKS ticked while `task check` still counts it open.
NONCANONICAL_TICK_RX = re.compile(r"^\[([^x ])\] ")


def _is_ticked(item: str) -> bool:
    return item.startswith(TICK_PREFIX)


def _marker_warnings(cid: str, items: list) -> list[str]:
    """Non-canonical done-markers found in a checklist (#334).

    Returns problem strings: a marker the reader does not count is the
    one state worse than unticked — it reads as progress and is not.
    """
    out = []
    for i, item in enumerate(items, 1):
        m = NONCANONICAL_TICK_RX.match(str(item))
        if m:
            out.append(
                f"{cid}: checklist item {i} carries a non-canonical done "
                f"marker '[{m.group(1)}] ' — only '[x] ' counts; use "
                f"`gov task tick {cid} {i}`")
    return out


def _matches(cid: str, path: Path, term: str) -> bool:
    """Does one card answer to ``term`` (#352)?

    Three handles: the id, an id prefix, and the card-file stem — the
    slug `gov task new` prints (`task: wrote .gov/tasks/T-0013-<slug>.json`).
    A full filename (with or without .json) is normalized to its stem by
    ``_resolve`` before matching.
    """
    slug = path.stem
    return (cid == term or cid.startswith(term)
            or slug == term or slug.startswith(term))


def _resolve(cards: list[tuple[str, Path, dict]], prefix: str
             ) -> tuple[Path, dict]:
    """Resolve an id (or unique id prefix, or card-file slug) to one card.

    #352: parallel workers mint colliding ids (per-worktree counters), so
    one `T-0013` can name several cards. Two narrowings keep the common
    case workable: the filename slug is a legal handle (it is what
    `gov task new` prints, and it is unique even when the id is not), and
    when several cards match but exactly ONE is still in flight
    (status ``open``), that one wins — every other match being terminal
    is precisely the shape parallel merges leave behind. Anything still
    ambiguous aborts naming each candidate's file, because the ids alone
    are identical and name nothing.
    """
    term = Path(str(prefix)).name
    if term.endswith(".json"):
        term = term[:-5]
    hits = [(p, c) for cid, p, c in cards if _matches(cid, p, term)]
    if not hits:
        print(f"task: no card matches '{prefix}'", file=sys.stderr)
        raise SystemExit(2)
    if len(hits) > 1:
        open_cards = [(p, c) for p, c in hits if c.get("status") == "open"]
        if len(open_cards) == 1:
            return open_cards[0]
        names = ", ".join(f"{c['id']} ({p.name})" for p, c in hits)
        print(f"task: '{prefix}' is ambiguous ({names})", file=sys.stderr)
        raise SystemExit(2)
    return hits[0]


def cmd_new(args: argparse.Namespace) -> int:
    title = " ".join(args.title).strip()
    combined, files = rules_hash()
    if args.rules and not combined.startswith(args.rules):
        print(f"task new: --rules {args.rules} does not match the current "
              f"rule set ({combined[:12]}) — the rules moved since the "
              "pin was taken; re-read them before briefing",
              file=sys.stderr)
        return 2
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--", ".gov/rules.md", "gates.json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode == 0 and proc.stdout.strip():
        print("task new: WARNING — the working diff already touches "
              ".gov/rules.md or gates.json; this card pins the CURRENT "
              "rules hash and goes stale the moment this task lands the "
              "adoption. Re-brief (gov task new) and close in the same "
              "change, or void the card when it retires (gov task void).",
              file=sys.stderr)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    card = {
        "title": title,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules": {"hash": combined, "files": files},
        "checklist": args.check or [],
        "status": "open",
        "receipt": None,
    }
    # ID allocation happens under the inter-process mutex: five parallel
    # workers used to read the same "next free" number and write three
    # T-0001 cards, and an ambiguous id could never be claimed again
    # (_resolve refuses prefixes that match more than one card). The
    # lock covers read-through-write; the card itself lands via
    # atomicio (a crash mid-write used to brick every task subcommand
    # on a half-written card).
    with lockfile.exclusive(TASKS_DIR / ".new.lock"):
        cards = _load_cards()
        cid = _next_id(cards, root=Path.cwd())
        card["id"] = cid
        path = TASKS_DIR / f"{cid}-{_slugify(title)}.json"
        atomicio.write_text(path, json.dumps(card, indent=2) + "\n")
    print(f"task: wrote {path}")
    print(brief_line(combined))
    for item in card["checklist"]:
        print(f"  [ ] {item}")
    return 0


def _receipt_failures(gates_records: list) -> list[str]:
    """Gate ids whose outcome fails the green judgment — the ONE
    predicate for both writing (close, #323) and reading (_check_receipt,
    #329): the writer and the reader of a receipt must never disagree
    again. PASS passes; NON_RUN outcomes (SCOPED_OUT/NOT_SELECTED/
    NOT_RUN/DISABLED) are bookkeeping, not verdicts; everything else —
    FAIL/TIMEOUT/MISSING and SKIP (evidence genuinely missing) — fails.
    """
    try:
        from . import gates as gates_mod
    except ImportError:  # direct-script execution
        import gates as gates_mod
    ok = {"PASS", *gates_mod.NON_RUN_OUTCOMES}
    return [g.get("gate", "?") for g in gates_records
            if not isinstance(g, dict) or g.get("outcome") not in ok]


def _check_receipt(cid: str, card: dict) -> list[str]:
    """Problems with a done card's receipt; empty means verifiable green."""
    problems: list[str] = []
    receipt = card.get("receipt")
    if not isinstance(receipt, dict):
        return [f"{cid}: status is done but the receipt is missing"]
    gates = receipt.get("gates")
    if not isinstance(gates, list) or not gates:
        return [f"{cid}: receipt records no gate run"]
    bad = _receipt_failures(gates)
    if bad:
        problems.append(f"{cid}: receipt run is not all-green "
                        f"({', '.join(bad)})")
    pinned = card.get("rules", {}).get("hash")
    if receipt.get("rules") != pinned:
        problems.append(f"{cid}: receipt was taken against a different "
                        "rule set than the card pins")
    return problems


def cmd_check(args: argparse.Namespace) -> int:
    combined, _files = rules_hash()
    cards = _load_cards()
    if not cards:
        print("task: no cards in .gov/tasks/")
        return 0
    verbose = bool(getattr(args, "verbose", False))
    strict = bool(getattr(args, "strict", False))
    problems: list[str] = []
    warnings: list[str] = []
    counts = {"open": 0, "stale": 0, "done": 0, "voided": 0}
    counts_unticked: dict[str, int] = {}
    for cid, path, card in cards:
        status = card.get("status")
        pinned = card.get("rules", {}).get("hash", "<missing>")
        title = card.get("title", "")
        items = card.get("checklist", [])
        if status == "done":
            problems.extend(_check_receipt(cid, card))
            counts["done"] += 1
            print(f"done  {cid} {title}")
        elif status == "voided":
            counts["voided"] += 1
            line = f"voided {cid} {title}"
            # #357: the void reason IS the audit trail (adopters record
            # the whole exit story) and grows with the retirement ledger
            # — one line per card by default, the full text behind
            # --verbose or `gov task show`.
            reason = card.get("void", {}).get("reason", "")
            if verbose and reason:
                line += f" — {reason}"
            print(line)
        elif status == "open":
            counts["open"] += 1
            warnings.extend(_marker_warnings(cid, items))
            unticked = [i for i, it in enumerate(items, 1)
                        if not _is_ticked(str(it))]
            if unticked:
                counts_unticked[cid] = len(unticked)
            if strict and unticked:
                problems.append(
                    f"{cid}: {len(unticked)} unticked checklist item(s) "
                    f"({', '.join(str(i) for i in unticked)}) — tick them "
                    "(gov task tick) or close the card (rule 9)")
                print(f"OPEN  {cid} {title} ({len(unticked)} unticked)")
            elif pinned != combined:
                counts["stale"] += 1
                problems.append(
                    f"{cid}: pins rules@{pinned[:12]} but the project is at "
                    f"rules@{combined[:12]} — the brief is stale after a "
                    f"governance adoption ({path}); if the same brief still "
                    f"describes the work, advance it: gov task re-pin {cid} "
                    "--reason <why>; otherwise close or void it")
                print(f"STALE {cid} {title}")
            else:
                print(f"open  {cid} {title} ({brief_line(combined)})")
        else:
            problems.append(f"{cid}: unknown status {status!r}")
    # #358: "open" alone hid the state the checklist exists to carry —
    # the default report names how much of the open work is still
    # unticked (advisory: an in-flight card is allowed to have them;
    # --strict is where a repo opts into teeth).
    unticked_total = sum(counts_unticked.values())
    open_note = f"{counts['open']} open"
    if unticked_total:
        open_note += (f" ({unticked_total} unticked item(s); --strict "
                      "blocks on them)")
    print(f"task: {len(cards)} card(s) — {open_note}, "
          f"{counts['stale']} stale, {counts['done']} done, "
          f"{counts['voided']} voided")
    # #334: a marker the reader does not count is worse than an unticked
    # item — it LOOKS like progress. Warn by default (visible, not
    # blocking); --strict makes it a problem like the rest.
    if warnings:
        if strict:
            problems.extend(warnings)
        else:
            print()
            for w in warnings:
                print(f"task: {w} (warning)", file=sys.stderr)
    if problems:
        print()
        for p in problems:
            print(f"task: {p}", file=sys.stderr)
        return 1
    return 0


def _named(card: dict, path: Path) -> str:
    """The card's name WITH its file identity (#378).

    An id alone names several cards once parallel workers mint colliding
    numbers, and the #378 incident class is a mutation that moves the
    WRONG one while a sibling is transiently absent — visible at the
    terminal only if the success line says WHICH file moved. The slug is
    what `gov task new` prints and what `--slug` guards against.
    """
    return f"{card['id']} ({path.stem})"


def _guard_slug(args: argparse.Namespace, path: Path, card: dict) -> None:
    """`--slug <file-stem>`: turn "I read this id earlier" into an
    assertion (#378). A remembered id is only unique at the moment it
    was read; in a shared checkout a sibling card can appear, leave
    (a stash), or be minted between the read and this command, and the
    resolver will honestly resolve to whatever the CURRENT tree holds.
    The caller who knows which card they mean passes its slug; a
    mismatch refuses BEFORE any mutation."""
    expected = getattr(args, "slug", None)
    if not expected:
        return
    want = expected[:-5] if expected.endswith(".json") else expected
    if want != path.stem:
        print(f"task: --slug guard: '{args.id}' resolved to "
              f"{_named(card, path)}, not '{expected}' — refusing to "
              "mutate a card you did not mean (gov task show lists the "
              "slug per card)", file=sys.stderr)
        raise SystemExit(2)


def cmd_tick(args: argparse.Namespace) -> int:
    """Tick one checklist item (#334) — the sanctioned way to record
    progress, where hand-editing .gov/tasks/<id>.json used to be the only
    one (and the one move the router skill forbids). The marker is
    canonical and boring: ``[x] `` and nothing else, so `task check` reads
    it and `--strict` counts only the items still unticked."""
    if args.item < 1:
        print("task: item numbers start at 1 (gov task show lists them)",
              file=sys.stderr)
        return 2
    cards = _load_cards()
    path, card = _resolve(cards, args.id)
    _guard_slug(args, path, card)
    if card.get("status") != "open":
        print(f"task: {card['id']} is {card.get('status')!r}, not open — "
              "ticking records progress on in-flight work", file=sys.stderr)
        return 2
    items = card.get("checklist", [])
    if not items:
        print(f"task: {card['id']} carries no checklist", file=sys.stderr)
        return 2
    if args.item > len(items):
        print(f"task: {card['id']} has {len(items)} item(s) — "
              f"{args.item} is out of range (gov task show {card['id']})",
              file=sys.stderr)
        return 2
    text = str(items[args.item - 1])
    if _is_ticked(text):
        print(f"task: {_named(card, path)} item {args.item} is already ticked")
        return 0
    items[args.item - 1] = TICK_PREFIX + text
    atomicio.write_text(path, json.dumps(card, indent=2) + "\n")
    remaining = [i for i, it in enumerate(items, 1)
                 if not _is_ticked(str(it))]
    print(f"task: ticked {_named(card, path)} item {args.item} — {text}")
    if remaining:
        print(f"  {len(remaining)} unticked: "
              + ", ".join(str(i) for i in remaining))
    else:
        print(f"  all {len(items)} item(s) ticked — close with "
              f"`gov task close {card['id']}`")
    _uncommitted_reminder(path)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Render one card in full (#334): checklist state, void reason,
    receipt summary — the surface that lets `task check` stay one line
    per card (#357)."""
    cards = _load_cards()
    path, card = _resolve(cards, args.id)
    print(f"{card.get('id', '?')} — {card.get('title', '')}  "
          f"[{card.get('status', '?')}]")
    print(f"  card:  {path.as_posix()}")
    print(f"  rules: {(card.get('rules', {}).get('hash') or '?')[:12]}")
    items = card.get("checklist", [])
    for i, item in enumerate(items, 1):
        text = str(item)
        mark = "x" if _is_ticked(text) else " "
        print(f"  [{mark}] {i}. {text[len(TICK_PREFIX):] if _is_ticked(text) else text}")
    if not items:
        print("  (no checklist)")
    void = card.get("void")
    if isinstance(void, dict):
        print(f"  voided: {void.get('reason', '')} "
              f"({void.get('by', '?')} {void.get('ts', '?')})")
    receipt = card.get("receipt")
    if isinstance(receipt, dict):
        print(f"  receipt: mode={receipt.get('mode', '?')} "
              f"green={receipt.get('green', '?')} "
              f"ts={receipt.get('ts', '?')}")
    return 0


def _uncommitted_reminder(card_path: Path) -> None:
    """#345: void/close mutate a tracked card file; if that mutation is
    still uncommitted, say so — the void-before-push ritual lands the
    mutation AFTER the last content commit, and a pushed tree carrying a
    stale card is exactly the silent regression rule 9 exists for."""
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--", str(card_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=locks._scrubbed_env())
    if proc.returncode == 0 and proc.stdout.strip():
        print("task: card mutation is uncommitted — commit it before "
              "pushing so the pushed tree carries the exit")


def cmd_repin(args: argparse.Namespace) -> int:
    """Advance a stale card's rules pin (#368): "same brief, new
    constitution".

    Wiring a gate — the sanctioned path `gov gate add` walks — changes
    `gates.json`, which recomputes the combined `rules@` hash every card
    pins. Every OPEN card goes stale at once, and the task gate blocks on
    stale pins by design; without this command the exits were close (dead
    for the #339 shapes), void (terminal, and it can refuse), or reverting
    the legitimate change. Neither direction was honest.

    Re-pinning is a RECORDED act, like void: it asserts the human
    judgment the gate cannot make — "I read what changed and this brief
    still describes the same work" — and the card keeps the from/to pair,
    the actor, the instant and the reason.
    """
    if not args.reason.strip():
        print("task: re-pin needs --reason (what changed, and why the "
              "brief still holds)", file=sys.stderr)
        return 2
    combined, _files = rules_hash()
    cards = _load_cards()
    path, card = _resolve(cards, args.id)
    _guard_slug(args, path, card)
    if card.get("status") != "open":
        print(f"task: {card['id']} is {card.get('status')!r}, not open — "
              "only an in-flight brief has a pin to advance",
              file=sys.stderr)
        return 2
    pinned = card.get("rules", {}).get("hash")
    if pinned == combined:
        print(f"task: {card['id']} already pins rules@{combined[:12]} — "
              "nothing to re-pin")
        return 0
    card.setdefault("repins", []).append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by": locks._holder_id(getattr(args, "agent", None)),
        "from": pinned,
        "to": combined,
        "reason": args.reason.strip(),
    })
    card["rules"]["hash"] = combined
    atomicio.write_text(path, json.dumps(card, indent=2) + "\n")
    print(f"task: re-pinned {_named(card, path)} rules@{str(pinned)[:12]} -> "
          f"rules@{combined[:12]} — {args.reason.strip()}")
    _uncommitted_reminder(path)
    return 0


def cmd_void(args: argparse.Namespace) -> int:
    """Retire a card without the gate receipt (#322): the exit rule 9
    promises ("or explicitly defer it") and the tool never had.

    A void is a RECORDED act — reason, caller, timestamp ride the card
    and the file stays in .gov/tasks/ (nothing is hand-deleted). The
    strict check tolerates a voided card: it is no longer in-flight
    work, and its history remains auditable. Close refuses a voided
    card like any non-open one — a void is terminal."""
    cards = _load_cards()
    path, card = _resolve(cards, args.id)
    _guard_slug(args, path, card)
    if card.get("status") == "done":
        # #329: trust the receipt's VALIDITY, not its presence — a done
        # card whose receipt fails validation is exactly the bricked
        # state this exit exists for (check is red on it, close refuses
        # it); voiding is the tool-sanctioned way out.
        problems = _check_receipt(card["id"], card)
        if problems:
            print(f"task: {card['id']} is done but its receipt fails "
                  f"validation ({'; '.join(problems)}) — voiding is the "
                  "exit from this bricked state")
        else:
            print(f"task: {card['id']} is done (green receipt on file) — "
                  "nothing to void", file=sys.stderr)
            return 2
    if card.get("status") == "voided":
        reason = card.get("void", {}).get("reason", "no reason recorded")
        print(f"task: {card['id']} is already voided ({reason})",
              file=sys.stderr)
        return 2
    card["status"] = "voided"
    card["void"] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by": locks._holder_id(getattr(args, "agent", None)),
        "reason": args.reason,
    }
    atomicio.write_text(path, json.dumps(card, indent=2) + "\n")
    _clear_task_lease(card,
                      holder=locks._holder_id(getattr(args, "agent", None)),
                      force=True)
    print(f"task: voided {_named(card, path)} — {args.reason}")
    print(f"  recorded by {card['void']['by']} at {card['void']['ts']} "
          "(the card file stays; its history is auditable)")
    _uncommitted_reminder(path)
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    combined, _files = rules_hash()
    cards = _load_cards()
    path, card = _resolve(cards, args.id)
    _guard_slug(args, path, card)
    if card.get("status") != "open":
        # #329: a done card whose receipt FAILS validation is a bricked
        # state (check red, void refused, close refused) —
        # --refresh-receipt is its exit: re-run the gates and rewrite
        # the receipt. A done card with a verifiable green receipt has
        # nothing to refresh.
        if card.get("status") == "done" and args.refresh_receipt:
            problems = _check_receipt(card["id"], card)
            if not problems:
                print(f"task: {card['id']} has a verifiable green receipt "
                      "— nothing to refresh", file=sys.stderr)
                return 2
            print(f"task: refreshing {card['id']}'s receipt — the recorded "
                  f"one fails validation ({'; '.join(problems)})")
        else:
            print(f"task: {card['id']} is {card.get('status')!r}, not open",
                  file=sys.stderr)
            return 2
    pinned = card.get("rules", {}).get("hash")
    if pinned != combined:
        print(f"task: {card['id']} pins rules@{str(pinned)[:12]} but the "
              f"project is at rules@{combined[:12]} — if this brief still "
              f"describes the work, advance it (gov task re-pin "
              f"{card['id']} --reason <why>); otherwise re-brief against "
              "the adopted rules (gov task check names the stale cards)",
              file=sys.stderr)
        return 1
    # #358: the checklist is the contract the card exists to carry, so a
    # close with items still unticked refuses — the exits are tick (the
    # work is done; `gov task tick` writes the canonical marker) or void
    # (the checklist no longer describes the work). Both exist, so this
    # is a gate with a door, not the bricked-state shape #329 removed.
    unticked = [i for i, it in enumerate(card.get("checklist", []), 1)
                if not _is_ticked(str(it))]
    if unticked:
        shown = ", ".join(str(i) for i in unticked[:8]) + (
            f" …and {len(unticked) - 8} more" if len(unticked) > 8 else "")
        print(f"task: refusing to close {card['id']} — {len(unticked)} "
              f"unticked checklist item(s) ({shown}): tick the items the "
              f"work satisfies (gov task tick {card['id']} <n>; gov task "
              "show lists them), or void the card if the checklist no "
              "longer describes the work (rule 9)", file=sys.stderr)
        return 1
    # A live lease naming someone else IS in-flight work: closing here
    # would silently delete the worker's claim out from under it. Only
    # the holder (or an explicit --force, a knowing steal) may close a
    # claimed card. The old "after close there is no in-flight work"
    # defense assumed the closer was the worker — nothing did.
    closer = locks._holder_id(getattr(args, "agent", None))
    claim = _claim_of(card, _common_dir_quiet())
    if claim and claim["claimed_by"] != closer and not args.force:
        print(f"task: {card['id']} is claimed by "
              f"'{claim['claimed_by']}' until {claim['expires_at']} — "
              "closing would delete their live lease; pass --force to "
              "steal it knowingly, or have the holder release first",
              file=sys.stderr)
        return 2
    argv = [sys.executable, "-m", "gov", "run", "--json",
            "--mode", args.mode]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(f"task: gate run timed out after {args.timeout}s",
              file=sys.stderr)
        return 1
    try:
        records = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("task: gate run produced no JSON report\n"
              f"{proc.stdout}\n{proc.stderr}", file=sys.stderr)
        return 1
    # #323/#329: the green judgment is the shared predicate — close
    # writes and _check_receipt reads the SAME rule, or the two drift
    # apart (a close whose scope-limited run left NOT_SELECTED records
    # used to write receipts the checker then rejected, bricking the
    # card). SKIP stays a refusal: a dependency failed, so evidence is
    # genuinely missing.
    failed = _receipt_failures(records)
    if failed:
        # A card closes only on an all-green run; a red run changes nothing
        # (the run itself is already in .gov/history/gates.jsonl).
        print(f"task: refusing to close {_named(card, path)} — gate run not green "
              f"({', '.join(failed)})", file=sys.stderr)
        return 1
    card["receipt"] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": args.mode,
        "rules": combined,
        "green": True,
        "gates": records,
    }
    card["status"] = "done"
    atomicio.write_text(path, json.dumps(card, indent=2) + "\n")
    _clear_task_lease(card, holder=locks._holder_id(getattr(args, "agent", None)),
                      force=args.force)
    print(f"task: closed {_named(card, path)} with an all-green "
          f"{args.mode} run ({len(records)} gates)")
    _uncommitted_reminder(path)
    return 0


def _common_dir_quiet() -> Path | None:
    """The resolved git common dir, or None outside a git repository.

    Quiet twin of locks._common_dir: the claim DISPLAY surfaces (list) and
    the incidental cleanup (close) must work wherever task cards do —
    outside a git domain there is simply no claim state, not an error.
    The lease-MUTATING commands (claim/release) keep locks' loud refusal.
    """
    proc = subprocess.run(["git", "rev-parse", "--git-common-dir"],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=locks._scrubbed_env())
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        return None
    p = Path(out)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _lease_resource(card: dict) -> str:
    """The lease key for ONE card (#332).

    Card ids are per-worktree high-water marks, so two workers' `T-0003`
    cards are different cards that used to fight over one lease key
    (`task/T-0003`) while sharing the lock root through the common git
    dir. The key carries the card's own identity instead: the id plus the
    card's `created` stamp, which every command can recompute from the
    card file itself (the issue's hash(title+created) shape, readable,
    so a lease file names its card at a glance).
    """
    created = "".join(ch for ch in str(card.get("created", ""))
                      if ch.isalnum())
    cid = str(card.get("id", "?"))
    return f"task/{cid}-{created}" if created else f"task/{cid}"


def _claim_of(card: dict, common: Path | None) -> dict | None:
    """The live claim on a card, or None when unclaimed/expired.

    Same freshness classification the lease layer itself uses: a lease
    past its expires_at reads as unclaimed (it may be taken over). The
    card JSON is never consulted for claim state — the lease file is the
    only claim state (D43: the card carries results, never claim
    bookkeeping); the card is consulted only to derive the key (#332).
    """
    if common is None:
        return None
    data = locks._read_lease(
        locks._lease_path(common, _lease_resource(card)))
    if not locks._is_fresh(data, datetime.now(timezone.utc)):
        return None
    return {"claimed_by": data.get("holder"),
            "expires_at": data.get("expires_at")}


def _clear_task_lease(card: dict, holder: str | None = None,
                      force: bool = False) -> None:
    """Best-effort: clear the closed card's own task lease.

    Holder-aware, unlike the unconditional delete this used to be: a
    lease naming ANOTHER live worker is their claim, and a close racing
    a fresh claim must not eat it (cmd_close already refuses a
    foreign-held card up front; this re-check closes the check-to-clear
    race). A lease naming the closer — or the --force steal cmd_close
    already announced — is dead weight and goes: left in place it
    starves the next claimer for the winner's full TTL. Silent when
    there is nothing to clear; this is incidental cleanup piggybacking
    on close's receipt write, not a command of its own.
    """
    common = _common_dir_quiet()
    if common is None:
        return
    resource = _lease_resource(card)
    lease = locks._lease_path(common, resource)
    data = locks._read_lease(lease)
    if data is None:
        return
    named = data.get("holder")
    if not force and holder is not None and named != holder:
        print(f"task: {card.get('id', '?')} was claimed by '{named}' "
              "while closing — their lease is left in place",
              file=sys.stderr)
        return
    # Under the guard flock, not a bare unlink: the unconditional-delete
    # version raced a concurrent taker-over exactly the way the guard's
    # own docstring says it prevents (check-then-unlink outside the lock
    # can delete a lease a takeover just re-issued). --force names the
    # knowing steal; the normal path is holder-verified by the check
    # above, and release's holder argument enforces it inside the guard.
    locks.release(resource, named or "", tool="task close")


def cmd_claim(args: argparse.Namespace) -> int:
    """Lease an open card for one worker; the loser is told who holds it.

    The card gate (must exist, must be open) runs BEFORE the lease — a
    claim on a closed card is a usage error (exit 2), not a busy (exit 3):
    no amount of waiting will reopen a closed card.
    """
    locks._refuse_hostile_env("task claim")
    _cards = _load_cards()
    _path, card = _resolve(_cards, args.id)
    _guard_slug(args, _path, card)
    if card.get("status") != "open":
        print(f"task: {card['id']} is {card.get('status')!r}, not open — "
              "only an open card can be claimed", file=sys.stderr)
        return 2
    resource = _lease_resource(card)   # #332: card identity, not the bare id
    holder = locks._holder_id(args.agent)
    rc = locks.acquire(resource, holder, args.ttl, args.wait,
                       tool="task claim")
    if rc != 0:
        return rc
    # The open-check ran BEFORE the lease, so a close could land between
    # the check and the take (TOCTOU): re-read now that the lease is
    # ours, and if the card closed meanwhile, drop the lease we just
    # took instead of squatting on a done card.
    _path_now, card_now = _resolve(_load_cards(), args.id)
    if card_now.get("status") != "open":
        locks.release(resource, holder, tool="task claim")
        print(f"task: {card_now['id']} closed while the claim was being "
              "taken — the fresh lease is released", file=sys.stderr)
        return 2
    data = locks._read_lease(
        locks._lease_path(_common_dir_quiet(), resource))
    if isinstance(data, dict):
        print(f"task: {_named(card_now, _path_now)} claimed by "
              f"'{data.get('holder')}' "
              f"until {data.get('expires_at')} (lease '{resource}'; the "
              "card JSON is untouched)", file=sys.stderr)
    else:
        print(f"task: {_named(card_now, _path_now)} claimed "
              f"(lease '{resource}')", file=sys.stderr)
    return 0


def cmd_task_release(args: argparse.Namespace) -> int:
    """Release a card lease — holder-verified, never on another's behalf.

    The lease key is the CARD's identity (#332), so the card must resolve
    first: an id alone names several cards once parallel workers minted
    it, and releasing under the wrong one would free a lease nobody
    holds while the real holder kept squatting.
    """
    locks._refuse_hostile_env("task release")
    path, card = _resolve(_load_cards(), args.id)
    return locks.release(_lease_resource(card),
                         locks._holder_id(args.agent), tool="task release")


def cmd_list(args: argparse.Namespace) -> int:
    cards = _load_cards()
    common = _common_dir_quiet()
    claim_by_id = {cid: _claim_of(c, common) for cid, _p, c in cards}
    if args.json:
        # stdout carries exactly one JSON value, even when empty —
        # the same purity contract `gov run --json` is held to.
        records = [
            {"id": card.get("id", "?"),
             "title": card.get("title", ""),
             "status": card.get("status", "?"),
             "rules": (card.get("rules", {}).get("hash") or "")[:12] or None,
             "claim": claim_by_id.get(card.get("id", "?"))}
            for _cid, _p, card in cards
        ]
        print(json.dumps(records, indent=2))
        return 0
    if not cards:
        print("task: no cards in .gov/tasks/")
        return 0
    for _cid, _p, card in cards:
        line = (f"{card.get('status', '?'):5} {card.get('id', '?')} "
                f"{card.get('title', '')}")
        claim = claim_by_id.get(card.get("id", "?"))
        if claim:
            line += (f" [claimed by {claim['claimed_by']} "
                     f"until {claim['expires_at']}]")
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("task")
    parser = argparse.ArgumentParser(
        prog="gov task", description="task cards for subagent briefs "
        "(rules pin + checklist + completion receipt)")
    # #138: `required=True` died with a TypeError under a shadowed pre-3.7
    # argparse backport; the subcommand-required rule is enforced by hand.
    sub = parser.add_subparsers(dest="subcommand")

    p_new = sub.add_parser("new", help="create a card pinning the current "
                            "rule set; prints the one-line brief pin")
    p_new.add_argument("title", nargs="+", help="task title")
    p_new.add_argument("--check", action="append", default=[],
                       metavar="ITEM", help="acceptance checklist entry "
                       "(repeatable)")
    p_new.add_argument("--rules", metavar="HASH", default=None,
                       help="require the current rule set to match this "
                       "hash prefix; abort loud on drift")
    p_new.set_defaults(func=cmd_new)

    p_check = sub.add_parser("check", help="name stale cards and verify "
                             "receipts (gate-scoped to .gov/tasks/**)")
    p_check.add_argument("--strict", action="store_true",
                         help="open cards with unticked checklist items "
                              "and non-canonical done-markers block (rule 9)")
    p_check.add_argument("--verbose", action="store_true",
                         help="print each retired card's full void reason "
                              "(#357: the default stays one line per card; "
                              "`gov task show <id>` renders one card whole)")
    p_check.set_defaults(func=cmd_check)

    p_tick = sub.add_parser("tick", help="tick a checklist item on an open "
                            "card (#334) — the sanctioned alternative to "
                            "hand-editing .gov/tasks/<id>.json")
    p_tick.add_argument("id", help="card id, id prefix, or card-file slug")
    p_tick.add_argument("--slug", metavar="STEM",
                        help="#378 scripted-use guard: fail unless the "
                             "resolved card's file stem is exactly this "
                             "(the slug `task new` prints)")
    p_tick.add_argument("item", type=int, metavar="N",
                        help="1-based checklist item number (gov task show "
                             "lists them)")
    p_tick.set_defaults(func=cmd_tick)

    p_show = sub.add_parser("show", help="render one card in full: "
                            "checklist state, void reason, receipt summary")
    p_show.add_argument("id", help="card id, id prefix, or card-file slug")
    p_show.set_defaults(func=cmd_show)

    p_close = sub.add_parser("close", help="run the gate DAG now and close "
                             "the card with a green-run receipt")
    p_close.add_argument("id", help="card id or unique prefix (T-0001)")
    p_close.add_argument("--slug", metavar="STEM",
                         help="#378 scripted-use guard: fail unless the "
                              "resolved card's file stem is exactly this")
    p_close.add_argument("--mode", default="all",
                         help="gate mode to run (default: all)")
    p_close.add_argument("--timeout", type=int, default=600,
                         help="gate-run timeout in seconds (default 600)")
    p_close.add_argument("--agent", metavar="ID",
                         help="closer identity for the lease check (default: "
                              "$GOV_CALLER, then user@host)")
    p_close.add_argument("--refresh-receipt", action="store_true",
                         help="on a done card whose receipt fails "
                              "validation (bricked state, #329): re-run "
                              "the gates and rewrite the receipt; a "
                              "verifiable green receipt refuses")
    p_close.add_argument("--force", action="store_true",
                         help="close even when the card is claimed by another "
                              "holder — a knowing steal of their live lease")
    p_close.set_defaults(func=cmd_close)

    p_list = sub.add_parser("list", help="list cards and their status")
    p_list.add_argument("--json", action="store_true",
                        help="machine-readable: stdout is exactly one JSON "
                             "array of {id, title, status, rules, claim}")
    p_list.set_defaults(func=cmd_list)

    p_claim = sub.add_parser("claim", help="lease an open card for one "
                             "worker (busy → exit 3 naming the holder)")
    p_claim.add_argument("id", help="card id or unique prefix (T-0001)")
    p_claim.add_argument("--slug", metavar="STEM",
                         help="#378 scripted-use guard: fail unless the "
                              "resolved card's file stem is exactly this")
    p_claim.add_argument("--agent", metavar="ID",
                         help="holder identity (default: $GOV_CALLER, then "
                              "the OS user)")
    p_claim.add_argument("--ttl", type=locks.duration,
                         default=locks.DEFAULT_TTL_S, metavar="DUR",
                         help="lease duration (seconds, or 20m/2h style; "
                              f"default {locks.DEFAULT_TTL_S:g}s); an "
                              "expired lease may be taken over lazily")
    p_claim.add_argument("--wait", type=locks.duration, default=None,
                         metavar="DUR",
                         help="poll up to this long for the card instead of "
                              "failing immediately (exit 3 on timeout)")
    p_claim.set_defaults(func=cmd_claim)

    p_release = sub.add_parser("release", help="release a card lease you "
                               "hold (holder-verified)")
    p_release.add_argument("id", help="card id as claimed (T-0001)")
    p_release.add_argument("--agent", metavar="ID",
                           help="holder identity (default: $GOV_CALLER, "
                                "then the OS user)")
    p_release.set_defaults(func=cmd_task_release)

    p_repin = sub.add_parser("repin", help="advance a stale card's rules "
                             "pin (#368): the constitution moved, the brief "
                             "is unchanged — a recorded act")
    p_repin.add_argument("id", help="card id, id prefix, or card-file slug")
    p_repin.add_argument("--slug", metavar="STEM",
                         help="#378 scripted-use guard: fail unless the "
                              "resolved card's file stem is exactly this")
    p_repin.add_argument("--reason", required=True, metavar="TEXT",
                         help="what changed, and why the same brief still "
                              "describes the work (required; recorded)")
    p_repin.add_argument("--agent", metavar="ID",
                         help="actor identity (default: $GOV_CALLER, then "
                              "the OS user)")
    p_repin.set_defaults(func=cmd_repin)

    p_void = sub.add_parser("void", help="retire a card without a gate "
                            "receipt — recorded, terminal (rule 9's "
                            "'explicitly defer it' exit, #322)")
    p_void.add_argument("id", help="card id or unique prefix (T-0001)")
    p_void.add_argument("--slug", metavar="STEM",
                        help="#378 scripted-use guard: fail unless the "
                             "resolved card's file stem is exactly this")
    p_void.add_argument("--reason", required=True, metavar="TEXT",
                        help="why this card is being retired (required; "
                             "recorded on the card)")
    p_void.add_argument("--agent", metavar="ID",
                        help="actor identity (default: $GOV_CALLER, then "
                             "the OS user)")
    p_void.set_defaults(func=cmd_void)

    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        parser.error("a subcommand is required "
                     "(new|check|close|claim|release|list|void|tick|"
                     "show|repin)")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
