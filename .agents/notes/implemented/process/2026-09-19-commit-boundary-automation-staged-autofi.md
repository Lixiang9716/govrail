# Agent Note: commit-boundary automation: staged autofix + staged derivation + evidence rubric R10

Status: implemented
Related: D64

## Problem

The efficiency bottleneck for high-frequency agent code generation is
feedback-loop length. Lint violations and derived-truth drift both went
red at the push boundary (the DAG) or later (CI) — #294's 69 ruff
findings rode a mechanical refactor all the way to master because no
boundary before CI could see them. Meanwhile, load-bearing claims in PR
descriptions ("tests pass", "the gate rejects") had no rubric item
holding them to verifiable coordinates, so agent self-report and
evidence were indistinguishable at review time. The DSH comparison
found both halves solved upstream: lefthook's staged `--fix` +
`stage_fixed` and "regenerate rather than reject" jobs on the commit
boundary, and committed-artifact citations on the review boundary.

## Decision

- **`staged-lint` gate** (pre-commit stage, blocking, dogfood-only):
  `scripts/staged_lint.py` runs `ruff check --fix` over staged *.py
  files and restages the fixes — an agent's commit is mechanically
  cleaned at commit time instead of costing a red-CI round trip. One
  hardening beyond the DSH prototype: a file whose staged content
  differs from its worktree content is **skipped by name** (a worktree
  fix re-added would silently swallow changes the author deliberately
  kept out of the commit); skipped files with findings still go red.
- **`staged-derive` gate** (same contract): `scripts/staged_derive.py`
  checks whether any staged file is an input to a derived truth (gov/,
  templates, skills, rules, rejection cases, the derivation tooling
  itself) and, if so, runs `scripts/derive_all.py` now and restages the
  outputs — regeneration is the fix, rejection is the fallback. A repo
  without the derivation surface is a named skip.
- Both gates ride the existing stage contract (the hook runner appends
  `--staged` and applies DAG semantics), live in `modes.all` as named
  no-ops outside a commit context, and carry six rejection-case legs
  across the two cases (fixable→restaged, unfixable→red,
  partial-staging protection, non-input no-op, failing derivation,
  surface-absent skip).
- **R10 in the review rubric** (en+zh): every load-bearing claim in a
  PR description cites a verifiable coordinate — receipt id, named test
  count, committed-artifact location, or gate output; "trust me, all
  green" is the named anti-pattern. Gate candidate marked partial:
  existence and resolvability are checkable, sufficiency is judgment.
- **This repo installed its own hooks** (`gov init --hooks
  --pre-commit`) for the first time — the plane now eats its own commit
  boundary, which is also what makes the two new gates real rather
  than vacuous.

## Alternatives considered

- **Putting `--fix`/regeneration into the existing lint/derive gate
  bodies** — rejected: it would force staged semantics onto gates whose
  contract is whole-tree (the gate is an external command; its command
  slot is data), and adopters have no derivation surface — the stage
  gates are dogfood-only by construction.
- **Skipping partially-staged files silently** — rejected: a silent
  skip trains people to ignore it; named skip plus red-on-findings is
  the fail-loud shape.
- **Not installing the hooks here** — rejected: writing stage gates
  that never fire in their own repo is rule 6's live opposite.
