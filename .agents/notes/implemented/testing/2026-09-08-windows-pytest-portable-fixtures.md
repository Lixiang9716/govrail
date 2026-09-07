# Agent Note: pytest suite ported to Windows — portable fixtures, named platform skips, windows CI runs the suite

Status: implemented

Related: #168 (the portability effort this continues), the 2026-09-08
bug-fix note (guarded fcntl / portable self-test fixtures / UTF-8 git
decode — whose Consequences left "pytest on Windows" as the recorded
follow-up this note closes), D1 (a gate command is a plain argv — the
same fixture honesty, now applied to the unit suite)

## Problem

The windows CI job shipped with #168 ran the CLI smoke and the tools
family of `gov self-test` but deliberately excluded `pytest`: the unit
suite said "a command that exits 0/1" with the Unix coreutils
(`["true"]`, `["false"]`, `["sh", "-c", ...]`) in ~60 fixtures, executed
POSIX shebang scripts (self-test project-family cases, a PATH `gov`
shim, a `sh -n` template lint), and pinned executable-bit semantics
(`chmod +x` + `os.access(X_OK)`) that Windows does not have — X_OK is
always true there. The suite was the last piece of the plane's own proof
that could only run on POSIX, so "OS Independent" was still only half
true for a contributor on Windows.

## Decision

- **Portable commands everywhere**: every test fixture that executes a
  gate now uses `sys.executable -c` commands (`PASS`/`FAIL` module
  constants, or the inline form) instead of coreutils — test_gates,
  test_run_merge (including its string-surgery `gates.json` blocks, via
  a `PASS_JSON` constant), test_task, test_receipt, test_doctor. On
  Linux nothing changes semantically; on Windows the same fixtures now
  mean what they always meant: "exits 0", "exits 1".
- **Named platform skips for POSIX-exec-inherent tests**, never silent:
  `@needs_posix_exec` (skipif win32, each with the reason in code) on
  the five test_self_test_rejections cases that execute shebang cases or
  pin the X_OK path, test_round_9_23's `sh -n` template lint and its
  executed `.py`-named shebang case, and test_presets' three acceptance
  tests whose PATH `gov` shim is a shebang script. These pin POSIX
  behavior on POSIX hosts; their Windows equivalents (a .bat shim, a
  named SKIP in self-test for OS-unrunnable cases) stay part of the
  deferred rule-6 decision.
- **test_pre_commit_hook's `GOV_BIN`** is built with
  `Path(sys.executable).as_posix()` — the hook runs under the shell git
  provides, where backslashes in unquoted shell context are escapes.
- **What the first Windows pytest run exposed, fixed for real:**
  - `os.execv` does not propagate the child's exit code on Windows — the
    locks/task race wrappers read `[0, 0]` because the loser's exit 3
    was lost. Wrappers now `subprocess.call` + `SystemExit` (the race
    proofs are unchanged on POSIX).
  - The takeover race's wording assert over-claimed: a plain O_EXCL
    create legally slips into the other's guarded unlink→recreate window
    (the fresh-create path never takes the guard, D52), so the winner's
    message may not say "took over". The assert now pins the actual
    guarantee — exactly one holder, loser REFUSED — and the takeover
    race test itself skips on Windows, where fcntl-less guards degrade
    by design (the double-takeover [0, 0] run there was the documented
    race window, empirically demonstrated).
  - Two separator defects in the product, found by the suite:
    `archive_notes` sealed relative paths with OS separators (a seal was
    not byte-stable across OSes — now `as_posix()`), and pairing
    `--staged` matched git's forward-slash paths against `str(Path)`
    (backslashes on Windows), silently checking nothing — both sides are
    now `as_posix()`-normalized.
  - Every test-side `write_text`/`read_text`/`open` is now pinned to
    `encoding="utf-8"` (315 call sites, AST-positioned): Windows defaults
    them to the locale codec, so non-ASCII fixtures crashed the fixtures
    themselves. The pinning is semantic (files are UTF-8 by convention),
    not cosmetic.
- **CI**: the windows job now installs `-e ".[dev]"`, runs
  `python -m pytest -q` before the smoke, and keeps the tools-family
  self-test. Ubuntu's job is unchanged (full self-test including this
  repo's POSIX dogfood cases).

## Alternatives considered

- **Put Git's `usr/bin` (true.exe/false.exe/sh.exe) on PATH in the
  windows job** — rejected: one CI line would green the whole suite
  while proving nothing about a Windows machine without coreutils; the
  claim "the suite is portable" would be a CI-environment artifact
  (rule 6: evidence must be the real thing, not a staged stand-in).
- **Port the POSIX-exec tests to Windows equivalents** (.bat shims,
  .cmd cases) — deferred with the rule-6 decision: it doubles the
  harness surface per platform and belongs to the same maintainer call
  as self-test's named-SKIP semantics.
- **Skip the whole suite on Windows again** — rejected: that is the
  vacuous-proof posture rule 6 exists to prevent; 3 named skips out of
  431 tests is the honest remainder.
