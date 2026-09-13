# Agent Note: docker e2e batch 22 — --any rank ordering, and next --count over the table format

Status: implemented

Related: the docker matrix + batches 1-21 notes (same series), D18
(recall's --any relaxation and ranking), F4 (current authority over
frozen evidence — the tie-break the ranking pins), D17 (table format's
D0-legal numbering)

## Problem

--any's RANKING (where a term hit: title 3 > heading 2 > body 1, with
archived demoted within a rank) had no E2E: unit tests pinned the
comparator, but the CLI journey — three notes, one term, three ranks —
never asserted the printed order. And `next --count` had no TABLE
format walk: tables number from D0 (legal there), and the count over
D0/D1 rows had no journey.

## Decision

- **recall_any_ranking** (47th scenario): three notes with the term at
  three ranks — the --any print order must be title > heading > body.
  Then an ARCHIVED title-match joins: same rank, frozen evidence — F4
  demotes it to AFTER its live peers. The pinned order: live title
  match, archived title match, heading match, body match.
- **next_count_table** (48th): two seeded rows (D0/D1 legal for
  tables), `next --count 2` prints D2/D3; a real add lands the D2 row
  and the count shifts to D3/D4; verify green throughout.

A test-iter lesson repeated from batches 8/9/16: my assertions
initially included the tally line ("recall: 3 partial hit(s)... ranked
by terms matched") because it contains the word "matched" — the filter
now requires the ` — matched ` hit separator AND excludes "recall:"
lines. The batch-12 dict lesson also held: the batch-16 patch's silent
no-op dict insert was caught by counting PASS lines; batch-22's
insertions are asserted.

## Alternatives considered

- **Pin --any's rank TIE-BREAKS beyond F4** — the comparator's third
  key (path) is implementation detail; the contract is rank + archived
  demotion, both pinned.
- **next --count over DIR format** — batch 21 pinned it (D2/D3 ->
  D3/D4 across an add); the table walk completes the format matrix.
