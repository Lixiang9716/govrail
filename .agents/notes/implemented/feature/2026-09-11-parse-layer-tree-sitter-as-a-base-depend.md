# Agent Note: parse layer — tree-sitter as a base dependency and gov stats

Status: implemented

Related: D54 (this decision), D1 (superseded in part — see below), D47
(the clean-replay premise this re-hones), D32/D44 (ledger anchoring and the
metrics/evidence line), D28 (templates stay language-free), D15 (glob
semantics), 0.29.1's "OS Independent made honest" (made honest again,
differently)

## Problem

The plane's entire knowledge of code was textual: `paths` globs, diff
scopes, conflict-marker greps. Adopter-side asks with real demand behind
them — complexity trend, structural facts, syntax-class static checks —
had no carrier: build a second toolchain (against the single-implementation
decision) or never. And "language-agnostic", the plane's own headline
claim, had never been tested against a non-Python instance: every shipped
preset is Python or docs. The real question was sharper than "add
tree-sitter": can the plane gain syntactic awareness WITHOUT handing
verdicts to an approximate frontend?

## Decision

tree-sitter (core + 8 official grammar packs: python, go, java, rust,
javascript, typescript, c, cpp) joins the BASE dependencies; `gov stats`
is the first consumer. The boundary that keeps it honest: the syntax layer
is used only where the syntax answer IS the answer — structure, shape,
counts, patterns. Anything needing types or flow (undefined symbols,
type errors, call graphs) is out, because an approximate frontend's
misses are SILENT, and a green check that misses is worse than a red one
that nags. Compile-level truth stays with each language's own compiler —
which is already a gate.

Mechanics, each answering a failure we actually hit or audited:

- Language packs are DATA (`gov/langs/*.json`), outside `gov/templates/`
  on purpose — templates enter the drift/adoption inventory (D34), and a
  grammar rule table must ship with the tool, not be injected into
  projects. Every node kind a pack names is validated against the
  grammar's kind table at load; an unknown kind REFUSES to load, named.
  This caught three real errors during development alone (java's
  `switch_statement` is `switch`, its for-each is `for_statement`, its
  text block is the hidden `_multiline_string_literal`) — a wrong kind
  silently zeroes its metric, and a plausible zero is the worst lie a
  metrics command can tell.
- File sets are declared per pack over a shared exclude floor (VCS,
  venvs, build outputs, caches); walk results name what was excluded.
  Parse errors (tree-sitter never raises — ERROR nodes are the only
  signal) are counted and the file named, never silently "checked".
- Metrics ship with their counting rules echoed in the output (a
  docstring is a string, not a comment — multi-line strings count as
  CODE; a function's depth is measured inside its body, from zero) and
  with hand-countable known-answer fixtures — the prototype's first
  depth walk recorded entry depth instead of subtree max and reported a
  flat, believable 0; the fixtures exist so that bug class cannot ship.
- `gov stats --record` appends to `.gov/history/stats.jsonl` under the
  SAME anchoring as the run ledger (D32, extracted into `gov/anchor.py`
  — one fact, one home). The stats ledger is metrics, not evidence: it
  participates in no verification, per D44's line, and trend may read it
  later the way it reads durations today.
- doctor gains a parser check (dependency importable, per-grammar
  versions, pack validation) appended AFTER the legacy checks;
  MIN_PYTHON moves to (3, 10) with the dependency's own floor.

D1 is narrowed, explicitly: single implementation (the shipped code is
still pure Python) and the argv-array gate contract are untouched; the
"install prerequisite = Python 3" clause becomes "Python 3.10 plus the
declared parser bindings". requires-python moves to >=3.10 (tree-sitter
0.26's floor; 3.9 is EOL). The `OS Independent` classifier is RETIRED —
a C extension makes the pure-wheel claim false again, and that claim was
made honest once already (0.29.1); this time the metadata changes instead
of re-learning it. Wheels were verified to exist for all nine packages on
all seven CI-relevant targets (glibc/musl x86_64+aarch64, macOS both,
Windows both) before any code was written. The D47 clean-replay docs no
longer claim a package copy is a "complete environment": the compiled
dependency resolves from the interpreter's site-packages in both
environments, and the one dishonest corner (a dependency importable only
via PYTHONPATH promotion) is stated in the classifier's own output
surface. README (both sides), architecture (both sides), and the package
docstrings were made honest in the same PR, pairs re-confirmed.

## Alternatives considered

- **Write our own parsers** — N languages x one implementation, drifting
  into green-on-uncompilable-code. The direction's biggest risk is
  exactly its most tempting part.
- **Consume toolchain diagnostics only** (vet/clippy/ruff JSON) — the
  right answer for SEMANTIC checks later (that layer is genuinely
  language-neutral), but it provides no structural metrics and no
  complexity trend; complementary, not a substitute.
- **Do nothing until a compiler/LSP integration exists** — the demand is
  real and would grow outside the plane, un-governed.
- **Keep `OS Independent`** — with a C extension it is claims-wider-than-
  capability, the packaging edition of a vacuous green; rejected.
- **tree-sitter as an optional extra** — keeps 3.9 and the pure-wheel
  story but adds a fail-loud path to every parse-dependent feature and a
  second install step for every real adopter; the base-dependency cost
  falls only on exotic platforms, so the simpler contract won.
- **LOC/depth thresholds as gates** — a number that can block a change
  starts being optimized (Goodhart); metrics go to trend and outlier
  lists, not verdicts.
