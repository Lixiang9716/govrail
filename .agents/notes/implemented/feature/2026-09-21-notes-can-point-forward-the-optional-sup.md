# Agent Note: notes can point forward: the optional Superseded by marker, marked by recall

Status: implemented

Related: D5, issue #364

## Problem

Rule 4's supersession has exactly one direction: the NEW note links back
to the one it replaces. Nothing makes the old note point forward, and
`Status:` has a closed set of one value (`implemented` — the lifecycle is
the directory), so a note that has been superseded is indistinguishable
from a current one. A reader who lands on it first — including through
`gov recall`, the designed entry point for "what did we decide, and
why" — gets retired guidance with no signal that it is retired. An
adopter measured the cost directly: a note describing a release-check
mechanism that was removed within the hour (and two more superseded the
same day) still read as considered, implemented advice.

## Decision

- **`Superseded by: <note>` is an optional header line.** `gov note
  verify` accepts it (every existing note stays valid), prints the pair
  as an informational line while it is reading every note anyway, and
  rejects an **empty** marker — a started-and-abandoned ritual reads as
  done, which is worse than no marker at all.
- **`gov recall` surfaces it twice**: every hit line for a superseded
  note carries ` (superseded by <target>)`, in the strict search, the
  `--any` ranking, and the `--recent` digest; and the ordering now breaks
  equal-rank ties by supersession, so the note that REPLACED another
  outranks the note it replaced. That is F4's own intent (current
  authority over frozen evidence) extended to the mid-life case, where
  nothing is archived yet.
- **The contract is documented where adopters meet it**: the notes
  README (the injected one and this repo's copy) states the line, what
  accepts it, and that superseding mid-life needs no archive pass — the
  archive skill remains the later aggregation step it always was.

## Alternatives considered

- **A second `Status:` value (`superseded`)** — rejected, and the issue
  explicitly did not ask for it: the lifecycle is the directory (D5),
  the field's single value is the design, and a superseded note is still
  an accurate record of what was implemented and why.
- **Require the marker on the old note** — rejected: rule 4's back-link
  is the required half and always will be, because only the new note's
  author knows the supersession is happening; a required forward pointer
  would fail every historical note and every note superseded by a
  decision entry instead of a note.
- **Auto-write the marker** by scanning new notes for prose like
  "supersedes <file>" — rejected for now: it edits an existing note
  (frozen content in spirit, even before archiving) on the strength of a
  prose match, and the diagnostic half of that idea (warn when a citation
  is one-sided) is cheap to add later without the write.
- **Demote superseded notes out of recall entirely** — rejected: they
  are the evidence of what was tried; `gov recall`'s job is to show
  history ranked, and the marker plus the tie-break does that without
  hiding anything.
