#!/usr/bin/env python3
"""Lease locks for oblivious parallel agents (``gov acquire/release/locks``).

D51 deferred the lock/lease layer behind a criterion — "there really are
≥2 parallel workers needing shared-resource coordination". That criterion
fired: real users run multiple workers that are oblivious to each other
and coordinate shared-resource writes by tool-blocking/continuing. This
module ships the LEASE class of lock — cross-process, cross-duration,
declarative — and only that. The flock(2) class stays where it already
lives: inside single commands (e.g. decision add's append), because an
flock belongs to its holding process and dies with it — a review-P0
finding that ruled out any long-held flock.

Liveness, not correctness (fail-open). A lease only prevents DUPLICATED
WORK; correctness is anchored elsewhere (push CAS for master, delivery
rebase for docs). A holder that stalls past its TTL can therefore share
the resource with a taker-over — the upper-layer validation catches that,
and the tests say so in plain language. The guard flock below is POSIX-only
(issue #168): on Windows the takeover critical section runs unserialized,
which widens that same already-priced-in race instead of breaking the CLI.

Storage: ``<git-common-dir>/gov-locks/<resource>.json`` (``/`` in the
resource name becomes ``__``), created on demand. The git common dir is
shared by every worktree of one clone, so leases span worktrees (D52's
supersede boundary: cross-clone/cross-machine correctness stays with the
CAS anchor; D40's "file locks don't lock independent checkouts" remains
true and un-superseded).

- ``gov acquire <resource> [--agent ID] [--ttl DUR] [--wait DUR]`` — atomic
  create (O_CREAT|O_EXCL). Existing fresh lease → busy: exit 3 naming the
  holder and expiry (``--wait S`` polls at 1s until the deadline). Existing
  EXPIRED lease → lazy takeover, legal only inside a flock-guarded critical
  section on a ``.guard`` sibling file (flock's lawful single-command
  duration — two takers-over are serialized and re-check expiry inside the
  guard; a fresh O_EXCL create never needs the guard and never unlinks).
- ``gov release <resource> --agent ID`` — holder-verified delete: a
  mismatching agent is refused (exit 2) with the real holder named; a
  lease is never released on another holder's behalf. Absent lease → exit 2.
- Both announce the resolved lock root on stderr (one line, success and
  busy alike): the concurrency drills caught an agent acquiring against
  the WRONG repository — a lease was silent about where it lived, so the
  misdomain lock looked exactly like a success until someone read
  ``gov locks`` in the right repo. Now the misdomain is visible at the
  moment it happens.
- ``gov locks`` — read-only listing of the lease directory, expired flags
  included. Pure diagnostics (review P1-3: the JSON layer never feeds an
  admission decision); no locks → an empty listing.

Exit codes (D2's 0/1/2 stay; D52 extends the vocabulary additively):
0 success; 2 configuration/usage error (not a git repository, hostile
environment variables, not the holder, releasing an unheld lease);
3 busy or wait timeout — the one outcome a caller must be able to branch
on, so it gets its own code rather than overloading 1.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:  # POSIX only (issue #168); on Windows the guard degrades to no
    # serialization — the lease stays fail-open liveness (D52), same
    # precedent and wording as decision.py's atomic-write lock.
    import fcntl
except ImportError:  # pragma: no cover - Windows has no fcntl module
    fcntl = None

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution
    from root import anchor_to_git_root

# D33 wall 1, at the refusal strength D51 chose for state-mutating
# commands: acquire/release write into the .git domain, so an environment
# that re-points git at another repository is refused by name, never
# silently re-domained. Every git call below also runs GIT_*-scrubbed.
HOSTILE_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
)

LOCK_DIR = "gov-locks"
DEFAULT_TTL_S = 3600.0
POLL_INTERVAL_S = 1.0
COMMANDS = ("acquire", "release", "locks")


def _scrubbed_env() -> dict:
    """Environment for git subprocesses (D33 wall 1)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _refuse_hostile_env(tool: str) -> None:
    leaked = [v for v in HOSTILE_VARS if os.environ.get(v)]
    if leaked:
        print(
            f"gov {tool}: REFUSING to run — the environment carries "
            f"repository-resolving variable(s): {', '.join(leaked)}. A lease "
            "resolves the git common dir of the repository it is invoked on; "
            "unset the variable(s) and re-run there (D33 wall 1: fail loud, "
            "never switch domain silently).",
            file=sys.stderr)
        raise SystemExit(2)


