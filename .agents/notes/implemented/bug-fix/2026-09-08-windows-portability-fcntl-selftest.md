# Agent Note: Windows portability — guarded fcntl, portable self-test fixtures, UTF-8 git decode

Status: implemented

Related: #168 (the report this fixes), D52 (lease locks are fail-open
liveness — the basis for degrading the guard flock), D47/#139 (the
self-test classifier whose tool-defect verdicts were correct: these WERE
tool defects), D1 (a gate command is a plain argv — the fixtures, not the
runner, were non-portable), decision.py's atomic-write lock (the
"POSIX only; absence degrades to no lock" precedent the guard now follows)

## Problem

The wheel ships `py3-none-any` and declares `Operating System :: OS
Independent`, but on Windows two things broke. First, `gov/locks.py`
imported `fcntl` at module top level — a Unix-only stdlib module — so
`cli.py`'s import of `locks` killed EVERY `gov` subcommand at startup
with `ModuleNotFoundError: No module named 'fcntl'` (#168 problem 1).
Second, with that hot-fixed, `gov self-test` still failed 10 of its 48
tools-family cases, every one classified tool-defect by the clean-env
replay (#168 problem 2). Root causes, all in the tool tree and none in
the gates runner itself:

- Nine fixtures said "a command that exits 0/1" with the Unix coreutils
  `true`/`false` and `sh -c`. Windows has none of them, so every such
  gate came out `MISSING` (`shutil.which` fails) — the fixtures tested
  "the executable exists", not the outcome semantics they were written
  to pin (default-mode scoping, disabled gates, advisory failure, `--base`
  path scoping, the failure summary, passing-with-output visibility, both
  receipt cases, and the `--merge` conflict preflight, whose scratch
  step went red on `MISSING` before branch b could conflict).
- `test_verify_decisions_rejects_base_collision` died differently:
  `decisions.numbers_in_rev` decoded `git show` output with the locale
  codec. On a GBK-locale Windows the UTF-8 decisions table (Chinese
  headings, em-dashes) raised `UnicodeDecodeError` inside the child —
  an uncaught crash exits 1, so the case saw "exit 1, no collision
  line". The same locale decode sat in every git-reading path: `--base`
  diffs, root anchoring, history/receipt paths, merge preflight, pairing
  hashes — any non-ASCII path, filename, or repo content could crash the
  tooling on any non-UTF-8 locale, not just Windows.
- A third layer, found by this PR's new Windows CI on its first run:
  the print side. Windows pipes give stdout/stderr the ANSI code page,
  and gates.py crashed with `UnicodeEncodeError` re-printing a child's
  captured output that carried an unencodable character — the report
  died mid-line. Decoding inputs as UTF-8 is half a wall without
  emitting UTF-8 as the other half.

## Decision

- `gov/locks.py` imports `fcntl` inside `try/except ImportError`
  (Windows: `fcntl = None`), and `_guarded` skips the `flock`/`LOCK_UN`
  pair when it is absent — the takeover/release critical section
  degrades to unserialized exactly where D52 already prices in a
  double-issue race ("liveness, not correctness"; upper-layer validation
  carries correctness). Same shape and wording as decision.py's
  atomic-write lock. Module and `_guarded` docstrings say so; the
  metadata claim `OS Independent` is now honest.
- `gov/self_test.py` gains `_pass_cmd()`/`_fail_cmd()` — portable
  always-exit-0/1 gate commands built on `sys.executable -c` — plus an
  inline `-c` form for the two `sh -c` fixtures (boom: stderr `boom`,
  exit 3; warny: stdout `heads up`, exit 0). Every fixture whose gates
  EXECUTE uses them: skip propagation, default-mode scoping, disabled
  gates, advisory failure, `--base` scoping, failure summary,
  passing-with-output, `_receipt_repo`, the `--merge` conflict fixture.
  Fixtures that exit 2 at config load before any gate runs keep their
  `["true"]` placeholders (never executed, nothing to port).
- Every git-output decode in the package is pinned to
  `encoding="utf-8", errors="replace"` (git communicates in UTF-8; the
  locale codec must never crash a tool on repo content): root.py,
  cli.py, doctor.py, gates.py (history path, gate output, changed
  files), locks.py, merge.py (helper, toplevel, step stdout), receipt.py,
  change_scope.py, decisions.py (both `numbers_in_rev` reads), task.py,
  trend.py, verify_conflict_markers.py, verify_decisions.py,
  verify_note_presence.py, verify_translation_pairing.py.
- The mirror of that decode wall is the PRINT side: Windows pipes give
  stdout/stderr the ANSI code page (cp1252/GBK), and gates.py died
  re-printing a child's output the moment it carried a character the
  codec could not encode. `root.force_utf8_stdio()` reconfigures stdio
  to UTF-8 with errors="replace" — the plane's reports always leave as
  valid UTF-8, on every OS; a real console is unaffected (PEP 528), and
  streams that cannot be reconfigured (pytest capsys) keep theirs. It
  rides `anchor_to_git_root` for the root-anchored tools and is called
  explicitly at every other entry point (cli, gates, self_test,
  receipt, presets, review, change_scope, doctor, verify_note_presence,
  verify_rubric). The self-test harness agrees with its children by
  construction: `_case_env` sets `PYTHONIOENCODING=utf-8` and every
  fixture capture decodes `utf-8`/`replace` — child-encode and
  parent-decode can no longer disagree about the codec.
- CI gains a `windows` job (windows-latest, Python 3.12): install the
  wheel, replay the reporter's verified end-to-end (`gov init` /
  `gov doctor` / `gov run --mode all` in a fresh repo), then
  `gov self-test`. pytest stays out — the unit suite still leans on
  POSIX shebangs/execute bits (known follow-up, not part of this
  contract). New unit tests in tests/test_locks.py pin the degraded
  guard: with `fcntl = None` the action runs once, its exception still
  propagates, and the CLI wiring answers named exits, never an
  ImportError.
- README/README.zh gain one mirror-lag line (install from the official
  index when a mirror's simple index trails its JSON API — #168's
  aside); the pair is re-confirmed in README.i18n.yaml (rule 7).

## Alternatives considered

- **`msvcrt.locking` adapter for the guard** (or excluding
  acquire/release/locks from Windows wheels) — rejected: the guard
  serializes a lazy-takeover optimization of a liveness mechanism;
  paying an OS-specific lock adapter (or a per-platform wheel split)
  to preserve an already-documented race window is complexity the
  fail-open contract does not demand. D52's supersede boundary is
  untouched: cross-clone correctness still anchors on CAS.
- **Teach `gates.py` to synthesize `true`/`false` (or a shell fallback)
  on Windows** — rejected: it would bend D1's "a command is a plain
  argv, no shell variants" contract and make MISSING — a real and
  useful verdict — unreportable. The runner was right; the fixtures
  lied.
- **Decode git output with `sys.getfilesystemencoding()`/
  `locale.getpreferredencoding()`** — rejected: that is exactly the
  crashing behavior; git's wire encoding is UTF-8 regardless of the
  process locale, and `errors="replace"` bounds the damage of
  non-UTF-8 legacy content to mojibake instead of a traceback.
- **Simulate Windows by skipping the nine fixtures on Windows** —
  rejected: skipping the tools' own proof on a shipped platform is
  rule 6's "vacuous script" wearing a platform hat; portable fixtures
  keep the proof running everywhere the wheel installs.
- **Require `PYTHONUTF8=1` / `PYTHONIOENCODING` from Windows users** —
  rejected: an environment ritual is exactly the tax a stdlib-only,
  pip-install-and-go tool must not levy; the tool pins its own codecs.
