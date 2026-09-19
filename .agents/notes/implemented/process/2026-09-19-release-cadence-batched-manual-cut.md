# Agent Note: release cadence — batched accumulation, deliberate cut (D66)

Status: implemented
Related: D66

## Problem

The release chain was end-to-end unattended by design (the 0.31.0
postmortem's remedy): every release-worthy merge armed auto-merge on the
release PR, and CI green shipped a tag + PyPI publish immediately. The
result was a per-merge cadence — ten-plus releases in two days, 91
version sections in the CHANGELOG — where each publish churns every
adopter's `govrail==` CI pin and drowns release notes' significance.
The maintainer's verdict: slow down.

## Decision

Keep release-please's accumulation machinery exactly as it was (PR
opened per push, HIGHLIGHTS draft amended into the release commit,
superseded runs cancelled, RELEASE_PAT user-identity pushes so CI starts
immediately) and remove ONLY the auto-merge arming step. The release PR
now accumulates every release-worthy change and stays open; a human
squash-merging it IS the cut — one deliberate merge = one tag + one
GitHub Release + one PyPI publish, unattended per cut. The trigger set
is unchanged (feat/fix/perf/revert; chore/docs never open a release
PR). The contract flipped in tests/test_ci_health.py: the workflow must
NOT contain `--auto` anywhere, and the highlights job must state the
accumulation policy in its step names. CONTRIBUTING (en+zh) and README
(en+zh) describe the new rhythm.

## Alternatives considered

A weekly scheduled workflow that re-arms auto-merge (fixed cadence,
zero human acts) — rejected for now: new scheduled surface and PAT
permission scope, spins on weeks with no changes, and it can be layered
later without touching today's change. A `release:ship` label that arms
auto-merge on demand — rejected: it is a second, memorable bypass where
the manual merge it would automate is already a single command; label
channels without a wake-up condition price more culture than they save.
Trimming hidden changelog sections to further gate triggers — rejected
after checking the evidence: non-releasable types (0.43.1 was a
`fix(ci)`) never opened PRs on their own; the volume came from arming,
not from the trigger set.
