# Agent Note: recall quality of life: a quoted phrase searches its words, --recent primes a cold start

Status: implemented

Related: D18

## Problem

Two invocation shapes recall handled worse than its own contract
promised. A single quoted argument — `gov recall "client-modules
__DSH_BOOT__ ModuleLoader"`, the most natural way to type a
natural-language query — matched as ONE literal substring, so the query
always missed while the same words as separate arguments hit; the
per-term breakdown even printed the whole phrase as one "term", making
the miss undiagnosable. And the recall-first ritual's first step had a
cold-start hole: with no vocabulary yet, there was nothing to distill
terms FROM — `gov recall` without a query was a usage error, so the
session started with two guessed-keyword recalls and a hope.

## Decision

Every query argument splits on whitespace before matching: quote marks
are shell syntax, not a phrase operator, and `gov recall "why does X
fail"` now searches the same AND over words as the unquoted form. The
AND stays over words-in-one-entry (D18 unchanged); a miss still prints
per-term counts, now over the real terms. `gov recall --recent [N]`
(default 10, positive) needs no query and prints the N most recent
entries — title plus a one-line summary, furniture and metadata lines
skipped. Recency is the first date in the entry's address (note and
postmortem filenames are dated by convention), else the first date in
its text; an undated decision ranks by D-number, which the registry
allocates in order. Bare `gov recall` remains a usage error that names
`--recent`. Both skills that teach recall (the router's stage table and
recall-first) name the new surfaces; the flag registry pins `--recent`.

## Alternatives considered

- **Keep phrase mode and print a hint on miss** (the issue's option b)
  — rejected: a mode that has never been the documented semantics and
  always misses on natural queries is a trap with a warning sign; the
  split makes the likely invocation correct instead of diagnosed.
- **An explicit `--phrase` for literal multi-word matching** — rejected:
  no user asked for phrase search (the literal-AND ceiling discussion,
  #319, is about fuzzing, not phrases); a flag nobody wants is surface
  area to pin, document, and drift.
- **Recent digest = last N by file mtime** — rejected: mtimes are
  checkout noise, not history; the date prefix (or D-number) is the
  corpus's own, deterministic chronology.
- **Digest lists notes only** — rejected: the primer exists to expose
  what the plane knows; decisions and postmortems are memory too, and
  their recency keys fall out of the same convention.
