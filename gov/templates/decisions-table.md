# Decisions

The project's decision log: one entry per settled decision, numbered D0,
D1, … contiguously. Allocate numbers with `gov decision next` (it checks
the branch base for collisions), append with `gov decision add`, and
never renumber or reuse a row — decisions are addresses, not prose.

Every entry records what the decision BEAT under its Alternatives
heading; a decision without its alternatives invites re-litigation,
which is the exact failure this log exists to prevent.
`gov verify-decisions` checks numbering, the alternatives record, and
orphaned references; `gov recall` searches these entries.

## D0 — Adopt the govrail governance plane

- **Decision**: gates + notes + receipts as the working discipline
- **Alternatives**: prose-only agent rules (not checkable); ad-hoc conventions (drift silently)
