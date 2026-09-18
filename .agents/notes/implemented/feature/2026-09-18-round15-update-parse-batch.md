# Agent Note: the round-15 batch — gov update and gov parse grow up

Status: implemented

Related: D58

## Problem

The round-15 review found four HIGHs concentrated in the two newest
primitives, plus a P1/P2 tail. gov update: the seal re-baseline
launders pre-existing drift (no `violations()` preflight — presets.py
does it right), a corrupt manifest crashes on tuple arity with the
named error path unreachable, and a mid-migration refusal leaves a
half-migrated plane under a stale seal with no recovery text
(`repair_required` exists nowhere in the code). gov parse: an unknown
`--lang` or missing grammar escapes as a traceback with exit 1 (the
contract says 2), a missing explicit path exits 0, `.tsx` files always
parse with the plain-TS dialect (JSX → phantom ERROR nodes), and
single-file/directory selection follow two different matching
contracts. Plus: presets still install deprecated command names, the
docs-bilingual preset's paths don't cover doc-sync's real read
surface, `_adopt` rebuilds the manifest (dropping unknown keys,
non-atomic, following a symlinked manifest past N10's containment),
update runs unlocked, its plan and apply diverge, and the ritual is
best-effort after the fact.

## Decision

update.py is rebuilt around a TRIED plan: the gates merge is computed
before any write, `violations()` runs at plan time, and apply refuses
(exit 2, named) unless every drifted file is one the migration writes;
the whole sequence runs under the plane's guard flock with a step
counter and a named "FAILED after N/6 steps — git restore . && git
clean -fd" recovery tail. parse gains the missing contracts (unknown
lang / missing grammar → named 2; missing explicit path → named 2)
and tsx-aware parser selection (`parser_for` by file suffix — the TS
grammar's own `language_tsx` factory, previously unreachable through
the fallback chain). `_adopt`'s manifest write goes through atomicio
with the project as the containment boundary, dict-merge semantics
preserving unknown keys. The install-line refresh honors the
recorded-as-adopted hash (pristine-after-upstream-move is not
"customized"). Preset bundles migrate to the current command
vocabulary; gate IDS stay identity (verified-decisions is a name, not
a command). The full detail lives in the round-15 ledger.

## Alternatives considered

Wrap every step in best-effort try/except and keep going — rejected:
a half-migrated plane under a stale seal is worse than a stopped one;
the command now fails loud with the recovery command printed.
Lock only `gov update` against itself — rejected: the race that
matters is against `verify-plane --write`, so the guard flock is taken
for the whole apply. Ship `.tsx` support by splitting the typescript
pack into two packs — rejected: one pack with suffix-selected dialect
keeps the registry, the defaults, and the adopter configs stable.
