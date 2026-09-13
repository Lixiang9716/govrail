# Agent Note: docker e2e batch 20 — the cost roll-up's ordering pinned, and recall across three corpora

Status: implemented

Related: the docker matrix + batches 1-19 notes (same series), D45 (the
cost ledger's roll-up shape), D30 (the review dossier), #148 (recall
across corpora)

## Problem

Two read-side DETAILS had no journey. trend --cost's caller ORDER
(alphabetical with (untagged) first — paren sorts before letters) and
its MULTI-UNIT row (one run reporting tokens AND calls produces two
cells, each with its own early/late split) were unpinned E2E — a
reordering or a merge would have passed silently. And the review
dossier's recall section had only been walked with a notes corpus
(batch 13): the decisions source and the postmortem corpus — the
other two classes the statement counts — had never been asserted as
hits in ONE dossier.

## Decision

- **cost_ordering** (42nd scenario): three runs — beta (tokens=50),
  alpha (tokens=100, calls=2), untagged (tokens=80) — and the roll-up's
  exact output shape is pinned: callers alphabetical with (untagged)
  FIRST (paren < letters), and a multi-unit run renders each unit as
  its OWN early/late cell ("calls 2 (0 early → 2 late); tokens 100
  (0 early → 100 late)") — neither merged into a total nor reordered.
  The first draft asserted a joined total; the tool's real format
  taught the fixture, and the fixture now pins the teaching.
- **review_dossier_corpora** (43rd): a diff touching
  fx/hedge-rates.py with three seeded corpora (implemented note,
  decisions entry, postmortem) — the dossier's recall section names a
  hit from EACH in one block. The reviewer reads every memory that
  mentions the change, from every corpus the statement counts.

## Alternatives considered

- **Assert the single-unit cell merge ("tokens 100 total")** — the tool
  deliberately reports per-unit cells with their own splits; asserting
  a merged total would pin a format that does not exist.
- **Also walk review --grade over the three-corpora dossier** — batch
  7/16 cover the grade loop's stdin contract; the corpora walk is the
  new surface, and composing it with grading would test two things in
  one flake domain.
MD
