# Agent Note: locking, leases, and atomic writes without the unlink race

Status: implemented

## Problem

`decision add` flocked `.decision.lock` and then closed-and-unlinked it
in the same breath — the classic lockfile-unlink race: holder A closes
and unlinks while B blocks on the path; C recreates a fresh inode and
is granted instantly, so B and C both enter the critical section and
the second `os.replace` loses a decision. Windows degraded silently to
no lock at all. `task new` had no lock whatsoever: five parallel
workers produced three T-0001 cards and a permanently ambiguous id.
Task cards were written with bare `write_text` (a crash bricked every
task subcommand on half-written JSON), `task close` deleted whatever
lease the card carried — including a live one naming another worker —
`task claim` checked card status before taking the lease, `a/b` and
`a__b` mapped to one lock file, and the default holder identity was the
bare OS user, whom every same-machine worker shares.

## Decision

`gov/lockfile.py` provides the mutex: the lock file is durable (never
unlinked — the mutex lives on the inode), POSIX flocks it, Windows
msvcrt.locking takes it, and a platform with neither refuses loudly.
`task new` allocates ids under it and writes via `gov/atomicio.py`
(temp file, fsync, mode-preserving `os.replace` — also adopted by
decision add, presets, and archive-notes). `task close` now refuses a
card claimed by someone else unless `--force` (a knowing steal), and
re-checks the open status after taking the claim lease (the TOCTOU).
Lease filenames percent-encode the resource (distinct from `__`
literals), the default holder is `user@host`, lease temps are swept
past their TTL and shown by `gov locks`, and lease files chmod 0644
before linking so other users can classify them.

## Alternatives considered

O_EXCL lock directories instead of flock — rejected: no wait mechanism
and stale-lock recovery re-invents exactly the races flock solved.
Quoting `$GOV_BIN` in the hooks — rejected by the existing contract:
GOV_BIN is an argv string ("python -m gov") and word-splitting is its
documented behavior. Requiring `--agent` always — rejected: the
user@host default keeps single-agent flows ergonomic while the skill
docs tell parallel workers to set GOV_CALLER; same-machine same-user
workers without identity remain fundamentally indistinguishable, and
the docstring says so instead of pretending otherwise.
