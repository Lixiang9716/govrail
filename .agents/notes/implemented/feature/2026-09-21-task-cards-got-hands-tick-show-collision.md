# Agent Note: task cards got hands: tick/show, collision-tolerant resolve, a check output that stays one line per card

Status: implemented

Related: D55, issues #334, #352, #357

## Problem

Three defects in one surface, all reported from a live parallel-worker
repo. The checklist the card exists for had no way to be ticked: `gov
task --help` offered new/check/close/list/claim/release/void, so the
sanctioned workflow was hand-editing `.gov/tasks/<id>.json` — the one
move the router skill lists under "Never". Because only `[x] ` counted
(and nothing wrote it), `task check --strict` counted EVERY item of an
open card as unticked, so ticking could not have changed the verdict
even if someone had hand-ticked it; and a hand-written `[X] ` looked
ticked while the reader still called the card unfinished. Second, ids
are per-worktree counters, so parallel workers mint colliding ids and
the matcher refused every command naming such a card — `'T-0013' is
ambiguous (T-0013, T-0013, T-0013, T-0013)` — with no way in: the
filename slug matched nothing and terminal cards counted toward the
ambiguity, so the card could never be closed or voided by any command.
Third, `task check` reprinted every retired card's full `void.reason`:
adopter retirements are deliberately verbose (the reason IS the audit
trail), 24 KB in one measured repo, re-emitted on every pre-push run and
truncated by the runner where it matters.

## Decision

- `gov task tick <id> <n>` marks item n with the canonical `[x] ` prefix,
  refuses out-of-range and non-open cards by name, is idempotent, prints
  the remaining items (or the close command), and appends the
  uncommitted-mutation reminder. `gov task show <id>` renders the whole
  card: checklist state, void reason, receipt summary.
- `task check` counts only unticked items — so ticking actually moves
  `--strict` — and warns on non-canonical done-markers (`[X] `, `[✓] `…)
  that would otherwise read as progress: advisory by default, a problem
  under `--strict`.
- `_resolve` accepts three handles: the id, an id prefix, and the
  card-file stem (the slug `task new` prints, `.json` and directories
  tolerated). When several cards match and exactly ONE is still open,
  that one wins — every other match being terminal is the shape parallel
  merges leave behind. Still-ambiguous matches abort naming each
  candidate's FILE, since the ids alone are identical.
- `task check` prints one line per card; the full void reason moved
  behind `--verbose` (and `gov task show`). A summary line counts
  open/stale/done/voided so the state a reader acts on is one glance.
- Flag registry + help probed for the new surfaces (`--verbose`,
  `--strict` on check; tick/show positional), and the registry test's
  probe list extended so a future flag cannot drift unregistered.

## Alternatives considered

- **Tick via `--check-done "substring"` or a `done` field** — rejected:
  positional item numbers are what `--check` created and what the
  terminal can show; substring matching re-introduces the ambiguity the
  card ids just escaped, and a parallel field splits the single source
  of truth the checklist is.
- **Keep printing void reasons and rely on the runner's truncation** —
  rejected: the truncation eats exactly the lines a reader needs (and
  #357 documents the state that matters being hidden mid-list), while an
  unbounded gate output makes every pre-push run pay for history it is
  not asking about.
- **Make non-canonical markers a blocking problem always** — rejected:
  hand-ticked cards exist in the wild and a sudden red on an unexitable
  card is the bricked-state shape #329 spent effort removing; the
  advisory names the fix, `--strict` is where the repo opts into teeth.
- **Namespace ids per worktree at `task new`** (the issue's option a) —
  rejected as the primary fix: it changes the id contract every existing
  doc and card carries, and the collision is only fatal because the
  MATCHER refused — teaching the matcher the two extra handles fixes the
  live repos without a format migration. A global high-water allocation
  remains the better long-term shape and is not foreclosed.
