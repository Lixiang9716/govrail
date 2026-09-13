# Agent Note: docker e2e batch 17 — the grade loop's conservative edges, and the preset journey on the real specimen

Status: implemented

Related: the docker matrix + batches 1-16 notes (same series), D30 (the
review workbench), D53 (presets), the demo specimen (D33's living
example), rule 5

## Problem

Two more adoption-facing surfaces had no journey. The grade loop's
conservative edges — q quits, EOF aborts, an unrecognized key is
skipped — were pinned only by unit fixtures; the E2E question "what
does a reviewer's fat finger do to the verdict" had no walk. And the
preset adoption journey ran only against scratch projects: the REAL
specimen (the demo, batch 12's repair) had never received an
agent-heavy apply, so the additive adoption contract was untested
against a project whose gates.json already carries customized gates.

## Decision

- **grade_quit_skip** (33rd... the conservative edges, every cell):
  q at the first prompt blocks (exit 1, "review: grade quit", NO
  verdict block — an aborted review is never an approval); unrecognized
  keys are skipped without a verdict (a human's typo is never
  transcribed; an empty verdict list approves with zero blockers); and
  input END aborts with the same conservative shape. The contract is
  asymmetry with intent: quit/EOF block, typos don't.
- **preset_on_specimen** (34th): the demo copy — no manifest — refuses
  preset apply (exit 2, naming gov init); `gov init` adopts it for
  real; agent-heavy apply lands ADDITIVELY (verify-decisions gate
  merges in, the specimen's OWN gates — including its `archive` gate —
  preserved, parallel-workers skill lands, manifest hint written);
  re-apply is idempotent ("already adopted"); governance mode runs
  green and the full repaired DAG stays green WITH the adoption.
  One assertion lesson: the specimen's gate is named `archive` (its
  own naming from the batch-12 repair), not the repo's
  `verify-archive` — asserting the repo's name failed while the
  CONTRACT (own gates preserved) held.
- **The dict-insertion discipline from batch 12 is now load-bearing**:
  the batch-16 patch inserted the new dict entries without an assert
  and the silent no-op was caught by counting PASS lines (31 vs 33).
  Every future batch patch asserts both the def block AND the dict
  entries.

## Alternatives considered

- **Treat q as approval-neutral (exit 0)** — an aborted review that
  exits 0 would let "reviewer walked away" read as "reviewer approved"
  in any caller checking exit codes; conservative blocking matches the
  pre-push gate's stance on ambiguity.
- **Assert preset idempotence by BYTE-diffing gates.json across the
  re-apply** — the apply prints "already adopted" and writes nothing;
  byte-diffing gates.json alone would miss manifest/skill churn. The
  exit + message pins the idempotence contract where it lives.
MD
