#!/usr/bin/env python3
"""Assemble the review dossier for a diff (D28, wish 10).

The code-review skill expects a reviewer to recall first and grade against
the rubric — but assembling the material was four manual commands. This
command produces the dossier in one shot:

1. **Change scope** — surfaces and suggested gates (change-scope's data);
2. **In-scope notes** — notes touched by the diff, and whether the change
   carries one when it should (note-presence's data);
3. **Recall** — memory hits for the change's own keywords (top 5);
4. **Rubric items** — the item list, when the project maintains one
   (three sections, gracefully, when it does not).

Bad refs abort with exit 2 (fail loud). The reviewer — human or agent —
starts from the dossier, not from a cold repository.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from . import change_scope as cs
    from . import recall as rc
    from . import verify_note_presence as vnp
    from . import verify_rubric as vr
except ImportError:  # direct script execution
    import change_scope as cs
    import recall as rc
    import verify_note_presence as vnp
    import verify_rubric as vr

RUBRIC = Path("docs/review-rubric.md")


def _rubric_bodies(text: str) -> dict[str, str]:
    parts = re.compile(r"(?m)^### (R\d+)\b.*$").split(text)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _keywords(files: list[str], limit: int = 5) -> list[str]:
    """Distinctive path tokens of the change — recall terms, not stopwords."""
    stop = {"main", "index", "init", "test", "tests", "src", "lib", "docs",
            "config", "setup", "utils", "core", "app"}
    seen: list[str] = []
    for f in files:
        for token in re.split(r"[/_\-\.]+", Path(f).stem) + [Path(f).parent.name]:
            token = token.strip().lower()
            if len(token) < 4 or token in stop or token in seen:
                continue
            seen.append(token)
    return seen[:limit]


def main(argv: list[str] | None = None) -> int:
    try:
        from .root import force_utf8_stdio
    except ImportError:  # direct-script execution (self-test scratch dirs)
        from root import force_utf8_stdio
    force_utf8_stdio()  # reports leave as UTF-8 on every OS (#168)
    parser = argparse.ArgumentParser(
        prog="gov review",
        description="Assemble the review dossier for a diff (scope, notes, recall, rubric).",
    )
    parser.add_argument("--base", default="HEAD",
                        help="git ref to diff against (default: HEAD — the working tree)")
    parser.add_argument("--hits", type=int, default=5,
                        help="recall hits to include (default: 5)")
    parser.add_argument("--grade", action="store_true",
                        help="grade the rubric items interactively after the "
                             "dossier; emits the code-review verdict block")
    args = parser.parse_args(argv)

    files, err = cs._changed(args.base)
    if err is not None:
        print(f"review: cannot diff against {args.base!r}: {err}", file=sys.stderr)
        return 2
    if not files:
        print(f"review: no changes since {args.base}")
        return 0

    surfaces_cfg = cs._load_surfaces()

    print("## 1. change scope")
    names = sorted({cs._classify(f, surfaces_cfg) for f in files})
    for s in names:
        changed = [f for f in files if cs._classify(f, surfaces_cfg) == s]
        print(f"  {s}: {len(changed)} file(s)")
        for f in changed[:5]:
            print(f"    {f}")
        if len(changed) > 5:
            print(f"    …and {len(changed) - 5} more")
    suggested, from_paths = cs._suggest_gates(files, surfaces_cfg)
    source = "gates.json paths" if from_paths else "surface fallback"
    print(f"  suggested gates ({source}): {', '.join(suggested) or 'code gates'}")

    print("## 2. notes in this change")
    notes = [f for f in files if f.startswith(".agents/notes/")]
    for f in notes:
        print(f"  {f}")
    if not notes:
        exempt_globs, ex_err = vnp._load_exempt_globs()
        if ex_err is not None:
            print(f"review: {ex_err}", file=sys.stderr)
            return 2
        non_trivial = [f for f in files if not vnp._is_trivially_scoped(f)
                       and not vnp._is_exempt(f, exempt_globs)]
        if non_trivial:
            shown = ", ".join(non_trivial[:5])
            more = f" …and {len(non_trivial) - 5} more" if len(non_trivial) > 5 else ""
            print(f"  WARNING: {len(non_trivial)} behavior-bearing file(s) ({shown}{more}) "
                  "with no note change (rule 2)")

    print("## 3. recall (change keywords)")
    terms = _keywords(files)
    if not terms:
        print("  (no distinctive keywords in the diff)")
    else:
        print(f"  terms: {', '.join(terms)}")
        entries = rc._entries()
        scored: list[tuple[int, str, str]] = []
        for e in entries:
            best = None
            for t in terms:
                got = rc._score(e, [t])
                if got:
                    rank, where = got
                    if best is None or rank > best[0]:
                        best = (rank, e.source, where)
            if best:
                scored.append((*best, ) if False else (best[0], best[1], best[2]))
        scored.sort(key=lambda h: (-h[0], "/archived/" in h[1], h[1]))
        if not scored:
            print("  (no memory hits — you may be first; plan the note)")
        for rank, source, where in scored[: args.hits]:
            print(f"  {source} — matched in {where}")

    items = []
    if RUBRIC.is_file():
        print("## 4. rubric")
        text = RUBRIC.read_text(encoding="utf-8")
        items = re.findall(r"(?m)^### (R\d+ — .+)$", text)
        item_bodies = _rubric_bodies(text)
        for heading in items:
            print(f"  {heading}")
            rid = heading.split(" —", 1)[0]
            body = item_bodies.get(rid, "")
            m = re.search(r"\*\*Checks:\*\*\s*(.+)", body)
            anchors = re.findall(r"`([^`]+)`", m.group(1)) if m else []
            shown = 0
            for anchor in anchors:
                if shown >= 2:
                    break
                for f in files:
                    local = Path(f)
                    if not local.is_file():
                        continue
                    try:
                        lines = local.read_text(encoding="utf-8",
                                                errors="replace").splitlines()
                    except OSError:
                        continue
                    for idx, line in enumerate(lines):
                        if anchor in line:
                            lo = max(0, idx - 4)
                            hi = min(len(lines), idx + 6)
                            print(f"    evidence candidate: {f}:{idx + 1}")
                            for ln in lines[lo:hi]:
                                print(f"      {ln[:100]}")
                            shown += 1
                            break
                    if shown >= 2:
                        break
        print("  grade only the items the diff touches, each with evidence")
        print("  (evidence candidates are leads to verify, not verdicts)")
    else:
        print("  (no review rubric — reviewing without one)")

    print(f"review: dossier for {len(files)} file(s) vs {args.base}")

    if args.grade:
        if not items:
            print("review: --grade needs a rubric to grade against",
                  file=sys.stderr)
            return 2
        return _grade(items)
    return 0


def _grade(items: list[str]) -> int:
    """Wish 1/D30: the human decides, the machine transcribes.

    Prompts per rubric item (p/f/s/q), then emits the code-review skill's
    output contract: one line per graded item (Rn — verdict — evidence),
    the blocker list, and the explicit final verdict.
    """
    verdicts: list[tuple[str, str, str]] = []  # (Rn, verdict, evidence)
    print()
    print("grade the items the diff touches — [p]ass, [f]ail, [s]kip, [q]uit")
    for heading in items:
        rid, title = heading.split(" — ", 1)
        try:
            answer = input(f"{rid} — {title} [p/f/s/q]: ").strip().lower()
        except EOFError:
            print("review: grade aborted (input ended)")
            return 1
        if answer in ("q", "quit"):
            print("review: grade quit")
            return 1
        if answer in ("s", "skip", ""):
            continue
        if answer in ("f", "fail"):
            try:
                evidence = input(f"    evidence (file:line or text): ").strip()
            except EOFError:
                evidence = "(no evidence given)"
            if not evidence:
                evidence = "(no evidence given)"
            verdicts.append((rid, "fail", evidence))
        elif answer in ("p", "pass"):
            verdicts.append((rid, "pass", ""))
        else:
            print(f"    (unrecognized '{answer}' — item skipped)")
    print()
    print("--- review verdict ---")
    blockers = []
    for rid, verdict, evidence in verdicts:
        line = f"{rid} — {verdict}" + (f" — {evidence}" if evidence else "")
        print(line)
        if verdict == "fail":
            blockers.append(f"{rid}: {evidence}")
    if blockers:
        print("blockers:")
        for b in blockers:
            print(f"  {b}")
        print(f"verdict: request changes ({len(blockers)} blocker(s))")
        return 1
    print("verdict: approve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
