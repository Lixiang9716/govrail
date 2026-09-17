# Agent Note: round 9 — the deletion push that never skipped, hollow notes, and a default gate that finally looks at code

Status: implemented

Related: D55

## Problem

Three findings from the ninth external review round, one of them the
last outstanding HIGH:

- `gov/templates/pre-push` compared `$local_ref` against the all-zero
  OID to detect deletion pushes — but git sends `local_ref="(delete)"`
  with the zero OID in `local_sha` (captured live from a real push), so
  a ref name never equals zero and NO deletion was ever skipped. A pure
  `git push origin :branch` ran the full gate DAG, and a mixed push let
  the deletion pollute the base count into an unnecessary full run.
- D3, the hollow-note item: `gov note new`'s scaffold passed
  verify-notes AS WRITTEN — the e2e scenario pinned that as the
  contract — so a note satisfying only the format (the D4 sections,
  placeholder bodies and all) sailed through the gates, making the
  empty shell the path of least resistance for rule-2 compliance.
- D1, the default-gates item, raised round after round: the injected
  gate set inspects only the governance plane, while the check engine
  D54 deferred ("事件到了再建") had since shipped — and still ran
  nowhere, not even in this repository's own gates.json.

## Decision

The deletion skip now matches `$local_sha` against the zero OID (the
wire format both sha1- and sha256-correct via the template's existing
object-format probe), and a push whose refs are ALL deletions exits 0
without invoking gov at all. verify-notes rejects an implemented note
whose required section is empty or still carries the `note new`
placeholder, naming the section (the placeholders moved into
`gov.note.PLACEHOLDERS`, one home for writer and checker). The check
gate joins the default gate set — template and this repo's own
gates.json, all mode, locked as D55 — with `gov check`'s first act as a
gate being to bite its own house: three real #172-class text-mode
spawns in this repo's tests/, found and fixed the same day.

## Alternatives considered

Also match `local_ref` against `"(delete)"` in addition to the sha —
rejected: one canonical signal (the zero oid, git's own sample-hook
convention) with a wire-format anchor test beats two tests that can
disagree. Let the scaffold pass verify-notes and rely on review to
catch hollow prose — rejected: that was the status quo, and eleven
rounds of the same finding is the evidence against trusting it to
review. Keep the check gate out of the defaults and point auditors at
`--preset` (D28's letter) — rejected in D55 itself: a decision whose
standard reading contradicts the product's own rule 1 for its entire
default install is a decision that needs revising, not re-explaining.
