"""The pre-push hook's push-range parsing, against the hook TEMPLATE.

The round-9 template review found the deletion skip comparing
``$local_ref`` (a ref NAME — for deletions git sends the literal
``(delete)``) against the all-zero OID, so no deletion was ever
skipped: a pure ``git push origin :branch`` fell through to a full
gate run. These tests feed the hook the exact stdin lines git sends
(the wire format verified live: update, new branch, deletion, and a
mixed push) and watch a recording stub stand in for ``gov``.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from gov import cli, plane

HERE = Path(__file__).resolve().parent.parent
TEMPLATE = HERE / "gov" / "templates" / "pre-push"
ZERO = "0" * 40
SHA = "1234567890abcdef1234567890abcdef12345678"

# The hook is a POSIX sh script: Windows executes hooks through git's
# own sh, never as a Win32 process, so driving it directly from Python
# is a POSIX-shaped test. The parsing contract is covered by the POSIX
# CI jobs and the docker e2e cells.
pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX sh hook; Windows runs it via git's sh")


@pytest.fixture()
def hooked(tmp_path, monkeypatch):
    """A git repo with the hook installed and gov replaced by a stub
    that appends its argv to a log file."""
    import subprocess as sp

    sp.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    assert plane.init(tmp_path, hooks=True) == 0
    checkout = ("refs/heads/"
                + sp.run(["git", "symbolic-ref", "--short", "HEAD"],
                         cwd=tmp_path, check=True, capture_output=True,
                         text=True).stdout.strip())
    log = tmp_path / "gov-calls.log"
    stub = tmp_path / "gov-stub.sh"
    stub.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\nexit 0\n",
                    encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("GOV_BIN", str(stub))
    return tmp_path, log, checkout


def _push(hooked, stdin_lines):
    tmp_path = hooked[0]
    return subprocess.run(
        [str(tmp_path / ".git" / "hooks" / "pre-push"), "origin", "url"],
        input="\n".join(stdin_lines) + "\n", capture_output=True,
        text=True, encoding="utf-8", errors="replace", cwd=tmp_path,
        timeout=60, env={**os.environ, "PYTHONUTF8": "1"})


def _calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_deletion_push_runs_nothing(hooked):
    """git sends local_ref='(delete)' with the ZERO OID in local_sha —
    the wire format captured live from a real `git push origin :b`."""
    tmp_path, log, checkout = hooked
    r = _push(hooked, [f"(delete) {ZERO} refs/heads/b {SHA}"])
    assert r.returncode == 0, r.stderr
    assert _calls(log) == [], \
        "a pure deletion push must skip the gates entirely"


def test_mixed_push_deletion_does_not_pollute_the_base(hooked):
    """One update + one deletion is still ONE push range: scoped to the
    update's base, not blown up to the full matrix by the deletion."""
    tmp_path, log, checkout = hooked
    r = _push(hooked, [
        f"{checkout} {SHA} {checkout} {SHA}",
        f"(delete) {ZERO} refs/heads/side {SHA}2",
    ])
    assert r.returncode == 0, r.stderr
    assert _calls(log) == [f"run --base {SHA}"]


def test_pushing_a_non_checked_out_branch_forces_full(hooked):
    """W3: the worktree only represents the checked-out branch — an
    update to a DIFFERENT ref cannot be summarized by that diff and
    takes the full matrix."""
    tmp_path, log, checkout = hooked
    r = _push(hooked, [
        f"refs/heads/other {SHA} refs/heads/other {SHA}",
    ])
    assert r.returncode == 0, r.stderr
    assert _calls(log) == ["run"]


def test_new_branch_pushes_the_full_matrix(hooked):
    tmp_path, log, checkout = hooked
    r = _push(hooked, [f"refs/heads/main {SHA} refs/heads/main {ZERO}"])
    assert r.returncode == 0, r.stderr
    assert _calls(log) == ["run"]


def test_two_ranges_push_the_full_matrix(hooked):
    tmp_path, log, checkout = hooked
    r = _push(hooked, [
        f"refs/heads/a {SHA} refs/heads/a {SHA}",
        f"refs/heads/b {SHA} refs/heads/b {SHA}2",
    ])
    assert r.returncode == 0, r.stderr
    assert _calls(log) == ["run"]


def test_single_range_scopes_to_its_base(hooked):
    tmp_path, log, checkout = hooked
    r = _push(hooked, [f"{checkout} {SHA} {checkout} {SHA}"])
    assert r.returncode == 0, r.stderr
    assert _calls(log) == [f"run --base {SHA}"]


def test_real_git_deletion_push_is_relayed_verbatim(tmp_path, monkeypatch):
    """The wire-format anchor: run an actual deletion push through a
    recording hook and assert git really sends what the parser assumes.
    If git ever changes the format, this names it before the parser
    silently mis-scopes again."""
    import subprocess as sp

    remote = tmp_path / "remote.git"
    sp.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    sp.run(["git", "-C", str(remote),
            "config", "receive.denyDeleteCurrent", "ignore"], check=True)
    work = tmp_path / "work"
    sp.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    monkeypatch.chdir(work)
    sp.run(["git", "config", "user.email", "t@t"], check=True)
    sp.run(["git", "config", "user.name", "t"], check=True)
    (work / "f.txt").write_text("x\n", encoding="utf-8")
    sp.run(["git", "add", "-A"], check=True)
    sp.run(["git", "commit", "-qm", "one"], check=True)
    hook = work / ".git" / "hooks" / "pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        "while read -r lf ls rr rs; do\n"
        f"  echo \"$lf|$ls|$rr|$rs\" >> {tmp_path / 'wire.log'}\n"
        "done\nexit 0\n", encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    sp.run(["git", "push", "-q", "origin", "master"], check=True)
    sp.run(["git", "push", "origin", ":master"], check=True,
           capture_output=True)
    wire = (tmp_path / "wire.log").read_text(encoding="utf-8").splitlines()
    assert wire[-1].split("|")[0] == "(delete)", wire
    assert set(wire[-1].split("|")[1]) == {"0"}, \
        "deletion local oid must be all zeros"
