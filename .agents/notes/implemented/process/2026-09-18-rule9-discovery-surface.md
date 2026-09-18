# Agent Note: rule 9 — the discovery surface is part of the command

Status: implemented

Related: D56

## Problem

`gov update` (D58) shipped with every mechanical surface green — help
honest, flag registry matched, exit-code contract pinned — but the
`govrail` router skill's stage table had no line for it. The one
surface agents actually enumerate was blind to the new command, and
nothing in the process would have caught it: every "red on drift"
check in the repo watches registries and hashes, not the routing
prose. The round-14 review named the gap and its fix as a rule.

## Decision

Rule 9 in `.gov/rules.md` (template mirrored, demo synced, plane
re-sealed): a new user-facing `gov` command — or a rename — ships its
discovery surface in the same PR, across three named homes, each
catching a different drift: `--help` plus the flag registry (both
directions enforced by the registry test), the `govrail` skill's stage
table (agents enumerate skills, not help output), and the exit-code
contract registries (failure leg or declared 0/2-only). Deprecated
aliases meet the same bar while they work. D56 amended: the skills
routing is the third must-name home of the machine-interface
discipline, beside help and the exit vocabulary.

## Alternatives considered

A structural gate over the router skill (parse the stage table, fail
when a shipped command is missing) — rejected for now: the table is
organized by stage with prose judgment, and a mechanical parser would
force a rigid format onto the one surface whose value is phrased
judgment; the rule plus review covers it, and if stragglers appear the
gate becomes the fix. Fold the rule into D56's text only — rejected:
decisions record why; rules.md is where standing orders are read
before starting work, and this is a standing order.
