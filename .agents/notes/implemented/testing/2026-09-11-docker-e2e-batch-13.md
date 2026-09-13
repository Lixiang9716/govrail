# Agent Note: docker e2e batch 13 — the dossier's recall section, and the demo upgrade surface that caught a silent init

Status: implemented

Related: the docker matrix + batches 1-12 notes (same series), the
review workbench (D30: human decides, machine transcribes), rule 5 (an
explicit flag must not be silently ignored), the demo specimen (D33's
living example)

## Problem

Two more judgment-adjacent surfaces had no journey. The review
dossier's recall section — the "read memory before judging" step whose
terms are PATH TOKENS of the change — ran only through unit fixtures;
no E2E proved a real diff's path tokens recall the note that remembers
them, with the rubric section composing alongside. And the demo
specimen had no manifest (it is a static example), which batch 12's
demo_specimen could not have surfaced — until demo_upgrade_surface
walked `gov init --upgrade` over it and the FIRST run went red: the
demo was silently FULLY INITIALIZED by the --upgrade flag. Same for
--adopt. Only --adopt-new had the uninitialized guard; --upgrade and
--adopt ran a fresh init and manufactured a manifest out of flags that
say "report drift" / "land files".

## Decision

- **review_dossier_recall** (27th scenario): a diff touching
  `fx/hedge-rates.py` — the recall terms are its path tokens ("hedge",
  "rates"); the dossier's recall section must name the remembered note
  (`2026-01-01-hedge-rates.md`) and, once a rubric exists, compose the
  rubric section (R1) alongside. The term extraction contract (>= 4
  chars, not stopwords) is the thing under test — it is how the
  reviewer is told "you are not the first".
- **demo_upgrade_surface** (28th): the demo specimen's drift surface,
  now that the guard exists — `init --upgrade`/`--adopt all` on an
  UNINITIALIZED copy must exit 2 naming "initialized project" and must
  NOT manufacture a manifest; initialized, `--upgrade --json` reports
  `initialized_with`/`package`/`files` as exactly one value.
- **A pinned contract caught my fix, and stood**: the scenario's first
  draft refused `--upgrade`/`--adopt` on an uninitialized project (rule
  5, matching --adopt-new's guard) — and the host suite went red:
  tests/test_cli.py pins `init --upgrade` on an uninitialized project
  as the NORMAL INIT PATH (assert == 0). The pinned contract stands; my
  guard was reverted the same hour, and the scenario now pins the REAL
  behavior (the convenience path initializes for real; the drift report
  surfaces on the second call). The design question — guard it like
  --adopt-new, or keep the convenience — is flagged here for the
  maintainer; superseding the pin is a decision row, not a test edit.
- **The demo copy's git state** (init + commit before the git-driven
  gates) also landed in the scenario — the matrix run failed on exactly
  that until the copy was a repository.

## Alternatives considered

- **Keep the silent init as convenience** — a flag that says "report
  drift" silently CREATING the thing it reports on is the anti-pattern
  rule 5 exists to kill; convenience is `gov init`, one word shorter.
- **Assert the dossier's evidence candidates** — leads to verify, not
  verdicts; the layout would over-constrain the presentation.
