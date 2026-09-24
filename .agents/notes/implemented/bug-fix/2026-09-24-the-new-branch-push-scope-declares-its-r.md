# Agent Note: the new-branch push scope declares its root; self-test is structurally immune to an ambient scope

Status: implemented

Related: D21, issues #371, #363

## Problem

The #363 pre-push template's new-branch branch exported
`GOV_CHANGE_BASE` but not `GOV_CHANGE_ROOT` — the ranged branch sets
both, and the template's own comment explains why the root matters: the
env is inherited by every subprocess a gate spawns, and a scratch repo
would otherwise be judged against a ref it never had. With the root
absent, that protection was off on exactly one path — every first push
of a new branch — and `gov self-test` (a default-DAG gate) died in its
scratch repositories on `bad object <host fork sha>`: six failures, all
tool-defect, push refused. `--no-verify` was the only way past, which
is the move the plane exists to prevent. The weakness was per-call-site:
any future branch of the hook script could drop the variable again, and
any tool spawning a repository of its own (fixture repos, worktrees)
was exposed the same way.

## Decision

- **The hook's new-branch branch declares both variables**, byte-for-byte
  like the ranged branch: `GOV_CHANGE_BASE="$fork"
  GOV_CHANGE_ROOT="$repo_root"` — the shipped template and this
  repository's installed copy move together.
- **The self-test is immune structurally, not per call site.** The
  runner scrubs `GOV_CHANGE_*` from its own environment next to the
  GIT_* wall it already has (#20) — in-process cases read `os.environ`
  directly, so a case-level strip alone left five of them red; and the
  case/fixture/replay env builders strip the pair for subprocesses too,
  in case a case spawns before the wall is up. A push scope is valid in
  the repository that declared it; nowhere else.
- A hand-set `GOV_CHANGE_BASE` with no root is still honored as written
  in the repository where it is set (the D21 contract) — the scrub is
  scoped to the self-test runner, which is not a consumer of the scope
  but a verifier of the tools.

## Alternatives considered

- **Only fix the template line** — rejected as the whole fix: it repairs
  today's branch of one script and leaves the class open; the issue's
  own repro (`GOV_CHANGE_BASE=<sha> gov self-test`) stays red, and the
  next hook edit can silently re-arm the leak.
- **Make `gov run` refuse a declared base whose root does not match the
  cwd** — rejected: it inverts the documented hand-set contract (a scope
  with no root is honored as written), breaks adopters' gate tooling
  that reads the pair for cross-repo checks, and a refusal at run time
  is the push-blocking shape this issue is about, one layer over.
- **Clear the pair inside `verify_note_presence` /
  `verify_conflict_markers` when the cwd has no such ref** — rejected:
  two more call sites guarding one leak, and "cannot diff against <sha>"
  would still be the first symptom anywhere else the env reaches.
