# Agent Note: the checklist is a contract again: close refuses unticked items, and a lease names its card

Status: implemented

Related: D55, issues #332, #358

## Problem

Two ways the task plane's own promises were decorative.

- **The checklist was unenforceable (#358).** `gov task close` stamped a
  green receipt with every item still unchecked — the card went `done`
  with all seven `[ ]` printed by `gov task list` — and the shipped
  `task` gate (mode `all`, the pre-push DAG) ran the non-strict form
  that reports unticked items neither as a warning nor as a failure. A
  card whose whole reason to exist is "a contract between the caller and
  the plane" could not fail on its contract. (`tick` landing in the
  previous batch removed the "cannot be ticked at all" half; nothing
  read the state yet.)
- **A lease keyed by the bare id (#332).** Card ids are per-worktree
  high-water marks, so two workers' `T-0003` cards are different cards
  that shared one lease key — while the lock root is the COMMON git dir,
  so linked worktrees contend. One worker's dead 8h lease blocked the
  other's card, `gov task release` is holder-verified by design, and the
  only recovery was a human running release on the dead holder's behalf.

## Decision

- `gov task close` refuses while items remain unticked, naming the count
  and the numbers and both exits: tick what the work satisfies (`gov
  task tick <id> <n>`), or void the card if the checklist no longer
  describes the work. The refusal happens BEFORE the gate run, so a card
  that cannot close does not spend a DAG. This is a gate with a door —
  both exits exist and are cheap — not the bricked shape #329 removed.
- The default `task check` report names the state instead of hiding it:
  `5 card(s) — 3 open (18 unticked item(s); --strict blocks on them), 0
  stale, 2 done, 0 voided`. Advisory, because an in-flight card is
  ALLOWED to carry unticked items — that is what "open" means — and
  `--strict` remains the repo's opt-in to teeth.
- `_lease_resource(card)` keys a claim by the card's own identity: the
  id plus the card's `created` stamp (the issue's hash(title+created)
  shape, readable so a lease file names its card at a glance). Every
  command derives the same key from the same card file; `gov task
  release` resolves the card first for exactly that reason.

## Alternatives considered

- **Warn on close instead of refusing** — rejected: a warning on the one
  path whose entire job is to certify the contract is the decorative
  behavior #358 reports; and with `tick` shipped, the refusal's remedy
  is one command per item.
- **Make the shipped gate strict by default** — rejected: an open card
  in flight legitimately carries unticked items, and a red pre-push for
  everyday mid-work state is how a gate earns being parked. Rule 9's
  teeth are at the close boundary (the card must not be certified), and
  `--strict` stays available for repos that want more.
- **Refuse close unless ALL items are ticked, with no override** —
  considered and kept: the alternative (a `--skip-checklist` flag)
  creates the bypass the contract exists to deny, and `void` already
  covers "the checklist is no longer true" as a recorded act.
- **Key the lease by the card file's path** (the issue's first
  suggestion) — rejected: paths are worktree-relative, so the same card
  reached from a linked worktree and from its own directory would carry
  two keys; the `created` stamp travels with the card. A global
  high-water allocator remains the larger fix and is not foreclosed.
- **`task release --force --reason` for dead holders** (the issue's
  interim suggestion) — not taken now: it is a lease-layer act with
  ledger semantics (who stole whose claim, recorded where) and deserves
  its own decision rather than riding in on the key change.
