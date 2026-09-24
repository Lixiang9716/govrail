# Agent Note: a scoped run: --only-paths judges one worker's paths; every run leaves full evidence in .gov/last-run/

Status: implemented

Related: D21, D15, issues #374, #375, #363

## Problem

Two defects on the same surface, both from live multi-worker
repositories. First, `gov run` auto-scopes to the WHOLE dirty worktree,
so three concurrent workers in one checkout could not tell which gate
verdicts were theirs: worker B went red on worker A's in-flight JS, the
advisory note-presence warning spanned 42-44 files from three workers,
and there was no machine-readable way to say "judge only my lease's
paths" — the last runner owned everyone's noise. Second, a red DAG with
long gate output truncated its evidence mid-failure ("N earlier lines
not shown"), and the only way to read the failure was one `--gate`
re-run per red gate — four extra DAG executions to read four failures.

## Decision

- **`gov run --only-paths <glob,...>`** intersects the changed-file set
  (the auto cascade: working tree when dirty, the unpushed range when
  clean) with the declared globs, and path-scoped gates select against
  THAT set; unpathed gates keep judging the repository (self-test,
  plane, lint are not file-scoped judgments). The declared set is
  exported to the gates as `GOV_CHANGE_PATHS`, root-guarded exactly
  like `GOV_CHANGE_BASE` (#363's lesson — a scope is valid in the
  repository that declared it), and the in-box scoped tools
  (conflict-markers, note-presence — which the check gate funnels
  through) filter their file listings with it. An intersection that
  keeps NOTHING is a named exit 2: a scoped run that would judge
  nothing is a caller typo, not a green zero (rule 5). Exits are
  exclusive with --gate/--mode/--base/--every-gate; the union of every
  worker's paths is still what the pre-push hook verifies at push.
- **`.gov/last-run/<gate>.log`**: every gate with output leaves its
  FULL captured output there, cleared per run, gitignored (init and
  `update --apply` both ensure the line). The failure summary's rerun
  line names the file; the PASS-with-output truncation marker names it
  too. One run yields all the evidence; reading a failure never costs
  a re-run.
- The router skill's `gov run` stage line names the scoping surface,
  and the SKILL.md budget ceiling is raised 11100 → 11250 for it (the
  reviewed-diff path the budget gate itself names).

## Alternatives considered

- **`gov run --lease <resource>`** (the issue's other shape) — declined
  for now: leases do not record path sets (they are mutual-exclusion
  tokens over a resource name), so a lease-derived scope would have
  nothing to intersect with; the honest prerequisite is leases that
  name paths, and --only-paths is the primitive that needs nothing new.
  A future `--lease` can be sugar for "read the lease's paths, pass
  them here".
- **Attribute files to workers post-hoc** (partition the failure
  report by lease) — rejected: reporting whose noise a red gate is
  still spends the run and still blocks; intersecting the set BEFORE
  selection means worker B never runs worker A's gates.
- **Write evidence only for red gates** — rejected: a pass-with-output
  truncation hides warnings the same way, and "the evidence of the last
  run" is a simpler contract than "the evidence of the failures of the
  last run".
- **Keep the evidence in .gov/history/gates.jsonl only** — the ledger
  clips detail at its cap and is append-only history; a per-run
  overwritable directory matches what "last run" means and never
  grows.
