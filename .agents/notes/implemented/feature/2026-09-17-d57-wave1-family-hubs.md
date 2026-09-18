# Agent Note: D57 Wave 1 — four family hubs, thirteen deprecated aliases

Status: implemented

Related: D57

## Problem

The consolidation review approved family-first grouping, but approval
is not implementation. The 32-command surface had four families with
inconsistent vocabularies: notes tools split across `gov note new` and
`gov audit-notes`/`gov archive-notes`; the decisions gate named
`verify-decisions` while the family hub is `decision`; the lease trio
occupied three top-level slots; and eight `verify-*` commands sat at
top level as little more than the gates' CLI faces.

## Decision

Four hubs (`note`, `decision`, `lease`, `verify`) with the absorbed
commands as hidden deprecated aliases — identical behavior, one
deprecation line, removal after a two-minor window. The hub subparsers
DECLARE each child's flags and forward them explicitly, so `--help` is
honest and the flag registry matches without a second parsing path.
Every consumer of the vocabulary moved in the same commit: template and
root and demo gates.json (re-sealed), doctor's hand-tool tokens, the
D56 flag registry (canonical plus alias keys), the exit-code contract
registries, the skills router, and 125 doc citations across nine
bilingual pairs (re-confirmed). Historical notes and decisions text are
deliberately not rewritten — dated records. The ride-along: verify-notes'
unknown-argument refusal originally missed direct-script execution
(`main()` defaulted argv to None); the new self-test case caught its
own fix's gap the day it landed.

## Alternatives considered

Land the hubs without aliases and flip adopters immediately — rejected:
their gates.json and scripts cite the old names, and a governance tool
that breaks its adopters' automation on an upgrade trains `--no-verify`.
Rewrite historical notes/decisions to the new vocabulary — rejected:
retroactive edits falsify dated records; audit-notes names stragglers
informationally instead. Ship the hubs with REST-style forwarding that
passes argv through untouched and refuses to declare flags — rejected:
`--help` on a hub subcommand would list nothing while the flags work,
which is the invisible-flag failure mode #101 exists to prevent.
