# Agent Note: docker e2e batch 40 — task check audits both ends of a card, and the ledger survives eight concurrent writers

Status: implemented

Related: the docker matrix + batches 1-39 notes (same series), the
rules@hash pin (task briefs), D52 (the lease/lock family the
concurrency scenario pins), the stats ledger (batches 31/34's write
sides)

## Problem

Two spine surfaces had no journey. `gov task check` — the auditor
that makes a task brief's rules@hash pin mean something (a card
minted before a governance adoption is STALE, a done card without an
all-green receipt is not "verifiably done") — had no scenario walking
a card through open → stale → done-unreceipted → wrong-rules →
cleared. And the ledgers' append model rested on an untested
assumption: concurrent `--record` writers each land one INTACT line.
The concurrency scenario pins leases and decision appends, never the
stats ledger under simultaneous writers.

## Decision

- **task_receipt_audit**: one card, five states — open and fresh
  (exit 0), open after a rules.md edit ("STALE", "the brief is
  stale", exit 1), done with no receipt ("receipt is missing"),
  done with a receipt against rules@deadbeef ("different rule set"),
  done with an all-green receipt against the PINNED hash (exit 0).
  The stale case is the point: the pin exists so governance adoptions
  INVALIDATE outstanding briefs loudly.
- **ledger_concurrent_writes**: eight simultaneous `gov stats
  --record` processes on one project — exactly 8 lines land, each one
  parsing, each counting the same single file. No interleaving, no
  lost writer.

## Alternatives considered

- **Drive the done-state through `gov task close`** — close demands
  its own receipt flow (the receipt_squash scenario pins that end);
  editing the card JSON directly is the auditor's actual threat model
  (hand-edited cards must still fail LOUD, not pass).
- **More than 8 writers** — the atomicity question is answered by
  "two writers raced"; eight is already past the flake-noise floor a
  2-writer race carries.

## Verification

Host: both scenarios PASS first run; pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 77/77, cross×3 PASS.
