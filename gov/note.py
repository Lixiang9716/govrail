#!/usr/bin/env python3
"""Note scaffolding and pre-commit checking (D29).

The three-part format, the D-references, and the path validity were all
checked only after commit — a typo'd path (evalkit/case.py for
evalkit/evalkit/case.py) surfaced one audit too late. This command moves
the check to both ends of the writing window:

- ``gov note new --class process --ref D6 "Title"`` scaffolds the note at
  its lawful path with the required sections, pre-validating the class
  against the closed set and the D-reference against the decisions table
  (fail loud before you have invested prose in a wrong anchor);
- ``gov note check`` runs the format/placement gate and the D-reference
  audit now — small enough for a pre-commit hook.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

try:  # package context (`gov ...`)
    from . import decisions as dec
    from .root import anchor_to_git_root
except ImportError:  # direct script execution
    import decisions as dec
    from root import anchor_to_git_root

CLASSES = ("feature", "bug-fix", "simplification", "architecture", "process", "testing")
NOTES_IMPLEMENTED = Path(".agents/notes/implemented")

SKELETON = """# Agent Note: {title}

Status: implemented{related}

## Problem

(pain, stated to stand without the solution)

## Decision

(what shipped, present tense)

## Alternatives considered

(what it beat, and why each lost)
"""


def _configured_path() -> Path:
    """The decisions source path from the ONE configuration (.gov/decisions.json)."""
    return dec.configured_path_fmt()[0]


def _known_decisions() -> set[str] | None:
    """D-refs of the configured decisions source, via decisions.load —
    the same loader every other consumer uses (a hand-rolled regex here
    used to disagree with it and read a hardcoded docs/decisions.md).

    None = no source exists; an EMPTY set = a source exists but parses
    to zero entries — a format mismatch, named loudly, D-refs left
    UNCHECKED. Treating that empty set as ground truth used to flag
    every D-ref in every note as dangling: a wholesale false red.
    """
    src = dec.load()
    if src is None:
        return None
    found = {d for d, _, _ in src.entries()}
    if not found:
        print(f"note: {src.path} parses to zero decision entries — check "
              "its format or .gov/decisions.json (D-refs left unchecked)",
              file=sys.stderr)
    return found


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "note"


def _new(args: argparse.Namespace) -> int:
    anchor_to_git_root("note")
    if args.note_class not in CLASSES:
        print(f"note: unknown class '{args.note_class}' "
              f"(closed set: {', '.join(CLASSES)})", file=sys.stderr)
        return 2
    related = ""
    if args.ref:
        import re as _re
        if _re.fullmatch(r"govrail:D\d+", args.ref):
            # The one legal cross-project reference (D34): the tool's own
            # decisions table — nothing local to validate against.
            print(f"note: {args.ref} is an external reference (govrail's "
                  "decisions table) — recorded, not validated locally")
            known = None  # skip local validation
        else:
            known = _known_decisions()
        if known is None:
            # Rule 5, same lesson audit-notes learned: "nothing to check
            # against" is said out loud, never silently skipped.
            print(f"note: no decisions table found — {args.ref} left unchecked "
                  f"({_configured_path()})", file=sys.stderr)
        elif args.ref not in known:
            print(f"note: {args.ref} is not in {_configured_path()} — fix the "
                  "reference or add the decision first", file=sys.stderr)
            return 2
        related = f"\nRelated: {args.ref}"
    dest = NOTES_IMPLEMENTED / args.note_class / (
        f"{date.today().isoformat()}-{_slugify(args.title)}.md"
    )
    if dest.exists():
        print(f"note: already exists: {dest}", file=sys.stderr)
        return 2
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(SKELETON.format(title=args.title, related=related),
                    encoding="utf-8")
    print(f"note: wrote {dest}")
    print("note: fill the three sections; gov note check before committing")
    return 0


def _iter_implemented():
    """(path, class, title) for every implemented note, path order."""
    root = NOTES_IMPLEMENTED
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*.md")):
        try:
            first = p.read_text(encoding="utf-8-sig").splitlines()[0]
        except (OSError, IndexError):
            first = ""
        title = first.lstrip("# ").strip() if first.startswith("# ") else p.stem
        yield p, p.parent.name, title


def _stale_signals(text: str) -> list[str]:
    """Audit-notes' mechanical staleness signals for one note's text —
    the programmatic half of the audit -> archive handoff (dead commands,
    unknown flags, dangling D-refs), reused so the two commands can never
    disagree on what 'stale' means."""
    try:
        from . import audit_notes as an
    except ImportError:  # direct script execution
        import audit_notes as an
    commands = an._known_commands()
    if commands is None:
        print("note: needs package mode — run as `gov note list`", file=sys.stderr)
        raise SystemExit(2)
    return an._flags_note(text, commands, an._known_decisions())


def _list(args: argparse.Namespace) -> int:
    anchor_to_git_root("note")
    rows = [(p.as_posix(), cls, title) for p, cls, title in _iter_implemented()
            if getattr(args, "note_class", None) in (None, cls)]
    stale_only = getattr(args, "stale", False)
    signals_by_path: dict[str, list[str]] = {}
    if stale_only:
        for rel, _cls, _title in rows:
            try:
                text = (Path.cwd() / rel).read_text(encoding="utf-8-sig")
            except OSError:
                continue
            sigs = _stale_signals(text)
            if sigs:
                signals_by_path[rel] = sigs
        rows = [r for r in rows if r[0] in signals_by_path]
    if getattr(args, "json", False):
        print(json.dumps(
            [{"path": rel, "class": cls, "title": title,
              **({"signals": signals_by_path[rel]} if rel in signals_by_path else {})}
             for rel, cls, title in rows], indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("note: no implemented notes"
              + (" carrying staleness signals" if stale_only else "")
              + (f" in class '{args.note_class}'" if args.note_class else ""))
        return 0
    for rel, cls, title in rows:
        line = f"{rel} — {title}"
        if rel in signals_by_path:
            line += f" [stale: {signals_by_path[rel][0]}]"
        print(line)
    print(f"note: {len(rows)} note(s)"
          + (f", {len(signals_by_path)} with staleness signals" if stale_only else ""))
    return 0


def _show(args: argparse.Namespace) -> int:
    anchor_to_git_root("note")
    ref = args.ref
    candidates = [p for p, _cls, _t in _iter_implemented()
                  if ref in p.as_posix() or p.stem.startswith(ref)
                  or p.name.startswith(ref)]
    if not candidates:
        print(f"note: no implemented note matches '{ref}'", file=sys.stderr)
        raise SystemExit(2)
    if len(candidates) > 1:
        names = ", ".join(sorted(c.as_posix() for c in candidates))
        print(f"note: '{ref}' is ambiguous ({names})", file=sys.stderr)
        raise SystemExit(2)
    try:
        print(candidates[0].read_text(encoding="utf-8-sig"), end="")
    except OSError as e:
        print(f"note: cannot read {candidates[0]}: {e}", file=sys.stderr)
        return 2
    return 0


def _check(_: argparse.Namespace) -> int:
    anchor_to_git_root("note")
    from . import audit_notes as an
    from . import verify_notes as vn
    rc = vn.main([])
    if rc != 0:
        return rc
    # D-references of implemented notes against the decisions table
    known = an._known_decisions()
    if known is None:
        return 0
    violations = 0
    table = _configured_path()
    for p in sorted(NOTES_IMPLEMENTED.rglob("*.md")):
        try:
            text = an.EXTERNAL_D_RX.sub("", p.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError) as e:
            print(f"note check: cannot read {p}: {e}", file=sys.stderr)
            return 2
        for d in sorted(set(an.D_REF_RX.findall(text)), key=int):
            if f"D{d}" not in known:
                print(f"{p}: references D{d}, not in {table}")
                violations += 1
    if violations:
        print(f"note check: {violations} dangling D-reference(s)")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov note", description="Note scaffold and pre-commit check."
    )
    # #138: no `required=True` — a shadowed pre-3.7 argparse backport
    # rejects the kwarg; the rule is enforced by hand below instead.
    sub = parser.add_subparsers(dest="subcommand")
    p_new = sub.add_parser("new", help="scaffold a note (pre-validates class and D-ref)")
    p_new.add_argument("--class", dest="note_class", required=True,
                       help=f"one of: {', '.join(CLASSES)}")
    p_new.add_argument("--ref", default=None, help="decision anchor, e.g. D6")
    p_new.add_argument("title", help="the note's title")
    p_new.set_defaults(func=_new)
    p_check = sub.add_parser("check", help="format + placement + D-refs, now")
    p_check.set_defaults(func=_check)
    p_list = sub.add_parser("list", help="list implemented notes (path — title)")
    p_list.add_argument("--class", dest="note_class", default=None,
                        help=f"filter to one class ({', '.join(CLASSES)})")
    p_list.add_argument("--json", action="store_true",
                        help="one JSON array on stdout")
    p_list.add_argument("--stale", action="store_true",
                        help="only notes carrying audit-notes staleness "
                             "signals (dead commands, unknown flags, "
                             "dangling D-refs) — the audit -> archive "
                             "handoff, machine-readable")
    p_list.set_defaults(func=_list)
    p_show = sub.add_parser("show", help="print one implemented note (id or path prefix)")
    p_show.add_argument("ref", help="filename, stem, or path substring (e.g. 2026-09-15-plane)")
    p_show.set_defaults(func=_show)
    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        parser.error("a subcommand is required (new|check|list|show)")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
