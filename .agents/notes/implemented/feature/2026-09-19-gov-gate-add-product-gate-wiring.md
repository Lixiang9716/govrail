# Agent Note: gov gate add — wiring a product gate becomes a command (D65)

Status: implemented
Related: D65

## Problem

The shipped gates police the governance plane; the gates that make the
plane worth adopting — the project's own test/lint/build commands — were
the one part of the DAG every adopter had to author, and the only way to
author them was hand-writing JSON against a schema only
`gates.load_config` knew. Wiring friction lands directly on adoption,
and a hand-edited gates.json is also the easiest way to write a config
the runner refuses (or a gate no mode ever selects — silently dead).

## Decision

`gov gate add <id> [options] -- <command...>` (#309, D65): validates the
pieces (id grammar, glob compile, stage names, mode existence), merges
atomically into gates.json, validates the merged doc through the runner's
own schema loader BEFORE landing, and proves the gate can run with one
`gov run --gate <id>` whose verdict becomes the command's exit code. The
command never re-baselines the seal — in a governed repo the verification
run is refused by design and the ritual (`gov verify-plane --write`) is
named. `gov init` now leads its next steps with the product-gate wiring
(a governed repo must wire product gates to be worth anything) and the
python-lib preset description mentions strict note attribution. Rule 10's
discovery surface shipped with the command: `--help` + the FLAGS registry,
the govrail skill's stage table, the exit-code contract's failure leg.

## Alternatives considered

Hand-editing gates.json with better docs — rejected: it keeps the
failure mode (unvalidated config, mode-less gates) and adds nothing;
the friction is the JSON, not the documentation. Auto-running the gate
add inside `gov init` — rejected: init is a fresh-install path where
the project has nothing to test yet; the wiring belongs to the first
real change. Auto re-baselining the seal after the edit — rejected:
that re-opens the rogue re-seal hole (#311); the refusal with a named
ritual is the honest flow.
