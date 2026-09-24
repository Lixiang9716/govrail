# Agent Note: parse facts are single-visit; ArkTS rides the TypeScript grammar

Status: implemented

Related: D54, issues #372, #377, #265, #270

## Problem

`gov parse` on a real Swift file reported 42 functions for 16 `func`
declarations, rendered every table row as the column NAMES
(`name  start-end  depth depth`), and filed the same span twice — so a
size gate reported six violations for four genuinely-over functions,
under start lines that pointed into signature continuations, twice for
one of them. Two defects in one walk: `_walk_metrics` visited a
function node's children TWICE (once at depth 0 for the function's own
inner depth, once at the tree-walk depth), double-counting every nested
function, closure, class, and ERROR node inside a function body and
duplicating its span; and the human table iterated the span DICTS,
unpacking each one's four keys (`name`, `start`, `end`, `depth`) into
the row format's placeholders. Separately, a host tree could grow a
language no gate saw: ArkTS (`.ets`) matched no pack, so `gov check`
SKIPped it ("no rules") and the parse/size primitives never scanned it —
a 596-line `.ets` file was invisible while its Kotlin twin was gated.

## Decision

- **One child walk serves both measurements.** A function node's
  children recurse exactly once, at the body's own depth; `inner` is
  the subtree's deepest level minus the body's top (depth carries only
  nesting increments, so the difference is levels-inside). Counts,
  spans, error tallies, and `public` all land once per node — the
  outer-before-inner append order becomes inner-first, which no
  consumer keyed on (the size gate reads spans, not row order).
- **The table renders the values.** Rows index the span dicts by key;
  a row reads `a  2-2  depth 1` and cannot degenerate into the column
  names again.
- **ArkTS joins the parse layer** (`gov/langs/arkts.json`): `.ets`
  rides `tree_sitter_typescript` (ArkTS is a TS dialect; the grammar is
  real, not an indent heuristic), with the typescript pack's kind sets
  plus interface/enum declarations — same known-answer snippet
  contract every shipped pack carries. `gov parse`/`gov stats`/the
  size primitive now see a host's `.ets` files; `gov check` still
  SKIPs them ("no rules") until honest rules ship, which is the same
  grammar-first path Swift and Kotlin took (#335).
- **The adopter-side half of #377 stays adopter-side.** The "parse
  errors — falling back" warning and heuristic-backend labeling in the
  report are the adopter's size-gate tool's own strings; the honest
  data it needs to split "parsed with errors" from "never parsed" is
  in the contract (per-file `parse_errors`, `skipped` entries with
  reasons), and now every language a host actually uses is in the
  parsed set.

## Alternatives considered

- **Treat the closure double-count as intended** (closures ARE
  functions) — the count being twice the truth was never the intended
  part; one closure, one span, one row is the fact. Closures still
  count once each (the `lambda_literal` kind stays in the Swift pack):
  a 50-line closure over the size rule is exactly what the gate should
  see.
- **Drop the anonymous `function` keyword-child span for ArkTS** (a
  `function_declaration`'s keyword subtree shares the `function` kind
  with function expressions) — rejected: the shipped typescript pack
  carries the same shape, and dropping the kind loses real function
  expressions; one convention across the TS-family packs is worth one
  small keyword span.
- **A hand-written ArkTS grammar** — rejected: no shipped binding, and
  a TS-dialect grammar beats no coverage while a real one matures;
  upgrade is a pack edit (the packs are data).
