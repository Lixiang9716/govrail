# Agent Note: gate engine robustness — timeouts that fire, history that bounds

Status: implemented

## Problem

A gate's `timeoutMs` killed only the direct child: a grandchild holding
the output pipes hung `communicate` forever, so the timeout never
actually fired and `gov run` could hang for good. `--fail-fast` only
cancelled unstarted futures and then waited out every running gate.
`PermissionError`/exec-format failures escaped `_run_one` as a runner
traceback instead of a gate outcome. Windows died on bare `.cmd`
command names (`shutil.which` resolved the path and threw it away).
The receipts ledger crashed the whole run on a corrupt tail line, and
`trend` crashed on a naive timestamp or non-numeric duration while its
own `--cost` path skipped-and-named the same class of dirt — one
ledger, two policies. The history JSONL embedded full gate output per
line with no ceiling (a #109 ruling) and never rotated; Ctrl-C in
`run --merge` leaked the scratch worktree; the review dossier re-read
every changed file once per unmatched anchor; parse walked node_modules
in full before filtering; and the shipped template shipped no timeouts
at all.

## Decision

`_run_one` spawns gates in their own process group (session on POSIX,
`CREATE_NEW_PROCESS_GROUP` on Windows) and kills the whole tree on
timeout; fail-fast kills the live trees too, so the pool exits
immediately. Exec failures become a named `MISSING`; the resolved
executable path is what runs (Windows `.cmd` works). Unconfigured gates
get a 10-minute default (`DEFAULT_TIMEOUT_MS`). Receipt building skips
a corrupt ledger tail with a named line instead of a traceback, trend
validates durations exactly like `--cost` (named skips) and anchors
naive timestamps to UTC, and stats decodes identifiers with
`errors="replace"` like checks.py always did. The run REPORT stays
unclipped (#109's failure-first promise is about the human report) but
the JSONL record caps detail at 256 KB (`GOV_HISTORY_DETAIL_CAP`, 0
disables) and rotates one generation at 50 MB — the ledger bounds its
growth, the report keeps its evidence. `run --merge` un-docks the
scratch worktree on interruption, validates the step output is a JSON
array, and lists conflicts NUL-split. The review dossier reads each
file once; parse prunes excluded directories during the walk.

## Alternatives considered

Keep the ledger unclipped and rely on rotation alone — rejected: one
multi-MB gate output would still land whole in every record; the cap
is per-record with the full text one `--gate` rerun away. Kill only on
timeout and leave fail-fast lazy — rejected: a cancel that waits five
minutes is not fail-fast, and the process-group kill is the same
mechanism both need. Post-rotation reads in `trend` — rejected: the
rotated generation is archaeology, not a window; `--last` covers the
live ledger.
