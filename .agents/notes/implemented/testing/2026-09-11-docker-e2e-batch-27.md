# Agent Note: docker e2e batch 27 — per-caller cost attribution with the global window split

Status: implemented

Related: the docker matrix + batches 1-26 notes (same series), D45 (the
cost ledger's shape), D42 (caller tags), the batch-8/16 window-split
lessons (global halves, per-caller cells)

## Problem

trend --cost's per-caller attribution across the window's GLOBAL
halves had no E2E with multiple callers reporting multiple units:
the roll-up's per-caller early/late cells are where attribution bugs
would live (a caller's units landing in the wrong half, or two
callers' sums merged).

## Decision

- **cost_caller_ranking** (54th scenario): four runs — alpha (100
  tokens/2 calls + 50 tokens/1 call), beta (40 tokens/3 calls + 60
  tokens/1 call) — the roll-up's exact cells pinned: per-caller
  attribution alphabetical, each unit its own early/late cell, with
  the GLOBAL window halves landing alpha's runs entirely in early
  (calls 3, tokens 150) and beta's entirely in late (calls 4, tokens
  100). The first draft asserted the per-caller direction wrong
  (beta's runs are 3-4, in the LATE half — the global split, not
  per-caller halves); the fixture corrected its own arithmetic twice.
- **grade_rubric_contract** (55th): the grade loop's TRANSCRIPTION
  contract pinned: p prints a pass line, f demands the typed evidence
  verbatim in both the item line and the blockers list, the verdict
  names the blocker count — and s skips silently (a skipped item has
  no verdict line at all).

## Alternatives considered

- **Assert the raw history lines instead of the roll-up** — the raw
  ledger is the INPUT; the read-side's contract is the roll-up cells.
- **Per-caller halves instead of global** — the global split is the
  documented trend semantics; pinning per-caller halves would pin a
  behavior that does not exist.
MD
