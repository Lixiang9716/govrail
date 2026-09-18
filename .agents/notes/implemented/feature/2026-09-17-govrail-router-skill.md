# Agent Note: the govrail router skill — judgment lives in a skill, syntax stays in --help

Status: implemented

## Problem

First-use analysis (onboarding review) found two failures with the same
root: the command surface is 32 commands with no routing. After
`pip install govrail`, a user who finds `gov` at all faces a 32-line
usage dump (bare `gov` = full table + exit 2) and settles into using
two or three commands forever — the gates, notes, seals, leases, and
memory surfaces stay undiscovered. For AGENTS the gap is worse in kind:
they act on the repo without a human to ask "when do I run which
command", and the when/when-not judgment existed nowhere — scattered
across decision text, issue threads, and this session's own
conversations.

## Decision

ONE router skill, `govrail`, injected FIRST in the skills list (related:
D57 — the same review's command-surface consolidation, whose vocabulary
this skill now routes). (and
pointed to from the injected AGENTS.md reference line): it carries the
when/when-not judgment for the whole surface, grouped by stage
(adopt/upgrade, run, notes, pairing, seal, leases, memory, review) with
an explicit "Never" section (no --no-verify, no red-green rebaseline,
no hand-edited .gov state, no parked-for-convenience gates). Design
boundaries that keep it honest: the skill carries JUDGMENT only —
command SYNTAX stays in `gov <command> --help` (one fact, one home);
the four existing skills keep their deep dives and the router routes
into them; init injection is create-if-missing so existing adopters
gain it via `--adopt`, and the demo specimen is synced through the
existing script (which also re-seals the demo plane).

## Alternatives considered

A SKILL.md per command (32 skills) — rejected: most commands need one
line of when/when-not, which the router's stage table carries better
than 32 near-empty files bloating every project's .agents/ directory
and the injection surface. Parse gate-checker docstrings to auto-print
the contract on failure (#257's option 2, same shape) — rejected:
docstring format drifts; the schema-checked `description` field is the
contract's home. Leave discovery to the README — rejected for agents:
agents act on repositories without a human to point at the README, and
the skills list is the surface they actually enumerate.
