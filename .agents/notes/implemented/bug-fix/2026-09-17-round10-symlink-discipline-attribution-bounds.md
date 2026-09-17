# Agent Note: round 10 — symlinks that could not be followed, mentions that must stand alone, and the machine-interface contract

Status: implemented

Related: D56

## Problem

The tenth external review round, one HIGH reproduced by the reporter in
both directions:

- N10: nothing in the plane refused a symlink planted on a state path.
  A `.gov/rituals.jsonl` or `.gov/history/gates.jsonl` pointing outside
  the repository turned every honest writer into a courier — ritual
  records with caller identity, or full gate output, appended to a file
  an attacker pre-planted (a FIFO would stream it live). `.gitignore`
  as a symlink was read THROUGH (external content copied into the
  tracked file) and then replaced by a plain file.
- N11: strict note attribution matched bare substrings, so a note
  saying "renamed mysrc/auth/login.py.bak away" permanently attributed
  `src/auth/login.py` — one fat note silenced strict mode forever.
- N12, the structural item's third appearance: the round-7 atomic-write
  fix had landed only in `_copy`; `_install_hook`, `_install_ci` and
  the new-`.gitignore` branch were still torn-write traps, and trend's
  `--stats` reader crashed on a non-object ledger line exactly like the
  gates.jsonl reader used to.
- N14: error prose on stdout (rituals, review), an undocumented
  four-state exit contract, and 25 of 32 commands without `--json`.
- The finding also flagged gates members as strings crashing — probed
  on current master and found ALREADY closed (`load_config` rejects
  `gates[0] must be an object`, mode members, missing ids — all named
  ConfigErrors); recorded here so the item is not silently dropped.

## Decision

One append policy now guards every ledger: `atomicio.append_line` —
single O_APPEND write, fsync, and O_NOFOLLOW plus an lstat precheck
(the precheck is the whole guard on Windows) — and the four appenders
(rituals, gates history, receipts, stats) route through it with
evidence-appropriate verdicts: the rituals ledger refuses the ritual
outright; the receipts ledger refuses the receipt AND its chain-head
read (the head-read refusal lives in `_last_hash`, so even the pre-run
build cannot probe through a link); the trend ledgers warn, write
nothing anywhere, and continue. init pre-flights symlinked `.gov` and
symlinked `.gitignore` BEFORE any mutation — a refused adoption never
half-writes. The hooks, workflow, and fresh-`.gitignore` writes go
through `atomicio.write_bytes`, closing N12's remaining torn-write
sites. Attribution requires the path to stand as its own token
(lookaround-bounded, so backticked mentions still count). trend's
`--stats` skips non-object lines like its sibling. D56 locks the
machine-interface contract: errors never on stdout, the exit-code
vocabulary in `gov --help`, and `--json` promoted on demand along the
existing one-value shape.

## Alternatives considered

Realpath containment on every read (the finding's other half) —
adopted only where a read can leak (the receipt chain head); for
sealed configs the content hash already catches a redirected read
(proven by the finding itself on gates.json), and hashing copies of
the containment logic would add a second mechanism to drift. Warn on a
symlinked .gitignore instead of refusing — rejected: the useful
outcomes (append the ignore line INTO the linked file, or replace the
link) are exactly the two attacks; refusing is the only honest move,
and it pre-flights so nothing half-lands. Ship --json for all 25
commands now — rejected in D56: interfaces designed before their
second consumer are guesses with test suites.
