#!/usr/bin/env python3
"""The tracked ritual ledger — audit evidence that lives in git, not in
deletable local storage.

Two operations are RITUALS: they accept a new constitution state and
are lawful only as deliberate, recorded decisions:

- running with `--allow-unsealed-config` (a config outside the sealed
  plane was executed);
- re-baselining the seal (`verify-plane --write`).

Their receipts used to live only in gitignored `.gov/history/` — an
agent could `rm -rf .gov/history/` and erase the evidence with zero git
residue (N9). This ledger is TRACKED: init/`git add` commits it, every
append shows in `git status`, and deleting it is a tracked deletion no
reviewer can miss. History rewrite is the only silent erasure left, and
that is outside any worktree tool's threat model.

Fail-loud (rule 5): if the ledger cannot be appended, the caller
REFUSES the ritual — an unrecorded bypass is worthless.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:  # package context (`gov ...`)
    from .verify_plane import _identity
except ImportError:  # direct script execution
    from verify_plane import _identity

PROG = "rituals"
LEDGER = Path(".gov/rituals.jsonl")


def append(root: Path | None = None, *, ritual: str, **details) -> Path:
    """Append one ritual line; return the ledger path.

    The ledger is TRACKED (init does not gitignore it; the seeding
    commit includes it): every append is a visible working-tree change,
    its deletion a visible deletion, and git history preserves past
    entries — the tamper-evidence the seal system promises.
    """
    root = root or Path.cwd()
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ritual": ritual,
        "caller": _identity(),
        **details,
    }, ensure_ascii=False, sort_keys=True) + "\n"
    ledger = root / LEDGER
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    return ledger


def main(argv: list[str] | None = None) -> int:
    try:
        from .root import anchor_to_git_root
        anchor_to_git_root(PROG)
    except ImportError:
        pass
    root = Path.cwd()
    ledger = root / LEDGER
    if not ledger.is_file():
        print(f"{PROG}: no ritual ledger at {ledger} — no rituals recorded")
        return 0
    n = 0
    with ledger.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                entry = json.loads(line)
                print(f"{entry.get('ts', '?')}  {entry.get('ritual', '?'):24} "
                      f"{entry.get('caller', '?')}")
            except json.JSONDecodeError:
                print(f"{ledger}: UNPARSEABLE LINE — the ledger is "
                      "tamper-evident, not tamper-proof; investigate "
                      "(rule 5)")
                return 1
    print(f"{PROG}: {n} ritual(s) recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
