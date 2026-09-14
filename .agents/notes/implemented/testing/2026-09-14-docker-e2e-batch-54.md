# Agent Note: docker e2e batch 54 — the plane is not project code, explicit decision ids are guarded at the write, and --strict moves the exit not the vocabulary

Status: implemented

Related: the docker matrix + batches 1-53 notes (same series), the
D54 language packs (their exclude lists), D17/D40 (numbering),
#119's exit-code vocabulary (blocking vs strict)

## Problem

Three write-path behaviors were unpinned — and one was a real gap.
The language packs' exclude lists covered VCS and build caches but
NOT the plane's own surfaces: a `.py` under `.gov/` or `.agents/`
was counted into the adopter's stats and syntax-checked as project
code, mixing governance artifacts into project metrics. Explicit
decision ids had no journey: nothing showed whether a draft row
pinning "D9" (or `--id D9` against a fresh table) lands a hole
silently, refuses, or something else. And `--strict`'s summary line
could be misread as broken: the blocking COUNT still means
severity==error while the EXIT blocks on warnings.

## Decision

- **The product fix**: `.gov` and `.agents` join every language
  pack's exclude list — the plane's directories sit beside `.git`
  where they always belonged. plane_dirs_not_project_code pins both
  sides: stats counts only src/; check stays silent on a syntax-
  broken `.gov` file while naming the same breakage in src/ red.
- **decision_id_guards**: a table draft pinning D9 against the
  allocated D0 refuses (exit 1, "pins D9 but D0 was allocated; …
  or pass --id D9"); `--id D9` refuses too ("D9 skips D0..D8; next
  free is D0" — table numbering starts at D0). Holes are
  structurally impossible at the write, not merely flagged later.
- **check_strict_ignores_suppressed**: a discharged violation keeps
  the strict run green ("0 finding(s) (0 blocking), 1 suppressed");
  the ACTIVE violation under --strict exits 1 while the summary
  still reads "(0 blocking)" — the bar moved at the exit, the
  vocabulary did not.

## Alternatives considered

- **Exclude only .gov** — .agents is the same kind of surface
  (injected, inventoried, uninstall-removed); splitting them would
  make the next skill-side .py a metrics leak.
- **Make --strict re-brand warnings as blocking in the count** — that
  would blur the schema's own severity vocabulary; the exit already
  says what strict means.

## Verification

Host: all three scenarios PASS; pytest 481 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 104/104, cross×3 PASS.