def _common_dir(tool: str) -> Path:
    """The resolved git common dir; any failure is a named exit 2.

    No cwd-level silent degradation (rule 5): outside a repository the
    command refuses instead of quietly locking something in the current
    directory. Under the main worktree ``--git-common-dir`` prints the
    RELATIVE ``.git`` — it is resolve()d against the caller's cwd.
    """
    proc = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",  # git speaks UTF-8, not the locale codec (#168)
        env=_scrubbed_env(),
    )
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out:
        detail = (proc.stderr or proc.stdout).strip() or "not a git repository"
        print(f"gov {tool}: cannot resolve the git common dir: {detail} — "
              "lease locks live in <git-common-dir>/gov-locks and refuse to "
              "guess a fallback directory", file=sys.stderr)
        raise SystemExit(2)
    p = Path(out)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _announce_root(command: str, common: Path) -> None:
    """One stderr line naming the resolved lock root — every invocation.

    Success or busy, the caller sees exactly which directory the lease
    lives in; an acquire issued from the wrong cwd is visible immediately
    instead of at review time.
    """
    print(f"{command}: lock root {common / LOCK_DIR}", file=sys.stderr)


def _lease_path(common: Path, resource: str) -> Path:
    return common / LOCK_DIR / (resource.replace("/", "__") + ".json")


def _guard_path(common: Path, resource: str) -> Path:
    return common / LOCK_DIR / (resource.replace("/", "__") + ".guard")


def _holder_id(agent: str | None) -> str:
    """--agent, else $GOV_CALLER (D42's caller vocabulary), else the OS user.

    Whitespace-only counts as absent, same as D42 treats it for --tag.
    """
    if agent and agent.strip():
        return agent.strip()
    caller = os.environ.get("GOV_CALLER", "")
    if caller.strip():
        return caller.strip()
    return getpass.getuser()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_ts(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _read_lease(path: Path) -> dict | None:
    """The parsed lease, or None when absent/unreadable/corrupt.

    None reads as "not held by anyone" (fail-open: a lease only guards
    liveness, and a half-written or tampered file names no live holder).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _is_fresh(data: dict | None, now: datetime) -> bool:
    """True only when a readable lease exists and now <= expires_at."""
    if data is None:
        return False
    exp = _parse_ts(data.get("expires_at"))
    return exp is not None and now <= exp


def _create_exclusive(path: Path, payload: str) -> bool:
    """O_CREAT|O_EXCL create with content; False when the file exists."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(payload)
    return True


def _guarded(common: Path, resource: str, action) -> object:
    """Run ``action`` inside the resource's guard flock.

    The flock lives for this one command only — the lawful flock class.
    It serializes takers-over (and holder-verified releases) on the same
    resource so the unlink→recreate takeover can never double-issue a
    lease, and never holds anything once the process exits.

    Windows has no fcntl (issue #168): the guard degrades to an unserialized
    critical section — the takeover race window widens exactly as the
    module docstring's fail-open contract already prices in (a lease only
    prevents duplicated work; upper-layer validation carries correctness).
    """
    guard_path = _guard_path(common, resource)
    guard_path.parent.mkdir(parents=True, exist_ok=True)
    with open(guard_path, "w") as guard:
        if fcntl is not None:
            fcntl.flock(guard, fcntl.LOCK_EX)
        try:
            return action()
        finally:
            if fcntl is not None:
                fcntl.flock(guard, fcntl.LOCK_UN)


def _takeover(common: Path, resource: str, payload: str,
              now: datetime) -> bool:
    """Replace an expired lease inside the guard's critical section.

    The only place an expired lease is ever unlinked — and only after the
    expiry is RE-checked inside the guard (another taker may have won the
    race between the caller's classification and this critical section).
    A fresh lock is never unlinked here.
    """
    def action() -> bool:
        path = _lease_path(common, resource)
        if _is_fresh(_read_lease(path), now):
            return False  # someone re-acquired; no longer expired
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        return _create_exclusive(path, payload)

    return bool(_guarded(common, resource, action))


_DURATION_UNITS = {"s": 1.0, "m": 60.0, "h": 3600.0}


def duration(value: str) -> float:
    """Parse a duration for --ttl/--wait: ``600``, ``600s``, ``20m``, ``2h``.

    Bare numbers stay seconds (the original contract, kept for every caller
    that already passes them); suffixes exist because both drill agents
    wrote ``20m`` unprompted — agents think in durations, not seconds.
    """
    text = value.strip().lower()
    try:
        if text and text[-1] in _DURATION_UNITS:
            seconds = float(text[:-1]) * _DURATION_UNITS[text[-1]]
        else:
            seconds = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid duration {value!r} — use seconds, or a suffix of "
            f"{', '.join(sorted(_DURATION_UNITS))} (e.g. 600, 20m, 2h)")
    if seconds <= 0:
        raise argparse.ArgumentTypeError(
            f"invalid duration {value!r} — must be > 0")
    return seconds


