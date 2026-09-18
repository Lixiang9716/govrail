# Agent Note: gov agent-hooks — the plane's presence at every agent lifecycle event

Status: implemented
Related: D59

## Problem

The plane met the agent only at push time (the pre-push gate) and,
implicitly, at session start through AGENTS.md pointing at the skills.
Claude Code-class frameworks expose lifecycle hooks — SessionStart,
PreToolUse, UserPromptSubmit, Stop — and the plane had a seat at none
of them, so mid-session destructive commands (`rm -rf /`,
`git reset --hard`) reached the worktree with no governance trace and
no chance for the plane to speak first. Every future in-session rule
would also have needed this plumbing first; the gap was structural,
not one rule's.

## Decision

`gov agent-hooks <event>` ships five handlers (session-start,
pre-tool-use, post-tool-use, user-prompt-submit, stop) under one
`handler(payload, event)` signature. `gov init` installs
`.claude/settings.json` from the shipped `claude-settings.json`
template, so init's write, `_inventory`'s drift classification,
uninstall's customized check, and `_template_for`'s reverse mapping all
read the same bytes; the manifest's `created[]` records the bare path,
and uninstall reverses a pristine install while naming a customized
one. A pre-existing settings.json is reported and skipped, never
merged. Session-start and user-prompt-submit inject context with the
framework's own PascalCase `hookEventName` (the settings.json key
spelling — anything else is silently ignored by the framework).
Pre-tool-use denies `rm -rf /` and `git reset --hard`; this is a
presence, not a fence — the match is string-level and bypassable, and
`gov run` with the pre-push gate remain the enforcement (git push is
left to the pre-push hook, no double gate). An empty stdin is a
legitimate no-payload call; a malformed one is named on stderr and the
handler continues without it — loud fail-open that keeps the command
0/2-only in the exit-code contract.

## Alternatives considered

Merging the hooks into an existing settings.json — rejected: the
adopter's config is their territory, and automatic JSON merging
eventually mangles hand-written comments and key order; report-and-skip
leaves the decision with the adopter. Exit 2 on a malformed payload
(fail-closed) — rejected: a compatible framework that doesn't speak
JSON would have every PreToolUse call blocked, which trains uninstalling
the hooks; naming the error on stderr keeps the loudness without
failing shut. Inline JSON written by cli.py with no shipped template —
rejected: install bytes no other surface could see, and the
annotation-suffixed `created` entry (`".claude/settings.json
(agent hooks)"`) was a path uninstall could never match, so the install
was not reversible (D10). Teaching users to wire the hooks by hand —
rejected: a checkable promise is a gate (rule 1), and hand-configured
hooks have no idempotency, no uninstall path, and no single shape.
