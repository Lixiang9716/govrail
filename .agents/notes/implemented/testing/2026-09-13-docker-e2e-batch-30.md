# Agent Note: docker e2e batch 30 — bilingual recall ranks CJK like English, and the parse layer reads 中文 identifiers

Status: implemented

Related: the docker matrix + batches 1-29 notes (same series),
postmortem_recall (the body hit + miss statement this deepens),
recall_rank_classes (batch 29's four-class ranking), the tree-sitter
parse layer (D54), #172 (the encoding wall these scenarios stress)

## Problem

Two surfaces had no bilingual journey. postmortem_recall pinned a
Chinese term hitting a BODY and the miss diagnostics, but never the
RANK dimension: a Chinese term in an H1 title, --any's k/N line
counting terms across scripts, or a strict AND joining a Chinese and
an English term. And the tree-sitter layer's e2e fixtures were all
ASCII — CJK identifiers are legal Python the grammar must index, and
nothing proved a syntax error buried after Chinese content still
raises an ERROR node rather than a silent skip.

## Decision

- **postmortem_bilingual_rank**: three postmortems seeded so each
  script crosses each where — 中文标题+英文正文, 英文标题+中文正文,
  English title+CJK body. Strict AND "雪崩 复盘" names only the doc
  whose TITLE carries both (title(3) hit, same as English); --any
  "雪崩 storm" prints each doc's per-term where list, two 2/2 ties
  split by path, the 1/2 doc last. The first run pinned a REAL
  semantic the drafts had wrong: the where list follows QUERY order,
  not rank order — "(雪崩 in body, storm in title)" because 雪崩 was
  asked first. A pure-CJK miss gets the same per-term "不存在的词: 0"
  line, and the corpus statement counts all three postmortems.
- **stats_cjk_surface**: `def 雪崩计算(持仓, 阈值):` with Chinese
  whole-line and trailing comments, a Chinese docstring, and CJK
  arguments — stats indexes 1 function, classifies the known-answer
  lines (whole-line comment → comment, trailing comment → code,
  docstring → code), and depths count if/for/… not def. Then
  `def 雪崩(:` after a Chinese comment: `gov check` exits 1 naming
  坏的.py and python/syntax, while the CLEAN CJK file stays unnamed.

## Alternatives considered

- **decision next --count × dir format** (the other batch candidate) —
  already pinned by earlier batches (--count × sections/base/dir/table
  all have scenarios); re-pinning would duplicate.
- **Assert where lists sorted by rank** — that would pin a wish; the
  loader builds the list by filtering args.query in order. The
  scenario documents the actual contract; changing the product order
  would be a separate decision with its own note.

## Verification

Host: both scenarios PASS. Docker matrix: all eight inner-suite cells
(3.10/3.11/3.12/3.13-slim, 3.12-alpine, 3.10-bookworm, nonroot,
gbk-locale) at 62/62; cross, crossdir, crossalloc PASS; pypi-adopter
PASS in the first full run (SKIP on a network outage in the rerun —
an alpine pip-install exit 2 transient cost one rerun, not a red).
Host pytest 475 passed / 2 skipped, self-test 62 all pass,
`gov run --mode all` 10 gates pass.
