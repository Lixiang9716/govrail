#!/usr/bin/env python3
"""Decision-row tooling for parallel-branch workflows (#107/D40).

Radiant's M2 batch landed nine decision rows across eight PRs developed
in parallel worktrees, and every number was allocated by hand: two
branches computing "next free D-number" from their own base collide
silently, and appending to one markdown file is a textual merge-conflict
factory. This command group moves both steps into tooling:

- ``gov decision next [--count N] [--base|--against REF]`` — the next
  free number from the configured decisions source
  (``.gov/decisions.json``); ``--base`` (``--against`` is an alias,
  #147) unions the numbers already landed on REF, so a branch cut from
  an older base does not re-allocate a number master has taken, and
  warns when the local table is missing rows the ref has — a stale
  base numbering blind is how collisions mint in the first place;
- ``gov decision add --from FILE [--id Dn] [--base|--against REF]
  [--dry-run]`` — appends a decision atomically (temp file +
  os.replace, flock against concurrent adds in the same checkout) with
  validation BEFORE writing: number uniqueness, contiguity with what is
  already there, and the alternatives section verify-decisions would
  otherwise flag later. The same ref awareness applies as a soft
  warning (#147): it never blocks the write.

Formats follow the shared loader: ``sections`` (default) and ``table``
append to the single file; ``dir`` (one file per decision, e.g.
``.gov/decisions/D39-title.md``) creates a NEW file — parallel branches
appending from the same base then merge without textual conflicts,
structurally. Numbers two branches both took are caught loudly and by
name, either here (``add --id`` duplicate) or at gate time
(``verify-decisions --base`` names the collision before the merge).
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:  # package context (`gov ...`)
    from . import decisions as dec
    from .root import anchor_to_git_root
except ImportError:  # direct script execution
    import decisions as dec
    from root import anchor_to_git_root

ALT_RX = re.compile(r"被否|选项|否决|[Aa]lternatives")
ID_RX = re.compile(r"^D(\d+)$")


def _ref_numbers(base: str | None) -> set[int]:
    """Numbers present on an explicit ref (#107/#147); empty without one.

    A bad revision fails loud with the ref's name (rule 5) — an explicit
    ref is intent, and silently ignoring it would re-open the stale-base
    collision this flag exists to close.
    """
    if not base:
        return set()
    try:
        return dec.numbers_in_rev(base)
    except subprocess.CalledProcessError as e:
        print(f"decision: cannot read decisions at '{base}' — "
              f"{(e.stderr or '').strip() or 'unknown revision'}",
              file=sys.stderr)
        raise SystemExit(2)


def _warn_stale_base(local: set[int], ref_nums: set[int], base: str) -> None:
    """#147: a local table missing rows the ref has is a stale base.

    Soft warning, never a block — the union already answers with the
    number merged history will show; the warning names the rebase so
    the NEXT numbering (and the gate) doesn't start from a blind table.
    On stderr: `next`'s stdout stays exactly the number list.
    """
    behind = sorted(ref_nums - local)
    if not behind:
        return
    shown = ", ".join(f"D{n}" for n in behind[:5])
    if len(behind) > 5:
        shown += f", … (+{len(behind) - 5} more)"
    print(f"decision: note: your base is {len(behind)} "
          f"{'row' if len(behind) == 1 else 'rows'} behind '{base}' "
          f"(missing {shown}) — rebase before numbering", file=sys.stderr)


def _next_free(nums: set[int]) -> int:
    return max(nums) + 1 if nums else 0


def _next(args: argparse.Namespace) -> int:
    anchor_to_git_root("decision next")
    src = dec.load()
    local = set(src.numbers()) if src is not None else set()
    ref_nums = _ref_numbers(args.base)
    if args.base:
        _warn_stale_base(local, ref_nums, args.base)
    start = _next_free(local | ref_nums)
    for n in range(start, start + args.count):
        print(f"D{n}")
    return 0


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "decision"


def _example_row(src_text: str) -> str:
    """A minimal valid row, modeled on the table's own header (#132).

    The header names the adopter's columns, so the example borrows them:
    the refusal shows a row that fits THIS table, not a generic one.
    No header line → a generic three-cell fallback.
    """
    for line in src_text.splitlines():
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|") and len(s) > 1):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue  # the |---| separator, not the header
        return "|" + "|".join([" ? "] + [f" <{c or '…'}> "
                                         for c in cells[1:]]) + "|"
    return "| ? | <title> | <…> |"


def _parse_draft(path: Path, fmt: str) -> tuple[str | None, str]:
    """(title, body) for sections/dir; (None, rows) for table.

    sections/dir drafts: first non-empty line is the title, the rest the
    body (problem/options/status — the section under the generated
    ``## Dn —`` heading). table drafts: the raw row lines, first cell
    ``Dn`` (explicit) or ``?`` (allocate).
    """
    text = path.read_text(encoding="utf-8")
    if fmt == "table":
        if not text.strip():
            # an empty table draft would otherwise append nothing while
            # still rewriting the file — fail loud, named (#132)
            print(f"decision add: draft {path} is empty — table format "
                  "wants row lines (first cell Dn or '?')", file=sys.stderr)
            raise SystemExit(2)
        return None, text.strip("\n")
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        print(f"decision add: draft {path} is empty — first line must be "
              "the title, the rest the body", file=sys.stderr)
        raise SystemExit(2)
    return lines[0].strip("# ").strip(), "\n".join(lines[1:]).strip("\n")


def _locked(parent: Path):
    """Exclusive flock over one add's read-modify-write, same checkout.

    The lock must cover the READ too, not just the write: two concurrent
    `decision add` calls that both read the pre-add text and then write
    serialize on the file but the second write carries the first's stale
    view — one decision silently vanishes. Cross-checkout allocation
    races remain the ``--base`` flag's job (separate checkouts, separate
    locks; the docstring on the old write-only guard always said so).
    """
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        lock = None
        try:
            import fcntl  # POSIX only; absence degrades to no lock
            parent.mkdir(parents=True, exist_ok=True)
            lock = open(parent / ".decision.lock", "w")
            fcntl.flock(lock, fcntl.LOCK_EX)
        except ImportError:
            pass
        try:
            yield
        finally:
            if lock:
                lock.close()
                try:
                    (parent / ".decision.lock").unlink()  # don't litter
                except OSError:
                    pass  # a concurrent holder recreated it; harmless
    return _ctx()


def _atomic_write(path: Path, text: str) -> None:
    """Atomic temp-file + os.replace; the caller holds ``_locked``."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _validate_id(explicit: str | None, nums: set[int], local: set[int],
                 base: str | None) -> int:
    """Resolve the number to add; fail loud on any silent hazard."""
    if explicit is not None:
        if not ID_RX.match(explicit):
            print(f"decision add: --id '{explicit}' is not a D-number "
                  "(expected e.g. D39)", file=sys.stderr)
            raise SystemExit(2)
        n = int(explicit[1:])
        if n in local:
            print(f"decision add: REFUSED — {explicit} already exists in "
                  f"{dec.configured_path_fmt()[0]}; next free is "
                  f"D{_next_free(local)}", file=sys.stderr)
            raise SystemExit(1)
        # Contiguity against the local table (the gate's own rule):
        # a forced number beyond max+1 opens a gap unless --base says
        # the in-between numbers are landing elsewhere.
        legal_next = _next_free(local | (nums - local if base else set()))
        if n > legal_next:
            gaps = ", ".join(f"D{i}" for i in range(_next_free(local), n))
            print(f"decision add: REFUSED — {explicit} skips {gaps}; "
                  f"next free is D{_next_free(local)}"
                  + (f" ({gaps} exist only on '{base}' — merge it first "
                     "or take the next local number)" if base else
                     " (pre-partitioning across branches needs every "
                     "sibling to land)"), file=sys.stderr)
            raise SystemExit(1)
        return n
    return _next_free(nums)


