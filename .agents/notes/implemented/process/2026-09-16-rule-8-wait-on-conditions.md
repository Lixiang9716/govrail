# Agent Note: rule 8 — wait on conditions, not on clocks

Status: implemented

## Problem

The CI error rate review and the external red-team rounds traced one
recurring failure class to a missing rule: waiting was done by
sleeping a guessed duration and hoping a state had arrived — an agent
waiting out CI with a blind timed pause, fixtures sleeping past a
lease TTL, a docker drill sleeping 4.3s before a takeover assertion.
Every one of those is either a poll-with-deadline away from being
deterministic, or (when it waits for real wall-clock physics like a
TTL) an unasserted hope.

## Decision

Rule 8 joins the constitution: "Wait on conditions, not on clocks."
Poll the condition with a deadline and fail loud when it passes; sleep
only paces real wall-clock physics, and the condition is asserted
after the wait. Agent-facing CI waits are event-driven (gh pr checks
--watch, gh run watch --exit-status). The rule ships in the template
constitution too, and CONTRIBUTING (both languages) carries the
waiting guidance with the lawful/unlawful examples. The codebase was
audited first: every existing sleep is TTL physics, an agent
keepalive, or the lease poll loop's own interval — nothing needed
converting, which is why the rule lands without a code change.

## Alternatives considered

Encode the rule as a gate (a checker greping for sleeps) — rejected:
sleeps are lawful for TTL physics, and a grep gate cannot tell a
lawful pace from an unlawful hope without understanding intent; review
plus the rule text is the right enforcement point. Only fix the agent
runbook and skip the constitution — rejected: the lease/TTL scenarios
proved agents copy the waiting style they see, and a constitution rule
is what gets read before starting work.

