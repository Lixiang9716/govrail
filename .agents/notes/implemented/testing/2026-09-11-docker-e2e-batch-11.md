# Agent Note: docker e2e batch 11 — the cost/time split composed, and the bilingual postmortem pair

Status: implemented

Related: the docker matrix + batches 1-10 notes (same series), D45 (the
cost ledger), #119 (the --base split), rule 7 (the bilingual pair), the
postmortem corpus (#148's third class)

## Problem

Two composition surfaces stayed dark. `trend --cost --base` — cost
attribution AND the time split in ONE command — had no journey: batch 8
pinned the window halves, batch 10 pinned the --base cut on durations,
but their composition (per-caller attribution across a base-date cut)
was untested. And the postmortem corpus entered recall in batch 5 as
single-language files — a bilingual postmortem PAIR (rule 7's bread and
butter) flowing through pairing AND recall together had no E2E.

## Decision

- **cost_base_split** (23rd scenario): the batch-10 fixture shape
  (crafted ledger, backdated base 2 days ago) on the cost dimension —
  two 100-token runs 3 days old, two 300-token runs now, same caller:
  `trend --cost --base` must report `tokens 800 (200 early → 600 late)`
  and must NOT claim the un-crafted 8 runs. The window-split arithmetic
  and the caller attribution compose; both are hand-checked.
- **postmortem_pair** (24th): a bilingual postmortem pair under
  docs/postmortem — baselined, drifted (zh side moves), red with the
  file named, scoped fix, and recall reading BOTH sides from one corpus
  (`stampede` hits the en file, `缓存雪崩` hits the zh file) — one
  corpus, two languages, no special casing.

A fixture lesson repeated from batch 8's window design: the scenario's
first draft "revised" the zh postmortem by OVERWRITING it without
keeping a hit term — recall's miss (exit 1) was the tool working
correctly and the fixture lying. The revision keeps the root-cause
term; the drift asserts pairing, the recall asserts the read-side, and
neither tests the other by accident.

## Alternatives considered

- **One combined "everything" scenario** — composition is the point of
  these two, but each pins ONE composition (cost×time; pairing×recall);
  a single mega-scenario would blur which composition broke.
- **Dir-format decisions in the cross drill too** — batch 4's drill
  already walks dir format's structural absorption across containers;
  the batch-11 additions cover the ledger read-side instead, where no
  journey existed.
