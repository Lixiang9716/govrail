# Agent Note: the push scope is what the push carries: ranged bases drop untracked files, and a new branch scopes to its fork point

Status: implemented

Related: D21, issues #363, #338

## Problem

The plane's change scope mixed two different questions into one list:
"what does this range carry" and "what is sitting in the working tree".
`gitutil.changed_files` always appended `git ls-files --others`, so a
commit-range review included files that were in no commit — and on the
push path that is load-bearing. A brand-new branch takes the hook's
`full=1` route, which runs `gov run` with no base; on a dirty shared
checkout that means "review the working tree", so **someone else's
untracked scratch file could block a push it was not part of** (an
adopter measured it blocking three pushes across two sessions, and the
only escapes were ones the plane lists under Never, or a detached
worktree the docs never mentioned). After #338 the adopter's own gates
also enumerate untracked files, so the two changes together made the
sharp edge sharp.

## Decision

- **Untracked files belong to the WORKING TREE, not to a range.** In
  `gitutil.changed_files`, the untracked listing joins the set only when
  the scope IS the working tree: `base` is `HEAD` (the dirty-worktree
  cascade), `base` is None (untracked-only listings), or the repository
  has no commit yet. A ranged base — `upstream...HEAD`, a fork point, a
  remote sha — lists what the range carries and nothing else.
- **A new branch is scoped to its fork point**, not to the full matrix
  when a shared ancestor exists: the hook resolves `@{upstream}` then
  `origin/HEAD` with `git merge-base <pushed sha> <ref>` and runs
  `gov run --base <fork>`, saying so on stderr. No shared ancestor
  (a genuinely new history) still takes the full matrix.
- **The hook declares that scope to the gates**: `GOV_CHANGE_BASE` is
  exported for the run, and the change-scoped tools (`gov check`,
  `note presence`, `conflict-markers`) use it in place of their own
  cascade when it is set. A project's own gate can read the same
  variable, which is what lets a repo-local size/logging tool judge the
  push instead of the checkout (the adopter's tools are the ones that
  still scan untracked; the contract now exists for them to honor).
- **The sanctioned escape is documented** where it is needed — the
  pre-push template's own header: make the tree clean, or push the
  commit from a detached worktree. `--no-verify` is named as the last
  resort, not the fix.
- While hardening that hook: the `while read` loop's final EOF iteration
  **clears every variable it names**, so the values the new branch needs
  are captured inside the loop (`updates`, `pushed_sha`), and a blank
  line is no longer mistaken for a ref named "".

## Alternatives considered

- **Partition the report instead of fixing the scope** (the issue's
  option 2) — rejected as the primary fix: naming "these files are not
  in your push" in a failure summary still spends a gate run and still
  blocks, and the plane would be reporting a scope it knows is wrong.
- **Keep untracked in every scope and exclude them only in the hook** —
  rejected: the same confusion then bites `gov check --base <sha>` and
  every other ranged review, which is where it was first noticed; one
  rule in one place is the plane's shape.
- **A `--no-verify`-shaped flag on the hook (skip gate X)** — rejected:
  the plane's Never list holds for a reason, and a knob that skips gates
  is the parked-gate failure with a friendlier spelling.
- **Hardcode `origin/main`/`origin/master` as the fork-point refs** —
  rejected: the plane does not know a repository's default branch;
  `@{upstream}` then `origin/HEAD` is git's own answer, and a repo
  without either falls back to today's behavior.
- **Have the hook pass `--base` to each gate instead of an env var** —
  rejected: gate commands are fixed argv in gates.json and the runner
  does not append flags to them; an exported scope is how the runner can
  tell a gate what this run is about without editing the constitution.
