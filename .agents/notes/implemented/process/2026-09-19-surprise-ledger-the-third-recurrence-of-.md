# Agent Note: surprise ledger: the third recurrence of a surprise escalates (rule 11)

Status: implemented
Related: D62

## Problem

The plane records failures (notes, decisions, postmortems) but not
surprises — the moment reality differs from expectation. A surprise
lives in the conversation, evaporates, and can happen five times with
nobody counting: each occurrence gets patched as one-off bad luck while
the actual defect is the process that keeps producing the surprise.
Every existing genre is backward-looking or decision-shaped:
postmortems carry a high bar (subtle + systemic + costly), notes record
decisions, not missed expectations. What was missing is light-grained
forward telemetry: record, count, force the escalation at a threshold.

## Decision

The surprise ledger ships as rule 11 of the constitution (D62):

- `gov surprise record "<expectation>" --reality "<what happened>"
  [--sig SLUG] [--surface PATH]` appends to the tracked, append-only
  `.gov/surprises.jsonl`; a signature groups recurrences of one kind
  (derived from the expectation when omitted, printed with the sig
  counts so the human keeps signatures consistent). At record time the
  command prints similar earlier surprises — "have I seen this before?"
  is answered when it is cheapest, before the human picks the
  signature.
- `gov surprise list [--sig] [--json]` counts per signature.
- The `surprises` gate (blocking, dogfood-only) enforces the
  escalation: any signature at three or more entries without a process
  note citing `surprise:<sig>` in the notes corpus is red. Corrupt
  ledger lines and one-sided entries (missing expectation or reality)
  fail loud (rule 5) — counts drive the threshold, so silent shrinkage
  hides escalations.
- Recording never blocks on the threshold: data first, verdict in the
  gate. Below three, no note is owed — one or two surprises are data,
  not yet a pattern.
- Rule 10's full discovery surface landed in the same change: cli
  dispatch, `commands.py` panel, `audit_notes.FLAGS`, the exit-code
  contract's 0/2-only declaration, and the `govrail` skill's stage
  table (which the `skill-coverage` gate now enforces — the plane ate
  its own gate within hours of it landing).

The first real entry seeds the ledger: the truth-source register's row
7 claimed the constitution had 8 rules while it has carried 10 since
rule 9 landed — recorded under sig `truth-source-register-stale`, and
fixed in the same change (row 7 now says 11).

## Alternatives considered

- **Prose ledger + README convention** — rejected: no counting, no
  lookup, no gate; exactly the wishful-discipline pattern rule 1
  exists to end.
- **Refusing the third record until the note ships** — rejected: it
  trades away the third event's data for the enforcement; the gate's
  red achieves the same force without losing the record.
- **Machine fuzzy-matching of signatures** — rejected: deciding that
  two paraphrases are "the same surprise" is a verdict, not a fact;
  a wrong merge trains the human to ignore the tool. The human picks
  the signature with full counts in view.
- **Sealing the ledger** — rejected: it is evidence telemetry, not
  constitution (same call as the ritual ledger).
- **Shipping the gate in the adopter template** — deferred: the ledger
  and command ship (any adopter can use them), but the gate goes into
  the template only with run evidence, per the P0-3 polarity
  discipline (the lint-gate precedent).
