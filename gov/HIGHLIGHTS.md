# What's new — govrail highlights, per release

Usage-oriented highlights (the CHANGELOG carries commits; this carries
how to use them). `gov whatsnew [--since <version>]` prints from here.

## 0.30.0 — the plane learns to read code: tree-sitter parse layer, gov stats, gov check

- **tree-sitter joins the base dependencies** (core + 8 official grammar
  packs: python, go, java, rust, javascript, typescript, c, cpp) — the
  plane can now parse the code it governs. Requires Python >= 3.10
  (tree-sitter's floor); the OS classifiers name the supported platforms
  explicitly. Boundary locked in D54: the syntax layer is used only
  where the syntax answer IS the answer — types and flow stay out, and
  compile truth stays with each language's own compiler.
- **`gov stats`** — structural facts per language: lines (counting rule
  echoed: a docstring is a string, so it counts as CODE), symbols,
  nesting depth (p50/p95/max + the deepest functions). Facts, not
  verdicts — nothing here gates. `--record` appends to the stats ledger
  so complexity trend becomes visible over time.
- **`gov check`** — syntax-class checks as data rules. Shipped: the
  editor-level syntax check for all eight languages (it claims "does
  not parse", never "does not compile"), plus the #172 scar-tissue
  rules: subprocess / open() / read_text() / write_text() without
  `encoding=` go red — on a GBK-locale host those decode with the
  locale codec and crash on the first non-ASCII byte. Suppressions are
  `# gov:ignore-check <id>` and they are COUNTED — an exemption that
  grows is a trend someone should see. `--strict` makes warnings block.
- Language packs are data (`gov/langs/*.json`) and every node kind they
  name is validated against the grammar at load — a typo'd kind would
  silently zero its metric. Parse failures are named, never silently
  skipped. `gov doctor` reports the parse layer and per-grammar
  versions.
- Platform honesty: `requires-python` moves to >=3.10 and the
  `OS Independent` classifier is retired — the dependency carries
  compiled parts, so the supported-platform story is named per platform
  (D54).

## 0.29.4 — the coverage ledger's warning finally tells you how to fix it

- `gov self-test`'s undeclared-case warning now prints the remedy beside
  the file it names: add `# gate: <id>` within the first five lines
  (a line inside a module docstring counts) to link a project rejection
  case to the gate it proves (issue #167). `gov self-test --help`
  documents the contract, and the rejections README says the same —
  previously both the syntax and the five-line scan window had to be
  reverse-engineered from the source.
- The "write one" hint keeps its guard: a case that ran and passed is
  never nagged about being written (#18/D32).

## 0.29.3 — the pytest suite runs on Windows, its skips named

- The `windows` CI job now runs `pytest -q` alongside the fresh-project
  smoke, so the suite is proven on a platform the wheel claims
  (`OS Independent`) instead of on Linux alone (#168's follow-up).
- Every fixture that executes a gate uses a `sys.executable -c` command
  instead of coreutils `true`/`false`/`sh` — "exits 0" and "exits 1" now
  mean the same thing on both platforms, with no semantic change on
  Linux.
- Tests that inherently need POSIX exec (shebang cases, the `X_OK` path,
  the PATH `gov` shim) skip themselves on Windows under a named
  `@needs_posix_exec` reason, each carrying why — said, never silently
  passed.
- The first Windows run exposed two defects the Linux runner could not:
  `os.execv` does not propagate a child's exit code there (the lock and
  task race wrappers read `[0, 0]` and lost the loser's exit 3 — now
  `subprocess.call` + `SystemExit`), and the takeover-race assertion
  over-claimed a message a legal `O_EXCL` create may not produce.

## 0.29.2 — self-test pins its own decodes; a crashed thread fails the run

- Every text-mode subprocess in the package routes through one helper
  that pins `encoding="utf-8", errors="replace"`. `text=True` without
  `encoding` decodes with the HOST locale codec — on a zh-CN Windows
  (ANSI = GBK) the first non-ASCII UTF-8 byte in a case's output raised
  `UnicodeDecodeError` inside the reader thread (issue #172). Binary
  spawns keep plain `subprocess.run`: there is nothing to decode.
- The crash can no longer hide behind a PASS. A recording
  `threading.excepthook` keeps the traceback on stderr and fails the run
  (`HARNESS-ERROR …`, exit 1), because a crashed reader thread empties
  the capture it was filling — the case kept its emptied output and
  still passed (rule 5).
- The wall is enforced by the product, not only by CI: a new shipped
  case re-scans the package's own sources for text spawns missing
  `encoding=` and names each `file:line`, so the next regression fails
  `gov self-test` on every host.

## 0.29.1 — "OS Independent" made honest: the CLI runs on Windows

- `import fcntl` no longer kills the CLI on a host that has none:
  `gov/locks.py` guards the import and skips the `flock`/`LOCK_UN` pair
  where it is absent — the degradation D52 already priced in ("liveness,
  not correctness", upper-layer validation carries correctness)
  (issue #168).
- Decodes and encodes are pinned on both sides of every spawn: git
  output is read as UTF-8 (`errors="replace"`) everywhere in the
  package, and stdout/stderr are pinned too — Windows pipes hand
  children the ANSI code page (cp1252/GBK), and the runner died
  re-printing a child's output the moment it carried a character that
  code page cannot represent.
- The self-test's gate-command fixtures are portable
  (`sys.executable -c` instead of `true`/`false`/`sh -c`), so the tools'
  own rejection proof runs on a host without coreutils — the wheel is
  `py3-none-any`, so its proof has to be too.
- CI keeps a `windows` job alive end-to-end — fresh project, `gov init` /
  `doctor` / `run --mode all`, then `gov self-test --scope tools` — as
  the reporter's environment, held open.

## 0.29.0 — task claims: two workers cannot take the same card

- `gov task claim T-0001 --agent <id> [--ttl DUR] [--wait DUR]` leases a
  card with D52's lock machinery verbatim — the same atomic create, lazy
  takeover of an expired lease, holder-verified release, and exit 3 for
  busy naming holder and expiry (issue #165). A missing or closed card is
  exit 2, not busy: waiting cannot reopen it.
- The claim never touches the card JSON. A card is a D43 receipt (a
  `rules@hash` pin plus a green-run record), so the lease file is the
  only claim state: `gov task list --json` reports it as
  `{claimed_by, expires_at}` — an expired lease reads `null`, the same
  freshness classification the lock layer uses — and the text listing
  appends `[claimed by … until …]` to otherwise unchanged lines.
- `gov task close` clears the card's lease unconditionally, because a
  successful close means the work is finished. Holder-verified cleanup
  was tried first and starved the next claimer for the winner's whole
  TTL in the claim-race drill.
- `gov acquire` and `gov release` now announce the resolved lock root
  (`acquire: lock root <path>`) on stderr, on success and busy alike: a
  drill agent with the wrong cwd had locked a real repository and could
  not tell, because its success line looked like every other one.

## 0.28.0 — presets: one command lands a project-type bundle

- `gov preset list|show|apply <name>`, and `gov init --preset <name>` to
  init and apply in one step. A preset is a declarative patch bundle —
  gate fragments, modes, skills, hints — under a strict closed-key
  schema; `show` is read-only and prints exactly what would land (D53).
- Apply reuses the existing adoption contracts instead of inventing merge
  semantics: gate fragments merge by id (D39), skills copy byte-for-byte
  create-if-missing (D29), hints write only manifest keys that are absent
  (D49). It is additive and idempotent — a re-apply reports "already
  adopted" everywhere, exits 0, and writes nothing; adopting into an
  uninitialized project exits 2 naming `gov init`.
- Three bundles ship: `agent-heavy` (the multi-agent parallel workflow
  the D51/D52 concurrency drills validated — the decisions gate, the
  parallel-workers skill, task-receipt exemptions), plus `python-lib`
  and `docs-bilingual` on the same matrix (#162, #164).

## 0.27.0 — rehearse the union before landing it, and lease what it touches

- `gov run --merge <branch>… [--base <ref>]` rehearses integration before
  it happens: branches merge in command-line order into a detached
  scratch worktree, and after every merge the gate DAG runs on that
  step's union tree, scoped to the diff that step introduced (D15). The
  last step's tree IS the union, so every gate ends up examining merged
  content (D51). Green → the scratch is cleaned and a per-step summary
  printed. A conflict or a red step → named (`branch 2 (b) conflicts
  with already-merged set (a)`, plus the conflicted files), later
  branches never run, and the scratch is KEPT for inspection.
  Repository-resolving `GIT_*` variables abort it loudly before anything
  runs (exit 2, variables named) instead of being scrubbed silently, and
  acceptance tests pin that the host worktree is byte-identical before
  and after.
- `gov acquire <resource> [--agent ID] [--ttl S] [--wait S]`,
  `gov release <resource> --agent ID`, `gov locks`: file leases in the
  git common dir, so they span every worktree of one clone. Acquire is an
  atomic create; a fresh lease in the way is exit 3 naming holder and
  expiry (`--wait` polls to its deadline); an EXPIRED lease is taken over
  lazily inside a flock-guarded critical section; release is
  holder-verified, so a lease is never released on someone else's behalf.
  Exit 3 joins D2's vocabulary additively — busy is neither a gate
  failure (1) nor a config error (2). `gov locks` is a read-only listing
  that never feeds an admission decision.
- Neither is a correctness layer, and the docs say so: a holder that
  stalls past its TTL shares the resource with a taker-over. The lock is
  the liveness layer; upper-layer validation (push CAS, delivery rebase)
  still carries correctness.

## 0.26.0 — fewer wolves, better diagnostics

- `gov decision next|add --against <ref>` (an alias of `--base`): when
  your base is behind the ref it prints `your base is N rows behind
  '<ref>' (missing …) — rebase before numbering`, while `next`'s stdout
  stays exactly the number list. `decision add` carries the same soft
  warning and still writes the row — awareness, not a block (D48).
- `gov doctor` gains a `gate-adoption` check: it inventories the gates
  this govrail version ships and names any absent from your
  `gates.json` — a note, never a problem. A gate parked with
  `enabled: false` counts as adopted: parking is the loud, deliberate
  mechanism (D24, D48).
- `gov verify-note-presence` stops crying wolf on bookkeeping:
  `.gov/tasks/**` is exempt by default, and a repo can exempt further
  surfaces with `"note_presence_exempt": [glob, …]` in
  `.gov/manifest.json`. A manifest that exists but cannot serve exits 2
  naming file and key (rule 5), and the active exemptions are printed
  when the gate runs (D49, issue #149).
- The pairing sidecar explains itself (#150/D50): a generated
  `.i18n.yaml` carries comments stating that `pair.en`/`pair.zh` are git
  blob hashes (not file sha256) and that `en_commit`/`zh_commit` are the
  last commits that touched each side (not HEAD, informational);
  `--write` echoes the field values it wrote, and `--explain` prints the
  schema, your project's conventions, and the command surface without
  judging anything.
- `gov recall` misses are diagnosable (#148): every invocation states its
  corpus on stderr (per-class counts: notes, decisions, postmortems), a
  miss adds per-term hit counts (`效用: 0 / utility: 2`) so a zero reads
  "the corpus lacks this term" while a nonzero beside a miss reads "the
  AND failed", and `--any` ranks partial matches — an empty `--any`
  still exits 1, because fail loud is not relaxed, only the AND.

## 0.25.0 — a red self-test says whether the tool or the host broke

- Every FAIL is classified from evidence, not guessed (D47, issue #139):
  a failing tools-family case is replayed once in a minimal environment —
  a temp copy of the package alone on `PYTHONPATH`, every host `PYTHON*`
  variable dropped, user-site disabled — so the #138 shadowing mechanism
  cannot occur there. The replay passes → `environment-suspect` (check
  this host's site-packages and `PYTHON*`); it fails again →
  `tool-defect`; it cannot run → `unclassified` with the hand-rerun
  command.
- The FAIL line now quotes the killing exception — its last non-empty
  line, instead of a bare `Traceback (most recent call last):`.
  Project-family failures get a reproduce-by-hand hint rather than a
  replay: arbitrary scripts may legitimately need the host, so an
  automatic replay would prove nothing.
- The replay's building block is a command of its own: `gov self-test
  --case NAME` runs one case, one line, exit 2 on an unknown name. And
  classification never changes a verdict — a classified FAIL still fails
  the run.

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

## 0.24.0 — the release PR drafts its own HIGHLIGHTS section

- `gov verify-doc-sync --write` drafts the section for every released
  version that is missing one, from CHANGELOG: bullets copied verbatim
  (provenance link groups stripped), under a heading that declares
  itself a draft pending your rewrite — the phrase `draft: copied from
  CHANGELOG, rewrite for usage` in the heading is what to look for —
  then re-runs the gate's own check and returns its exit code. The usage
  rewrite stays human: a machine-written usage section would be invented
  content wearing an evidence costume (D46).
- The release-please workflow gains a `highlights` job that runs while
  the release PR is open — checkout the release branch, draft, and, only
  when the file actually changed, commit and push the draft onto the PR
  branch. The release merge then lands CHANGELOG + version bump +
  HIGHLIGHTS together and master never sees the red; on the merge push
  the job skips, because the section must already be in the merged tree.
- Why it exists: every release since 0.19.0 — four in a row — merged and
  immediately turned master's doc-sync gate red, and someone hand-pushed
  the missing section afterwards. A gate whose failure is a routine step
  of the release process is a failure being normalized.

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
