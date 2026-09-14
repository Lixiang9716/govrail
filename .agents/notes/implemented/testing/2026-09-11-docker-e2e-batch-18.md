# Agent Note: docker e2e batch 18 — multi-allocation, and the recall corpus's two exits

Status: implemented

Related: the docker matrix + batches 1-17 notes (same series), D17 (the
decisions formats and numbering), D18 (recall's exit contract: 0 hit /
1 corpus-miss / 2 no-memory), #148 (the miss diagnostics)

## Problem

Two read-side contracts had edges with no journey. `decision next
--count N` — the multi-allocation surface — was pinned only by unit
fixtures; the E2E questions "does the count CONTINUE from the landed
end after a real add" had no walk. And recall's exit contract had a
two-tier boundary that only one tier had E2E: exit 1 (corpus exists,
term missing) was covered by batches 5/11, but exit 2 — NO memory
sources at all, "is this a project root?" — had never been walked in a
container, and its fixture shape (a project with NO notes, NO
decisions, NO postmortems) is exactly what a brand-new adopter has on
day one.

## Decision

- **next_count_allocation** (35th scenario): `next --count 3` over a
  D1-seeded source prints exactly D2/D3/D4, one per line; after a real
  D2 add, `next --count 2` prints D3/D4 — allocation follows the
  source, not a fixed window. verify-decisions stays green throughout.
- **recall_corpus_boundaries** (36th): the corpus statement's three
  phases. Phase 1: NO sources → exit 2 "no memory sources found — is
  this a project root?" with the three-zero statement — a stricter
  boundary than term-miss (exit 1 means the corpus EXISTS and lacks
  the term). Phase 2: an archived-only note → the statement counts
  archived 1, the hit names the sealed document. Phase 3: a decisions
  source joins → the statement counts `decisions 1 (docs/
  decisions.md)`. Every invocation states what was searched — the
  boundary contract is that a miss is never ambiguous about WHICH
  corpus was missed.

## Alternatives considered

- **Fold both into existing scenarios** — next_count rides
  decisions_formats' format matrix, recall boundaries ride
  postmortem_recall's corpus — but each composition pins a DIFFERENT
  contract (multi-allocation arithmetic; the two-exit boundary), and
  separate named scenarios keep failures diagnosable.
- **20k nightly tier tuning this batch** — the 10k measured actuals
  (2.3s/5.6s vs 60s/120s ceilings) have 20x headroom; a 20k tier adds
  minutes for no new assertion. Deferred until a real 10k+ project
  reports a wall-clock complaint.
MD
