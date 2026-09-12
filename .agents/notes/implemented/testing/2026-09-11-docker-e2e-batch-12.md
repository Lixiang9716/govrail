# Agent Note: docker e2e batch 12 — the demo specimen repaired inside the matrix, and by-tag x --base

Status: implemented

Related: the docker matrix + batches 1-11 notes (same series), the demo
specimen (D33's living example), #120 (by-tag x --base composition),
rule 1 (the smallest sufficient set, read back by change-scope)

## Problem

The demo specimen — "a governed project in action" — had never been RUN
by the matrix: the image carried no demo, and no scenario asserted the
specimen stays governed as the plane evolves. Batch 12 added the
specimen to the image and its first run went red TWO ways: the demo's
`gates.json` mode `all` referenced an UNDEFINED gate (`archive`), and
its `source-limits` gate was enabled but in NO mode — every `gov run`
in the shipped example exited 2 at config load. A specimen that cannot
run teaches the wrong lesson loudest of all.

## Decision

- **The specimen is repaired, and the matrix keeps it repaired**: the
  archive gate definition is added (paths `.agents/notes/archived/**`),
  source-limits joins `all` and `quick` (path-scoped, so it only runs
  when its files change), a rejection case for the archive seal ships
  with it (rule 6 — a gate without one is the vacuous thing the plane
  hunts), and the demo's decision TABLE is declared out of pairing
  scope in the demo's own `.gov/pairing.json` (a living decisions table
  is not translated; govrail's own repo excludes it identically). The
  shipped pairs (README, review-rubric) are baselined with sidecars.
  `demo_specimen` (a scenario in every cell, the specimen COPYed into
  the image) now asserts the repaired journey: the full DAG green,
  stats/check reading it, its own project rejection cases passing.
- **by_tag_split** (16th... the by-tag x --base composition): a crafted
  ledger where alpha lives entirely BEFORE the base date and beta
  entirely AFTER. Without --base, each group compares against itself
  (stable). With --base, each group's far side is EMPTY and the report
  says so — "need at least 2 comparable run(s) to split", twice —
  instead of inventing a comparison. First-appearance ordering is
  pinned. The composition's honest answer to a tag concentrated on one
  side of a cut is the interesting assertion.

## Alternatives considered

- **Translate the demo's decisions table** — a living table is churn;
  govrail's own repo excludes its decisions doc from pairing for the
  same reason (`.gov/pairing.json` exclude).
- **Leave the specimen's DAG broken and only assert its self-test** —
  the specimen's first impression is `gov run`; a red exit 2 from the
  EXAMPLE project contradicts every claim the plane makes.
- **Kata/gVisor cells** — deferred (batch-9 README note): no runtime
  plugin here, and stdlib-Python touches no OCI-boundary syscall.
- Two nonroot lessons: the /demo specimen is chmod a+rX in the image
  (user 1000 cannot read root's 600 SKILL.md files — Errno 13 was the
  nonroot cell's demo_specimen), and the demo copy needs `git init` +
  a commit before the git-driven gates can diff at all (the matrix run
  failed on exactly that until the scenario created the repository).
