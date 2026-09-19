# Agent Note: persistence acknowledgment chain: declared shapes move only with records

Status: implemented
Related: D63

## Problem

Every format the plane writes to disk — the seal, the ritual and
surprise ledgers, task cards, run receipts, the manifest, pairing
state, the note contract, gates.json — is adopter user data that must
keep working across releases. Nothing declared what those shapes are,
when they changed, or whether a change broke older readers: the
knowledge lived implicitly in code, and one refactor touching a
`json.dumps` call could silently strand an adopter's existing `.gov/`
data. The DSH comparison found the discipline fully mechanized
upstream (persistence-changes: declared types, digest-chained acknowledgment
records, a verifying gate) and this round ports the shape at govrail's
scale.

## Decision

`docs/persistence/` now carries the discipline (D63):

- **Ten declared types** as shape descriptors under `schemas/`
  (plane-seal, rituals-ledger, surprises-ledger, task-card, run-receipt,
  manifest, pairing-config, pairing-record, note-file, gates-config) —
  each authored from the code that writes and reads the format, naming
  artifact, writer, readers, runtime class (tracked vs
  runtime-deletable), and fields.
- **`changes/` acknowledgment records**: one fenced JSON block per
  record — number, date, class (`baseline`/`compatible`/`breaking`),
  per-type `before`/`after` digests. Record 0001 is the baseline.
- **The `persistence` gate** (blocking, dogfood-only): linear chain per
  type (successor's `before` == predecessor's `after`; baseline seeds
  with null), the newest `after` anchored to the live schema file's
  sha256 — touching a schema without a record is red — TODO drafts red,
  generated `catalog.json` must be fresh, unreadable descriptors exit 2
  (rule 5). Rejection case proves six legs; case is repo-only.
- **Honest boundary, stated in the README**: the gate proves in-tree
  chain consistency anchored to the declared shapes; code conformance
  to the schemas is review and tests, not this gate — DSH states the
  same limit for its verifier.
- Truth-source register row 18 (en+zh) names the inventory with this
  gate as its pin. Class semantics: `compatible` keeps older readers
  working; `breaking` means older readers refuse loudly and `gov
  update` owns the migration, stated in the record; `.gov/history/`
  companions are acknowledged but never migrated (N9).

## Alternatives considered

- **Runtime schema validation of actual artifacts** — deferred: it
  needs artifact construction per format and a validation dependency;
  the readable field descriptors carry the same communication value at
  a fraction of the cost. A separate, evidence-gated decision.
- **Anchoring digests to git history instead of the record chain** —
  rejected: history-rewrite resistance is already guaranteed
  structurally (register row 17); chaining adds the review-facing
  property git cannot give — each change named, classified, and
  diffable.
- **Shipping the gate in the adopter template** — deferred: the
  discipline and docs travel with the product for adopters who want
  them, but the gate enters the template DAG only with run evidence
  (P0-3 polarity discipline, the lint-gate precedent).
