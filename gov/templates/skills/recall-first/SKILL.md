---
name: recall-first
description: Use before designing a solution, re-opening a settled question, writing a plan, or grepping the repo to learn why something exists — runs gov recall over notes, decisions, and postmortems so prior decisions and their rejected alternatives are read before a new proposal is written.
---

# Recall first

Memory that is written but never read is dead weight — and the failure
mode this plane exists to prevent is re-opening a decision without its
counterarguments. Before proposing, arguing, or hand-grepping for
rationale, query the memory planes.

## Procedure

1. Distill one to three terms from the task's domain words — a component
   name, a mechanism, a decision keyword. Synonyms are not followed; pick
   the term the repository itself would use.
2. Run:

   ```sh
   gov recall <term> [<term>...]
   ```

   All terms must appear; hits rank title > section heading > body, so
   the top lines are usually the answer. Every run states the corpus it
   searched on stderr (per-class counts: notes, decisions,
   postmortems), so "no match" names its boundary; a miss also prints
   per-term hit counts — `term: 0` means the corpus lacks that term,
   while a nonzero count beside a miss means the AND failed and `gov
   recall --any ...` will rank the partial matches. Exit 1 means no
   match, not "no memory" — try the other term before concluding
   absence.
3. Read the top hits **before writing anything**: a note's
   `## Alternatives considered` and a decision entry's rejected options
   are the counterarguments you must either honor or explicitly supersede.
4. If a hit governs your task, link it (path or `Dn`) in your proposal or
   PR and state only your delta — do not restate its reasoning.
5. If your change supersedes it, say so, link back, and plan the archive
   (see the archive-agent-notes skill). Supersession moves forward; the
   old note is never edited.
6. If nothing matches, you are likely first — write the note because the
   change is non-trivial on its own merits (rule 2's test: would a
   maintainer ask why?), never because an empty result set "proved"
   anything. `gov note presence` will say so again at diff time.
   (Exit 2 from `gov recall` means the memory plane is empty — nothing
   to search yet, not "no match"; exit 1 is the searched-and-found-
   nothing signal.)

## Boundaries

- Recall reads repository memory only (notes, decisions, postmortems).
  What this session already knows is not recall's business.
- When touching an old area, `gov note audit` reports staleness signals
  (dead commands, missing D-refs, unresolved paths) — discovery aids for
  the archive skill, never verdicts.
