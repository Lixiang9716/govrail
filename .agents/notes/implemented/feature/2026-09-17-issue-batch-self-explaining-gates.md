# Agent Note: the issue-batch round — gate failures and install friction learn to explain themselves

Status: implemented

## Problem

Eleven open issues, all from real adopter friction on dsh-mobile and
radiant (0.29.4–0.30.5), clustered into six fixable defects and five
items whose honest answer is documentation or design:

- #201: a failing gate's own output was shown only for PASSING gates —
  the failure summary named the gate and a rerun hint, but hid the one
  thing that diagnoses it;
- #250: the hooks resolve gov for themselves (GOV_BIN → PATH →
  python3 -m gov, D29) and then died anyway: the GATES' commands name
  bare `gov`, which a `pip3 install --user` environment does not put on
  PATH — every gate reported `missing` with no cause;
- #259 (residual): the plane-drift refusal assumed the running binary
  is the newest thing in the room — a checkout initialized with 0.29.4
  hit the 0.34 seal refusal with no hint that versions were the story
  (the CI-pin half was already fixed: the template pins
  `govrail==<init version>`);
- #257: a gate's rule contract had no home (label is one line, JSON has
  no comments), so the contract lived in the checker's docstring;
- #253: `verify-pairing --write` stamped `untracked` for staged-but-
  uncommitted sides as a frozen fact that reads stale forever after the
  first commit;
- #251: no recovery path for a customized-then-lost gates.json, and the
  happy path never said "commit the plane now";
- #200 (partial): the seal's consent record was written but its
  location was never named.

## Decision

Fix the six at the surface where each pain lands. The failure summary
inlines each failing gate's captured output (last ten lines) under its
rerun hint. The hooks export their resolved GOV_BIN, and gate commands
naming bare `gov` resolve through it when PATH has no `gov` — without
GOV_BIN set, `missing` keeps its named `command not found` detail. The
plane-drift refusal reads the manifest and, when the checkout was
initialized with a different govrail than the one running, says which
side is which. Gates accept an optional `description` string, printed
on the failure line (schema-checked like every other key). `--write`
warns the moment a side is stamped `untracked` ("re-run --write after
your first commit"). init ends its next-steps with "commit the
generated governance files now", and the seal's consent message names
the tracked ledger. Plus pyproject's description now spells out
`pip install govrail → command: gov → first step: gov init`.

## Alternatives considered

A `retry-once` flag for load-flaky gates (#202, same family) — not
shipped: retries mask real failures and the wall-clock-budget fix
belongs to the gate author (process time, not wall time). Auto-migrate
the CI pin on `gov init --upgrade` (#259's suggestion 2) — deferred:
pin migration rewrites a file the project may have customized; the
version-aware refusal plus the documented pin is the honest step, and
the upgrade flow can come with its own decision. Seal bootstrapping for
fresh clones (#200's absent-vs-drifted distinction) — deferred to a
decision: unattended constitution-acceptance is exactly what the
ritual system exists to gate, and the tracked-ledger naming shipped
here makes that future argument auditable. Description parsed from the
checker's docstring (#257's option 2) — rejected: docstrings are for
humans reading code and their format drifts; an explicit schema-checked
field is one fact in one home.
