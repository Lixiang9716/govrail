# Agent Note: docker e2e batch 28 — the split's boundary equality, the evidence prompt's edges, and the nightly budgets tightened

Status: implemented

Related: the docker matrix + batches 1-27 notes (same series), #119
(the --base split's naming), D30 (the grade loop's transcription
contract), the batch-24 measured firsts (10k: stats 2.3s, check 5.6s)

## Problem

Three edges had no journey. The --base split's BOUNDARY (a run whose
ts exactly equals the base commit's date — `<=` lands early) was
unpinned; the evidence prompt's EMPTY answer (the "(no evidence
given)" fallback) and the q-discards-accumulation behavior were pinned
only by unit fixtures; and the nightly budgets (600s over 2-6s
actuals) were formalities a 100x walker regression could hide inside.

## Decision

- **trend_split_boundary**: three runs AT/BEFORE/AFTER the backdated
  base commit's date — the AT run groups with BEFORE (p50 150ms from
  [100,200]), the AFTER run alone in late (400ms), the mover line
  150ms → 400ms pinned. Hand-computed, deterministic.
- **grade_evidence_edges** (58th... the evidence prompt's edges): an
  f with an EMPTY answer falls back to "(no evidence given)" — still
  a fail verdict, still request-changes; and a q AFTER accumulated
  verdicts DISCARDS them (the verdict block never appears, quit
  blocks). The fixture needed TWO rubric items so the q lands
  mid-loop — with one item the loop ends before the q is read.
- **perf_night_budgets**: the nightly tier's budgets TIGHTEN to
  measured x ~20 headroom (stats 600s -> 60s, check 600s -> 120s) —
  a gross walker regression can no longer hide inside a 600s
  formality. Measured firsts recorded in the scenario output.

## Alternatives considered

- **Pin the strict-AND exit-1 in the bilingual scenario** — batch 21's
  postmortem_recall_any already pins it; the batch-28 edges scenario
  covers the empty-evidence and quit edges instead.
- **Keep the 600s nightly ceilings** — a ceiling 260x the measurement
  is a formality; tightening with 20x headroom keeps slow-runner
  flake out while a gross regression surfaces.
MD
