# Agent Note: surprise list answers keyword lookups: verbatim grep over the full entry, zero matches said out loud

Status: implemented

Related: D44, issues #376, #356

## Problem

The surprise ledger's whole point is the cheapest-possible "have I seen
this before?" check at record time (rule 11), but the lookup side only
answered by exact signature: `gov surprise list` counts signatures and
`--sig` filters by one. An operator who remembered a WORD from the
surprise's own text ("the CI pin thing") had no way in — on a live
multi-repo day this meant tailing `.gov/surprises.jsonl` by hand, and a
keyword guess that matched nothing was indistinguishable from an empty
ledger: the unfiltered "no surprises recorded" message read as "this
never happened before", inviting a duplicate record of a surprise that
was already in the file.

## Decision

- `gov surprise list` takes keyword arguments: `gov surprise list pin
  ci`. The words are grepped VERBATIM (case-insensitive substring)
  across every field a recurrence would share — signature, surface,
  expectation, reality — AND over words, the same shape `gov recall`
  taught. Filters compose (`--sig` narrows further); `--json` returns
  the filtered entries.
- A filtered query that matches nothing says so in its own words —
  "no recorded surprise matches <the filter> — the words are searched
  verbatim across signature, surface, expectation, and reality" — and
  the empty-ledger message stays reserved for an actually empty ledger.
  Zero-matching is an answer (exit 0), not a failure: a lookup that
  found nothing IS the information.
- The router skill's stage line names the keyword form, so agents
  enumerating skills see the lookup exists (rule 10's discovery
  surface); no new option flags, so the flag registry is unchanged.

## Alternatives considered

- **Tokenize into content terms like the record-time similarity hint
  (#356)** — rejected for the LIST side: #356's stopword/term machinery
  exists to propose "same kind?" hints without false leads, but a
  lookup the operator drives by hand needs verbatim predictability —
  searching a word that visibly appears in the entry and getting no
  hit because a stemmer dropped it is the exact "indexed only some
  fields" confusion the issue reports. AND-over-verbatim-substrings is
  dumb, visible, and composable.
- **Exit 1 on zero matches** so scripts can branch — rejected: a
  lookup with no hits is a successful lookup (the plane treats a green
  zero as an answer everywhere facts, not verdicts, are read), and an
  exit-1 surprise list inside a gate would read as "gate red".
- **A `--grep PATTERN` flag with regex** — rejected: the audience at
  record time is an agent mid-session typing nouns, and a regex flag
  invites quoting bugs in exactly the moment the ledger exists to make
  cheap. Keywords cover the lookup; `--json` covers anything fancier.
