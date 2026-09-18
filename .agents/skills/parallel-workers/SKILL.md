---
name: parallel-workers
description: Use when two or more coding agents work the same repository in parallel — lease shared files before editing, verify under the lease, preflight the union before landing, and coordinate only through locks and task cards.
---

# Parallel workers

Several oblivious agents can work one repository in parallel, but shared
surfaces — `gates.json`, the decisions table, shared documents — are shared
state. This is the protocol the 5/10/15-worker concurrency drills
converged on: lease before editing, verify before releasing, preflight the
union before landing, and never assume you know what another worker is
doing.

## When to use

- Two or more agents (workers) may touch the same repository concurrently.
- You are about to edit a shared governance surface: `gates.json`, the
  decisions table, shared documents — anything another worker may plausibly
  edit in the same window.
- You are the integrator of a parallel batch about to land.

## Procedure

1. **Lease before editing.** Before the first edit of any shared resource:

   ```sh
   gov lease acquire <resource> --ttl <2-3x your estimate> --agent <worker id> --wait <generous>
   ```

   Exit 3 means busy — pause and retry (the holder's lease expires at the
   named instant); never edit a locked resource "quickly". When done:
   `gov lease release <resource> --agent <worker id>`.
2. **Edit only under the lease; verify before releasing.** Make the edits,
   run `gov run --every-gate`, and let it go green BEFORE releasing — a
   released-but-red resource hands the next worker your breakage as their
   starting state.
3. **Preflight the union before landing.** The integrator of a parallel
   batch rehearses it first:

   ```sh
   gov run --merge <branch>... --base <integration baseline>
   ```

   Each step's gates run on the union tree; a text conflict or a red step
   aborts named. Branch authors rebase, resolve the named conflicts, and
   resubmit — nobody lands into an unrehearsed union.
4. **Stay blind; coordinate through artifacts.** Workers do not assume
   knowledge of each other's progress. All coordination flows through
   acquire/release leases and task cards (`gov task new`, `gov task
   check`, `gov task close`) — never through assumptions about what the
   "other" agent has or has not done yet. When the shared artifact is a
   TASK CARD, claim it instead of a raw lease —
   `gov task claim <task-id> --agent <worker id> --ttl 20m` — so two
   workers cannot take one card (busy → exit 3 names the holder);
   `gov task close` clears the card's lease when it lands. **Commit the
   closed card immediately** (`git add .gov/tasks && git commit`) — card
   status lives in each worktree's copy, so an uncommitted close is
   invisible to sibling worktrees and the card can be claimed again;
   the commit is what propagates completion.

## Size the TTL, then size --wait to match

A lease has no fairness guarantee (D52) and the concurrency drills
measured what that feels like: a worker holding with `--ttl 300s` kept
its rival — waiting with `--wait 120s` — parked for the rival's ENTIRE
120 s wait, which ended in exit 3 at the deadline, and the resource
stayed blocked until the winner's full 300 s TTL ran out. Nothing hands
over early: `--wait` shorter than the holder's remaining TTL can only
ever end in exit 3 at its own deadline.

- `--ttl` ≈ 2-3x your expected critical section (edit + verify). Too
  short: a slow holder is taken over mid-edit. Too long: every loser
  waits out the whole TTL, not the work.
- `--wait` ≥ the holder's remaining TTL + margin — or skip `--wait` and
  go do other work, polling `gov task list` / `gov lease list` instead.
- Work outgrew the TTL? Release and re-acquire with a fresh TTL rather
  than letting rivals wait for a stale holder.

## Boundaries

- Leases are the liveness layer, not correctness: they prevent duplicated
  work and never replace the gates. A crashed holder's lease expires by
  TTL; correctness stays anchored in the gates and the landing checks.
- `gov lease list` is a read-only diagnostic — never an admission decision.
- Single-agent work needs none of this: `gov run` before push remains the
  whole discipline.
