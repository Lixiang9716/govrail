# Agent Note: docker e2e batch 51 — a preset's skills and hints are as additive as its gates

Status: implemented

Related: the docker matrix + batches 1-50 notes (same series), D53
(additive adoption — "a local file or value is never overwritten"),
preset_adoption_bundle (the gates-and-modes half)

## Problem

The preset story was only half-told. python-lib exercises the gates-
and-modes merge; agent-heavy exercises the OTHER payloads — skill
file copies and a manifest hint — whose additivity is a different
mechanism entirely: files are copied only when absent (a locally
modified SKILL.md must survive byte-for-byte), and a manifest hint
must land without clobbering keys the project added itself.

## Decision

**preset_skills_additive**: a locally rewritten recall-first SKILL.md
and a custom manifest key survive `preset apply agent-heavy` — the
new parallel-workers skill is created (named in the output), the
modified skill is untouched, the hint writes exactly
note_presence_exempt = [".gov/tasks/**"] while custom_key stays, and
the verify-decisions gate joins governance mode. Four payloads, one
promise: additive everywhere.

## Alternatives considered

- **Apply docs-bilingual too** — its payload is a gate + hint, the
  same merge code agent-heavy already walks; a third bundle pins no
  new mechanism.
- **Pin the skip OUTPUT line for the existing skill** — the byte-for-
  byte assertion is the stronger evidence; output wording is not the
  contract.

## Verification

Host: preset_skills_additive PASS; pytest 481 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 96/96, cross×3 PASS.
