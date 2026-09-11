# Agent Note: check engine — syntax-class rules over the parse layer

Status: implemented

Related: D54 (the parse layer and its locked boundary — this executes the
"later, when the event arrives" clause D54 already designed), D15 (glob
semantics), D32/D44 (ledger anchoring; metrics are not evidence), rule 5
(eager refusal), rule 6 (every mechanism here ships with a rejection proof)

## Problem

D54 landed the parse layer with a deliberate hole: it produced facts
(stats) but no verdicts, so syntax-class static checks — the "basic
syntax check" adopters keep asking for — still had no carrier, and the
layer's machinery (queries, difference, suppression) was unproven. The
gap was shaped: rules needed to find patterns in the tree, claim
ABSENCE (queries cannot say "not"), suppress findings without making
them invisible, and fail loudly when a rule could never match.

## Decision

`gov check` — rules are data (`gov/checks/<lang>.json` shipped;
`.gov/checks/<lang>.json` additive per project). Two rule kinds:

- **parse-errors** — one finding per ERROR/missing node; the
  editor-level syntax check. It claims "does not parse", never "does
  not compile" — the message says so, because tree-sitter's tolerance
  differs from the compiler's and compile truth stays with the
  language's own compiler (D54's boundary).
- **query** — a tree-sitter query; negation is a SECOND query
  (`absent_query`) run inside the finding node's row span: any match
  discharges the candidate. The capture named by the rule (default
  `gov-node`) is the finding node; the absent query and the suppression
  window are evaluated against IT — the rule author must capture the
  node they mean, and the tests pin that capturing the callee identifier
  instead of the call silently disables both.

Guardrails, each earned in this branch's own test runs:

- **Eager validation**: a query naming a node kind its grammar lacks
  fails the run at startup (exit 2, rule named) even when no file would
  ever reach it — validation used to ride on the first matching file,
  so an empty directory meant a broken rule sat there silently. (This
  binding's Query compiler rejects unknown kinds at compile time on
  some versions; the engine's own kind-table check is the backstop and
  the test pins either loud path.)
- **Additive project rules**: a project rule re-using a shipped id is
  refused, not overridden — an override that flips a shipped rule's
  meaning must be loud (rule 5).
- **Suppressions are counted, never invisible**: `# gov:ignore-check
  <id>` (same row as the finding, or inside its node's row span)
  discharges the finding AND the count lands in the stats ledger via
  --record (`kind: "check"`, per-rule findings/suppressed) — an
  exemption that grows is a trend someone should see; no other tool
  accounts for its own suppressions.
- **Severity gates the exit code**: error blocks; warning prints;
  --strict makes warnings block (advisory-first adoption, rule-for-rule
  with gates' allowFailure).
- The shipped rules are the syntax check for all eight D54 languages;
  the subprocess/text-IO scar-tissue checks with their differential
  proof are the NEXT PR (D54's other half) — this PR proves the
  machinery on known-answer fixtures instead of shipping unproven rules.

## Alternatives considered

- **Ship the subprocess/encoding rules here** — the machinery and its
  first real consumer in one PR looked efficient, but the differential
  proof against the existing regex implementation deserves its own
  review; splitting keeps each proof load-bearing.
- **Project rules override shipped ids** — convenient for tuning, and
  exactly how a rule's meaning gets silently flipped; additive-only
  keeps "what shipped" auditable.
- **Suppressions invisible (grep-and-ignore)** — every other linter
  already does invisible; the plane's whole point is that exemptions
  are decisions with a visible trend.
- **A new gate in the template by default** — D28's line holds: typed
  content is adopted, not injected. `gov check` is commandable; an
  adopter wires it into gates.json when they want it blocking.
