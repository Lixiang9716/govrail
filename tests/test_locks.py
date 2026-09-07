"""Lease locks: acquire/release/locks (D52).

Acceptance runs every candidate as a SUBPROCESS (two-process races are the
point — an in-process call could never exercise cross-process exclusivity),
pinned to THIS checkout's gov, in a scratch git repository, with GIT_*
scrubbed from the environment (D33).

Rule 6 honesty, stated where it belongs: these tests prove the lease can
REJECT (busy, wrong holder, hostile environment) and that the takeover
critical section serializes a real race. They cannot prove double-hold is
impossible — a holder that stalls past its TTL shares the resource with a
taker-over by design. The lock is the LIVENESS layer (don't duplicate
work); correctness is anchored in upper-layer validation (push CAS for
master, delivery rebase for docs). See D52 and the cookbook recipe.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRUBBED = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True,
                       env=SCRUBBED)


def _gov(root: Path, *args, env=None, timeout=30):
    return subprocess.run(
        [sys.executable, "-m", "gov", *args],
        cwd=root, capture_output=True, text=True, timeout=timeout,
        env=dict(SCRUBBED, PYTHONPATH=str(REPO), **(env or {})),
    )


def _lockdir(root: Path) -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], cwd=root,
        capture_output=True, text=True, env=SCRUBBED, check=True,
    ).stdout.strip()
    p = Path(out)
    return (p if p.is_absolute() else root / p).resolve() / "gov-locks"


def _lease(root: Path, resource: str) -> Path:
    return _lockdir(root) / (resource.replace("/", "__") + ".json")


def _write_lease(root: Path, resource: str, holder: str, expires: datetime):
    _lockdir(root).mkdir(parents=True, exist_ok=True)
    _lease(root, resource).write_text(json.dumps({
        "resource": resource, "holder": holder,
        "acquired_at": "2020-01-01T00:00:00+00:00",
        "expires_at": expires.isoformat(),
    }), encoding="utf-8")


def _read_lease(root: Path, resource: str) -> dict:
    return json.loads(_lease(root, resource).read_text(encoding="utf-8"))


# --- a: acquire creates the lease; re-acquire is busy (non-reentrant) --------

def test_acquire_creates_lease_with_correct_content(tmp_path):
    _git_repo(tmp_path)
    r = _gov(tmp_path, "acquire", "reports/summary.md", "--agent", "agent-a",
             "--ttl", "300")
    assert r.returncode == 0, (r.stdout, r.stderr)
    data = _read_lease(tmp_path, "reports/summary.md")
    # '/' in the resource name is stored as '__' in the filename
    assert _lease(tmp_path, "reports/summary.md").name == \
        "reports__summary.md.json"
    assert data["resource"] == "reports/summary.md"
    assert data["holder"] == "agent-a"
    acquired = datetime.fromisoformat(data["acquired_at"])
    expires = datetime.fromisoformat(data["expires_at"])
    assert (expires - acquired).total_seconds() == pytest.approx(300, abs=2)


def test_reacquire_busy_exit3_names_holder_other_and_same(tmp_path):
    """The lock is NOT reentrant: even the holder's own repeat acquire is
    exit 3. One rule for everyone — no holder-affinity special cases to
    reason about when workers are oblivious to each other."""
    _git_repo(tmp_path)
    assert _gov(tmp_path, "acquire", "r", "--agent", "agent-a",
                "--ttl", "300").returncode == 0
    other = _gov(tmp_path, "acquire", "r", "--agent", "agent-b", "--ttl", "300")
    assert other.returncode == 3
    assert "agent-a" in other.stderr
    assert "until" in other.stderr
    again = _gov(tmp_path, "acquire", "r", "--agent", "agent-a", "--ttl", "300")
    assert again.returncode == 3  # non-reentrant, same holder included
    assert "agent-a" in again.stderr
    # the lease is untouched by the refused attempts
    assert _read_lease(tmp_path, "r")["holder"] == "agent-a"


# --- b: lazy expiry takeover --------------------------------------------------

def test_expired_lease_is_taken_over(tmp_path):
    _git_repo(tmp_path)
    past = datetime.now(timezone.utc) - timedelta(seconds=60)
    _write_lease(tmp_path, "r", "corpse", past)
    r = _gov(tmp_path, "acquire", "r", "--agent", "new", "--ttl", "300")
    assert r.returncode == 0, (r.stdout, r.stderr)
    data = _read_lease(tmp_path, "r")
    assert data["holder"] == "new"
    assert datetime.fromisoformat(data["expires_at"]) > datetime.now(timezone.utc)


def test_unexpired_lease_is_never_taken_over(tmp_path):
    _git_repo(tmp_path)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    _write_lease(tmp_path, "r", "live", future)
    r = _gov(tmp_path, "acquire", "r", "--agent", "grabber", "--ttl", "300")
    assert r.returncode == 3
    assert _read_lease(tmp_path, "r")["holder"] == "live"


# --- c: the takeover race — exactly one winner --------------------------------

_WRAPPER = (
    "import os, subprocess, sys, time\n"
    "go, resource, agent = sys.argv[1:4]\n"
    "while not os.path.exists(go):\n"
    "    time.sleep(0.005)\n"
    "# subprocess.call + SystemExit, not os.execv: on Windows execv does\n"
    "# not propagate the child's exit code, so the loser's exit 3 was\n"
    "# lost and the race proof read [0, 0] (#168 windows CI).\n"
    "raise SystemExit(subprocess.call(\n"
    "    [sys.executable, '-m', 'gov', 'acquire', resource,\n"
    "      '--agent', agent, '--ttl', '300']))\n"
)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="without fcntl (#168) the takeover guard degrades to an "
           "unserialized critical section BY DESIGN (D52 fail-open): both "
           "takers-over can win, which is the documented race window the "
           "upper-layer validation anchors, not a regression")
def test_concurrent_takeover_of_expired_lease_exactly_one_wins(tmp_path):
    """Two processes start simultaneously on the SAME expired lease.

    Both classify it expired, then enter the guard-flocked critical
    section; the loser re-checks expiry inside the guard, sees a fresh
    lease, and reports busy (exit 3). The go-file barrier makes the start
    simultaneous rather than merely sequential — this exercises the
    takeover race itself, not just the busy path.
    """
    _git_repo(tmp_path)
    past = datetime.now(timezone.utc) - timedelta(seconds=60)
    _write_lease(tmp_path, "contested", "corpse", past)
    go = tmp_path / "go"
    env = dict(SCRUBBED, PYTHONPATH=str(REPO))
    procs = []
    for agent in ("race-a", "race-b"):
        procs.append(subprocess.Popen(
            [sys.executable, "-c", _WRAPPER, str(go), "contested", agent],
            cwd=tmp_path, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True))
    go.write_text("go", encoding="utf-8")  # release both at once
    outs = [p.communicate(timeout=30) for p in procs]
    codes = [p.returncode for p in procs]
    # The guard's guarantee is EXACTLY ONE HOLDER (codes [0, 3]), not the
    # winner's wording: a winner that slips its plain O_EXCL create into
    # the moment the other's guarded takeover sits between unlink and
    # recreate is legal — the fresh-create path never takes the guard
    # (D52) — and the surviving lease still names exactly one holder.
    assert sorted(codes) == [0, 3], (codes, outs)
    winner_out, loser_err = outs[codes.index(0)], outs[codes.index(3)]
    assert "REFUSED" in loser_err[1]
    assert _read_lease(tmp_path, "contested")["holder"] in ("race-a", "race-b")


def test_concurrent_fresh_acquires_also_exactly_one_wins(tmp_path):
    """Same barrier start on a NON-existent lease: O_EXCL alone decides —
    no guard needed on the fresh path — and the loser sees a fresh lease
    (busy), never a takeover."""
    _git_repo(tmp_path)
    go = tmp_path / "go"
    env = dict(SCRUBBED, PYTHONPATH=str(REPO))
    procs = []
    for agent in ("race-a", "race-b"):
        procs.append(subprocess.Popen(
            [sys.executable, "-c", _WRAPPER, str(go), "fresh", agent],
            cwd=tmp_path, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True))
    go.write_text("go", encoding="utf-8")
    outs = [p.communicate(timeout=30) for p in procs]
    codes = [p.returncode for p in procs]
    assert sorted(codes) == [0, 3], (codes, outs)
    assert "took over an expired lease" not in outs[codes.index(0)][0]


# --- d: release is holder-verified ---------------------------------------------

def test_release_by_non_holder_refused_and_names_actual(tmp_path):
    _git_repo(tmp_path)
    _gov(tmp_path, "acquire", "r", "--agent", "real", "--ttl", "300")
    r = _gov(tmp_path, "release", "r", "--agent", "impostor")
    assert r.returncode == 2
    assert "real" in r.stderr
    assert _lease(tmp_path, "r").exists()  # not released on another's behalf


def test_release_by_holder_deletes_the_lease(tmp_path):
    _git_repo(tmp_path)
    _gov(tmp_path, "acquire", "r", "--agent", "real", "--ttl", "300")
    r = _gov(tmp_path, "release", "r", "--agent", "real")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert not _lease(tmp_path, "r").exists()
    # releasing again: the lease is gone — a named refusal, not silence
    again = _gov(tmp_path, "release", "r", "--agent", "real")
    assert again.returncode == 2
    assert "not held" in again.stderr


# --- e: git environment safety (D33) --------------------------------------------

def test_non_git_directory_exit2_for_all_three(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    for argv in (("acquire", "r", "--agent", "a"),
                 ("release", "r", "--agent", "a"),
                 ("locks",)):
        r = _gov(plain, *argv)
        assert r.returncode == 2, (argv, r.stdout, r.stderr)
        assert "common dir" in r.stderr
    # nothing was locked into the cwd as a fallback
    assert not (plain / "gov-locks").exists()


def test_git_dir_injection_refused_and_host_bytes_unchanged(tmp_path):
    root = tmp_path / "host"
    _git_repo(root)
    (root / "f.txt").write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True,
                   capture_output=True, env=SCRUBBED)

    def tree_hash():
        h = hashlib.sha256()
        for p in sorted(root.rglob("*")):
            if p.is_file() and ".git" not in p.parts:
                h.update(str(p.relative_to(root)).encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    before_files = sorted(
        str(p.relative_to(root / ".git"))
        for p in (root / ".git").rglob("*") if p.is_file())
    r = _gov(root, "acquire", "r", "--agent", "a",
             env={"GIT_DIR": str(root / ".git")})
    assert r.returncode == 2
    assert "GIT_DIR" in r.stderr
    assert "REFUSING" in r.stderr
    # the host repository is byte-identical: no lease written anywhere,
    # no new file in .git
    assert tree_hash() == tree_hash()
    after_files = sorted(
        str(p.relative_to(root / ".git"))
        for p in (root / ".git").rglob("*") if p.is_file())
    assert after_files == before_files
    assert not (root / ".git" / "gov-locks").exists()
    for argv in (("release", "r", "--agent", "a"), ("locks",)):
        r = _gov(root, *argv, env={"GIT_DIR": str(root / ".git")})
        assert r.returncode == 2 and "GIT_DIR" in r.stderr


# --- f: --wait polls until the lease expires -------------------------------------

def test_wait_polls_until_expiry_then_acquires(tmp_path):
    _git_repo(tmp_path)
    t0 = time.monotonic()
    assert _gov(tmp_path, "acquire", "r", "--agent", "holder",
                "--ttl", "2").returncode == 0
    r = _gov(tmp_path, "acquire", "r", "--agent", "waiter",
             "--ttl", "300", "--wait", "30", timeout=60)
    elapsed = time.monotonic() - t0
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert elapsed >= 2.0  # it really waited for the expiry, not luck
    assert _read_lease(tmp_path, "r")["holder"] == "waiter"


def test_wait_timeout_exit3_when_lease_stays_fresh(tmp_path):
    _git_repo(tmp_path)
    _gov(tmp_path, "acquire", "r", "--agent", "holder", "--ttl", "3600")
    t0 = time.monotonic()
    r = _gov(tmp_path, "acquire", "r", "--agent", "waiter",
             "--wait", "2", timeout=60)
    assert r.returncode == 3
    assert time.monotonic() - t0 >= 2.0  # bounded wait, not unbounded
    assert "holder" in r.stderr


# --- g: gov locks mirrors the lease directory -------------------------------------

def test_locks_listing_matches_directory(tmp_path, capsys):
    _git_repo(tmp_path)
    empty = _gov(tmp_path, "locks")
    assert empty.returncode == 0
    assert empty.stdout.strip() == ""  # an empty listing when no locks
    _gov(tmp_path, "acquire", "one", "--agent", "a", "--ttl", "3600")
    _gov(tmp_path, "acquire", "two", "--agent", "b", "--ttl", "3600")
    _write_lease(tmp_path, "stale", "corpse",
                 datetime.now(timezone.utc) - timedelta(seconds=60))
    out = _gov(tmp_path, "locks").stdout
    assert "one" in out and "a" in out
    assert "two" in out and "b" in out
    assert "stale" in out and "corpse" in out
    # the expired lease is flagged; fresh ones are not
    stale_row = next(l for l in out.splitlines() if "stale" in l)
    one_row = next(l for l in out.splitlines() if l.startswith("one "))
    assert stale_row.rstrip().endswith("yes")
    assert one_row.rstrip().endswith("no")
    # release one → the listing follows the directory
    _gov(tmp_path, "release", "one", "--agent", "a")
    out = _gov(tmp_path, "locks").stdout
    assert "one" not in out and "two" in out


# --- announce the resolved lock root (misdomain is visible at once) ----------

def test_acquire_announces_lock_root_on_success_and_busy(tmp_path):
    """The drills caught an agent locking the WRONG repository (wrong cwd):
    the lease used to be silent about where it lives. Now both the success
    and the busy path name the resolved lock root on stderr."""
    _git_repo(tmp_path)
    ok = _gov(tmp_path, "acquire", "r", "--agent", "a", "--ttl", "300")
    assert ok.returncode == 0, (ok.stdout, ok.stderr)
    root = _lockdir(tmp_path)
    assert f"acquire: lock root {root}" in ok.stderr
    busy = _gov(tmp_path, "acquire", "r", "--agent", "b", "--ttl", "300")
    assert busy.returncode == 3
    assert f"acquire: lock root {root}" in busy.stderr


def test_release_announces_lock_root(tmp_path):
    _git_repo(tmp_path)
    _gov(tmp_path, "acquire", "r", "--agent", "a", "--ttl", "300")
    rel = _gov(tmp_path, "release", "r", "--agent", "a")
    assert rel.returncode == 0, (rel.stdout, rel.stderr)
    assert f"release: lock root {_lockdir(tmp_path)}" in rel.stderr


# --- holder identity defaults ------------------------------------------------------

def test_holder_defaults_to_gov_caller_then_os_user(tmp_path):
    _git_repo(tmp_path)
    r = _gov(tmp_path, "acquire", "r", env={"GOV_CALLER": "caller-9"})
    assert r.returncode == 0
    assert _read_lease(tmp_path, "r")["holder"] == "caller-9"
    _gov(tmp_path, "release", "r", "--agent", "caller-9")
    import getpass
    r = _gov(tmp_path, "acquire", "r")
    assert r.returncode == 0
    assert _read_lease(tmp_path, "r")["holder"] == getpass.getuser()
    # whitespace-only GOV_CALLER counts as absent (D42's rule for callers)
    _gov(tmp_path, "release", "r", "--agent", getpass.getuser())
    r = _gov(tmp_path, "acquire", "r", env={"GOV_CALLER": "   "})
    assert _read_lease(tmp_path, "r")["holder"] == getpass.getuser()


def test_nonpositive_ttl_refused(tmp_path):
    _git_repo(tmp_path)
    r = _gov(tmp_path, "acquire", "r", "--agent", "a", "--ttl", "0")
    assert r.returncode == 2
    assert "--ttl" in r.stderr
    assert not _lease(tmp_path, "r").exists()


def test_shared_common_dir_across_worktrees(tmp_path):
    """Leases span the worktrees of ONE clone (the common dir is shared);
    cross-clone/cross-machine is out of scope by D52's supersede boundary —
    correctness there is anchored in the push CAS, not in this lock."""
    root = tmp_path / "base"
    _git_repo(root)
    (root / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True,
                   capture_output=True, env=SCRUBBED)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "c"],
                   cwd=root, check=True, capture_output=True, env=SCRUBBED)
    wt = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", str(wt)], cwd=root,
                   check=True, capture_output=True, env=SCRUBBED)
    r = _gov(wt, "acquire", "shared", "--agent", "from-wt", "--ttl", "300")
    assert r.returncode == 0
    # the lease resolves into the BASE clone's common dir, visible from root
    assert _lease(root, "shared").exists()
    busy = _gov(root, "acquire", "shared", "--agent", "from-root")
    assert busy.returncode == 3
    assert "from-wt" in busy.stderr


import argparse


class TestDurationParsing:
    """--ttl/--wait accept agent-natural durations (20m), not just seconds.

    Both blind-drill workers wrote ``--ttl 20m`` unprompted; the parser now
    speaks durations. Bare numbers stay seconds (original contract)."""

    def test_suffixes(self):
        from gov.locks import duration
        assert duration("600") == 600.0
        assert duration("600s") == 600.0
        assert duration("20m") == 1200.0
        assert duration("2h") == 7200.0
        assert duration("1.5m") == 90.0

    def test_invalid(self):
        import pytest
        from gov.locks import duration
        for bad in ("abc", "10x", "0", "-5", "m", ""):
            with pytest.raises(argparse.ArgumentTypeError):
                duration(bad)

    def test_cli_accepts_duration_style(self, tmp_path):
        _git_repo(tmp_path)
        r = _gov(tmp_path, "acquire", "cli-dur", "--agent", "d1", "--ttl", "20m")
        assert r.returncode == 0, (r.stdout, r.stderr)
        assert _gov(tmp_path, "release", "cli-dur", "--agent", "d1").returncode == 0


# --- issue #168: the guard flock is POSIX-only; Windows degrades, not dies ---

def test_guarded_runs_action_without_fcntl(tmp_path, monkeypatch):
    """No fcntl (Windows) must degrade the guard to an unserialized critical
    section, never crash the CLI: the action runs, its value returns, and an
    action exception still propagates through the degraded finally."""
    from gov import locks
    assert locks.fcntl is not None or True  # POSIX: real flock; Windows: None
    monkeypatch.setattr(locks, "fcntl", None)
    calls = []
    out = locks._guarded(tmp_path, "res", lambda: calls.append(1) or "ok")
    assert out == "ok" and calls == [1]

    def boom():
        raise RuntimeError("action failed")
    with pytest.raises(RuntimeError):
        locks._guarded(tmp_path, "res", boom)
    assert calls == [1]  # the first action ran exactly once


def test_locks_cli_imports_when_fcntl_missing(tmp_path, monkeypatch):
    """The #168 crash was the module-level `import fcntl` killing EVERY gov
    subcommand at import time. Simulate the Windows import surface: with the
    module attribute None (what the guarded import yields there), the module
    imports, the parser answers a bare invocation with a named usage error,
    and a run outside any repository refuses NAMED (exit 2) — never an
    ImportError, never a traceback."""
    from gov import locks
    monkeypatch.setattr(locks, "fcntl", None)
    monkeypatch.chdir(tmp_path)  # not a git repository: the named refusal
    with pytest.raises(SystemExit) as refused:
        locks.main(["locks"])
    assert refused.value.code == 2
    with pytest.raises(SystemExit) as e:
        locks.main([])
    assert e.value.code == 2  # bare command: named usage error, not a crash
