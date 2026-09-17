# Agent Note: the UTF-8 wall now covers the filesystem, not just stdio

Status: implemented

## Problem

The GBK hostile-locale CI job failed again after the audit fixes: two
gitutil tests asserted a UTF-8 filename round-trip and got GBK mojibake
surrogates back. #168 had pinned stdio UTF-8, but a hostile locale
still kept two doors open: Python's FILESYSTEM encoding follows the
locale (so a Chinese filename landed on disk as GBK bytes no utf-8
decode can read back), and unpinned subprocess text reads decoded the
locale codec. The reporter's Windows machine and my own shell dodged
the class only because they happened to export PYTHONUTF8=1 — CI has
no such luxury, which is exactly why the job exists.

## Decision

`gov/root.py:ensure_utf8_runtime` makes the contract ambient instead of
incidental: it exports `PYTHONUTF8=1` for every Python child the
process spawns, and when the process entered through a real CLI entry
(`-c` and library calls are excluded; pytest re-enters via the test
conftest) and the filesystem encoding is not UTF-8, it re-execs itself
under PEP 540 UTF-8 mode (`-X utf8`), rebuilding the entry exactly —
`-m` invocations re-enter through `__main__.__spec__.name` (a basename
heuristic cannot tell gov's `__main__.py` from pytest's), console
scripts re-enter through their resolved script path. Windows needs only
the env export: its path API has been UTF-8 since PEP 529.

The test suite takes the same treatment, but at `pytest_configure` with
the capture suspended — never at conftest-import time. pytest loads the
initial conftests *while its global capture already owns fds 1/2*
(`_pytest/capture.py`: "trigger conftest loading but while capturing"),
so an exec from there hands the capture's temp files to the restarted
interpreter: the whole run's report, every failure included, lands in a
file nobody dumps. The gbk-locale job was output-blind for exactly that
reason — green runs said nothing, and the red one reported an exit code
with no failure text. `pytest_configure` runs with the capture
suspended, so the exec'd run reports into the real streams; when no exec
happens (xdist workers enter through `-c`), the capture is resumed and
the workers take UTF-8 from the exported env instead.

## Alternatives considered

Decode git listings with `os.fsdecode` so bytes round-trip through the
host codec — rejected: it makes listings "work" while every matcher
compares mojibake strings against UTF-8 globs; the failure moves, not
ends. Re-exec from `force_utf8_stdio` — rejected: verify modules call
it mid-process (including from inside a live pytest run); a restart
there is a test loop, so the exec belongs at real entries only. Set
only `PYTHONUTF8` and skip the re-exec — rejected: it fixes the
children and abandons the process that is already running GBK-encoded.
Re-exec at conftest import (this decision's first shape) — rejected by
the evidence: it did hold the contract, and it also swallowed the
report, so the gate could not say what it ran or what failed. A green
step that cannot be read is not evidence, and a red one that cannot be
read is not a finding.
