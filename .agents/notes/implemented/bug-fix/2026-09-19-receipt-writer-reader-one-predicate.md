# Agent Note: receipts have one green predicate; bricked done cards get exits (#329)

Status: implemented
Related: D65

## Problem

#323 fixed the WRITE side of the receipt contract (close's green
judgment excludes NON_RUN outcomes) but not the READ side: `_check_receipt`
still required `PASS` for every record, so every close whose diff did
not reach every path-scoped gate wrote a receipt the checker rejects —
and `done` + rejected receipt was a state with no exit: close refuses a
non-open card, void trusted receipt PRESENCE without validating it,
and the red check blocked every push. Found live the same day on a
scope-limited close (verify-decisions NOT_SELECTED in the receipt).

## Decision

One predicate, `_receipt_failures`, now judges green in both places
(close writes what check reads): PASS passes, NON_RUN outcomes
(SCOPED_OUT/NOT_SELECTED/NOT_RUN/DISABLED) are bookkeeping, FAIL/
TIMEOUT/MISSING/SKIP fail. The exits around the bricked state:
`task void --reason` validates the receipt first — a done card whose
receipt fails validation is voidable (the recorded, terminal exit),
a verifiably green one stays unvoidable; and `task close
--refresh-receipt` re-runs the gates on a bricked done card and
rewrites the receipt, letting today's already-bricked cards recover
without git surgery. `--refresh-receipt` ships its rule-10 surface
(FLAGS registry + close's help).

## Alternatives considered

Only tightening _check_receipt (no exits) — rejected: the state machine
would still brick; the exits are what make the strict reader safe.
Auto-refreshing on any close of a done card — rejected: a silent
receipt rewrite hides the fact that the recorded evidence was rejected;
the flag makes the re-judgment explicit. Letting void bypass validation
for ANY done card — rejected: a verifiably green card is finished work;
voiding it would erase a valid record without cause.
