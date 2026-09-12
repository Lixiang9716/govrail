# Agent Note: docker e2e batch 24 — the cost ledger's rule-5 edges, and the --no-record opt-out

Status: implemented

Related: the docker matrix + batches 1-23 notes (same series), D45 (the
cost ledger's shape), D29 (recording is the default), rule 5 (malformed
named and skipped, never silently summed)

## Problem

trend --cost's rule-5 edges — a malformed cost FIELD (a string instead
of the unit=value object), a NON-NUMERIC unit value, and the
no-cost-reporting window — had no E2E: the first would be silently
summed into a total (rule 5 violated), the last would read like a
zero roll-up. And the --no-record opt-out (recording is the default
since D29) had no journey proving the ledger stays empty and resumes.

## Decision

- **cost_malformed** (50th scenario): one valid run (alpha, 100
  tokens) plus TWO malformed lines crafted into the ledger (metrics,
  not evidence — D44's line makes crafting legitimate): a string cost
  field and a non-numeric unit value. The assertions: BOTH junk lines
  named on stderr (skipping malformed cost field / skipping
  non-numeric 'tokens'), the roll-up counts ONLY the valid line (alpha
  100), beta shows its run count with EMPTY cells (junk contributed no
  units, but the run count is honestly kept), and a no-cost window
  prints the opt-in pointer instead of a zero roll-up.
- **no_record_optout** (51st): `gov run --no-record` leaves the ledger
  empty, trend says "no history yet — never recorded", and a normal
  run resumes recording.

The scenario body needed a clean rewrite mid-batch: a stale assert
block from the first draft survived two assert-alignment passes and
kept asserting an older roll-up shape (caught by running the CURRENT
function in-container with full output — the same
mount-the-current-file debug pattern that worked all along).

## Alternatives considered

- **Assert the exact stderr wordings verbatim** — they name the unit
  and the expected shape; asserting the stable substrings (skipping
  malformed cost field / skipping non-numeric 'tokens') is enough and
  less brittle.
- **Also walk --cost --gate/--by-tag refusals** — batch 8's
  cost_attribution asserts both refusals (exit 2, reasons named);
  duplicated coverage buys nothing.
MD
