# Agent Note: docker e2e batch 47 — one command adopts the preset, and note-presence's two gears

Status: implemented

Related: the docker matrix + batches 1-46 notes (same series), D53
(typed adoption bundles), D3 (warn, never block — the advisory gear)

## Problem

Two first-contact paths were unpinned. `gov init --preset` — the
one-command adoption the preset docstring advertises — had no
journey from an EMPTY repo: gates and modes landing from birth, a
repeat `preset apply` reporting already-adopted, and the wired quick
mode going green once the adopter writes the first test. And
verify-note-presence's two gears — advisory by default with the
remedy inline, --strict blocking — were pinned only by unit fixtures
on hand-built diffs.

## Decision

- **init_preset_from_scratch**: init --preset python-lib on an empty
  repo adds exactly the preset's gates ("added 2 … pytest, build"),
  quick mode ends with pytest, a repeat apply reports "already
  adopted". The E2E cells carry no pytest BY DESIGN (the wheel's
  dependency closure only), so the scenario swaps the wired gate's
  command for a stub and proves the WIRING — the mode runs the
  preset's gate on a matching change; the preset's real command
  belongs to an adopter environment. Two more discoveries recorded:
  on a tree with zero tests the wired pytest gate is loud-red ("no
  tests ran") — a preset-ergonomics question for its own decision —
  and with an EMPTY change scope the mode runs ALL its gates
  (conservative: scope-empty means run, not skip).
- **note_presence_strict**: a code commit with no note — advisory
  exits 0 with "warning (advisory; --strict to enforce)" and the
  remedy inline; --strict exits 1 with "violation (--strict)";
  committing a note turns strict green (the reviewed diff carries the
  note file).

## Alternatives considered

- **Pin the empty-tree pytest red** — it may legitimately become a
  skip if a preset-ergonomics decision says so; pinning either color
  today would make that decision a breaking test. The scenario pins
  the adoption shape and the green path instead.
- **Assert the advisory's file list verbatim** — the injected skill
  files are template content; the gear (exit code + the two gear
  lines) is the contract.

## Verification

Host: both scenarios PASS; pytest 480 passed / 2 skipped, `gov run
--mode all` 10 gates pass. Docker: all eight inner-suite cells at
90/90, cross×3 PASS.
