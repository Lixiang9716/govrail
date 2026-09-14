# Agent Note: docker e2e batch 19 — the count x base composition, and dir format's parallel-safety raced for real

Status: implemented

Related: the docker matrix + batches 1-18 notes (same series), D17 (the
decisions formats; dir's structural-conflict-freedom claim), D40 (the
base-aware allocation), batch 9 (the sections-format same-race fix)

## Problem

Two composition surfaces stayed dark after batch 14/18. `next --count
N` x `--base`: after a sibling lands D2, does the multi-allocation
count shift to D3/D4 when the base is consulted? And dir format's
headline claim — "parallel appends are structurally conflict-free" —
had never been RACED for real in E2E: batch 9's sections-format fix
serialized the lock, but dir format's two-process same-id race (the
mutual-exclusion edge) had no walk.

## Decision

- **next_count_base** (40th scenario): a sibling branch lands D2
  through the tool itself; the STALE `next --count 2` says D2/D3 while
  the BASE-AWARE `next --count 2 --base agent-a` says D3/D4 — the
  advice changes when the base is consulted. Deterministic: the
  sibling's D2 is committed before the counts are read.
- **decisions_dir_parallel** (41st): two REAL processes race for the
  SAME D2 in dir format. Deterministic contract: exactly one exit 0,
  the other exit 1 (already exists, named loudly), the winner's file
  present, the seed untouched, verify green — and a sequential D3
  lands after (different decisions never conflict; each is its own
  file). The first draft raced D2 against D3 with different ids, which
  hit the contiguity validator NON-deterministically (whichever
  process validated before the other's file landed refused "skips
  D2") — mutual exclusion, not ordering, is the deterministic contract
  of a race.

## Alternatives considered

- **Assert the non-deterministic D2/D3 race** — a scenario that passes
  on scheduling luck is a flake factory; mutual exclusion is the
  deterministic contract of a race.
- **trend --cost --by-tag deepening** — that composition is a REFUSAL
  by design (cost already groups by caller; batch 8's scenario asserts
  the exit 2), nothing to deepen.
- **20k nightly tier tuning** — the 10k measured actuals (2.3s/5.6s vs
  60s/120s) hold 20x headroom; tuning before a real wall-clock
  complaint is churn. Deferred.
MD
