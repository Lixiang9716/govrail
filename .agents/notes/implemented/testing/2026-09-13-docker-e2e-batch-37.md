# Agent Note: docker e2e batch 37 — next --base reads the dir source from git history, and --lang narrows honestly

Status: implemented

Related: the docker matrix + batches 1-36 notes (same series), D40
(the dir-format decisions source), #147 (the stale-base warning),
D54 (the per-language check/stats filters)

## Problem

Two filter composites were unpinned. `decision next --base` unioned
the ref's decision numbers with local — but only the FILE format had
an e2e journey (the cross-container allocation drill); the dir
format's --base path reads D-files out of GIT HISTORY (ls-tree), a
different mechanism the batch-29 loader work never touched. And the
`--lang` filters on check/stats had no scenario proving the negative
half: a file of an UNrequested language stays unnamed even when
broken — narrowing that silently widened back would go unnoticed.

## Decision

- **decision_next_base_dir**: dir-format source, a sibling branch
  lands D2/D3; `next --base sibling` from the trunk prints D4 and the
  stale-base warning ("2 rows behind", naming D2) on stderr; after the
  rows are absorbed the same base prints D4 with SILENT stderr. The
  warning stays soft (never a block) and the number stays the union —
  exactly #147's contract, on the dir mechanism.
- **lang_filter**: one clean python file plus one broken go file;
  `check --lang python` exits 0 and never names b.go; `check --lang
  go` exits 1 naming b.go and never a.py; `stats --json --lang
  python` reports exactly {"python": …} with the file counted.

## Alternatives considered

- **Fold the dir --base case into the cross-container allocation
  drill** — the drill's value is the container boundary; this
  composite's value is the loader mechanism, and one container pins it
  fine.
- **Also pin stats --lang with a broken file of the requested
  language** — stats_ledger_roundtrip already pins parse_errors
  accounting; this scenario pins only the filter's honesty.

## Verification

Host: both scenarios PASS first run; pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 72/72, cross×3 PASS.
