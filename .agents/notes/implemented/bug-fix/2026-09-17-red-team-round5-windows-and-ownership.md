# Agent Note: red-team round 5 — write windows, file ownership, and asymmetric reads

Status: implemented

## Problem

A fifth red-team pass over the plane found the same three shapes that
earlier rounds found, in places earlier rounds did not look:

- **A window that loses state.** `gov init` appended to `.gitignore` by
  rewriting the file through the injection recorder, so a project's own
  rules were dropped whenever the marker was already present;
  `_copy` and the manifest write were non-atomic, so a torn injection
  was then frozen as project-owned by re-init's guards; a lease payload
  is a whole file's worth of state with no exclusive-create guarantee.
- **An ownership claim nobody verified.** `gov uninstall` deleted
  whatever sat at a hook path and resolved the hooks directory the
  naive way, ignoring `core.hooksPath` and worktrees; `_template_for`
  had no mapping for the decision log or the memory-plane README, so
  uninstall could delete a project's decision log; a receipt that
  described a non-`gates.json` config could still verify as full-green
  because `config` was not part of the hashed set.
- **Two readers that disagreed.** The pre-commit hook read the config
  file twice (seal over one buffer, parse of another — N8's discipline
  had not reached the hook); the note gates matched `.md`
  case-sensitively in some sites and not others, so an uppercase `.MD`
  slipped past; the trend views crashed on a non-object ledger line
  instead of skipping it; strict attribution rejected a change whose
  note already existed elsewhere.

## Decision

One rule per shape, applied at every site: writes go through an atomic
temp-and-rename or an exclusive create; deletion requires a positive
ownership mark (the gov marker, a mapped template, a shipped-gate
registry) and nothing is deleted when the mapping is unknown; a
reader reads the bytes once — seal, parse, and hook all consult the
same buffer. Alongside those: archive manifests guard their shape,
`require` overrides no longer accept trivial prefixes, non-object seal
JSON is a named exit 2, four verify mains wrap unexpected exceptions as
exit 2 so a crash is never mistaken for a rejection, `run_gates`
settles on `FIRST_COMPLETED` instead of polling, receipts append under
a guard lock with the previous entry finalized inside the lock, and
`gov run` anchors to the git root. Deliberately deferred, with the fix
site named: `uninit --upgrade/--preview` still writes back silently —
the file was owned by another workstream this round, and a
half-applied write discipline is worse than a recorded gap.

## Alternatives considered

Patch each finding where it was reported — rejected: four rounds of
that produced the same class again one module over; the value of the
fifth pass is in the rule, not the instances. Serialize every write
behind one global lock — rejected: it would make the write window
correct and the plane single-threaded, and the locks it already has are
per-resource for a reason. Treat the uppercase-`.md` match as a note
convention to document rather than a gate to widen — rejected: a gate
whose rejection depends on the case of a suffix is a gate an operator
can walk around without noticing.
