# Agent Note: runtime artifacts and one-time notices: hooks re-wired, the re-baseline note prints once, the decision lock is ignored, the lease note knows worktrees

Status: implemented

Related: D37, issues #331, #336, #337, #353

## Problem

Four places where the plane described a state it did not hold, each
found by an adopter on a governed repo.

- **Executed hooks diverge from the tracked template (#331).** `gov
  update --apply` refreshes `.gov/hooks/<name>`; the copy git actually
  executes (`.git/hooks` or `core.hooksPath`) is untracked and was never
  re-wired. After two upgrades the checkout ran a hook body two
  releases old: deprecation warnings per commit today, dead command
  spellings the day the aliases go, and gates.json's
  stages/allowFailure contract bypassed the whole time.
- **The re-baseline NOTE repeats forever (#337).** Every `gov run`
  started with "the constitution was re-baselined N time(s)…" — the
  same paragraph on the hundredth run as on the first. A notice that
  never changes stops being a notice: the reader learns to skip the
  line, including the day it describes a NEW re-baseline.
- **The self-test coverage ledger read as an action item (#337).** Every
  green run ended with a per-gate `(NONE — rule 6)` list plus "write
  one: …", on a plane where the project had deliberately not authored
  project cases. A state, not an event.
- **The decision lock sits in `git status` forever (#353).** `#325`
  fixed this for the task allocator's flock anchor; the decision
  ledger's persistent lock — which must STAY (unlinking it is the
  classic lockfile race) — was never ensure-ignored, so a zero-byte
  artifact appeared in every governed checkout and a habitual
  `git add -A` would track it. The lease independence note (#336) had
  the same shape: it said "a lease coordinates THIS checkout only"
  while printing a lock root in the SHARED git dir of every linked
  worktree — two contradictory sentences, and the false one was the
  operating instruction.

## Decision

- `gov update --apply` re-wires every executed hook copy to the tracked
  template's bytes (mode 755; a file without the `# govrail:` marker is
  someone else's hook and is left alone), and `gov doctor` gains a
  `hook-sync:<name>` note naming byte drift with the one-line fix.
- `verify_plane.announce_rebaselines(tool)` prints the note once per
  observed record: the last announced timestamp lives in
  `.gov/history/rebaseline-notice` (runtime state, ensure-ignored). The
  tracked ritual ledger stays the audit trail and `gov verify-plane` the
  full-detail surface — nothing is hidden, only repeated less.
- `self-test` reports coverage as counts by default
  (`K/N gate(s) carry a project rejection case`) with no imperative;
  `--explain` restores the per-gate ledger and the case-authoring
  remedy. The undeclared-case warning (a case that ran but declares no
  gate) is unchanged — that one IS an event.
- `decision._ensure_lock_ignored` adds the ignore line at the moment
  the lock appears (idempotent, symlink-refusing, never raises), and
  the init/adopt ignore list carries `docs/.decision.lock` so fresh
  checkouts start clean. The lease note derives its wording from the
  git dirs: a linked worktree is told its lock is SHARED with its
  siblings; only the main-checkout wording claims clone independence.

## Alternatives considered

- **Fresh inits set `core.hooksPath .gov/hooks`** (the issue's
  alternative) — rejected for now: one source of truth is elegant, but
  it changes uninstall/doctor semantics and the hooks-path resolution
  every existing adopter's tooling (husky, lefthook) already relies on;
  copy-sync is the smaller move and the doctor check names drift either
  way.
- **A state file for the re-baseline note under `.gov/` (tracked)** —
  rejected: whether a human has SEEN a notice is per-checkout runtime
  state, not a project fact; putting it in the tracked tree would make
  every checkout re-announce and make the file a merge conflict.
- **Delete the re-baseline note entirely** — rejected: the note is
  #311's whole point (a rogue re-seal must cost something); once per
  record keeps that cost and drops the wallpaper.
- **Make `--explain` the self-test default and silence the ledger** —
  rejected: the counts still answer "does this repo prove its gates",
  which is the rule-6 question an operator asks first; hiding the fact
  entirely would trade one silence for another.
- **Ignore the decision lock from `.gitignore` templates in the
  adopting repo** — rejected: papering over a missing ensure-ignore is
  exactly the workaround #353 asked to end, and a template line cannot
  heal checkouts that already exist.
