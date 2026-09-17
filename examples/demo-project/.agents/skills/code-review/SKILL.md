---
name: code-review
description: Use when reviewing a pull request in this repository; orients the reviewer to what code alone cannot show — decisions, guardrail proof, and pairing honesty — graded item by item against docs/review-rubric.md when the project maintains one.
---

# Code review

A short review with one substantiated blocker beats a list of nits. Machines already checked format, structure, and freshness; review what they cannot — with the project's rubric as the anchor when there is one, never impressions alone.

## Before reading the diff

1. Assemble the dossier in one shot:

   ```sh
   gov review --base <verified-ref>
   ```

   It carries the change scope, the in-scope notes, recall hits for the
   change's own keywords, and the rubric items — grade from the dossier,
   not from a cold repository. A dirty worktree means the PR author must
   either commit or exclude those files.
2. Find the PR's Agent Note. A non-trivial change without a note in the same PR is a blocker by rule 2 — and `gov verify-note-presence` will have said so.

## Grade against the rubric

If the project maintains `docs/review-rubric.md`, grade **only the items the diff touches**, each with observed evidence (file and line). The rubric is the closed set of judgment axes; anything outside it is either a nit (grouped at the end, non-blocking) or a new criterion being invented — propose it as a rubric item instead of repeating it ad hoc.

Without a rubric, review what only a reviewer can check:

- **Guardrail proof**: for every new gate, is there a rejection case proving it rejects an invalid case? A guard that has never failed is decoration.
- **Docs standing at HEAD**: no change narration, no citations of drafts or sessions, no reviewer-addressed justification in prose.
- **Pairing honesty**: if a `.zh.md` changed, its sidecar must be re-recorded in the same PR; "I will translate later" fails the pair gate and the PR.
- **Silent skips**: any new code path that ignores an unknown value instead of failing loud is a blocker regardless of convenience.

## Output

One line per graded rubric item — `Rn — verdict — evidence` — or one substantiated finding per axis above when there is no rubric. Then blockers with file and line. End with the explicit verdict: approve, or the blocking list.
