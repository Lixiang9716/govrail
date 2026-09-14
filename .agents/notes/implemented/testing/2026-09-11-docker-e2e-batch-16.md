# Agent Note: docker e2e batch 16 — three callers across the cut, and a rubric that grows live

Status: implemented

Related: the docker matrix + batches 1-15 notes (same series), #120
(by-tag x --base composition), D30 (the review workbench), the batch-12
dict lesson (applied: every dict entry insertion now asserted)

## Problem

Batch 12 pinned the by-tag x --base composition but only with two
callers, one per side — the STRADDLER case (a caller with samples on
both sides of the cut) was untested, and it is the case where the
composition produces a real comparison instead of a "cannot split"
notice. Separately, review --grade's loop reads the rubric LIVE —
pinned by unit tests on a static file, but the journey property "the
loop asks about the CURRENT standard" had no walk: a rubric that grows
between two grade runs must change what the loop asks.

## Decision

- **by_tag_multi**: three callers straddling a backdated base — alpha
  entirely early, beta entirely late, gamma with samples on BOTH sides.
  Assertions: alpha/beta each report "need at least 2 comparable
  run(s) to split" (their far side is empty — named, not invented);
  gamma produces the real mover `p50 100ms → 300ms (×3.0 ↑)`; and
  first-appearance ordering holds (alpha's group prints before beta's).
- **grade_rubric_evolution**: a one-item rubric grades with exactly one
  prompt; after the rubric file grows to two items (committed, like a
  real governance change), the SAME command asks two questions and the
  two-p stdin approves. The loop reads the live file — no caching, no
  stale copy.

## Alternatives considered

- **A gamma that straddles via MORE alpha-style callers** — dilutes the
  three-way shape; one straddler is the minimal distinguishing fixture.
- **Assert trend's mover THRESHOLD semantics (x1.5) in by-tag** — the
  threshold is trend's own unit-tested surface; the E2E pins the
  composition and the straddler's real comparison, not thresholds.
MD
