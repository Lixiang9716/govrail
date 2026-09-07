# What's new — govrail highlights, per release

Usage-oriented highlights (the CHANGELOG carries commits; this carries
how to use them). `gov whatsnew [--since <version>]` prints from here.

## 0.29.2 — (draft: copied from CHANGELOG, rewrite for usage)

- pin UTF-8 on self-test's own spawns; thread crashes fail loud

## 0.29.1 — (draft: copied from CHANGELOG, rewrite for usage)

- Windows portability — guarded fcntl, portable self-test fixtures, UTF-8 git decode

## 0.29.0 — (draft: copied from CHANGELOG, rewrite for usage)

- task claims — lease semantics for parallel workers

## 0.28.0 — (draft: copied from CHANGELOG, rewrite for usage)

- presets — python-lib and docs-bilingual bundles
- presets — typed adoption bundles (machinery + agent-heavy)

## 0.27.0 — (draft: copied from CHANGELOG, rewrite for usage)

- acquire/release — lease locks for oblivious parallel agents
- run --merge — preflight the union of parallel branches before landing

## 0.26.0 — (draft: copied from CHANGELOG, rewrite for usage)

- decision --against alias with stale-base warning; doctor names unadopted shipped gates
- note-presence exemptions — task receipts by default, manifest note_presence_exempt
- pairing sidecar is self-describing — template comments, --write field echo, --explain ([#155](https://github.com/Lixiang9716/govrail/issues/155)) ([d446b2d](https://github.com/Lixiang9716/govrail/commit/d446b2db9bcbd36c995725de376d4fc66e583206)), closes [#150](https://github.com/Lixiang9716/govrail/issues/150)
- recall misses are diagnosable — corpus statement, per-term counts, --any

## 0.25.0 — (draft: copied from CHANGELOG, rewrite for usage)

- self-test classifies FAILs via clean-env replay

## 0.24.1 — subcommand CLIs survive a shadowed argparse

- `gov task`, `gov note`, `gov decision`, and `gov receipt` no longer lean
  on argparse's `required=True` — legal stdlib argparse since Python 3.7,
  but a fossil `argparse==1.4.0` backport installed beside gov rejects it
  the moment PYTHONPATH promotes that dir, and 0.21–0.24's `gov task` died
  in an unreadable TypeError on such machines (issue #138). A bare
  `gov task` still fails loud: exit 2, usage plus the named choices.
- `gov doctor` names the shadow instead of leaving the crash: when
  `argparse` resolves outside the stdlib it exits 1 with the file and the
  remedy — `pip uninstall argparse`.
- CI keeps the reporter's exact environment alive: the `backport-shadow`
  job installs the wheel plus `argparse==1.4.0`, promotes site-packages
  onto PYTHONPATH, and requires the task happy paths, `gov self-test`,
  and the doctor flag to hold anyway.

## 0.24.0 — (draft: copied from CHANGELOG, rewrite for usage)

- release flow drafts HIGHLIGHTS sections — verify-doc-sync --write (D45)

## 0.23.0 — LLM cost ledger: the run line learns `cost`

- `gov run --cost tokens=1200,calls=4` (or `GOV_COST="…"`; the flag wins)
  records caller-reported resource cost on the run's history line, next
  to D42's `caller` — multi-agent cost attribution finally speaks one
  language (issue #126/D45). Units are free-form tokens, values finite
  non-negative numbers; govrail meters nothing itself, it standardizes
  the ledger shape.
- `gov trend --cost` rolls the window up per caller: per-unit totals and
  an early→late split, untagged cost-bearing runs under `(untagged)`.
  Runs that don't report behave exactly as before; a window with nothing
  reported points at the opt-in instead of reading like a roll-up of
  zero, and a malformed value fails loud naming the fragment.

## 0.22.0 — run receipts: "an agent verified this" becomes checkable

- `gov run --receipt` writes a tamper-evident receipt of the run to
  `.gov/history/receipts.jsonl`: per-gate outcomes bound to the tree's
  commit and tree sha, each record hashing the previous one — edit,
  delete, or reorder history and every later link breaks loudly
  (issue #124, D44).
- `gov receipt verify <commit>` answers, with an exit code: was a FULL
  (every enabled gate), CLEAN (no tracked file differed from the
  commit), GREEN (every gate PASS) run recorded on exactly this tree?
  It matches across a squash merge too — the commit sha moves, the
  tree does not.
- Cite the receipt instead of prose: paste the JSON line into a PR body
  and machine-check it with `gov receipt verify <commit> --record
  '<json>'`. The receipt's tag is the run's caller (`--tag`/
  `$GOV_CALLER`, D42); narrowed runs are recorded with `selected_by`
  (#119) and refused as full evidence.
- Runs without `--receipt` behave exactly as today. The chain is
  deliberately keyless — it proves consistency and binding, not
  authorship; real signatures are future work.

## 0.21.1 — `decision add` draft shape: help and validator agree

- In a `table`-format repo, `gov decision add --help` now describes the
  shape the validator enforces: table-row lines ONLY (first cell `Dn`
  or `?`), not title+body; sections/dir repos keep the title+body
  wording — the help you read is the truth for YOUR repo (issue #132).
- The non-row refusal quotes the exact line it rejects AND shows a
  minimal valid row modeled on the table's own header, e.g.
  `| ? | <title> | <alternatives> |` — the first failed attempt now
  teaches the fix instead of dead-ending an agent following the help.
- An empty table draft fails loud ("wants row lines") instead of
  rewriting the decisions file to append nothing.

## 0.21.0 — task cards: a brief says obey rules@<hash>

- `gov task new "Title" --check "criterion"` writes
  `.gov/tasks/T-0001-*.json` pinning the current rule set
  (`.gov/rules.md` + `gates.json`) by content hash — a subagent brief
  carries the one-line pin `obey rules@<hash>` instead of fifteen lines
  of restated governance prose (issue #125, D43).
- `gov task check` — a gate scoped to `.gov/tasks/**` — names the STALE
  cards after a governance adoption, so pasted-rule drift is detectable
  instead of silent; done cards' receipts are re-verified too.
- `gov task close T-0001` runs the gate DAG now; only an all-green run
  becomes the card's completion receipt. Red runs change nothing (they
  still land in history); a stale-pinned card refuses to close.

## 0.20.0 — caller tagging in gate history

- `gov run --tag <name>` (or `$GOV_CALLER`) records the caller's own
  free-text label on every history record in `.gov/history/gates.jsonl`
  — multi-agent repos can finally attribute runs: which caller's runs
  keep failing pairing, whether subagent runs are systematically slower
  (issue #120, D42). Absent label = no `caller` key: records keep their
  pre-0.20.0 shape.
- `gov trend --by-tag` groups runs by that label (first-seen order,
  untagged as `(untagged)`) and compares p50 halves inside each group;
  `--base` cuts every group at the same commit date. Privacy-light by
  design — the label is only what the caller typed.
(feat: caller-reported cost ledger in .gov/history — gov run --cost/GOV_COST, gov trend --cost (D43, #126))

## 0.19.0 — target another worktree without cd

- `gov -C <path> <command>` (or `--path`, before the command) chdirs by
  value before dispatch — a supervisor orchestrating several worktrees
  steers `gov run --base Y`, `gov doctor`, the verify-* gates, etc. at
  another tree with no cd bookkeeping (issue #121). Flags chain like
  git's `-C`, each path resolving against the previous one.
- The output header names the resolved work-tree root
  (`gov: targeting <root> (via -C …)`), so a wrong-tree invocation is
  visible, not just valid; a nonexistent path fails loud with exit 2.
- Subcommands with their own `--path` (verify-decisions,
  verify-rubric — a file argument after the command) are unaffected.

## 0.18.0 — optional pre-commit hook

- `gov init --hooks --pre-commit` installs an OPT-IN pre-commit hook
  that runs only the cheap content gates on the staged files:
  `gov verify-pairing --staged` (sidecar freshness for just the pairs
  the index touches — source, counterpart, or record) and
  `gov verify-conflict-markers --staged`. Pair drift now surfaces at
  `git commit` with the scoped fix inline, one stage earlier than the
  pre-push block (issue #110, D41).
- Repos without the flag see zero change at the commit stage — the
  pre-push model is untouched; a lone `--pre-commit` fails loud, a
  foreign pre-commit is never overwritten, and `gov uninstall` reverses
  both hooks. `gov doctor` treats pre-commit as optional (absent is a
  choice).
- Bypass for one commit: `git commit --no-verify`. The full gate DAG
  stays on pre-push; CI owns the full matrix (rule 1).

## 0.17.0 — decision-row tooling for parallel branches

- `gov decision next [--count N] [--base REF]` prints the next free
  D-number from the configured decisions source; `--base origin/master`
  unions what already landed there, so a branch cut before a sibling
  landed prints the number the eventual merged history will show
  instead of re-allocating a taken one (issue #107, D40).
- `gov decision add --from FILE [--id Dn] [--dry-run]` appends a
  decision atomically and validates before writing: a number that
  already exists, a number that opens a gap, and a draft without the
  options/rejected-alternatives section are each refused by name.
- A `dir` decisions format (`{"path": ".gov/decisions", "format":
  "dir"}`, one file per decision) makes parallel appends structurally
  conflict-free: each `add` creates a new file, so two worktrees
  appending from the same base merge with no textual conflict at all.
- `gov verify-decisions --base REF` is the gate-time net: a number both
  branches added since the merge-base is a named collision with the
  renumber command in the message; pre-partitioned gaps (the number
  exists on the base) stay informational.

## 0.16.0 — additive gate adoption for customized installs

- `gov init --adopt-new gates.json` merges newly shipped gates into a
  customized gates.json by gate id: the added ids are named in the
  output, every local gate is preserved untouched, and the merged file
  is schema-validated before anything lands (issue #108, D39). This is
  the one-command answer to drift that used to mean hand-copying blocks
  out of `site-packages` templates.
- Non-additive drift — a shared gate id whose content differs locally —
  is refused loudly with the id named; those keep the two-step manual
  path. Unsupported targets fail loud too: only gates.json has an entry
  identity to merge on.
- See the drift first as always: `gov init --upgrade` lists per-file
  diffs, `--json` for agents.

## 0.15.1 — failure-first gate output

- `gov run` prints failed evidence in full and never clips it, and the
  failure line names the exact rerun command — reading a red run no
  longer means scrolling past a wall of green (issue #109).

## 0.15.0 — conflict-marker gate

- `gov verify-conflict-markers` fails naming `file:line` when a changed
  file still carries git conflict markers — the rebase failure mode git
  itself refuses to police (`git add` stages them, `git rebase
  --continue` commits them; issue #104, D38).
- A line-initial start/end/diff3 marker (exactly seven characters) is
  primary evidence; a bare `=======` counts only beside a sibling
  marker, so Markdown setext underlines stay legal. The escape hatch
  for deliberate literals: append `gov:ignore-marker` to the line.
- The gate ships in the template's `all` mode (fresh `gov init` gets
  it); existing installs see the drift with `gov init --upgrade` and
  adopt or copy the gate block. `--staged` reviews just the index;
  rejection proofs ride with `gov self-test`.

## 0.14.1 — flag registry pinned to each command's --help

- `gov audit-notes` no longer reports real flags as dead commands: notes
  documenting working runs of `gov init --adopt <file>` (also `--preview`,
  `--json`), `gov run --no-record`, `gov review --grade` read as working;
  a genuinely unknown flag (`gov init --nonexistent`) is still named
  (issue #101).
- `gov init --help`, `gov uninstall --help`, `gov verify-notes --help`
  list their real options — the terse one-line command summary is a
  description, never the machine-checked surface.
- The registry is pinned mechanically now: every command's `--help`
  options must equal `audit_notes.FLAGS`, and a registry that lags the
  CLI fails audit-notes itself (exit 2) instead of silently skipping.

## 0.14.0 — CHANGELOG ↔ HIGHLIGHTS pairing

- `gov verify-doc-sync` gate: every released version in CHANGELOG must
  have a matching HIGHLIGHTS section (version read FROM CHANGELOG, never
  guessed); ahead-of-release sections caught too. This very gate went
  red on the release PR that shipped it — the first dogfood bite.

## 0.13.2 — explicit version mapping

- `gov whatsnew` prints the installed wheel version and, when the wheel
  carries no section for itself (a docs-only release, or a section added
  after its release ships in the next wheel), says the mapping out loud
  instead of reading one version short (issue #92's wheel-lag residual).

## 0.13.1 — alignment round

- Bare `gov init --adopt --preview` names the drift inventory
  (`adoptable: N missing, M drifted`) and cross-links `--upgrade` and
  the single-file preview (issue #91).
- HIGHLIGHTS headers are aligned with wheel versions, enforced by a
  tag-coverage guard test; the index-propagation note (retry
  `pip install -U` before suspecting the release) is in CONTRIBUTING
  (issue #92).

## 0.13.0 — provenance and external references

- `gov init --upgrade` distinguishes WHO moved: UPSTREAM MOVED (your
  copy is untouched since adoption — `--adopt <rel>` takes the new
  template safely) vs BOTH MOVED (merge by hand) vs legacy ambiguity
  (labeled). The manifest now records each adopted template's hash.
- `gov init --adopt <file> --preview` shows what would land and writes
  nothing; adopt discloses its manifest updates.
- `govrail:D<n>` is the legal external decision reference: citing the
  tool's decisions no longer reads as a dangling local D, and
  `gov note new --ref govrail:D24` records it as external.

## 0.12.2 — host integrity

- The self-test's scratch fixtures run behind three independent walls
  (env scrub + GIT_CEILING_DIRECTORIES + a toplevel guard that aborts
  loud on any escape): a fixture can no longer configure, stage, or
  commit into any repository but its own — verified byte-identical
  hosts from linked-worktree runs, including under hostile GIT_*
  leaks (#24).

## 0.12.1 — worktrees, hook context, blast radius

- The pre-push hook now selects gates from the push range (docs-only
  pushes skip the suite) and runs under a scrubbed environment — the
  hook-context self-test failures are gone (#20/#22). UPDATE your
  hook: it is a modified-file adoption (see gov init --upgrade).
- Bare `gov verify-pairing --write` touches only out-of-sync pairs —
  green sidecars keep the confirmation they earned (#16).
- The decisions source is configurable (`.gov/decisions.json` —
  sections or markdown-table format); with no source while notes
  reference D-refs, verify-decisions answers REFUSED, not ok (#17).
- `gov doctor` is worktree-aware and names manifest/package version
  drift (#15/#19); run history records into the main checkout, not per
  worktree (#23); path-scoped gates say `n in change scope` — zero is
  visibly not a scan (#21); the coverage ledger names executed cases
  that lack a `# gate:` declaration instead of nagging (#18).

## 0.12.0 — usability round: examples, cookbook, discovery

- `gov whatsnew` — this command: what arrived since your init version
  and how to use it. `gov init --upgrade` now points here when the
  package is newer than your manifest.
- `docs/cookbook.md` in the repository — task-oriented recipes (pairing
  went red, add a gate end-to-end, review a PR, read a trend mover).
- `examples/demo-project` is now a living specimen: every feature
  exercised (rubric, rejection cases with `# gate:` declarations,
  surfaces.json, decisions with review-by, paired docs).
- Reports point to their own next steps: the coverage ledger names the
  case file format; trend movers say what a mover means.

## 0.11.0 — review workbench, pairing round-trip, coverage ledger

- `gov review --base <ref> --grade` — dossier then interactive rubric
  grading (p/f/s/q); emits the review verdict block. Failures exit 1.
- Pairing drift errors carry the fix command inline and the sidecar
  records which side moved in which commit after which confirmation.
- `# gate: <id>` in a rejection case's first five lines feeds the
  self-test coverage ledger (`gate(n)`; uncovered gates say
  `NONE — rule 6`).
- `gov doctor` resolves every gate command — a typo'd binary is a
  problem before a run reports MISSING.
- `gov trend --gate <id> [--base <ref>]` — single-gate view; split the
  early/late window at a git ref's commit date.
- `gov init --upgrade --json` — machine-readable drift for programmatic
  adoption.

## 0.10.x — adopt, doctor, note scaffolding, strict schema

- `gov init --adopt [file…|all]` — land missing template files (never
  overwrites existing ones).
- `gov doctor` — environment self-check: PATH, Python, hooks, gates
  schema, decisions table.
- `gov note new --class <c> --ref <D> "Title"` — scaffold pre-validated;
  `gov note check` — pre-commit-light format + D-ref check.
- Unknown gates.json keys abort loud (`"enable": false` is gone).
- Run history records by default (`.gov/history/`, gitignored);
  `--no-record` opts out.

## 0.9.0 — decision guard, review dossier, skill drift, trends

- `gov verify-decisions` — decisions table: numbering, alternatives,
  orphans. `gov review --base <ref>` — one-shot review dossier.
- audit-names checks skills' gov command/flag references.
- `gov trend` reads `--record` history (p50 per window halves).
- `--staged` (index-only note-presence), dangling-record reporting.

## 0.8.0 — template upgrade path

- `gov init --upgrade` — per-file template-vs-local diffs, never writes;
  MISSING items marked adoptable.

## 0.7.x — adopter wishes round one

- `.gov/rejections/` — project rejection cases wired into self-test
  (`tools N + project M`, `--scope`, 10s budget).
- `gov run --json` — one JSON array (gate/outcome/blocking/duration_ms/
  detail); pure stdout, human report on stderr.

## 0.6.x — honesty rounds

- Gate reachability (one loud parking mechanism: `enabled: false`);
  `--every-gate`; `--gate <disabled>` exits 2.
- Archive seal detector (`gov verify-archive`) + no-laundering re-seal.
- Two-step uninstall (`--force`); retrofittable `--hooks/--ci`;
  `gov recall` / `gov audit-notes` (the memory read side); skills ship
  with the plane.
