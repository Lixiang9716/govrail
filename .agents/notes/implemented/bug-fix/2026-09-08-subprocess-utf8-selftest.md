# Agent Note: self-test's own spawns decode pinned UTF-8; thread crashes fail loud

Status: implemented

Related: #172 (the report this fixes), #168 (the decode wall this
continues — it pinned the runner's git spawns; this pins the harness's
own), rule 5 (fail loud — the second half of the report), D47/#139 (the
classifier whose replay path was one of the crash sites)

## Problem

`gov self-test` on a zh-CN Windows (ANSI = GBK) intermittently printed a
`UnicodeDecodeError: 'gbk' codec can't decode byte 0x94 … buffer.append(fh.read())`
inside its gate output while still reporting PASS. The reported frame is
CPython's `subprocess._readerthread` — the Windows reader-thread for
`text=True` spawns — not govrail code: the real defect is that the
self-test harness spawns subprocesses with `text=True` and no `encoding`,
so children are decoded with the LOCALE codec. #168 pinned every git
spawn in the runner (`gates.py`, `cli.py`, `merge.py`, …) but left nine
call sites in `self_test.py` unpinned — among them `_run_project_case`
(the project rejection-case path) and `_classify_tool_failure` (the
clean-env replay), exactly the paths that copy Chinese rejection content
through a capture. Any non-ASCII UTF-8 byte in a child's output crashed
the reader thread; the exception surfaced only through
`threading.excepthook`, changed no exit code, and the case kept its
emptied capture and still PASSED — a silent-skip in rule 5's exact
shape.

## Decision

- `gov/self_test.py` gains `_run_text()` — a text-mode
  `subprocess.run` wrapper pinning `encoding="utf-8",
  errors="replace"` — and all nine unpinned call sites route through it
  (the two paths named in the report included). Binary spawns keep plain
  `subprocess.run`: there is nothing to decode. The whole package now
  sits on one codec wall: children speak UTF-8 (`_case_env`'s
  `PYTHONIOENCODING`, #168), the harness decodes UTF-8.
- A recording `threading.excepthook` keeps the default's stderr
  traceback and additionally records the crash; `main()` — both the
  `--case` and full paths — checks the record after the run and fails
  loud (`HARNESS-ERROR …` lines, exit 1) whenever a harness thread
  crashed, because a crashed reader thread empties the capture it was
  filling and any PASS printed alongside it may be blind. The record is
  cleared after reporting so in-process repeats (pytest) start clean.
- New self-test case `test_text_subprocess_decodes_are_pinned` (shipped,
  runs in every wheel): `_unpinned_text_spawns()` re-scans the package's
  own sources for `text=True`/`universal_newlines` subprocess calls
  without `encoding=` and names each `file:line` — the regression gate
  for the wall, run by `gov self-test` everywhere, not just this repo's
  CI.
- pytest proofs in `tests/test_self_test_rejections.py`: a child
  emitting GBK bytes decodes to replacement characters instead of
  crashing (the report's crash, made deterministic on every OS); the
  scanner names an unpinned spawn and passes pinned and binary ones
  (rule 6: the scan can fail); a pre-recorded thread crash fails
  `main()` with no case failures.

## Consequences

- The reported symptom is gone at the root: with the codec pinned, the
  reader thread cannot raise, so there is no exception to swallow; the
  excepthook guard covers any future thread crash class, not just
  decodes.
- The scan is textual (balanced-paren call capture), so a call that
  spreads `text=True` through a variable or a helper other than
  `_run_text` could slip past it; the wrapper remains the documented
  choke point and CI's Windows replay exercises the real decode path.
- `self-test` can now fail with zero case failures (harness thread
  crash) — a distinct, louder verdict than a case FAIL; the summary line
  still says `all pass` only when nothing crashed.

## Alternatives considered

- **Add `encoding="utf-8", errors="replace"` inline at the nine sites** —
  rejected as the whole fix: it repairs today's crash but leaves the
  pattern free to regrow (this is precisely how #168's wall ended up
  with nine holes — the pin was applied per call site by hand). The
  wrapper plus the shipped scan case make the invariant self-checked;
  the note D-naming means the next editor meets the wall at diff time.
- **Recommend `PYTHONUTF8=1` for Windows users in the README** —
  rejected, per #168's recorded alternative: an environment ritual is
  exactly the tax a stdlib-only, pip-install-and-go tool must not levy;
  the tool pins its own codecs. A GBK-locale CI matrix (`chcp 936` /
  system-locale change needs a reboot on windows-latest) is the
  reporter's optional follow-up and stays with a maintainer.
- **Treat PASS-with-traceback-in-output by sniffing captured text for
  exception markers** — rejected: matching traceback shapes in child
  output is a heuristic that false-positives on tools whose subject
  matter is tracebacks (self-test's clean-env replay prints one on
  purpose); the thread-excepthook record catches the actual defect — a
  crash in the harness's own threads — at the source, with no parsing.
- **Mark the run environment-suspect instead of failing** (the report's
  softer suggestion) — rejected: the crash is in govrail's own harness
  thread, not the adopter's environment; calling that
  environment-suspect would misattribute a tool defect — the exact
  misclassification #139/D47 built the classifier to prevent. Fail loud
  (rule 5), name the crash, let the replay/classifier do its own job.
