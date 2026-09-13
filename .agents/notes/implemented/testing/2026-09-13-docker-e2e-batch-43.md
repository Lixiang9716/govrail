# Agent Note: docker e2e batch 43 — the scope line is load-bearing, and --wait polls instead of failing

Status: implemented

Related: the docker matrix + batches 1-42 notes (same series), rule 1
(check only what changed), #109 (the rerun hint), D52 (--wait/--ttl
lease semantics)

## Problem

Two promises ran only in unit fixtures. Rule 1's runtime half — a
gate whose paths the change does not touch is NOT SELECTED — was
pinned by `test_run_base_scopes_gates_by_paths` asserting on
selection LISTS; nothing proved the unselected gate's command never
RAN (the whole point: the smallest sufficient set is not just
reported, it is not executed). And `acquire --wait S` — the polling
half of the lease vocabulary the cross-container drill only exercises
through expiry — had no journey proving a waiter TAKES the lease when
it frees, rather than failing busy or sleeping the full wait.

## Decision

- **change_scope_skips**: two gates with disjoint paths, one carrying
  a POISON command (`false`). A docs-only change runs
  "1/2 gate(s) selected; out of scope: poison", docs-gate passes, the
  run is green — the poison provably never executed. Then a src
  change selects the poison and the run fails with "1 blocking
  failure". The scope line is load-bearing in both directions.
- **acquire_wait_polling**: A holds a 3s lease; B's `--wait 8`
  acquires after a MEASURED 2.5–7.5s (not instantly busy, not the
  full wait) and the lease is then B's to release.

## Alternatives considered

- **Prove non-execution with a marker file instead of exit 1** — a
  `false` command is stricter: any execution fails the run, no
  filesystem timing involved.
- **Pin the poll INTERVAL** — the contract is "acquires when free,
  within the wait"; the interval is an implementation detail this
  scenario deliberately does not own.

## Verification

Host: both scenarios PASS first run; pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 83/83, cross×3 PASS.
