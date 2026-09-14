# Agent Note: docker e2e batch 34 — the stats ledger's write side, and audit-notes' staleness signals

Status: implemented

Related: the docker matrix + batches 1-33 notes (same series), D54
(the stats ledger), check --record (batch 31's half of the same file),
the archive-agent-notes skill (audit-notes is its evidence source)

## Problem

Two read/audit surfaces had no journey. `gov stats --record` — the
metrics half of stats.jsonl, sharing the file with batch 31's
check-recorded exemption counts — had no e2e write, so the ledger's
interleaving (stats lines with no kind, check lines with kind=check)
and its honesty rule (a file that does not parse is still inventoried,
its parse_errors counted — metrics, not verdicts) were pinned nowhere.
And audit-notes — the mechanical staleness audit feeding the
archive-agent-notes skill — had no scenario exercising any of its
three signal kinds against a real tree.

## Decision

- **stats_ledger_roundtrip**: two stats records around a syntax break
  (the second counts parse_errors >= 1 with BOTH files inventoried),
  one check record after — three lines, append-only, kinds
  distinguishable exactly by the kind key's presence.
- **audit_notes_signals**: one note carrying all four signals at once
  (unknown `gov` subcommand, known command with a flag it does not
  accept, D999 against a decisions.md that knows only D1, and a
  backticked path that does not resolve) — all four named in one run,
  exit 0 throughout; then the clean note (real command, real D1) stays
  unnamed. Findings are evidence, never a verdict — the scenario pins
  the exit code too.

## Alternatives considered

- **Split into one scenario per signal kind** — four fresh projects to
  pin one output format; the audit is a report (no mode, no state), so
  one run naming four kinds pins more contract per container-second.
- **Assert audit-notes flags notes whose dates are old** — date-based
  staleness is deliberately NOT mechanical (the audit's docstring:
  signals the world no longer satisfies); pinning an age heuristic
  would pin a wish.

## Verification

Host: both scenarios PASS first run; pytest 478 passed / 2 skipped,
self-test 62 all pass, `gov run --mode all` 10 gates pass. Docker:
all eight inner-suite cells at 68/68, cross×3 PASS.
