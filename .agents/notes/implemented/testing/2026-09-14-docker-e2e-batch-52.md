# Agent Note: docker e2e batch 52 — the where collapses to the best hit, and --against walks the same path

Status: implemented

Related: the docker matrix + batches 1-51 notes (same series), #148
(recall's where vocabulary), #147 (the stale-base warning's
pluralization)

## Problem

Two long-tail semantics were unpinned. When a recall term appears in
a note's title AND its body, the where list could legitimately report
either place — the contract says the stronger where wins ("title >
section heading > body"), and nothing pinned that the collapse
happens in BOTH the strict and the --any lines. And `decision next
--against` — the #147 alias for --base — was pinned only by unit
fixtures; its e2e journey through a real branch (numbering union,
stale-base warning with correct SINGULAR pluralization for one
missing row) had no run.

## Decision

- **recall_where_precedence**: a note whose title and body both
  contain "alpha" reports "matched in title" on the strict line and
  "matched 1/1 terms (alpha in title)" on the --any line — one
  mention per term, at the strongest where.
- **decision_against_alias**: a sibling branch lands D2; the trunk's
  `next --count 2 --against sibling` prints D3 D4 with "your base is
  1 row behind" (singular) on stderr — the alias shares --base's
  entire machinery, warning pluralization included.

## Alternatives considered

- **Pin the where list showing BOTH places for one term** — that
  would double-count a single term's presence; the collapse-to-best
  is the documented vocabulary (WHERE = {3: title, 2: headings,
  1: body}) and the scenario pins it.
- **Also pin `--against` with the dir format** — decision_next_base_dir
  owns the dir-format --base composite; the alias shares that code.

## Verification

Host: both scenarios PASS; pytest 481 passed / 2 skipped, `gov run
--mode all` 10 gates pass. Docker: all eight inner-suite cells at
98/98, cross×3 PASS.
