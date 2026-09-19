# Agent Note: task card ids are addresses — allocation is a high-water mark (#327)

Status: implemented
Related: D65, D66

## Problem

`task new` allocated the lowest free slot, so the pre-#322 re-brief
escape (delete the stale card, create a fresh one) freed a number that
the very next task reused: T-0001, once an upgrade brief, silently
became a different card. Every historical citation — a commit message,
a receipt, another card's title — now points at the wrong brief.
Decisions already fixed the principle ("ids are addresses, never
renumbered or reused"); the task registry violated it.

## Decision

`_next_id` allocates strictly beyond the high-water mark of ids that
EVER existed: current cards under `.gov/tasks/` plus every card path
git history records (`git log --name-only -- .gov/tasks/` covers
committed-then-deleted cards — the exact re-brief flow). Outside git,
allocation walks current cards only (nothing was ever committed, so
nothing can cite history). D66's batched releases ship this in the
first accumulated cut; the flow that created the collision is already
retired by #322's `task void`.

## Alternatives considered

A persisted monotonic counter in plane state — rejected: a new
persisted format under the D63 acknowledgment chain, plus state that
must survive manual cleanups, to derive what git history already
records authoritatively. Refusing re-brief entirely (void only) —
rejected: the ids fix is orthogonal; void covers exits, but any
legitimate delete-with-history still deserved non-recycling.
