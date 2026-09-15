# Decisions

The project's decision log: one row per settled decision, numbered D0,
D1, … contiguously. Allocate numbers with `gov decision next` (it checks
the branch base for collisions), append with `gov decision add`, and
never renumber or reuse a row — decisions are addresses, not prose.

Every row records what the decision BEAT in its Alternatives column; a
decision without its alternatives invites re-litigation, which is the
exact failure this log exists to prevent. `gov verify-decisions` checks
numbering, the alternatives column, and orphaned references; `gov
recall` searches these rows.

| ID | Decision | Alternatives |
|----|----------|--------------|
| D0 | Adopt the govrail governance plane (gates + notes + receipts) | prose-only agent rules; ad-hoc conventions — neither is checkable, and both drift |
