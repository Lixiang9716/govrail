# Agent Note: gov update — the migration choreography becomes one command

Status: implemented

Related: D58

## Problem

The dsh-mobile plane migration (the fix for #259's CI-breakage class)
was executed by hand as five commands plus a hand-edited file: upgrade
report → adopt → adopt-new gates merge → seal re-baseline → workflow
pin bump → gitignore. Every step was mechanical, but the sequence
lived in one expert's head — and the CI pin had NO update path at all
(`_install_ci` skips when the file exists), which is how 0.29.4
checkouts ended up pinned to a version whose successors break them.

## Decision

`gov update`: dry run by default (the printed plan IS the deliverable
until `--apply`), with hard preconditions evaluated before any
mutation — git worktree, zero uncommitted tracked changes, manifest
present, and seal consent (TTY or `--confirm-unattended`). The
sequence reuses existing mechanisms only: classification via the
extracted `_upgrade_files` (one home — the report and the migration
now read the same adoption facts), adopt for missing + upstream-moved
files, `verify-plane`'s own baseline + tracked-ledger ritual for the
seal, and a LINE-LEVEL CI pin refresh that rewrites only
`pip install govrail...` run-lines, preserving customized workflow
shapes. The command is declared 0/2-only in the exit-code contract.

## Alternatives considered

`init --upgrade --apply` — rejected: the migration spans init, seal,
and CI domains; hanging it under init misnames what runs. Auto-pinning
by regenerating the whole workflow — rejected: adopters customize
(comments, triggers); regeneration would destroy their edits, so the
refresh is line-level and skips named when the install line is absent.
Skipping the seal step and leaving re-baseline to the user's next
`verify-plane --write` — rejected: an unsealed migration is exactly
the "plane drifted" limbo #259 escaped; the command finishes the job
it starts, with the consent recorded.
