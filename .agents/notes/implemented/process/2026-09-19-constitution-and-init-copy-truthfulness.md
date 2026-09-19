# Agent Note: constitution text and init copy say only what is true (D65)

Status: implemented
Related: D65

## Problem

The injected constitution promised things an adopter's checkout could
not satisfy: rule 10 named `audit_notes.FLAGS` and
`tests/test_exit_code_contract.py` (govrail-internal), rule 11 named a
`surprises` gate the shipped template does not carry, and a duplicated
sentence sat in rule 2. `gov init` recommended the deprecated
`verify-pairing` spelling (which printed a deprecation warning naming a
removal target five minors past) and told monolingual projects — the
most common shape — to run a pairing baseline that fails the same day.
The README claimed "language-agnostic" over a facts layer bound to
eight grammars, and the agent-hooks copy implied full-platform
governance. CHANGELOG carried re-listed feature entries (same feature
in several release sections; same-commit duplicates).

## Decision

Rule 10 is genericized (a project's own machine-checked registries and
exit-code contract — adopters have CLIs too), rule 11 keeps the ledger
and escalation but says the blocking gate is the adopting project's
wiring choice, and the duplicated line is gone; the template stays
byte-identical to the live copy (test_template_sync's constraint).
`gov init` speaks canonical spellings only, gains the monolingual
branch (#315: probe for any counterpart before advising a baseline),
and the deprecation line no longer cites a removal version that passed
(#316). Deprecation drift is now surfaced mechanically (#274): `gov
init --upgrade` lists gates.json entries still using deprecated
commands with their replacements, and `gov doctor` flags them per gate.
README/zh qualify "language-agnostic" with the facts-layer boundary,
and the agent-hooks section states the four-dialect boundary and that
MCP is out of scope. CHANGELOG de-duplicated section-scoped plus
hash-anchored cross-section re-listings, keeping each feature's oldest
release home (doc-sync stays green).

## Alternatives considered

Splitting rules.md into a template layer plus a self-hosted addendum
(#314's literal suggestion) — rejected: the truth-source register pins
live == template == demo byte-for-byte; one text, honestly genericized,
beats two files with a drift gate to maintain. Removing the deprecated
aliases now — rejected: notes cite them and they still work; the copy
fix (no fake deadline) plus the migration assists are the honest move
within the window. Reconstructing the "true" release for every
re-listed CHANGELOG entry — rejected: hash-anchored dedupe keeping the
oldest home is mechanical and matches release-please semantics.
