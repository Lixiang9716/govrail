"""#24/D33: the self-test must never mutate the host repository."""
import hashlib
import os
import subprocess
import sys
from pathlib import Path


def _main_repo_with_worktree(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "real@x"],
                ["git", "config", "user.name", "real"]):
        subprocess.run(cmd, cwd=main, check=True)
    (main / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=main, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "base"],
                   cwd=main, check=True)
    wt = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", str(wt)], cwd=main, check=True)
    return main, wt


def _fingerprint(repo):
    config = hashlib.sha256((repo / ".git" / "config").read_bytes()).hexdigest()
    refs = subprocess.run(["git", "show-ref"], cwd=repo,
                          capture_output=True, text=True).stdout
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                            capture_output=True, text=True).stdout
    heads = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True).stdout
    return config, hashlib.sha256(refs.encode()).hexdigest(), status, heads


def test_full_selftest_from_worktree_leaves_host_identical(tmp_path):
    main, wt = _main_repo_with_worktree(tmp_path)
    before = _fingerprint(main)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)}
    result = subprocess.run(
        [sys.executable, "-m", "gov", "self-test"],
        cwd=wt, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _fingerprint(main) == before  # byte-identical host (#24 acceptance)


def test_full_selftest_from_worktree_under_hostile_env(tmp_path):
    """Incident-(a) shape: leaked GIT_DIR/GIT_INDEX_FILE during the run."""
    main, wt = _main_repo_with_worktree(tmp_path)
    before = _fingerprint(main)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent),
           "GIT_DIR": str(main / ".git"),
           "GIT_INDEX_FILE": str(main / ".git" / "index"),
           "GIT_WORK_TREE": str(main)}
    result = subprocess.run(
        [sys.executable, "-m", "gov", "self-test"],
        cwd=wt, env=env, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "scrubbed repository-resolving" in result.stdout
    assert _fingerprint(main) == before


def test_toplevel_guard_aborts_loud_on_escape(tmp_path, monkeypatch):
    """If git resolves anywhere but the scratch, the fixture refuses."""
    from gov import self_test as st
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if cmd[:3] == ["git", "rev-parse", "--show-toplevel"]:
            class R:
                returncode = 0
                stdout = "/somewhere/else/repo\n"
                stderr = ""
            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(st.subprocess, "run", fake_run)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    try:
        st._git_repo(scratch)
        raise SystemExit("guard did not fire")
    except AssertionError as e:
        assert "escaped" in str(e) and "refusing" in str(e)
