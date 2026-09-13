# Agent Note: docker e2e batch 25 — three-branch preflight depth, and the cost roll-up's mixed-tag order

Status: implemented

Related: the docker matrix + batches 1-24 notes (same series), D51 (the
staged integrator: per-step union trees), D45 (the cost ledger), D24
(a gate in no mode is a config error — the rule the fixture tripped)

## Problem

Batch 8-era coverage walked `run --merge` with TWO branches (green +
conflict); the THREE-branch preflight's distinguishing surface — each
step's summary naming the ALREADY-MERGED SET as it grows (<base> → a →
a, b) — had no assertion. And the cost roll-up's ORDER with mixed
tagged/untagged runs — (untagged) sorts FIRST because paren < letters
— was unpinned E2E.

## Decision

- **merge_three_branch** (52nd): three branches rehearsed in one
  preflight; the assertions pin the per-step summaries' already-merged
  sets in order (<base>, a, a, b). The fixture walked the real demo
  gates.json (batch 12's repaired specimen + an "ok" gate) — which
  surfaced a rule-5 chain in MY OWN fixture: adding a gate to gates[]
  WITHOUT wiring it into a mode is a config error (D24) — the runner
  refused, correctly, twice, before the fixture wired it.
- **cost_untagged_multi** (53rd): four runs — untagged, beta, alpha,
  untagged — the roll-up's exact order pinned ((untagged) first:
  paren < letters; then alpha, beta) with honest per-caller counts
  (untagged 2 runs/160 tokens).

## Alternatives considered

- **Assert only the exit code of the three-branch preflight** — the
  already-merged SET is the integration ORDER made visible; asserting
  it is the difference between "it ran" and "it ran in this order".
- **Whole-matrix single invocation** — at 12 cells x 26 scenarios the
  full sweep now exceeds a 40-minute window; run.sh gains no internal
  fix in this batch — the wrapper timeout is the caller's, and the
  per-cell invocations (`--cell`) are the documented way to finish a
  split sweep. Each cell is independent by design (stamps, images),
  which is what makes the split sweep sound.
- **Kata/gVisor runtime cells** — deferred (batch 9 note): no runtime
  plugin here, and stdlib-Python touches no OCI-boundary syscall.
MD