def acquire(resource: str, holder: str, ttl: float,
            wait: float | None, tool: str = "gov acquire") -> int:
    now = datetime.now(timezone.utc)
    expires = _iso(datetime.fromtimestamp(now.timestamp() + ttl, timezone.utc))
    payload = json.dumps(
        {"resource": resource, "holder": holder,
         "acquired_at": _iso(now), "expires_at": expires},
        ensure_ascii=False, sort_keys=True,
    ) + "\n"
    common = _common_dir(tool)
    _announce_root("acquire", common)
    path = _lease_path(common, resource)
    path.parent.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + (max(0.0, wait) if wait is not None else 0.0)
    while True:
        now = datetime.now(timezone.utc)
        if _create_exclusive(path, payload):
            print(f"acquire: '{resource}' leased by '{holder}' until {expires}")
            return 0
        data = _read_lease(path)
        if not _is_fresh(data, now):
            # expired or unreadable → lazy takeover under the guard
            if _takeover(common, resource, payload, now):
                print(f"acquire: '{resource}' leased by '{holder}' until "
                      f"{expires} (took over an expired lease)")
                return 0
            # lost the takeover race; re-classify on the next loop pass
            continue
        held_by = data.get("holder")
        until = data.get("expires_at")
        remaining = deadline - time.monotonic()
        if wait is None or remaining <= 0:
            print(f"acquire: REFUSED — '{resource}' is held by '{held_by}' "
                  f"until {until}"
                  + ("" if wait is None else
                     f" (waited {wait:g}s; --wait S polls until the lease "
                     "expires or is released)"),
                  file=sys.stderr)
            return 3
        time.sleep(POLL_INTERVAL_S)


def release(resource: str, holder: str, tool: str = "release") -> int:
    common = _common_dir(tool)
    _announce_root("release", common)

    def action() -> int:
        path = _lease_path(common, resource)
        data = _read_lease(path)
        if data is None:
            print(f"release: REFUSED — '{resource}' is not held "
                  f"(no readable lease at {path})", file=sys.stderr)
            return 2
        actual = data.get("holder")
        if actual != holder:
            print(f"release: REFUSED — '{resource}' is held by '{actual}', "
                  f"not '{holder}'; a lease is never released on another "
                  "holder's behalf", file=sys.stderr)
            return 2
        try:
            os.unlink(path)
        except FileNotFoundError:
            print(f"release: REFUSED — '{resource}' is not held "
                  f"(the lease vanished before release)", file=sys.stderr)
            return 2
        print(f"release: '{resource}' released by '{holder}'")
        return 0

    # check + unlink inside the guard: a stale-check release must never
    # unlink a lease a concurrent takeover has just re-issued.
    return int(_guarded(common, resource, action))


