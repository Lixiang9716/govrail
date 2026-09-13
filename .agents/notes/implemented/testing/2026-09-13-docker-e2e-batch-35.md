# Agent Note: docker e2e batch 35 — the preset flow lands gates without stepping on the project's own

Status: implemented

Related: the docker matrix + batches 1-34 notes (same series), D53
(typed adoption bundles), D39 (the gates.json schema the merge must
pass)

## Problem

`gov preset` — list/show/apply, the typed adoption path (D53) — had
no e2e journey: every preset guarantee lived in unit fixtures. The
promises an adopter actually feels are cross-surface: show is
read-only while apply writes; the merge is additive against a
gates.json the PROJECT has customized (its own gate ids and mode
slots must survive); a second apply is a loud no-op rather than a
silent rewrite; an unknown preset names the available ones instead of
guessing.

## Decision

- **preset_adoption_bundle**: list names all three shipped bundles;
  show prints the bundle (gates, mode deltas, the read-only hint) and
  leaves gates.json byte-identical; a project that has declared its
  OWN gate (my-gate, in gates[] and in mode all) applies python-lib —
  my-gate keeps its id and its mode slot, pytest/build join in preset
  order at the tail; the second apply reports "nothing to add /
  already adopted — nothing written" (exit 0); an unknown name exits
  2 naming the available presets. The scenario's first run also
  demonstrated the schema refusal from the inside: my fixture's
  initial gate carried a key the gates.json schema does not know, and
  apply refused the WHOLE merge naming the key — rule 5 working on a
  typo'd adopter, which is exactly the composite this scenario pins.

## Alternatives considered

- **Apply every shipped preset** — three bundles × their mode
  injections is the same merge code three times over; python-lib is
  representative (gates + two mode extensions), and the schema refusal
  path is the part worth the container seconds.
- **Pin `gov init --preset`** — same apply core with a different
  entry flag; the init surface is already pinned by lifecycle.

## Verification

Host: preset_adoption_bundle PASS; pytest 478 passed / 2 skipped,
self-test 62 all pass, `gov run --mode all` 10 gates pass. Docker:
all eight inner-suite cells at 69/69, cross×3 PASS.
