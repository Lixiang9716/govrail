# Agent Note: docker e2e batch 4 — dir-format cross-container drill, the nightly tier, and the old-glibc cell

Status: implemented

Related: the docker matrix + batch 2/3 notes (same series), D40/D17 (the
dir format's structural-conflict-freedom claim, now walked across real
containers), D52 (why THIS drill uses separate clones and the lease
drill uses a shared one)

## Problem

Batch 2's cross drill proved the collision net on the sections format,
but the decisions source's OTHER format — `dir`, whose entire reason to
exist is parallel appends (one file per decision, no textual merge to
resolve) — had never been walked across containers. And the scale story
stopped at 1,200 files: the 10k-file regime where walker corner cases
(pack fan-out, accumulator drift over 50k symbols) would surface ran
nowhere, ever. The glibc axis also had exactly one point (the newest
Debian); "supported" included oldstable bookworm only by assumption.

## Decision

- **cross_dir_drill.sh** — two containers, two SEPARATE clones of one
  origin (the layout D40's net exists for; leases need a shared common
  dir, decision collisions live in repo HISTORY — different mechanisms,
  different topologies, and the batch-2/batch-4 drills now deliberately
  cover both). Arc: both agents allocate D2 from the same base (each
  add creates its OWN file — zero git conflict, the structural claim),
  the verify-decisions --base net goes red naming the D2 number
  collision, and absorption follows the tool's OWN prescribed flow —
  the refusal message says "pre-partitioning across branches needs
  every sibling to land", so the drill merges the sibling first, then
  renumbers its own D2 to D3 with no local gap, and the gate turns
  green. The refusal taught the drill; the drill now pins that the
  prescribed flow actually terminates green.
- **perf_night** — the 10k-file nightly tier: exact counts (10,000
  files, 50,000 functions, 290,000 lines) and a stated budget, gated
  behind GOV_E2E_NIGHTLY=1 / `run.sh --nightly` — minutes-wide budgets
  are a scheduled act, not a per-PR default.
- **3.10-bookworm cell** — the floor interpreter pinned to the previous
  Debian stable: the oldest-glibc × oldest-python corner, pulled
  explicitly (`python:3.10-slim-bookworm`).

## Alternatives considered

- **A shared-clone dir drill** (batch 2's architecture) — tried first,
  and it cannot collide: `decision add` self-allocates by reading the
  shared dir, so agent B never duplicates agent A's number. Separate
  branches are the collision's habitat; the lease drill keeps the
  shared clone because leases need the common dir. The two drills are
  complements by mechanism, and the README says so.
- **Dry-run `--id D3` with a local gap** — the allocator refuses it
  ("D3 skips D2"), with the refusal message prescribing the merge-first
  flow the drill implements; testing the refusal as the endpoint would
  pin a dead end instead of the working resolution.
- **Big5/zh_TW as a second hostile locale** — same wall, same code
  path (force_utf8_stdio), near-zero marginal signal over GBK; the
  nightly tier earns its minutes more.
