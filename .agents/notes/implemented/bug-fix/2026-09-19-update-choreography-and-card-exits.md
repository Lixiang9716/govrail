# Agent Note: update choreography completes, cards get an exit, locks stay out of the tree (D65)

Status: implemented
Related: D65

## Problem

Six follow-up defects (issues #320-#325) shared one theme: the plane's
own flows could dead-end. `gov update`'s plan read the shipped gates
template repo-relatively — [Errno 2] in every adopter checkout; a
mid-flight abort left adopted-but-unsealed files the launder guard then
refused forever (retry impossible, only a manual `gov verify-plane
--write` could finish the choreography). Task cards had no exit when a
stale pin was the point of the task: close refuses stale, no defer
exists, rule 9's "explicitly defer it" had no tool. `task close`
counted NOT_SELECTED/SKIPPED as failures, making close impossible in
any repo whose enabled set outgrew the mode. `gov update`'s guard flock
was created under the worktree root, dropping a `gov-locks/` directory
into the tracked tree, and `gov task new`'s `.new.lock` anchor was
swept into commits by habitual `git add -A`.

## Decision

The plan reads the template from the installed package
(`importlib.resources`); the launder guard recognizes its own tool's
incomplete run — manifest already at the running version AND every
drifted file byte-identical to its shipped template (gov.yml compared
as-written) — and resumes with a named note, anything else still
refuses. `gov update` names installed-hook drift (an older plane's
hook keeps calling retired spellings — the false pre-commit
deprecation warnings of #324) with the exact refresh command. `gov
task void <id> --reason` retires a card recorded-but-terminal (status,
reason, actor, ts ride the card; the file stays; check tolerates it;
close refuses it), and `task new` warns when the working diff already
touches rules-bearing files. Close's green judgment excludes
`NON_RUN_OUTCOMES` (SCOPED_OUT/NOT_SELECTED/NOT_RUN/DISABLED — one
home in gates.py, trend reuses it) while SKIP still refuses. The
guard flock moved to the git common dir and init ensure-ignores
`.gov/tasks/.new.lock`.

## Alternatives considered

Ledger-marker resume (a rituals record written before the migration
that the guard matches) — rejected for now: pristine-template drift on
a current-version manifest identifies update's own incomplete run
without a new ledger format or a trust question about who wrote the
marker. A `--defer` status — rejected: defer needs a wake-up condition
to be honest; void (terminal, recorded, reason-owed) covers the real
case (the task's purpose evaporated with the adoption), and re-brief
covers "still wanted". Tolerating SKIP in close — rejected: a skipped
dependent means evidence is genuinely missing, which is exactly what a
receipt must not paper over.
