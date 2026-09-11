# Agent Note: self-test's undeclared-case warning prints the remedy inline

Status: implemented

Related: issue #167, #18/D32 (the ledger that names undeclared cases),
#139/D47 (the diagnostics round), #30-round wish 4 (the ledger itself)

## Problem

The coverage ledger's undeclared-case warning named the file and stopped:
`executed case(s) without a '# gate: <id>' declaration (first five lines):`
followed by paths. The two things needed to fix it — the marker's syntax
and its scan window — lived only in the source. An adopter (the issue's
reporter) paid two debugging round-trips to discover that the marker works
inside a module docstring and that the window is five lines, and only then
did the coverage cell flip from `NONE — rule 6` to a count. A warning that
names a violation without naming its remedy is a warning that gets
tolerated: the ledger's whole job is to make rule 6's ramp visible.

## Decision

The warning prints the fix inline, next to the paths:
`fix: add '# gate: <id>' within the first 5 lines to link the case to the
gate it proves (a line inside the module docstring counts; keep the
shebang on line 1)`. `gov self-test --help` gains an epilog carrying the
same contract — declaration syntax, the five-line window, and that the
ledger is a reminder, never a failure — so the surface is documented where
a caller looks for it, not only where the violation appears. The
rejections README (the template, this repo's copy, and the demo project's)
states that a docstring line counts and that an undeclared case is named
with the fix printed inline.

The "write one" hint keeps its `and not undeclared` guard: a case that
ran and passed but declared nothing is never nagged about being written
(#18/D32's rule, pinned by `test_18_ledger_credits_executed_undeclared`).

A shipped tools-family case, `test_coverage_warning_names_the_marker_fix`,
pins both halves of the issue's discovery from a scratch project: the fix
line appears for an undeclared case, and a marker placed on line 4 of a
five-line Python case — inside its module docstring — is credited as
`x(1)`.

## Alternatives considered

**Documenting the syntax in the README only.** The warning is read at the
moment of confusion; the README is a different file in a different
directory. The issue's own report is the evidence that having the warning
in hand is not enough.

**`gov self-test --explain-declaration` (the issue's optional
suggestion).** A whole flag for one sentence, and nobody runs it while
staring at the warning. The `--help` epilog carries the same text with zero
new surface to keep truthful.

**Making the ledger a failure.** Rejected in the ledger's own round
(wish 4 / D30): during ramp-up that pressure deletes gates instead of
adding cases. #167 asks for a usable warning, not a louder one.
