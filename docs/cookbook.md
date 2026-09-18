# Cookbook — tasks, commands, what to expect

English | [中文](cookbook.zh.md)

Recipes are task-shaped: a symptom or goal, the command, what good
output looks like. The reference lives in the README; this is the
"what do I do now" layer.

## Install and first day

```sh
gov init --project .            # rules, gates, notes, skills land
gov doctor                      # PATH, python, hooks, gates schema — sound?
gov run                         # pairing runs advisory until baselined
```

A fresh install must not go red. When you have documents to pair:

```sh
gov verify pairing --write      # baseline every pair (partial: records
                                # what it can, reports the rest)
```

## I want to start a project by its type

`gov init` injects the generic floor (D28: typed content stays out of
the default template). A **preset** adds the typed set — gates, skills,
and manifest hints for a project kind. Look before you leap:

```sh
gov preset list                 # what types ship with this package
gov preset show <name>          # read-only: every gate, mode, skill, hint
```

Three ship today (D53): `agent-heavy` — multi-agent parallel
development (decisions guard, worker-protocol skill, bookkeeping
exemption); `python-lib` — pytest and build gates for Python package
repos, wired into `all` and `quick`; `docs-bilingual` — the
CHANGELOG/HIGHLIGHTS sync guard, for repos that really carry those
files (a red gate naming a missing one is correct fail-loud; HIGHLIGHTS
headings must read `## <version> <description>` — a bare `## 1.0.0` is
not recognized as a section).

Then start the project with the preset in one command:

```sh
gov init --preset agent-heavy   # or: python-lib / docs-bilingual
```

```
init: initialized /path/to/project
  …
preset: applying 'agent-heavy' to /path/to/project
  gates: added 1 (in preset order): verify-decisions
  skill: created .agents/skills/parallel-workers/SKILL.md
  hint: wrote manifest 'note_presence_exempt' = [".gov/tasks/**"]
```

Apply lands additively through the plane's adoption contracts — a local
gate with the same id is kept and named (D39), an existing skill is
skipped (D29), a manifest key you already set wins (D49) — so it also
retrofits onto an initialized project (`gov preset apply <name>`),
and a re-apply reports "already adopted" and writes nothing. Unknown
preset name? Exit 2 lists what does exist.

## Pairing went red after an edit

The error carries its own fix — copy it:

```
docs/foo.md: out of sync — re-confirm: gov verify pairing --write docs/foo
(the en side last moved in a1b2c3d, confirmed 2026-09-01T10:00:00+00:00)
```

`--write <stem>` re-baselines ONLY the named pair. The parenthetical
says which side moved, in which commit, after which confirmation —
check the translation before re-confirming, not after.

## What do the sidecar fields actually mean?

