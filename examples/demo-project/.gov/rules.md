# Governance rules

These rules are machine-enforced where possible and human-judged otherwise.
They are the single source of truth injected by `gov init`; a project's own
AGENTS.md points here instead of duplicating them.

## 1. Gates over prose

Any promise a command can check is a gate in `gates.json`. Run the smallest
sufficient set for what changed (`gov change-scope --base <ref>`);
CI owns the full matrix. A convention that cannot be checked belongs in
review, not in wishful writing.

## 2. Every non-trivial change carries an Agent Note

A change is non-trivial when it alters behavior, architecture, a cross-file
contract (interface / schema / format), process or tooling, or a decision a
maintainer may reasonably revisit. Test: would a maintainer a month later ask
"why was this done?" If yes, write a note. Purely mechanical or local edits
(typo, format, local rename, comment sync) are exempt.

## 3. A note has three required sections

`## Problem` (motivation, stated to stand without the solution), `## Decision`
(what shipped, present tense), and `## Alternatives considered` (what it beat,
why). `## Consequences` is optional. A decision recorded without what it beat
invites re-litigation — the exact failure notes exist to prevent.

## 4. Notes live in a lifecycle, and archived notes are frozen

Notes live at `.agents/notes/implemented/<class>/<date>-<topic>.md`
(class: `feature`, `bug-fix`, `simplification`, `architecture`, `process`,
`testing`). An archived note is frozen: never edit, move, or delete it;
supersede it with a new note that links back.

## 5. Fail loud, never silently skip

Unknown values, malformed configs, and missing referents abort with the
offending name. A misconfiguration discovered late is a defect now.

## 6. Verify the world, not the self-report

A gate that never fails is a vacuous script, not evidence. Each governance
gate ships a rejection case that proves it catches the violation it claims to;
`gov self-test` runs them.

## 7. Bilingual pairs merge whole

A human-facing document is a three-file pair: source + counterpart +
`.i18n.yaml` record, under the naming conventions this project declared
in `.gov/pairing.json` (govrail's own convention: `foo.md` + `foo.zh.md`
+ `foo.i18n.yaml`). Editing one side without re-confirming the pair fails
the pairing gate; a PR never lands one language of a pair alone.


## 8. Wait on conditions, not on clocks

Never `sleep` hoping a state has arrived — poll the condition with a
deadline, and fail loud when the deadline passes. A sleep may only pace
real wall-clock physics (a lease TTL expiring, a rate-limit window),
and even then the condition is asserted after the wait. Waiting for CI
or another process is event-driven: `gh pr checks --watch`,
`gh run watch --exit-status` — never a blind timed pause.
