# Agent Note: docker e2e batch 8 — cost attribution with a hand-computed window split

Status: implemented

Related: the docker matrix + batches 1-7 notes (same series), D45 (the
cost ledger's shape), D42 (caller tags), D15 (window halves)

## Problem

Batch 6 asserted the cost roll-up's GROUPING but not its arithmetic:
"tokens appears in the output" would pass even if the early/late window
split silently swapped sides or dropped the untagged runs. The deeper
surface — per-caller attribution across the window's two halves — is
where attribution bugs would live, and it had no E2E.

## Decision

`cost_attribution` (18th scenario, every cell): eight runs whose order
is DESIGNED against the window-split rule (early = first four runs,
late = last four) so every number is hand-computed — alpha triples
200 -> 600 across the halves (the 3x jump story), beta drains
100 -> 0, and the two untagged runs are attributed to "(untagged)"
0 -> 160 rather than dropped. The assertions read trend --cost's
ROLL-UP cells, not the raw history. The documented refusals are walked
too: `--cost --by-tag` and `--cost --gate` each exit 2 with the reason
(--cost already groups by caller; cost belongs to the run).

Two design lessons the first draft paid for: the window halves are
GLOBAL (first N runs vs last N), not per-caller — a plan that put all
of alpha's runs first gave alpha (800 early, 0 late), testing nothing
about the split; and a single-run caller lands entirely in late
(0 early → total late), which the untagged assertion originally got
backwards. Both are now the fixture's stated arithmetic.

## Alternatives considered

- **Assert raw history lines instead of the roll-up** — the raw ledger
  is the INPUT; the read-side's contract is the roll-up, and that is
  what an operator reads when attributing spend.
- **--base time-split coverage** — commit dates in a seconds-long test
  cannot be ordered reliably against run timestamps; the by-window
  halves carry the same split logic deterministically. The --base path
  keeps its unit coverage.
