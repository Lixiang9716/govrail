# Agent Notes

One kind of design doc lives here. An **Agent Note** records a decision — the
*why* and *what we gave up*, the parts code and docs cannot carry. Agents and
humans write them; `gov verify-notes` enforces the format mechanically.

## Layout

A note's path encodes its lifecycle and class:
`{lifecycle}/{class}/yyyy-mm-dd-topic-title.md`.

- **Lifecycle** (two states): `implemented/` — the decision shipped, kept
  current with the shipped facts; `archived/` — frozen, never edited, not
  current authority.
- **Class** (closed set): `feature`, `bug-fix`, `simplification`,
  `architecture`, `process`, `testing`.
- The filename date is when the topic was **first proposed**. Notes are
  English-only.

## Format

The header is a title and a status line:

```
# Agent Note: <title>

Status: implemented
```

The value is exactly `implemented` — the lifecycle state itself is
the directory (`implemented/` vs `archived/`), never the field.

The body carries three required sections, in this order:

```
## Problem
## Decision
## Alternatives considered
```

- `## Problem` — the motivation, written to stand without the solution.
- `## Decision` — what shipped, present tense.
- `## Alternatives considered` — each genuine alternative and why it lost.
  **Mandatory**: a decision recorded without what it beat invites re-litigation.

`## Consequences` is optional: state what the trade-off cost and bought. Other
sections (`## Testing`, `## Related`) are allowed and not enforced. `gov verify-notes`
rejects a note missing any required section.

## When to write one

Every non-trivial change adds or updates at least one note in the same PR. A
change is non-trivial when it alters behavior, architecture, a cross-file
contract, process/tooling, or a decision a maintainer may revisit. Test: would
a maintainer a month later ask "why was this done?" Purely mechanical or local
edits are exempt.

When a note is fully superseded, the successor absorbs its unique rationale and
links back, then the old note moves to `archived/`.

## Archiving

Archived notes are frozen: never edit, move, or delete them, and do not treat
them as authority for current behavior. Supersede an implemented note with a new
one; keep both cross-linked.
