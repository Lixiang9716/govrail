# Agent Note: docker e2e batch 46 — pairing violations name their remedy before they block, and the rerun hint is a real command

Status: implemented

Related: the docker matrix + batches 1-45 notes (same series), D3
(warn, never block — strictness is earned), #109 (the rerun hint)

## Problem

Two gate-behavior shapes were unpinned. The pairing gate's violation
contract — what counts as a violation (an .md with no .zh.md
counterpart; an orphan .zh.md is NOT one), how it is named (file plus
the translate-or-register remedy inline), and where strictness lives
(the tool exits 1, the TEMPLATE gate stays allowFailure — blocking is
a project's explicit choice) — had no e2e journey; the lifecycle only
baselines pairing and moves on. And the failure summary's rerun hint
(`rerun: gov run --gate <id>`, #109) was pinned as TEXT: nothing
proved the hinted command is real, single-gate, and turns green when
the gate is fixed.

## Decision

- **pairing_violation_contract**: baseline a pair, land an unmatched
  .md — the run output names the file with "translate it, or register
  one: --write en:… zh:…", the gate stays "FAIL pairing (advisory;
  allowFailure)" and the run exits 0; standalone verify-pairing exits
  1 counting "1 violation(s)". Flipping the gate's allowFailure makes
  the SAME tree block ("1 blocking failure") — the same violation,
  two strictness levels, both pinned.
- **run_gate_rerun**: a wired boom gate fails mode-all with the
  rerun hint in the summary; the hinted command runs exactly boom
  (no "PASS notes" anywhere), same red; fixing boom's command turns
  the rerun green.

## Alternatives considered

- **Pin the orphan.zh.md non-violation as a separate case** — folded
  into this scenario's design notes instead; the contract that
  matters at run time is the .md-side violation and its remedy.
- **Also pin verify-pairing --write registering a custom counterpart**
  — test_pairing_write_resolves_bare_stem_and_zh_side owns the write
  conventions; this scenario owns the gate's teeth.

## Verification

Host: both scenarios PASS; pytest 480 passed / 2 skipped, `gov run
--mode all` 10 gates pass. Docker: all eight inner-suite cells at
88/88, cross×3 PASS.
