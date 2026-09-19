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
The presence gate is advisory until you flip it blocking (P0-3: a fresh
install never goes red on day one).

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
+ `foo.i18n.yaml`). Editing one side without re-confirming the pair
fails the pairing gate (advisory until baselined — flip it blocking by
removing `allowFailure` after your first green run); a PR never lands
one language of a pair alone.

## 8. Wait on conditions, not on clocks

Never `sleep` hoping a state has arrived — poll the condition with a
deadline, and fail loud when the deadline passes. A sleep may only pace
real wall-clock physics (a lease TTL expiring, a rate-limit window),
and even then the condition is asserted after the wait. Waiting for CI
or another process is event-driven: `gh pr checks --watch`,
`gh run watch --exit-status` — never a blind timed pause.

## 9. Multi-step tasks carry a task card; open cards block pushes

A task with three or more steps (or any step whose omission would be a
silent regression) gets a task card: `gov task new "title" --check "step 1"
--check "step 2"`. The card IS the checklist — anchored to the caller's
verbatim instructions, stored in `.gov/tasks/`, and gated by the `task`
gate in the default DAG. An open card means the work is in progress;
the task gate fails on stale pins and receipt-less done cards, and the
pre-push hook surfaces both. To push, close the card (all items checked
+ green receipt) or explicitly defer it. The checklist is not a
self-authored todo — it is a gate-enforced contract between the caller
and the plane.

## 10. A new command ships its discovery surface in the same PR

Adding a user-facing command (or renaming one) must update, in the
same PR, the homes that make it discoverable — each catches a
different drift, so missing any one is a regression:

- `--help` and the project's machine-checked flag registry: the
  registry test enforces both directions — a listed-but-unregistered
  flag gives false `unknown flag` signals on working invocations, a
  registered-but-unlisted one silently misses typos;
- the router skill's stage table (when to use the command, when not —
  judgment, not syntax): agents enumerate skills, not help output;
- the exit-code contract: a failure leg for every failure-capable
  command, or an explicit declaration that the command cannot fail.

Deprecated aliases are held to the same bar — they stay working through
the deprecation window, and citations of them are not drift.

## 11. Record surprises; the third recurrence is a process defect

When reality differs from what you expected, record it the session you
notice it: `gov surprise record "<what you expected>" --reality "<what
happened>"` — the tracked, append-only ledger `.gov/surprises.jsonl`
groups recurrences by signature, and the lookup "have I seen this
before?" happens at record time, when it is cheapest. A surprise is
not a bug report; it is telemetry about where the mental model and the
process disagree. When one signature reaches three recorded surprises,
a process note citing `surprise:<sig>` ships: recurring surprise means
the process, not the person, needs to change. (Escalating that
threshold into a blocking gate is the adopting project's wiring
choice; govrail's own plane runs one.) Recording never blocks on the
threshold — data first, verdict wherever the project enforces it.
