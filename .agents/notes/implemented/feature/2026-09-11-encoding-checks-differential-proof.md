# Agent Note: encoding= checks ride the check engine — differential proof retires the regex scanner

Status: implemented

Related: D54 (the clause this completes), #172/#173 (the incident that
built the wall), #168 (the decode wall), rule 6 (the differential IS the
proof), tests/test_encoding_differential.py (the preserved reference)

## Problem

D54 shipped the parse layer with its follow-up clause half-done: the
check engine existed (D54's note, next PR), but the two scar-tissue
checks — subprocess and text-I/O spawns missing `encoding=` — had not
moved onto it. The subprocess scan was still the #172-era hand-roll:
a regex for `subprocess.(run|Popen|check_output)(` plus a balanced-paren
walk to read multiline calls. It worked, but it sat OUTSIDE the engine:
no suppression accounting, no severity vocabulary, no project-rule
surface, and a scanner that cannot see tokens — it flags calls inside
string literals and comments, and treats `universal_newlines=False` as
text mode because its substring test ignores the value.

## Decision

Three shipped query rules in `gov/checks/python.json`, and the regex
scanner retires from production:

- **python/subprocess-text-encoding** (error): `subprocess.run/Popen/
  check_output/call` with `text=True` or `universal_newlines=True` and
  no `encoding=` keyword — predicates (`#eq?`, `#match?`) pin the
  package and require the flag value to be `true`. This is #172's rule,
  moved onto the engine.
- **python/open-text-encoding** (warning): bare `open()` without
  `encoding=`; discharges include a `mode=` keyword or two positional
  strings (the binary-mode shapes) — deliberately conservative v1: a
  text-mode `open(path, "r")` escapes, and the docstring says so.
- **python/pathlib-text-encoding** (warning): `read_text()`/
  `write_text()` without `encoding=`.

The engine gained one small generalization for this: `absent_query`
accepts an ARRAY — open() needs several independent discharge shapes,
and "any of these present discharges" is the same difference semantics
applied N times.

**The differential proof** (tests/test_encoding_differential.py) is the
heart of the PR. The old scanner is preserved VERBATIM as the reference
implementation, and the new rule must agree with it on every corpus case
where the reference was right — same file:line sets — while being
strictly quieter on exactly the two classes where the reference was
wrong by construction (string/comment false positives;
`universal_newlines` with a non-true value). On the real `gov/` package
both must agree, and agree on clean. Deleting the reference would have
made the new rule self-certified; keeping it makes the equivalence a
checked fact, forever.

The shipped self-test case (`test_text_subprocess_decodes_are_pinned`)
now drives the ENGINE over the `gov/` package with
`include_project=False` — a host project's `.gov/checks` can never
perturb the product's own rejection cases, and a wheel user gets the
proof without pytest. The old pytest test pinning the production scanner
is superseded by the differential module (its exact shapes are pinned
there against the preserved reference).

Small honest costs, stated: the engine rule requires the flag VALUE to
be `true` where the regex matched any `universal_newlines` token —
`universal_newlines=False` was an old false positive and is now silent
(the differential pins this as a delta, not as parity); and
`subprocess.run(cmd, **opts)` remains invisible to both implementations
alike — parity, not progress, and the corpus says so.

## Alternatives considered

- **Keep the regex scanner alongside the engine** — two scanners, two
  truths, and the engine's suppression/trend machinery would never
  apply to the one case that historically mattered most (#172).
- **Broaden the open() rule to catch positional-mode text opens** —
  needs negation over argument POSITION, which the query language
  cannot say; the conservative discharge list keeps the false-positive
  budget at zero for binary users at the price of missing exotic text
  opens (documented in the rule's message).
- **Ship these as gates in the template** — D28's line: typed content
  is adopted (`gates.json` paths), not injected. The rules ship;
  blocking is the adopter's wiring decision.
