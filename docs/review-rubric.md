# Review rubric

English | [中文](review-rubric.zh.md)

Reviews of this repository grade against this rubric, item by item, with
evidence. Freeform impressions are welcome *in addition to* — never instead
of — these verdicts. Authors self-check before opening a PR; reviewers check
the items the diff touches, not every item every time.

An item lives here while it needs judgment. When its promise becomes
mechanically checkable it leaves the rubric and becomes a gate with a
rejection case — the `Gate candidate` field says which way each item flows.
`gov verify rubric` checks this file's structure; the pairing gate checks
its bilingual pair.

### R1 — Non-trivial changes carry an honest note

- **Checks:** the diff changes behavior, architecture, a cross-file contract, process or tooling — and carries a new or updated Agent Note whose `## Alternatives considered` names real alternatives.
- **Evidence:** the note's Problem stands without the solution; the alternatives lost for stated reasons, not straw men.
- **Anti-pattern:** a note that records what was done but not what it beat — presence without honesty.
- **Gate candidate:** no — presence is already gated (`gov note presence`); honesty is judgment.

### R2 — A new or changed gate proves it can reject

- **Checks:** any gate added or changed in `gates.json`, and any `gov verify-*` command, has a rejection case in `gov self-test`.
- **Evidence:** a case that introduces the violation, asserts red, restores.
- **Anti-pattern:** a gate that has only ever passed — a vacuous script (rule 6).
- **Gate candidate:** no — self-test runs the cases that exist; a missing case is exactly what review must catch.

### R3 — Fail loud, with the offending name

- **Checks:** unknown values, malformed configs, and missing referents abort naming the offender; exit code 2 means config, 1 means failure.
- **Evidence:** error text contains the bad value or id itself.
- **Anti-pattern:** silent fallbacks, defaulting past typos, best-effort continues.
- **Gate candidate:** no — style-level judgment; spot-check the touched paths.

### R4 — The install surface stays idempotent and exactly reversible

- **Checks:** changes to `gov init`/`uninstall` (files created, hooks wired, manifest entries) remain a no-op on re-run and are reversed by uninstall.
- **Evidence:** a roundtrip test in `tests/test_cli.py` covering the new artifact, including the conflict path.
- **Anti-pattern:** a created file missing from the manifest; an add-on that can leave a half-initialized project.
- **Gate candidate:** yes — covered by the init/uninstall roundtrip tests.

### R5 — Bilingual pairs merge whole

- **Checks:** a human-facing doc change updates both languages and re-confirms the pair in the same PR.
- **Evidence:** `gov verify pairing` green in the PR; the two sides semantically equivalent, not lexically parallel.
- **Anti-pattern:** landing `foo.md` with `foo.zh.md` "to follow"; machine-flavored translation.
- **Gate candidate:** yes — the hashes are gated (`gov verify pairing`); semantic equivalence is judgment.

### R6 — The check set is chosen, not reflexive

- **Checks:** the PR states which gates were run and why that set is sufficient for the touched surfaces.
- **Evidence:** `gov change-scope --base <ref>` output (or its conclusion) plus the run results.
- **Anti-pattern:** "ran everything to be safe" with no reasoning; skipping gates silently.
- **Gate candidate:** no — sufficiency is judgment; the tools report, the chooser reasons.

### R7 — One fact, one home

- **Checks:** the change does not duplicate a fact that has a home elsewhere (see [tiers.md](tiers.md)); it updates the home or links to it.
- **Evidence:** every touched doc is the authoritative home for what it says.
- **Anti-pattern:** a second place for the same fact — wrong on the day they drift.
- **Gate candidate:** no — drift detection is judgment.

### R8 — Decisions that outlive the diff are locked

- **Checks:** a design-level choice (schema, contract, posture) is recorded in [decisions.md](decisions.md) with options and the rejected ones.
- **Evidence:** a D-numbered entry marked 已决 (decided), or a note explaining why no entry was needed.
- **Anti-pattern:** a locked-looking decision living only in a commit message.
- **Gate candidate:** no — what counts as design-level is judgment.

### R9 — The monolith stays modular

- **Checks:** new code lands in the layering contract — leaves import no gov module, only entrypoints import the dispatcher, the import-time graph gains no cycle, and files stay within their declared size budgets (`scripts/import-layers.json`, `scripts/size-limits.json`; both gates advisory today).
- **Evidence:** `gov run --gate import-layers --gate size-limits` green on the diff; a new registry entry (command, case) landed in its one home (`gov/commands.py`, `@case`) instead of a second list.
- **Anti-pattern:** a "temporary" helper module importing the dispatcher; a second hand-maintained list shadowing a registry; a file quietly crossing 1600 lines.
- **Gate candidate:** yes — the gates exist; this item is the reviewer's judgment on the seams (what *should* be a leaf) until the limits learn to say so.

### R10 — Claims cite artifacts; self-report is not evidence

- **Checks:** every load-bearing claim in the PR description ("tests pass", "the gate rejects", "the UI works", "it is faster") cites a verifiable coordinate — a receipt id (`gov receipt verify <id>`), a named test count from a cited run, a committed-artifact location (file + line/sequence), or a gate/run output. Reproducible commands beat screenshots; screenshots beat nothing.
- **Evidence:** the description carries the coordinates and a reviewer can re-verify each one mechanically; for UI claims, a recorded artifact (gif/snapshot) attached or linked.
- **Anti-pattern:** "trust me, all green"; a summary asserting outcomes with no coordinates; a claim only the author's session could confirm.
- **Gate candidate:** partial — receipt existence and citation resolvability are checkable; whether a claim's evidence is *sufficient* is judgment.
