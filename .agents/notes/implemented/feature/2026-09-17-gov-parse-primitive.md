# Agent Note: gov parse — the parse layer becomes a declared primitive

Status: implemented

Related: D54

## Problem

Issue #265 came from a real adopter gate (dsh-mobile's code-size limit:
files ≤500 lines / functions ≤50 / indent ≤5). The gate started as
~200 lines of per-project regex + brace-depth heuristic even though
govrail ships the exact parser it needed — because the tree-sitter
stack was load-bearing but UNDECLARED as an interface: nothing said
custom gates may import it, and the same adopter separately pinned
`tree-sitter==0.23.*` in CI for a local Python 3.9, downgrading the
core out from under the grammar packs (language ABI 15 vs 13-14 —
govrail's own parse layer broke live).

## Decision

`gov parse <path>... [--json] [--lang L]`: per-file structure facts
from the SAME walk `gov stats` aggregates — function spans
(name/start/end/inner-depth), line counts, max depth, parse errors.
Polarity per D56: --json is exactly one array on stdout; the human
report is stdout by default and moves to stderr under --json.
Unsupported files are skipped and NAMED (facts, not verdicts — the
command never exits 1). D54 amended in place: the stack is an
interface — govrail ships core + grammars, custom gates may import
them, and tree-sitter's version is managed by govrail (a project pin
downgrades the core out from under the grammars; proven live). README
(en/zh) now declares the interface beside the new command.

## Alternatives considered

Fold per-file detail into `gov stats` — rejected: stats is an
aggregate by design (facts per LANGUAGE), while a size gate needs
per-FILE spans; overloading one command with two shapes re-runs the
polarity problem. A separate `gov parse` module — rejected: the walk,
line classification, and depth semantics live in stats.py, and a second
implementation is the R7 duplication shape; the command reuses
`_walk_metrics` with spans added. Emit raw indent levels as text —
rejected: syntactic nesting depth (pack.nesting) is the honest measure
of what the gate means by "indent ≤5", and it is grammar-aware where
column counting is whitespace-blind.
