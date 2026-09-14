# Agent Note: docker e2e batch 9 — surfaces.json, the parallel-add lost update, and the runtime-variant evaluation

Status: implemented

Related: the docker matrix + batches 1-8 notes (same series), D25 (the
surfaces most-specific-first rule), D40 (cross-clone allocation vs
same-checkout locking), rule 5 (the malformed-mapping refusal)

## Problem

Two surfaces had never been walked end to end. `.gov/surfaces.json` —
the custom change-surface mapping (most specific first, D25) — had unit
tests for its parser but no journey: a real project defining a custom
surface, changing a file under it, and reading the suggestion. And the
parallel `decision add` story had a hole the batch-8-era code allowed:
the flock guarded only the WRITE, while the numbers READ happened
outside it — two concurrent adds in one checkout could serialize on the
file and still lose the first writer's decision to the second's stale
view. A same-checkout lost update is exactly the class the lock's own
docstring claimed was handled.

## Decision

- **surfaces_custom** (19th scenario): a custom surface
  (`experiments/**` → gates `source-limits`) — a change outside it
  falls back to gates.json paths (custom gates NOT suggested); a change
  under it names the surface and suggests its gates; a malformed
  mapping exits 2 naming the pattern (rule 5).
- **decision_parallel** (20th): two REAL processes racing for the SAME
  D2 in one checkout. Deterministic by design: exactly one exit 0, the
  other exit 1 (already-exists), the winner's decision present exactly
  once, the seed D1 untouched, no lock litter, verify-decisions green —
  and a sequential D3 after the race lands (serialization is
  observable). The first draft raced D2 against D3, which is
  NON-deterministic: whichever lands first makes the other a legal
  skip-refusal. The race is for MUTUAL EXCLUSION; ordering is a
  different assertion.
- **The fix the scenario forced**: `decision add`'s flock now covers the
  whole read-modify-write (`_locked` context manager wrapping the
  numbers read through the write), with the source RE-READ inside the
  lock — the source loaded at command start caches the file's text, so
  the stale view had merely moved from `numbers()` to the earlier load.
  A dry run reads and never writes, so it takes no lock. Host decision
  tests (18) all pass; the scenario passed three consecutive runs.
- **Kata/gVisor runtime variants: evaluated, deferred.** Both need a
  runtime plugin this Docker environment does not ship (runc only), and
  the plane's code is stdlib-Python whose behavior under a different
  OCI runtime differs (if at all) in syscalls the suite doesn't touch
  (no cgroups, no networking, no userns). Revisit if a runtime-specific
  incident exists. Recorded in the README with the same shape as the
  Big5 deferral.

## Alternatives considered

- **Race D2 against D3** — non-deterministic (first-lander wins, the
  other is a legal skip-refusal); mutual exclusion is the deterministic
  contract of the lock, ordering belongs to `decision next --base`.
- **Fix the lost update by locking inside `numbers()`** — locks the
  read but not the whole validate+write region; the refusal exits inside
  the region would release fine, but the write would sit outside again.
  The region wrapper is the honest shape.
