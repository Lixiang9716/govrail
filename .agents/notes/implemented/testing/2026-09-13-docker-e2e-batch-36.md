# Agent Note: docker e2e batch 36 — non-positive windows refuse loudly, and the --last slice is visible in the verdict

Status: implemented

Related: the docker matrix + batches 1-35 notes (same series), rule 5
(fail loud, name the value), #119/--last (the trend window),
D40/--count (the allocation window)

## Problem

Two machine-facing window parameters could silently mean "nothing":
`decision next --count -3` printed an EMPTY stdout (a caller reads
that as "no decisions exist"), and `trend --last -1` silently emptied
the window (`runs[-n:]` with negative n slices from the FRONT, `0`
yields `[]` — an empty trend that reads as "no runs exist"). Both are
the quiet-lie shape rule 5 exists for: the command succeeds while the
answer is not what was asked. Neither edge had a test of any kind.

## Decision

- **The product fix**: `--count < 1` (decision next) and `--last < 1`
  (trend) exit 2 naming the value and the floor. Two unit tests pin
  both refusals.
- **window_edges** pins the refusals AND the positive semantics the
  refusal protects: `--count 3` prints three consecutive D-numbers,
  and `--last` is a REAL slice — a 4-run ledger reads p50 100ms →
  200ms on the full window but 300ms → 100ms under `--last 2`, the
  opposite verdict from the same file, so the slice cannot regress to
  "ignored" without this scenario going red.

## Alternatives considered

- **Clamp instead of refuse** (treat --last -1 as 1, --count 0 as 1) —
  hides the caller's bug behind a plausible answer; the refusal names
  the value so the caller fixes the call.
- **Only unit tests** — the refusals are one `if` each, but the e2e
  also pins that the POSITIVE windows still compose with the CLI in a
  real project (the unit fixtures hand-build the ledger; the scenario
  proves the same slice through `gov trend` on disk).

## Verification

Host: window_edges PASS; pytest 480 passed / 2 skipped (two new),
self-test 62 all pass, `gov run --mode all` 10 gates pass. Docker:
all eight inner-suite cells at 70/70, cross×3 PASS.
