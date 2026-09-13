# Agent Note: docker e2e batch 23 — the table format's gap/skip/duplicate edges, and --any's term-count ranking

Status: implemented

Related: the docker matrix + batches 1-22 notes (same series), D17 (the
table format: D0-legal, options-cell mandatory), D40 (the gap-fill vs
skip refusal semantics), rule 3 (a decision without what it beat)

## Problem

The table format's gate-time EDGES — a numbering GAP (D0/D2 with no
D1), a SKIP refusal (--id D4 when D3 is next free), a DUPLICATE number
— had no CLI journey: batch 14 walked the happy rows, batch 23's
drafts walked nothing of the refusal surface. And --any's
terms-matched RANKING (2/2 beats 1/1 regardless of where they hit)
had no E2E.

## Decision

- **table_edges** (48th scenario): the gap named loudly (missing: D1)
  → FILLING it via --id D1 is legitimate (verify turns green) → a SKIP
  (--id D4 when D3 is next free) is refused naming the skipped number
  → a DUPLICATE D0 is named. Each edge asserted through the CLI, and
  the fixture corrected MY OWN reading twice: filling a gap is
  legitimate (I first asserted it refused); the refusal fires on
  SKIPPING.
- **recall_any_multilingual** (49th): an entry matching 2/2 query
  terms (title: hedge + exposure) outranks an entry matching 1/2
  (title: Hedge, case-insensitive) — the "matched k/N" cell and the
  ordering both pinned.

## Alternatives considered

- **--base pre-partitioning branch in the same scenario** — the
  base-aware skip refusal is D40's cross-branch semantics; batch 14's
  table walk and the batch-11 dir drill cover the surrounding
  behavior. Kept this drill on same-branch edges.
- **Assert the exact refusal message for the skip** — the message
  names the skipped number ("skips D3") which IS asserted; the rest of
  the wording is presentation.
MD