def _add(args: argparse.Namespace) -> int:
    anchor_to_git_root("decision add")
    src = dec.load()
    if src is None:
        print(f"decision add: no decisions source at "
              f"{dec.configured_path_fmt()[0]} — create it or configure "
              ".gov/decisions.json", file=sys.stderr)
        raise SystemExit(2)
    path, fmt = src.path, src.fmt
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"decision add: draft file '{args.draft}' not found",
              file=sys.stderr)
        raise SystemExit(2)
    title, body = _parse_draft(draft, fmt)

    # The flock covers the whole read-modify-write: the numbers read and
    # the write must see the same file state, or two concurrent adds in
    # one checkout lose the first writer's decision to the second's
    # stale view. A dry run reads and never writes — no lock needed.
    lock = _locked(path.parent) if not args.dry_run \
        else contextlib.nullcontext()
    with lock:
        return _add_locked(args, src, path, fmt, title, body)


def _add_locked(args: argparse.Namespace, src, path: Path, fmt: str,
                title: str | None, body: str) -> int:
    # re-read INSIDE the lock: the source loaded at command start caches
    # the file's text, and a concurrent add may have moved it since
    src = dec.load()
    path, fmt = src.path, src.fmt
    local = set(src.numbers())
    ref_nums = _ref_numbers(args.base)
    if args.base:
        _warn_stale_base(local, ref_nums, args.base)
    nums = local | ref_nums
    n = _validate_id(args.id, nums, local, args.base)

    # The alternatives rule, checked BEFORE the write rather than by the
    # gate one commit later (a table header column covers every row).
    if fmt in ("sections", "dir") and not ALT_RX.search(body):
        print(f"decision add: REFUSED — the draft records no options or "
              "rejected alternatives (被否/选项/alternatives); a decision "
              "without what it beat invites re-litigation "
              "(.gov/rules.md rule 3)", file=sys.stderr)
        raise SystemExit(1)

    if fmt == "table":
        rows = []
        for line in body.splitlines():
            if not line.strip():
                continue
            if not line.lstrip().startswith("|"):
                print(f"decision add: REFUSED — table drafts are table "
                      f"rows (first cell Dn or '?'), one row per line; "
                      f"this line is not: {line!r}\n"
                      f"  a valid row for this table: "
                      f"{_example_row(src.text)}", file=sys.stderr)
                raise SystemExit(1)
            cells = line.strip().strip("|").split("|")
            first = cells[0].strip()
            if ID_RX.match(first) and int(first[1:]) != n:
                print(f"decision add: REFUSED — draft row pins {first} "
                      f"but D{n} was allocated; fix the draft or pass "
                      f"--id {first}", file=sys.stderr)
                raise SystemExit(1)
            cells[0] = f" D{n} " if not cells[0].strip() or first == "?" \
                else cells[0]
            rows.append("|" + "|".join(cells) + "|")
        new_text = src.text.rstrip("\n") + "\n" + "\n".join(rows) + "\n"
        target = path
    else:
        section = f"## D{n} — {title}\n\n{body}\n"
        if fmt == "dir":
            target = path / f"D{n}-{_slugify(title)}.md"
            if target.exists():
                print(f"decision add: REFUSED — {target.name} already "
                      "exists", file=sys.stderr)
                raise SystemExit(1)
            new_text = section
        else:
            target = path
            new_text = (src.text.rstrip("\n") + "\n\n" + section
                        if src.text.strip() else section)

    if args.dry_run:
        delta = new_text if fmt == "dir" else (
            "\n".join(rows) + "\n" if fmt == "table" else "\n" + section)
        print(f"decision add (dry run): would "
              f"{'create ' + target.name if fmt == 'dir' else 'append to ' + str(target)}")
        print(delta, end="" if delta.endswith("\n") else "\n")
        return 0
    _atomic_write(target, new_text)
    where = target.name if fmt == "dir" else str(target)
    print(f"decision add: D{n} written ({where}); run "
          "`gov verify-decisions` before pushing")
    if args.base:
        pending = sorted(x for x in (nums - local) if x <= n)
        if pending:
            names = ", ".join(f"D{x}" for x in pending)
            print(f"note: {names} exist only on '{args.base}' — "
                  "verify-decisions flags the local gap until you "
                  "rebase onto it")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov decision",
        description="Allocate and append decision rows (parallel-branch safe).",
    )
    # #138: no `required=True` — a shadowed pre-3.7 argparse backport
    # rejects the kwarg; the rule is enforced by hand below instead.
    sub = parser.add_subparsers(dest="subcommand")

    p_next = sub.add_parser(
        "next", help="the next free D-number from the decisions source")
    p_next.add_argument("--count", type=int, default=1,
                        help="print N consecutive free numbers (default 1)")
    # #147: --against is an alias of --base, not a second semantic — the
    # issue's requested surface and the shipped vocabulary name one flag.
    # Two actions share the dest (last on the command line wins; they can
    # never disagree semantically).
    p_next.add_argument("--base", metavar="REF",
                        help="also count numbers landed on REF (e.g. "
                             "origin/master) — a branch cut before a "
                             "sibling landed must not re-allocate; warns "
                             "when the local table is behind REF")
    p_next.add_argument("--against", metavar="REF", dest="base",
                        help="alias of --base")
    p_next.set_defaults(func=_next)

    # The draft shape the help describes must be the shape the validator
    # enforces FOR THIS REPO's configured format (#132): a title+body
    # clause in a table-format repo reads as correct and is not.
    if dec.configured_path_fmt()[1] == "table":
        from_help = ("draft file: table-row lines ONLY — first cell Dn or "
                     "'?', one row per decision; not title+body (a "
                     "non-row line is refused, with an example row)")
    else:
        from_help = ("draft file: first line the title, the rest the body "
                     "(state the options / rejected alternatives)")
    p_add = sub.add_parser(
        "add", help="append a decision atomically, validated before writing")
    p_add.add_argument("--from", dest="draft", metavar="FILE",
                       required=True, help=from_help)
    p_add.add_argument("--id", metavar="Dn",
                       help="explicit number (default: next free)")
    p_add.add_argument("--base", metavar="REF",
                       help="allocate above REF's numbers too; warns when "
                            "the local table is behind REF")
    p_add.add_argument("--against", metavar="REF", dest="base",
                       help="alias of --base")
    p_add.add_argument("--dry-run", action="store_true",
                       help="print what would be written; write nothing")
    p_add.set_defaults(func=_add)

    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        parser.error("a subcommand is required (next|add)")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
