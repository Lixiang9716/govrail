# Agent Note: docker e2e batch 38 — upgrade never writes, and every ledger writer anchors to the main checkout

Status: implemented

Related: the docker matrix + batches 1-37 notes (same series), D23
(the two-step upgrade philosophy), #23/D32 (the shared history
anchor), worktree_history (the run-ledger half this completes)

## Problem

Two "the tool never surprises the adopter" promises were half-pinned.
`gov init --upgrade` calls itself a report, but no scenario proved a
customized project survives it — the BOTH-MOVED diff naming the
local gate id, the stale manifest still naming itself, and nothing on
disk rewritten. And the shared-history anchor was pinned only for
`gov run`: stats --record and check --record (two newer writers
through the same module) had no worktree journey — a regression that
anchored them to cwd would fragment ledgers per worktree and nobody
would notice.

## Decision

- **upgrade_preserves_local**: a project with its own my-gate and a
  stale manifest runs `init --upgrade` — the report says "nothing is
  changed by this report", the gates.json line is "BOTH MOVED — merge
  by hand" with my-gate IN the printed diff, and after the run
  my-gate is still on disk and the manifest still reads 0.1.0. The
  upgrade's honesty (report-only) is the contract, not a side effect.
- **worktree_ledgers**: from a linked worktree, `stats --record` and
  `check --record` both land in the MAIN checkout's stats.jsonl (two
  lines: the kindless stats line, the kind=check line), and the
  worktree grows no .gov/history of its own — the anchor module's
  worktree-awareness holds for every writer that routes through it.

## Alternatives considered

- **Also pin `init --upgrade --json` here** — manifest_drift already
  pins the machine report (initialized_with / package); this scenario
  pins the HUMAN report's honesty and the disk's untouched state.
- **Extend worktree_history instead of a new scenario** — that
  scenario pins the run ledger's ONE writer; cramming two more into
  it would blur which writer regressed. One scenario per promise.

## Verification

Host: both scenarios PASS first run; pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 74/74, cross×3 PASS.
