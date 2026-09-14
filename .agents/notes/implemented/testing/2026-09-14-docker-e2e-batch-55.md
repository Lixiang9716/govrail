# Agent Note: docker e2e batch 55 — an unreadable lease is busy, never stolen

Status: implemented

Related: the docker matrix + batches 1-54 notes (same series), D52
(the lease vocabulary), #119's fail-open lesson — this is the case
where fail-open priced in a double-issue

## Problem

CI's nonroot cell caught the plane's own promise breaking: the
concurrency race produced TWO winners ("exactly one winner, got
[3, 3, 3, 3, 3, 3, 0, 0]"). The window: `_create_exclusive` wins with
O_EXCL, then writes the payload a few microseconds later — in
between, the lease file EXISTS but is EMPTY. `_read_lease` fail-opens
("a half-written file names no live holder") → the second racer
classifies it as expired → `_takeover` re-checks, sees the same
empty file, and UNLINKS the first holder's lease — two valid leases
from one race. The window is microseconds wide, which is why 50+
matrices passed before a loaded CI runner hit it. The old loop also
SPUN on an unreadable file forever under --wait (takeover always
False → `continue` never reached the refusal).

## Decision

Fail-SAFE for the unreadable case, fail-open nowhere it can
double-issue:

- `_takeover` unlinks ONLY a PARSED lease whose expires_at is
  provably past; a present-but-unreadable file returns False
  (busy) with the file untouched.
- The acquire loop takes over only parsed-expired leases; an
  unreadable file falls through to the busy refusal as
  "held by '<unreadable lease>'" — which also fixes the --wait spin
  (the refusal is now reachable).

Two unit tests freeze the mid-create window (empty file) and the
tampered file: busy 3, byte-for-byte untouched, no spin under
--wait; the parsed-expired takeover keeps its existing coverage.
The e2e scenario walks the frozen window, the untouched file, and
the legal parsed-expired takeover in one journey.

## Alternatives considered

- **Write the payload before creating the file** (temp + rename) —
  rename is a second atomicity assumption per platform; the O_EXCL
  create already works everywhere and the fix is one predicate.
- **Treat unreadable as busy ONLY when small/empty** — size heuristics
  price in tampering models; unreadable means unverifiable, and
  unverifiable means busy. The holder's write lands in milliseconds;
  a tampered file now blocks loudly instead of being destroyed.

## Verification

Host: lease_unreadable_never_stolen PASS; pytest 483 passed /
2 skipped (two new), self-test 62 all pass, `gov run --mode all` 10
gates pass. Docker: all eight inner-suite cells at 105/105 (the
concurrency race included), cross×3 PASS.
