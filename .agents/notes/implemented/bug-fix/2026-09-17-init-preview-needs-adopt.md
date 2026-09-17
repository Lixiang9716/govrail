# Agent Note: init's dropped modifiers refuse instead — preview rides with adopt

Status: implemented

## Problem

The post-merge review of the round-5 fix (#235) found the same class one
branch over: flags that mean something only in combination were silently
dropped by the paths they fell into. On an INITIALIZED project a bare
`gov init --preview` answered "already initialized", exit 0, no preview;
`--upgrade --preview` ran the report as if the flag existed; `--preset X
--preview` applied the preset with the flag dropped; and on a bare
directory `--adopt X` performed a plain fresh init with the adoption
target quietly discarded. #235 had fixed uninitialized `--preview`/
`--upgrade` writing the whole plane; these four were the same shape — a
modifier an init path quietly ignores — left in the branches that fix
did not open.

The same review flagged a second duplication risk (R7): the
needs-UTF-8-restart predicate lived byte-level in both `gov/root.py`
and `tests/conftest.py`, where the copy decides whether pytest's
capture gets suspended before the re-exec — a drifted copy re-blindfolds
the gbk-locale job, the exact defect #233 fixed.

## Decision

One composition rule, checked once, state-independently, where the
`--pre-commit`/`--hooks` check already lives: `--preview` requires
`--adopt` (the only preview that exists is `--adopt <files> --preview`),
and any other combination — bare, with `--upgrade`, with `--preset`,
initialized or not — refuses with exit 2 naming both flags. The
uninitialized refusal extends to `--adopt` the same sentence #235 gave
`--upgrade`/`--preview`: a fresh init already installs the current
templates, so there is nothing to adopt into. The UTF-8 predicate moved
into `gov.root.needs_utf8_runtime`, and conftest consults it instead of
its copy — one home, two callers. Known remaining instance, recorded
not fixed: bare `--json` (scoped by help text to `--upgrade`) is still
dropped outside that combination; output-format modifiers are lower
stakes and the flag-registry tests pin its documented scoping.

## Alternatives considered

Keep ignoring the modifier where it has no meaning (the status quo) —
rejected: it is the blocker; a user asking for a preview believes one
happened. Make bare `--preview` print the drift summary instead of
refusing — rejected: that is `gov init --upgrade`'s report (the two
would diverge only in header), and a flag that silently means a
different flag is harder to reason about than a flag that refuses.
Leave the predicate duplicated with a comment pointing at root.py —
rejected: a pointer still needs a human to obey it; the conftest copy
sat exactly one careless edit away from re-blindfolding the gbk job's
report.
