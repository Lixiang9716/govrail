# Agent Note: docker e2e batch 32 — recall reads the dir-format decisions source, and the nightly tier learned to scale

Status: implemented

Related: the docker matrix + batches 1-31 notes (same series), D40
(the dir-format decisions source), D32 (one loader for gates and
reads), the batch-28 nightly budget tightening

## Problem

Two read-side composites were unpinned. recall loads its decisions
through `dec.load()` — the same configured source the gates
enforce — but every recall scenario used the default
docs/decisions.md: a project on the dir format (D40, one file per
decision) had no proof its decisions were recallable at all, that the
corpus statement names the configured path, or that a miss still
counts the dir rows. And the nightly tier measured exactly ONE point
(10k files): a walker whose cost grew with a constant-factor
regression (2x slower per file) would look fine forever — a scaling
curve needs at least two points.

## Decision

- **recall_dir_decisions**: a `.gov/decisions.json` pointing at
  docs/decisions/ (dir format), two D-files seeded; recall "hedge"
  names `docs/decisions#D1 — matched in title` (title from the file's
  `## D1 —` section heading, source the DIR path + D-number, not the
  filename), the corpus statement reads "decisions 2 (docs/decisions)"
  on both a hit and a miss.
- **perf_night tiers**: GOV_E2E_NIGHTLY=N walks N×10,000 files with
  budgets scaling by tier (stats < 60·N s, check < 120·N s); run.sh's
  nightly cell walks tiers 1 and 2 — measured seconds stay trivial
  (2.3s/5.6s at tier 1), and 2× files landing inside 2× budget is the
  linearity witness a single 10k point could never give.

## Alternatives considered

- **Bump the nightly default to 20k** — that doubles every scheduled
  run to re-measure a point tier 1 already covers; two adjacent tiers
  give the scaling witness at half the marginal cost.
- **Pin the dir recall source string with the filename**
  (docs/decisions/D1-hedge.md#D1) — that would pin a wish; entries()
  carries (number, title, body) and the source is built as
  `<configured path>#Dn`. The scenario documents the actual shape.

## Verification

Host: recall_dir_decisions PASS; pytest 476 passed / 2 skipped,
self-test 62 all pass, `gov run --mode all` 10 gates pass. Docker:
all eight inner-suite cells at 65/65, cross×3 PASS, and the nightly
cell walking tiers 1 AND 2 — tier 1 (10k) measured stats 2.3s /
check 5.5s, tier 2 (20k) measured 4.5s / 11.1s: the 2×-files-inside-
2×-budget linearity witness, on record. One flake cost a matrix
rerun: both 3.10 cells failed lifecycle's self-test gate once
(test_change_scope_suggests_from_paths, the runner's own diagnosis
said environment-suspect with the clean replay PASSING); 3 full-suite
reruns, a 12× `gov run --receipt` loop, and both cell reruns all
passed 65/65 — never reproduced, logged here as the series' first
environment-suspect flake rather than fixed by wishful patching.