def list_locks() -> int:
    common = _common_dir("locks")
    lock_dir = common / LOCK_DIR
    leases = sorted(lock_dir.glob("*.json")) if lock_dir.is_dir() else []
    rows = []
    now = datetime.now(timezone.utc)
    for p in leases:
        data = _read_lease(p)
        if data is None:
            rows.append((p.stem, "(unreadable)", "-", "-", "yes"))
            continue
        exp = _parse_ts(data.get("expires_at"))
        expired = "yes" if (exp is None or now > exp) else "no"
        rows.append((
            str(data.get("resource") or p.stem),
            str(data.get("holder") or "(unknown)"),
            str(data.get("acquired_at") or "-"),
            str(data.get("expires_at") or "-"),
            expired,
        ))
    if rows:
        widths = [max(len(r[i]) for r in rows)
                  for i in range(5)]
        headers = ("resource", "holder", "acquired_at", "expires_at",
                   "expired")
        widths = [max(widths[i], len(headers[i])) for i in range(5)]
        print("  ".join(headers[i].ljust(widths[i]) for i in range(5)).rstrip())
        for r in rows:
            print("  ".join(r[i].ljust(widths[i]) for i in range(5)).rstrip())
    # no locks → an empty listing (exit 0): pure diagnostics, nothing is
    # admitted or rejected from it (review P1-3).
    return 0


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("locks")
    parser = argparse.ArgumentParser(
        prog="gov acquire/release/locks",
        description="Lease locks: cross-process, cross-duration, "
                    "declarative (liveness only — never correctness).",
    )
    sub = parser.add_subparsers(dest="subcommand")

    p_acq = sub.add_parser(
        "acquire", help="take a lease on a resource (busy → exit 3)")
    p_acq.add_argument("resource", help="resource name ('/' is stored as '__')")
    p_acq.add_argument("--agent", metavar="ID",
                       help="holder identity (default: $GOV_CALLER, then "
                            "the OS user)")
    p_acq.add_argument("--ttl", type=duration, default=DEFAULT_TTL_S,
                       metavar="DUR",
                       help="lease duration (seconds, or 20m/2h style; "
                            f"default {DEFAULT_TTL_S:g}s); an expired lease "
                            "may be taken over lazily")
    p_acq.add_argument("--wait", type=duration, default=None, metavar="DUR",
                       help="poll up to this long for the lease instead of "
                            "failing immediately (exit 3 on timeout)")

    p_rel = sub.add_parser(
        "release", help="release a lease you hold (holder-verified)")
    p_rel.add_argument("resource", help="resource name ('/' is stored as '__')")
    p_rel.add_argument("--agent", metavar="ID",
                       help="holder identity (default: $GOV_CALLER, then "
                            "the OS user)")

    p_list = sub.add_parser(
        "locks", help="list current lease locks (read-only diagnostics)")

    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.error("a subcommand is required (acquire|release|locks)")
    # Refuse the hostile domain BEFORE any git resolution (root anchoring
    # included): nothing may observe the wrong repository, even read-only.
    _refuse_hostile_env(args.subcommand)
    anchor_to_git_root("locks")
    if args.subcommand == "acquire":
        return acquire(args.resource, _holder_id(args.agent), args.ttl,
                       args.wait)
    if args.subcommand == "release":
        return release(args.resource, _holder_id(args.agent))
    return list_locks()


if __name__ == "__main__":
    raise SystemExit(main())
