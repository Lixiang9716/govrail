# Agent Note: vacuous verdicts named, run output evidence unclipped (D65)

Status: implemented
Related: D65

## Problem

Three gates reported verdicts their mechanics could not back. `gov
check` — the default template's only product-code gate — passed clean
for any project in PHP/Ruby/C#-class languages because NOTHING WAS
CHECKED: a fresh install read green precisely where rule 6 says a gate
that never fails is vacuous. `gov run` printed a failing gate's output
twice (body + summary tail) and the passed-gate tail cap hid the
`base=` judgment line that justifies the verdict it truncated. Notes
enforcement could be satisfied by a content-free template note: the
format gate checks structure, and nothing surfaced the boilerplate.

## Decision

`gov check` now prints `SKIP(nolang: php (2), …)` for source files no
shipped rule can judge — the judged scope only — and `--strict` turns
an unjudged source file into a blocking failure; `gov doctor` names the
project whose languages the check gate cannot reach (note, not problem:
P0-3 holds). `gov run` prints a failing gate's evidence exactly once in
the body under an outcome-specific header (`(failed)` / `(timed out)` /
`(command missing)`), the summary keeps only the rerun pointer, and the
passed-gate budget keeps head 2 + tail 3 so the `base=` line survives.
`gov note verify` emits per-section thinness advisories (word floor,
exit-code neutral), and `gov note audit` reports boilerplate-suspect
pairs (normalized similarity ≥ 85%); the python-lib preset lands
`.gov/note-presence.json` with `require: ["**/*.py"]` so strict
attribution is one preset away.

## Alternatives considered

Failing `gov check` outright on nolang files by default — rejected:
a fresh install must not go red on day one (P0-3), and the skip line
plus --strict gives teams the choice. Dropping the passed-gate cap
entirely — rejected: chatty passing gates bury the verdict (D20's
budget exists); head+tail keeps both the judgment and the outcome.
Making thin notes a blocking violation — rejected: substance is a
human judgment; a machine word floor that blocks would train exactly
the padding it tries to catch.
