# Agent Note: the check gate judges the change scope, not history

Status: implemented

Related: D55

## Problem

The post-merge review of the check gate's adoption (#239) found it
red on its own promise. `gov check` scanned the WHOLE tree with no way
to scope, so a fresh adopter whose pre-existing product code carries a
#172-class violation failed their very first `gov run` — on code they
never changed while adopting (`FAIL check`, verified live on a scratch
repository). That contradicts the advisory-first posture the template
has pinned since P0-3 (`test_init_template_is_advisory_first`: a fresh
install must not go red on the first run), and D55 had decided the gate
"error 级拦截" without reconciling the two. conflict-markers avoids the
same trap by judging only changed files; the check gate had no `--base`
at all. The same review found the gate carrying `check(NONE — rule 6)`
in the coverage ledger: adopted into the root DAG without a rejection
case of its own.

## Decision

`gov check` speaks the plane's standard scoping dialect now: default
`--base auto` (the F1/D21 cascade — dirty worktree reviews the working
tree, clean reviews unpushed commits, else the last commit, else
everything), explicit `--base <ref>`, and `--all` for the whole-tree
sweep that judges legacy. The implementation imports the cascade from
verify_conflict_markers — one home, not a second dialect. The gate
command in gates.json is unchanged, so the scoping fixed the behavior
without a seal dance. `.gov/rejections/case-check.sh` lands with the
`# gate: check` declaration, pinning all three faces: first-run green
over legacy, red on a violation in scope (naming file and rule), and
`--all` reaching history. D55 is amended in place with the revision and
the debt it pays.

## Alternatives considered

`allowFailure: true` until the adopter baselines — rejected, as D55
already rejected it: the defect was the scope, not the teeth, and
advisory teeth would have re-opened the exact hole the rule-6 ledger
names. Put `--base HEAD` literally in the gate command — rejected: a
hardcoded ref is a worse approximation of "this change" than the
cascade every other content tool already speaks (a clean tree with
unpushed commits is exactly what pre-push should judge, and HEAD sees
none of it), and a second scoping dialect is the R7 duplication shape
wearing a flag. Leave the gate whole-tree and warn on init — rejected:
a warning the user cannot act on without turning the gate off is a
diploma for ignoring it.
