# Agent Note: the HIGHLIGHTS draft backlog cleared — nine releases rewritten for usage

Status: implemented

Related: D46 (the draft mechanism this clears), D37 (the pairing gate),
the note 2026-09-04-release-flow-drafts-highlights-sections-.md (which
introduced the handoff), issue #125's follow-up

## Problem

`gov/HIGHLIGHTS.md` carried nine sections still wearing the machine-written
heading `— (draft: copied from CHANGELOG, rewrite for usage)`: every
release from 0.24.0 through 0.29.3. D46 designed that heading as an honest
handoff — the mechanical half (version pairing) lands on the release PR, the
usage rewrite stays human — and the pairing gate did its job, so nothing
went red. But the human half had not happened for four releases' worth of
the backlog, and the file adopters read first (`gov whatsnew` prints from
it, defaulting to their init version) was release-note bullets for the
newest month of work. The gate pairs versions, not prose: a file of nine
unrewritten drafts was green, and no signal anywhere said the rewrite was
still owed. A designed handoff that nobody receives is a drop, and the drop
was silent.

## Decision

All nine sections are rewritten for usage, in the format the hand-written
sections (0.12.0–0.24.1) established: `## x.y.z — <what it does for you>`
headings, bullets that lead with the command or flag and close with the
issue/D reference, and a "why it exists" line where the feature has one.
Sources were the shipped notes and `docs/decisions.md` — not the CHANGELOG
bullets the drafts were copied from, since a usage rewrite that only
reflows release notes is the same content twice.

Two small repairs rode along: a stray copy artifact at the tail of 0.20.0's
section (a `(feat: … cost ledger …)` fragment belonging to no bullet, and
attributing the cost ledger to D43 when it is D45) was dropped — 0.23.0
documents that feature properly — and 0.24.0's prose now describes the
draft heading without reproducing the literal marker, so
`grep '(draft:' gov/HIGHLIGHTS.md` stays a truthful "what still needs
rewriting" check. It returns nothing.

## Alternatives considered

**Leaving the drafts and rewording the heading to look deliberate.** The
heading's honesty ("copied from CHANGELOG") is the useful part; dressing
it up would have made the backlog permanent *and* invisible.

**Rewriting only the newest section (0.29.3).** Everything below it is what
`gov whatsnew --since <init version>` prints for anyone initialized in the
last month: the backlog is user-visible through the same command, so a
partial clear would leave the same first impression for most readers.

**Extending `verify-doc-sync --write` to "improve" the prose.** D46 already
rejected machine-written usage prose at draft time (invented content in an
evidence costume); the same argument holds at rewrite time, where the risk
is worse — a generated rewrite would be mistaken for a human one.

**Gating on the draft marker (a section that still says "draft" fails the
build).** It would make a content backlog a release blocker, and the marker
is the writer's own text — rule 1's line: what cannot be checked belongs in
review, not in a wishful gate. The version pairing (what the gate can
honestly check) already ships; this backlog needed eyes, and the missing
mechanism was attention, not enforcement.
