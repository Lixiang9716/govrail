# Agent Note: the machine contract gets its pin, and run's polarity stops being folklore

Status: implemented

Related: D56

## Problem

The round-14 review named two gaps in D56 that its admission criterion
cannot cover. First, `gov run` already HAS `--json` with pinned tests —
the defect was the undeclared DEFAULT: a CI wrapper that forgets the
flag gets prose in the machine stream, and nothing in `--help` says
that is the deal. Second, the four-state exit contract lived in `--help`
prose with no pin — by this repository's own precedent (the README's
hand-copied help and the 0.12-era flag registry both drifted), a
contract written as prose without a test is a next-round finding.

## Decision

The `--json` help now declares the polarity — without the flag, stdout
carries the human report; errors are always stderr; with the flag,
stdout is exactly one machine value — and D56 codifies it as contract:
not flipped for `run` alone, because every command in the family shares
the polarity and a single-command flip would create a second dialect.
`tests/test_exit_code_contract.py` pins the four-state contract
mechanically: every command in the command table refuses an unknown
flag with exit 2; sixteen failure-capable commands pin a deterministic
red invocation with exit 1 and the complement is declared
command-by-command (an undeclared new command goes red — day-one
compliance made mechanical); acquire busy is 3; both run polarities are
asserted on real process streams. The probe for the universal leg
caught a live defect the same day: `verify-notes` ignored argv entirely
and answered a mistyped invocation with a GREEN verdict — fixed with a
named exit 2, covering both the CLI path and direct-script execution
(the script path originally still passed, because `main()` defaulted
argv to None; the self-test case caught its own fix's gap). D56 is
amended in place with both clauses.

## Alternatives considered

Flip `run`'s default so prose always goes to stderr — rejected: the
family shares one polarity, and a single-command flip trades a
documentation defect for a second dialect; a family-wide flip is
real breakage with no consumer asking for it (recorded in D56 as the
reason the changelog would need). Generate the failure-leg registry
from the gates' rejection cases automatically — rejected: the rejection
cases prove a gate CAN reject, not which process exit code its CLI
reports; conflating the two ledgers would make both weaker. Let the
verify-notes refusal accept a --json-shaped ignore list — rejected:
flagless means flagless; a command that invents exceptions to its own
contract is the hollow-gate pattern wearing a flag.