The record's semantics used to live only in code — an agent re-stamping
a sidecar by hand was told "use HEAD" and fought the gate until an
amend + force-push later (#150). The fields are not HEAD:

```
pair:
  en: 6f0f…    # git blob hash (`git hash-object`) of the source — NOT file sha256
  zh: 5c81…    # same for the counterpart side
counterpart: foo.zh.md
last_confirmed: 2026-09-04T19:24:25+00:00  # UTC ISO-8601 instant of the confirmation
en_commit: 113b230  # last commit that TOUCHED each side at that moment —
zh_commit: 113b230  # not HEAD, not the confirmation commit; context only
```

Never hand-edit the record: `--write` regenerates it, says so in comment
lines inside the record itself, and now names every field value it
wrote. The generated record plus the full schema and this project's
conventions are one read-only command away:

```sh
gov verify pairing --explain
```

## Catch the drift at commit, not at push

The pre-push block works, but on a busy branch every pair edit costs a
blocked push first (issue #110's evidence). Install the optional
pre-commit hook — cheap content gates on the staged files only:

```sh
gov init --hooks --pre-commit   # add-on; --hooks alone stays push-stage
```

Now the same edit fails one stage earlier, at `git commit`, with the
same scoped fix inline — run it, re-stage, and the commit lands without
the push round-trip:

```
docs/foo.md: out of sync — re-confirm: gov verify pairing --write docs/foo
verify_translation_pairing: 1 violation(s) in 1 staged pair(s)
```

Nothing paired staged? The hook is quiet. Repos that find commit hooks
intrusive simply do not pass `--pre-commit` — zero change at the commit
stage, the pre-push model untouched.

## Add a gate, end to end

1. Define it in `gates.json` (unknown keys abort loud — typos cannot
   silently park):

```json
{"id": "source-limits", "command": ["./check_limits.sh"],
 "paths": ["src/**", "eval/**"]}
```

2. Prove it can reject — a rejection case under `.gov/rejections/`,
   shebang on line 1, gate declaration within the first five:

```sh
#!/bin/sh
# gate: source-limits
# introduce an oversized module, assert the gate goes red, restore
...
```

3. Check the ledger: `gov self-test --scope project` ends with
   `source-limits(1)` — not `NONE — rule 6`.

## A rebase left conflict markers in the diff

Symptom: `git add` during a rebase stages a file that still carries
`<<<<<<<` / `=======` / `>>>>>>>` blocks, and `git rebase --continue`
commits it without a word — git cannot tell a real marker from a
quoted one, so it stays silent. The conflict-markers gate ships in the
template's `all` mode and reads the changed files' content:

```sh
gov verify conflict-markers            # changed files vs the auto base
gov verify conflict-markers --staged   # only the index — pre-commit-light
```

Expected output when a marked file is in the diff (exit 1):

```
doc.md:3: conflict marker '<<<<<<<' — resolve the merge, or append 'gov:ignore-marker' to exempt a deliberate literal
doc.md:5: conflict marker '======='
doc.md:7: conflict marker '>>>>>>>'
verify_conflict_markers: 3 marker(s) in 1 file(s) — git will not police its own conflict text; the gate does (D38)
```

Escape hatch: a deliberate literal (a test fixture quoting markers, a
doc about merging) appends the token `gov:ignore-marker` to that line
and passes. A bare `=======` alone — a Markdown H1 setext underline —
is not a marker; it counts only beside a sibling marker in the same
file (D38).

## Experiments are not runtime code

`.gov/surfaces.json`:

```json
{"eval/**": {"surface": "experiments", "gates": ["source-limits"]}}
```

Now `gov change-scope` on an eval-only change suggests exactly
`source-limits` — no product-plane noise.

## Review a PR

```sh
gov review --base origin/main --grade
```

One command: the dossier (scope, notes, recall, rubric), then
interactive grading (`p`/`f`/`s`/`q`; `f` asks for evidence), then the
verdict block — graded lines, blockers, `verdict: approve` or
`request changes`. The human decides; the machine transcribes.

## Recall found nothing — which term failed?

`gov recall` requires every term in one entry, so a multi-term miss used
to be a blind guess. Now the miss itself carries the diagnosis, and
every run states the corpus it searched (on stderr, so the ranked hits
on stdout stay first):

```sh
gov recall 效用 utility 归因
```

```
recall: no match for '效用 utility 归因'
  per-term hits: 效用: 0 / utility: 2 / 归因: 0
  (strict AND — every term in one entry; retry with --any to rank partial matches)
```

`utility: 2` says the corpus knows the term — the AND with the others
failed; `效用: 0` says the corpus genuinely lacks it. Follow the hint:

```sh
gov recall --any 效用 utility 归因    # partial matches, ranked by terms matched
```

The strict AND stays the default; an empty `--any` result still exits 1.

## Write a note

```sh
gov note new --class process --ref D6 "Why we chose x"
gov note check        # format + placement + dangling D-refs, pre-commit-light
```

A wrong class or a dangling D-ref is refused before any prose is
invested. Without a decisions table the D-ref is announced unchecked —
never silently skipped.

## The decisions table

`gov decision verify` guards numbering (unique, contiguous),
alternatives (every D records what it beat), and reports orphans
(no note references — informational). A decision with a context that
may expire carries `review-by: 2027-01-01`; past dates print a
review-due note.

## Parallel branches both want the next D-number

```sh
gov decision next --base origin/master   # the number merged history will show
gov decision add --from draft.md --against origin/master  # --against = --base
gov decision verify --base origin/master
```

Two worktrees computing "next free" from the same base both get D39;
`--base` unions what already landed on the base branch, and the gate run
names the collision (`D39: number collision … renumber via gov decision
next --base`) instead of letting a duplicate row merge. Appending in the
single-file formats is atomic (temp file + replace) but still a textual
merge conflict across worktrees — configure
`.gov/decisions.json` `{"path": ".gov/decisions", "format": "dir"}`
(one file per decision) and appends become new files: parallel branches
merge with no conflict at all.

A stale base is named, not just absorbed (#147): when the local table is
missing rows the ref has, `next` and `add` warn —
`your base is 2 rows behind 'origin/master' (missing D2, D3) — rebase
before numbering` — soft, never blocking; the number you get is still
the one merged history will show. `--against` is an alias of `--base`,
not a second semantic.

## Parallel branches — rehearse the union before merging

```sh
gov run --merge feat-a feat-b feat-c --base origin/master
```

**Symptom**: each agent branch passed every gate on its own tree, yet the
merge is broken — text conflicts git catches, but semantic collisions
(each branch green, the union red: two branches adding the same gate id
to `gates.json`, or two edits that only break together) surface after
landing, when the tree has already shipped.

**Command**: the preflight merges the branches, in the order given, into
a detached scratch worktree built on `--base` (the integration baseline;
default `origin/master`, and a missing default is a named demand for an
explicit flag). After every merge the gates run on that step's union
tree — the minimal sufficient set for the diff the step introduced.

**Expected output** (all green): one summary line per step —
`merge: step 2/3: 'feat-b' -> tree 9a1b2c3d4e5f; gates: 4 ran, 4 pass` —
then `merge: union of 3 branch(es) is green` and exit 0. **On a text
conflict**: exit 1, `merge: branch 2 (feat-b) conflicts with
already-merged set (feat-a)` plus the conflicted files, and the scratch
worktree is KEPT (its path is printed) so you can inspect the scene; on
a red step the failed gates and their first output lines are named the
same way. Fix, then re-run. With `--receipt` the last step records a D44
receipt for the union tree — after landing (squash merges included),
`gov receipt verify <commit>` proves the landed tree is the one that
went green.

## Several agents write one file — how not to stomp on each other

```sh
gov lease acquire reports/summary.md --agent w1 --ttl 600  # exit 0 = you hold the lease
gov lease acquire reports/summary.md --agent w2            # exit 3, names the holder
gov lease release reports/summary.md --agent w1            # only the holder can release
```

**Symptom**: several parallel agents write the same file and clobber each
other — "whoever writes last wins". The workers are oblivious to each
other and need the tool to say "wait" or "go".

**Command**: take a lease before writing. The lease is one small JSON
file under the git common dir (it spans every worktree of the clone),
bounded by `--ttl` so it can never block forever, and **liveness-only**:
it prevents duplicated work, it does not carry correctness. A busy
resource exits 3 — that is the "block or continue" moment: poll with
`--wait 30` (1s interval, until the lease expires or is released), or go
work on something else.

**Expected output**: the winner prints
`acquire: 'reports/summary.md' leased by 'w1' until 2026-09-05T…`; the
loser gets on stderr
`acquire: REFUSED — 'reports/summary.md' is held by 'w1' until …` with
exit code 3 — same holder included, the lock is not reentrant. A release
by anyone but the holder names the impostor and exits 2. `gov lease list`
lists the current leases (pure diagnostics). If a holder crashes, the
lease expires after `--ttl` and the next acquirer takes it over — which
can overlap two writers (double-hold). That is exactly why the lock is
not the correctness layer: what lands is still judged by your gates and
review, and master's correctness is anchored in the push CAS.

## Two workers take the same task card

**Symptom**: two parallel workers both read card T-0001 as open and both
start the work — duplicated effort the card format alone cannot stop
(the card is a rules pin + receipt, D43; claim bookkeeping must not go
inside it).

**Command**: claim the card before starting:

```sh
gov task claim T-0001 --agent w1 --ttl 20m   # exit 0 = the card is yours
gov task claim T-0001 --agent w2             # exit 3, names the holder
gov task list                                # [claimed by w1 until …]
gov task release T-0001 --agent w1           # done working: let it go
```

**Expected output**: the winner's stderr says
`task: T-0001 claimed by 'w1' until 2026-09-05T…`; the loser gets
`acquire: REFUSED — 'task/T-0001' is held by 'w1' until …` and exit 3 —
the wait-or-move-on moment (`--wait 20m` polls at 1s; size the wait at
least the holder's remaining TTL, or it can only end in exit 3 at its
own deadline — see the parallel-workers skill's TTL section). An expired
lease is taken over by the next claim; claiming a closed card is exit 2,
not busy — waiting cannot reopen one. The claim lives only in the lease
file under the git common dir: `gov task list --json` surfaces it as
`claim` (expired reads as null), the card JSON never changes, and
`gov task close` clears the holder's own lease when the card lands.

## Templates evolved — see, then adopt

```sh
gov doctor                    # also names shipped gates you never adopted
gov init --upgrade            # per-file diffs; never writes
gov init --adopt all          # lands MISSING template files only
gov init --adopt-new gates.json  # merges NEW shipped gates into a
                                 # customized gates.json (by gate id)
gov whatsnew                  # what arrived since your init version
```

Modified files stay yours to merge (the two-step); pure additions land
with one command; a customized gates.json can absorb newly shipped gates
additively — local gates untouched, conflicting ids refused loudly
(D39); `--upgrade --json` lets an agent decide programmatically.

A gate absent from gates.json never runs, and nothing used to prompt its
adoption — `gov doctor` names what this govrail version ships that your
gates.json lacks (#147): template gates point at `--adopt-new`; the
tools whose paths are project-specific (`verify-decisions`,
`verify-rubric`, `verify-doc-sync`) name the command to wire into a
mode by hand. A note, never a failure — adoption is deliberate.

## Orchestrating several worktrees without cd

```sh
gov -C ../wt-x run --base master   # gates the wt-x tree, not this one
gov -C ../wt-x doctor
```

`-C <path>` (or `--path`, before the command; chainable like git's)
chdirs by value before dispatch, and the output header names the
resolved work-tree root — a wrong-tree invocation is visible, not just
valid. A nonexistent path fails loud (#121). Subcommands with their own
`--path` (verify-decisions, verify-rubric) keep it: theirs names a
file and comes after the command.

## Reading a trend mover

Runs record by default (`.gov/history/`, gitignored). `gov trend`
compares window halves per gate; a mover (`×1.8 ↑`) is a question to
investigate, not a verdict:

```sh
gov trend --gate tests --base v1.2.0   # before/after that release
```

## Multiple agents, one repo — whose runs are these?

Tag a run with `--tag` (or export `GOV_CALLER`; the flag wins) and the
tag lands in `.gov/history/gates.jsonl` as caller-supplied free text.
`gov trend --by-tag` splits the window per caller — each tag's movers
and stable gates report separately, untagged runs group under
`(untagged)`, and an absent tag keeps records exactly as before (#120):

```sh
gov run --tag subagent-3        # or: GOV_CALLER=subagent-3 gov run
gov trend --by-tag              # per-caller early/late p50 comparison
```

## What did this milestone's LLM spend cost?

Govrail meters nothing itself — but the tool driving your agents usually
already counts tokens/calls. Hand those numbers to the same run line in
one standard shape (#126/D45), then roll up per caller:

```sh
GOV_CALLER=bridge-agent GOV_COST="tokens=1200,calls=4" gov run
gov run --tag adjudicator --cost tokens=300.5,calls=1   # flags beat env
gov trend --cost   # per caller: per-unit totals and early→late split
```

Untagged cost-bearing runs group under `(untagged)`; runs without
`--cost`/`$GOV_COST` behave exactly as before; a malformed value fails
loud naming the fragment.

## Long session, drowning in untracked-file warnings

```sh
gov note presence --staged     # index only; silent when clean
```

Lists fold past five (`…and N more`).

## The note-presence advisory cries wolf on routine bookkeeping

It should not, any more: task-card receipts (`.gov/tasks/**`) are exempt by
default (#149). If another surface is routine for this repo, declare it in
`.gov/manifest.json` — the advisory then fires only where a note is
genuinely expected:

```json
{ "note_presence_exempt": ["docs/**", "tools/**"] }
```

When the warning does fire it says which absence it found — "no note file
appears anywhere in this diff" — and the active exemptions are printed on
every run.

## Something feels off in the environment

```sh
gov doctor
```

Names problems rule-5 style: gov unreachable on PATH, hook not
executable, a gate command that does not resolve, schema typos,
decisions that no longer parse.
