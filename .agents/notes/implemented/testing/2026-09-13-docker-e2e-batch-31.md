# Agent Note: docker e2e batch 31 — check --json's stderr promise kept, the ledger contract, and doctor's parser surface

Status: implemented

Related: the docker matrix + batches 1-30 notes (same series), the
check engine (#181), #126 (the stats ledger), D54 (the parse layer
doctor reports on)

## Problem

Three surfaces had no journey — and one hid a lie. `check --json`'s
own help text promised "the human report moves to stderr", but the
code printed the human report only in non-json mode: a --json run
emitted the machine value and NOTHING else, so an operator watching
the terminal saw silence and the documented contract was false. The
engine's accounting surfaces (warning-vs-strict blocking, suppression
counting, --record's ledger line) were pinned only by unit fixtures;
and doctor's parser check — the D54 dependency surface a broken wheel
must fail loudly against — had no e2e read at all.

## Decision

- **The product fix**: `check`'s human report now routes to stderr
  under --json (stdout stays exactly one JSON value, as the help
  always claimed). Pinned three ways: a unit test
  (test_json_report_lands_on_stderr_not_stdout), the e2e scenario
  asserting the summary on stderr across all matrix cells, and the
  pre-fix host repro that showed empty stderr.
- **check_ledger_contract**: a warning finding prints and exits 0,
  --strict flips it to exit 1; the `gov:ignore-check` marker keeps the
  finding VISIBLE ((suppressed), counted, never deleted); --json's
  shape pins rule/severity/line/suppressed and the summary triple;
  --record appends {kind: check, checks: {rule: {findings,
  suppressed}}} to stats.jsonl — the exemption count the trend side
  is meant to watch.
- **doctor_parser_versions**: doctor names "parse layer ok
  (python=…, …)" with every shipped grammar version, --json carries
  the parser check with state ok and zero problems.

## Alternatives considered

- **Fix the help text instead of the code** — the documented behavior
  is the useful one (machine stdout, human stderr); deleting the
  promise would keep the operator-facing silence that made the flag
  feel broken.
- **Assert the whole --json file list** — clean files may or may not
  appear in reports; the scenario selects the app.py entry and pins
  only the contract (one finding, its fields, the summary triple).

## Verification

Host: both new scenarios PASS; pytest 476 passed / 2 skipped (one new
test); self-test and `gov run --mode all` green. Docker matrix: all
eight inner-suite cells 64/64, cross×3 PASS (checks.py changed the
wheel, forcing a full rebuild).
