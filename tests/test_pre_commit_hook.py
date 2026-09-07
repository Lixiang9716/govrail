"""The optional pre-commit hook (#110): cheap content gates at commit time.

Acceptance from the issue: with the hook installed, `git commit` of a
pair whose sidecar is stale fails naming the scoped fix command; repos
without the flag see zero behavior change (the commit stage stays free —
pre-push owns the gate DAG).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from gov import cli

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env(root: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    # Deterministic hook resolution (the hook honors GOV_BIN first). The
    # hook runs under the shell git provides, so the interpreter path is
    # given with forward slashes — backslashes would be eaten as escapes
    # in unquoted shell context (Windows/git-bash, #168).
    env["GOV_BIN"] = f"{Path(sys.executable).as_posix()} -m gov"
    return env


def _git_repo(root: Path) -> None:
    env = _env(root)
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True, env=env)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "init"],
                   cwd=root, check=True, env=env)


def _gov(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "gov", *args],
                          cwd=root, capture_output=True, text=True, env=_env(root))


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args],
                          cwd=root, capture_output=True, text=True, env=_env(root))


def _baseline_pair(root: Path) -> None:
    """Create docs/a.md + docs/a.zh.md, confirm the pair, commit it."""
    docs = root / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("hello\n", encoding="utf-8")
    (docs / "a.zh.md").write_text("nihao\n", encoding="utf-8")
    r = _gov(root, "verify-pairing", "--write", "docs/a.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _git(root, "add", "-A").returncode == 0
    r = _git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "baseline")
    assert r.returncode == 0, r.stdout + r.stderr


def test_init_pre_commit_installs_both_hooks(tmp_path):
    _git_repo(tmp_path)
    assert cli.init(tmp_path, hooks=True, pre_commit=True) == 0
    for d in (tmp_path / ".git" / "hooks", tmp_path / ".gov" / "hooks"):
        for name in ("pre-push", "pre-commit"):
            assert (d / name).is_file(), f"{d/name} missing"
            assert os.access(d / name, os.X_OK), f"{d/name} not executable"
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gitHooks"] == ["pre-push", "pre-commit"]


def test_lone_pre_commit_flag_fails_loud(tmp_path):
    """--pre-commit rides with --hooks; alone it must abort (rule 5)."""
    _git_repo(tmp_path)
    r = _gov(tmp_path, "init", "--pre-commit")
    assert r.returncode == 2
    assert "alongside --hooks" in r.stderr
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()


def test_uninstall_removes_both_hooks(tmp_path):
    _git_repo(tmp_path)
    assert cli.init(tmp_path, hooks=True, pre_commit=True) == 0
    assert cli.uninstall(tmp_path) == 0
    for name in ("pre-push", "pre-commit"):
        assert not (tmp_path / ".git" / "hooks" / name).exists()


def test_without_flag_commit_stage_unchanged(tmp_path):
    """Acceptance: no flag, no commit-stage gate — drift commits fine."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path, hooks=True) == 0
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    _baseline_pair(tmp_path)
    (tmp_path / "docs" / "a.md").write_text("hello v2\n", encoding="utf-8")
    assert _git(tmp_path, "add", "docs/a.md").returncode == 0
    r = _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "drift")
    assert r.returncode == 0, r.stdout + r.stderr  # pre-push model unchanged


def test_commit_of_stale_pair_fails_naming_scoped_fix(tmp_path):
    """Acceptance: with the hook, the drift commit is blocked at `git
    commit` with the scoped fix command inline (#110)."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path, hooks=True, pre_commit=True) == 0
    _baseline_pair(tmp_path)
    (tmp_path / "docs" / "a.md").write_text("hello v2\n", encoding="utf-8")
    assert _git(tmp_path, "add", "docs/a.md").returncode == 0
    r = _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "drift")
    assert r.returncode != 0, "a stale sidecar committed without complaint"
    out = r.stdout + r.stderr
    assert "gov verify-pairing --write docs/a.md" in out, out
    # The scoped fix + re-stage + commit now lands (the issue's workflow).
    assert _gov(tmp_path, "verify-pairing", "--write", "docs/a.md").returncode == 0
    assert _git(tmp_path, "add", "-A").returncode == 0
    r = _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "drift")
    assert r.returncode == 0, r.stdout + r.stderr


def test_commit_with_markers_blocked_by_hook(tmp_path):
    """The hook's second gate: staged conflict markers block the commit."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path, hooks=True, pre_commit=True) == 0
    (tmp_path / "doc.md").write_text(
        "intro\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n", encoding="utf-8")
    assert _git(tmp_path, "add", "doc.md").returncode == 0
    r = _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "markers")
    assert r.returncode != 0
    assert "doc.md:2" in r.stdout + r.stderr


def test_doctor_sound_with_pre_commit_installed(tmp_path, monkeypatch, capsys):
    """Acceptance: with the hook installed, doctor stays green on hooks."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path, hooks=True, pre_commit=True) == 0
    monkeypatch.chdir(tmp_path)
    from gov import doctor
    doctor.main([])
    out = capsys.readouterr().out
    assert "ok: .gov/hooks/pre-commit is executable" in out


def test_staged_check_quiet_on_unrelated_index(tmp_path):
    """--staged passes when nothing paired is staged (#110's cheap gate)."""
    _git_repo(tmp_path)
    (tmp_path / "code.py").write_text("x = 1\n", encoding="utf-8")
    assert _git(tmp_path, "add", "code.py").returncode == 0
    r = _gov(tmp_path, "verify-pairing", "--staged")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "no staged file belongs to a pair" in r.stdout


def test_staged_check_catches_counterpart_side(tmp_path):
    """Editing the .zh.md side alone is the same drift (#110's evidence)."""
    _git_repo(tmp_path)
    _baseline_pair(tmp_path)
    (tmp_path / "docs" / "a.zh.md").write_text("nihao v2\n", encoding="utf-8")
    assert _git(tmp_path, "add", "docs/a.zh.md").returncode == 0
    r = _gov(tmp_path, "verify-pairing", "--staged")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "gov verify-pairing --write docs/a.md" in r.stdout


def test_staged_check_green_when_sidecar_also_staged(tmp_path):
    """Pair + refreshed sidecar staged together: the commit must pass."""
    _git_repo(tmp_path)
    _baseline_pair(tmp_path)
    (tmp_path / "docs" / "a.md").write_text("hello v2\n", encoding="utf-8")
    (tmp_path / "docs" / "a.zh.md").write_text("nihao v2\n", encoding="utf-8")
    assert _gov(tmp_path, "verify-pairing", "--write", "docs/a.md").returncode == 0
    assert _git(tmp_path, "add", "-A").returncode == 0
    r = _gov(tmp_path, "verify-pairing", "--staged")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 staged pair(s) ok" in r.stdout
