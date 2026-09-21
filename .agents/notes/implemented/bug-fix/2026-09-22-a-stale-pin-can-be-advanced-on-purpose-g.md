# Agent Note: a stale pin can be advanced on purpose: gov task re-pin, and the stale report names its remedy

Status: implemented

Related: D55, issue #368

## Problem

Wiring a gate — the sanctioned path `gov gate add` walks, and the one
the router skill recommends — changes `gates.json`, which recomputes the
combined `rules@` hash every card pins. **Every open card goes stale at
once**, and the `task` gate blocks on stale pins by design (rule 9). An
adopter measured seven open cards staled by one gate addition.

That is correct in isolation and unrecoverable in composition. The cards
that go stale are not necessarily cards you can retire: `close` refuses a
stale pin, `void` is terminal and can refuse too, and the duplicate-id
matcher made `void` unresolvable in the reported case (#352, fixed in the
same release train). Neither the gate addition nor the brief was wrong —
the missing piece was a way to say "the constitution moved, the brief
did not" — so the only honest escape was reverting the legitimate change
and re-sealing back, which is why the adopter's matrix gate stayed
unwired.

## Decision

- **`gov task repin <id> --reason <TEXT>`** advances an open card's pin
  to the current `rules@` hash. It is a RECORDED act, like void: the card
  keeps a `repins` entry with the from/to pair, the actor, the instant and
  the reason — it asserts the human judgment the gate cannot make ("I read
  what changed, and this brief still describes the same work"), and the
  audit trail says who asserted it. A current card is a no-op (not an
  error); a non-open card is refused by name; `--reason` is required.
- **Both stale reports name the remedy**, not just the state: `task check`
  and `close` print "if this brief still describes the work, advance it:
  `gov task re-pin <id> --reason <why>`; otherwise close or void it" —
  the issue's point that a report describing a state the reader cannot
  leave is a dead end with prose around it.
- Discovery surfaces follow the command: the subcommand list in `task
  --help` and the docs-consistency registry, the one-line `gov --help`
  description, the regenerated README block, and both READMEs' worked
  examples (the EN block and the zh list moved together, pair
  re-confirmed).

## Alternatives considered

- **Make `check` distinguish stale-pin-only from stale-and-unresolvable**
  (the issue's option 1, narrower form) — rejected as the fix: the
  distinction is real but it only re-labels the dead end; the card still
  needs an exit, and the exit is the assertion nobody could record.
- **Auto-re-pin on gate addition** — rejected outright: it would make a
  constitution change silently re-certify every outstanding brief, which
  is precisely the "stale pin" signal rule 9 exists to produce. The
  advance must be a deliberate act by someone who read the change.
- **Have `close` accept a stale pin with `--accept-rules`** — rejected:
  closing is terminal and already carries a receipt; folding "I accept the
  new constitution for this brief" into it would let the acceptance ride
  an unrelated completion, and the same escape could not help a card that
  is not ready to close.
- **Reverting the gate addition as the documented remedy** — rejected:
  the plane would be telling adopters that the sanctioned wiring path is
  unsafe, when the actual gap was a missing verb.
