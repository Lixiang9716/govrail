# Agent Note: docker e2e batch 45 — the brief's whole arc, with the four contracts the arc taught

Status: implemented

Related: the docker matrix + batches 1-44 notes (same series), the
rules@hash pin, D43 (task-card receipts), lifecycle (adoption day one
— this is the agent's first brief on top of it)

## Problem

The agent brief lifecycle — `task new` (pins rules@H) → work →
`task close` (runs the gates itself, attaches the receipt) → `task
check` → `run --receipt` — existed only as fragments: the concurrency
scenario held the lease edges, task_receipt_audit hand-edited cards
to reach the audit states, receipt_squash squashed receipts. No
scenario walked one brief through the REAL commands from birth to a
verified receipt.

## Decision

**agent_lifecycle_receipt** walks the arc and pins FOUR contracts the
arc itself taught (each was a scenario failure before it was an
assert):

1. a DIRTY tree keeps the advisory pairing gate non-green, and close
   refuses to spend a run it cannot pass — an agent commits before
   closing (and baselines pairing on day one, as lifecycle shows);
2. a gates.json edit STALES every outstanding brief: the card briefed
   against the red gate runs and fails ("not green", card untouched),
   and after the gate is fixed the SAME card is refused again — with
   "re-brief" — because close checks the pin BEFORE running;
3. a dead brief has no abandon verb: dismissing it is removing the
   card file — a deliberate, git-visible act;
4. card numbers are RECLAIMED after dismissal: the re-brief becomes
   T-0002 again, closes green, and `run --receipt` verifies the
   receipts on the committed tree.

## Alternatives considered

- **Add an `abandon` verb to task** — the scenario found the
  file-removal path workable and visible; adding a verb is a product
  decision with its own note, not a test's side effect.
- **Brief T-0002 against the red gate and close it there** — the red
  state is a deliberate governance change, not a world to complete
  work in; the scenario pins the refusal and the re-brief instead.

## Verification

Host: agent_lifecycle_receipt PASS; pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 86/86, cross×3 PASS.
