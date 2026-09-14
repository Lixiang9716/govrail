# Agent Note: docker e2e batch 21 — dir x count composition, and --any across a bilingual pair

Status: implemented

Related: the docker matrix + batches 1-20 notes (same series), D17 (the
dir format's structural-conflict-freedom), D18 (--any's relaxation and
ranking), batch 11 (the bilingual postmortem pair this deepens)

## Problem

Two compositions stayed dark. `next --count N` x DIR format — the dir
scan and the counter must agree (D2/D3 from a D1-seeded dir, shifting
to D3/D4 after a real add lands D2-*.md) — had no walk; a disagreement
would mean the counter and the scanner read the corpus differently.
And --any across a BILINGUAL pair — en side carries one term, zh side
the other — is the exact case --any exists for (strict AND misses both
sides; --any ranks each with one term matched), pinned only by unit
fixtures until now.

## Decision

- **next_count_dir** (45th scenario): dir format, D1 seeded as its own
  file — `next --count 2` = D2/D3; after `decision add` lands
  D2-*.md (exactly one file), the count shifts to D3/D4; verify green.
  The scanner and the counter agree across an add.
- **postmortem_recall_any** (46th): a bilingual postmortem pair where
  each side carries ONE of two terms — the strict AND misses both
  entries (exit 1, "no match"), --any ranks BOTH (exit 0, both files
  named). One corpus, two languages, two honest answers to the same
  query, both pinned.

A debug lesson repeated from batches 8/9: my probe's `git branch -a`
ran without `cd /work` and reported "not a git repository" — the probe
was wrong, not the state. And the scenario's first draft repeated the
other direction: a revision that overwrites the zh postmortem without
keeping a hit term makes recall's miss correct and the fixture wrong.
Both now stand as assertions.

## Alternatives considered

- **next --count in TABLE format** — batch 14's decisions_formats
  walks table add/verify; count-over-table rides the same scanner and
  adds no new contract beyond what decisions_dir pins.
- **--any with THREE terms and rank ordering by count** — rank
  semantics are recall's unit-tested surface; the E2E pins the
  language-pair case an adopter actually hits.
MD
