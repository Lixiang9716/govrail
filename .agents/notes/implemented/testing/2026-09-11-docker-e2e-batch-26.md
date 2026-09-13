# Agent Note: docker e2e batch 26 — --any's two ranking keys crossed, and the cross-conflict preflight

Status: implemented

Related: the docker matrix + batches 1-25 notes (same series), D18
(recall's --any relaxation and ranking), D51 (the staged integrator's
conflict path), rule 6

## Problem

Two composition depths stayed dark. --any's ranking has TWO keys —
terms matched first, where-it-hit as tie-break — and batch 22 pinned
single-term ordering (the tie-break alone); a CROSSING corpus (one
entry with 2/2 terms in its BODY vs one with 1/2 in its TITLE) is the
case that proves terms-matched is the PRIMARY key over where. And
run --merge's conflict path was walked with two branches — the
three-branch topology where the collision emerges at step 3 (after two
clean steps) had no walk.

## Decision

- **recall_any_multiling** (54th): a 2/2 body entry vs a 1/2 title
  entry — the pinned order is body-2/2 FIRST, title-1/2 SECOND: terms
  matched is the primary key, where-it-hit only breaks ties within the
  same count.
- **merge_conflict_cross** (55th): three branches where shared-a and
  shared-c both touch shared.txt — the preflight fails at the step
  naming the collision, the scene is kept, and the summary shows the
  already-merged set at the moment of failure.

## Alternatives considered

- **Also pin --any's archived demotion across ranks** — batch 22's
  fixture walks it; composing archived demotion WITH crossing terms
  would test two keys in one flake domain.
- **A three-branch merge with a conflict at step 2 of 3** — the scene
  preservation and summary contract are the same as step 3; step 3 is
  the minimal deterministic case (two clean merges must precede it).
MD
