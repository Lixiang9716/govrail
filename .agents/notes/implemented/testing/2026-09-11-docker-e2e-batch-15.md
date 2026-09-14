# Agent Note: docker e2e batch 15 — decisions migration and the receipt across a squash merge

Status: implemented

Related: the docker matrix + batches 1-14 notes (same series), D17 (the
decisions formats), D44 (receipts match trees, not commits — the
squash-merge promise this walks)

## Problem

Two adoption-realistic journeys had no E2E. A project MIGRATING its
decisions source between formats (sections to table and back) had no
walk: numbering continuity across the migration, allocation continuing
from the migrated end, verify accepting both shapes of the same
content. And D44's flagship receipt promise — "matches across a squash
merge too: the commit sha moves, the tree does not" — was pinned by
unit tests but never walked as an adopter lives it: receipt on a
branch, squash-merge into the default branch, verify against the NEW
head.

## Decision

- **decisions_migration** (31st scenario): sections era (D1 seeded, D2
  added through the CLI, next = D3) -> mechanical migration to table
  rows + format flip -> verify green on the migrated table and `next`
  still says D3 -> D3 added as a row in the migrated format -> reverse
  migration to sections -> verify green, next = D4. Both formats accept
  the same decision content; numbering continuity is the invariant.
- **receipt_squash** (32nd): receipt recorded on a feature branch,
  squash-merged into the default branch (new sha, identical tree),
  `receipt verify HEAD` green; negative control COMMITS a different
  tree and expects red (an uncommitted edit changes nothing about the
  recorded tree — verify matches trees, so the negative control must
  move the committed tree, which the first draft got backwards).
- Both scenarios compose with the earlier arcs rather than duplicating
  them: decisions_migration rides the loader's both-formats contract
  (D17); receipt_squash rides the tree-match contract (D44) and pins
  the squash-merge mechanics (default branch captured BEFORE the
  feature branch exists — capturing it after made checkout a no-op and
  the merge staged nothing).

## Alternatives considered

- **`gov migrate` command for format conversion** — a real product
  idea, but this drill pins the ADOPTER journey (hand-convert + config
  flip + verify), which works today; a conversion command is a product
  decision with its own contract.
- **Verify across a REBASE instead of a squash** — same tree-match
  property, harder to stage deterministically; squash is the shape
  teams actually ship.
