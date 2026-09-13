# Agent Note: docker e2e batch 42 — adoption's exit and re-entry are idempotent, and a project mode runs exactly its list

Status: implemented

Related: the docker matrix + batches 1-41 notes (same series), D23
(uninstall/re-init two-step), the gates.json modes vocabulary, the
lifecycle scenario (adoption's first day — this is its last)

## Problem

The adoption lifecycle's EXIT had no journey. `gov uninstall` removes
the injected governance — but nothing pinned that it removes exactly
that (no stray .gov/.agents/gates.json), that a repeat init says
"already initialized" without duplicating a single gate, that a
second uninstall refuses calmly rather than crashing, or that re-init
re-injects the same set and runs green. On the same sweep, a
project-DECLARED mode (the modes vocabulary beyond all/quick) had no
e2e proof that it runs exactly its list — neither more nor fewer —
and that an unknown mode names the known ones.

## Decision

- **uninstall_reinit_roundtrip**: init twice (second says "already
  initialized", gate count identical); uninstall leaves only the git
  dir (gates.json, AGENTS.md, .gov, .agents all gone); a second
  uninstall exits 2 with "not initialized" (a refusal, calibrated —
  the host pipe had hidden the real code); re-init restores the SAME
  gate count and `gov run --mode quick` passes.
- **custom_mode_scoping**: a hand-declared mode "deep" over the first
  two gate ids runs those two PASSes and NONE of the others; mode
  "all" still spans every gate (verdict PRESENCE, not color — pairing
  runs advisory-fail until baselined); `--mode no-such-mode` exits 2
  with "unknown mode … (known: all, quick, governance, deep)".

## Alternatives considered

- **Pin the mode union's verdict COLORS** — pairing's advisory state
  is a project choice (baseline it and the color flips); which gates
  RAN is the mode's contract, what they concluded is each gate's.
- **Also pin `init --hooks/--ci` here** — a self-test case walks that
  roundtrip on every lifecycle run already; the uninstall half was
  the uncovered one.

## Verification

Host: both scenarios PASS; pytest 480 passed / 2 skipped, self-test
62 all pass, `gov run --mode all` 10 gates pass. Docker: all eight
inner-suite cells at 81/81, cross×3 PASS, nightly tiers 1 and 2.
