# Agent Note: ritual evidence lives in a tracked ledger

Status: implemented

## Problem

The external red-team's N9: the two constitution-accepting rituals —
running with `--allow-unsealed-config` and re-baselining the seal via
`verify-plane --write` — recorded their evidence only in gitignored
`.gov/history/`. An agent could exercise the ritual flag and then
`rm -rf .gov/history/`: zero git residue, the "recorded ritual" erased.
The seal system had spent three rounds moving its trust anchor into git
history (N2's adoption discriminator, N7's history anchor) while the
ritual audit log itself stayed outside git.

## Decision

`gov/rituals.py` — a TRACKED, append-only ledger at
`.gov/rituals.jsonl`. Every ritual appends one JSON line (ts, ritual,
caller identity, ritual-specific details): unsealed-config runs,
interactive and unattended seal re-baselines, and preset apply's
chain-extending re-baseline. Because the ledger is tracked, the append
is a visible working-tree change, deletion is a visible deletion, and
past entries survive in git history — tamper-evidence through git
itself, the one store an agent cannot rewrite without rewriting
history. Fail-loud (rule 5): if the ledger cannot be appended, the
ritual is REFUSED — an unrecorded bypass is worthless. The seal's own
`last_rebaseline` stays as the latest-state pointer; the ledger is the
append-only sequence.

## Alternatives considered

Keep evidence in .gov/history and let CI assert it "exists and is not
shortened" — rejected: an assertion watches one snapshot; the tracked
ledger makes every state visible continuously, and a shortened history
file would itself need a tracked record to be noticed. Record rituals
in the decisions table — rejected: a ritual is an execution event, not
a decision; mixing them devalues the table's numbering. Rely on the
seal's git history alone — accepted as the backstop it already is, but
the ledger adds the per-event detail (who, when, which ritual) that
history reconstruction cannot cheaply provide.
