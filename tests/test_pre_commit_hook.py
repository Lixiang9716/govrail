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

from gov import plane

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
                          cwd=root, capture_output=True, text=True, env=_env(root), encoding="utf-8", errors="replace")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args],
                          cwd=root, capture_output=True, text=True, env=_env(root), encoding="utf-8", errors="replace")


def _baseline_pair(root: Path) -> None:
    """Create docs/a.md + docs/a.zh.md, confirm the pair, commit it."""
    docs = root / "docs"
    docs.mkdir(exist_ok=True)  # init seeds docs/ (decisions log)
    (docs / "a.md").write_text("hello\n", encoding="utf-8")
    (docs / "a.zh.md").write_text("nihao\n", encoding="utf-8")
    r = _gov(root, "verify-pairing", "--write", "docs/a.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _git(root, "add", "-A").returncode == 0
    r = _git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "baseline")
    assert r.returncode == 0, r.stdout + r.stderr


def test_init_pre_commit_installs_both_hooks(tmp_path):
    _git_repo(tmp_path)
    assert plane.init(tmp_path, hooks=True, pre_commit=True) == 0
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
    assert plane.init(tmp_path, hooks=True, pre_commit=True) == 0
    assert plane.uninstall(tmp_path) == 0
    for name in ("pre-push", "pre-commit"):
        assert not (tmp_path / ".git" / "hooks" / name).exists()


def test_without_flag_commit_stage_unchanged(tmp_path):
    """Acceptance: no flag, no commit-stage gate — drift commits fine."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path, hooks=True) == 0
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    _baseline_pair(tmp_path)
    (tmp_path / "docs" / "a.md").write_text("hello v2\n", encoding="utf-8")
    assert _git(tmp_path, "add", "docs/a.md").returncode == 0
    r = _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "drift")
    assert r.returncode == 0, r.stdout + r.stderr  # pre-push model unchanged


def test_commit_of_stale_pair_fails_naming_scoped_fix(tmp_path):
    """Acceptance (#110), under the hook's configured contract: pairing
    ships advisory (allowFailure), so the hook WARNS and lets the commit
    through until the repo flips it to blocking — the documented
    "remove allowFailure to enforce" step — after which the drift commit
    is blocked at `git commit` with the scoped fix inline."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path, hooks=True, pre_commit=True) == 0
    _baseline_pair(tmp_path)
    (tmp_path / "docs" / "a.md").write_text("hello v2\n", encoding="utf-8")
    assert _git(tmp_path, "add", "docs/a.md").returncode == 0
    # advisory: the drift is NAMED, the commit is not blocked (H5 fix —
    # the hook honors gates.json instead of hard-wiring `|| status=1`)
    r = _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "drift")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "verify_translation_pairing: 1 violation(s)" in r.stderr
    # flip to enforce (init's documented next step), redo the drift
    gates = tmp_path / "gates.json"
    cfg = gates.read_text(encoding="utf-8").replace('"allowFailure": true,\n', "")
    gates.write_text(cfg, encoding="utf-8")
    assert _gov(tmp_path, "verify-plane", "--write",
                           "--confirm-unattended", "--reason", "test").returncode == 0
    (tmp_path / "docs" / "a.md").write_text("hello v3\n", encoding="utf-8")
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
    assert plane.init(tmp_path, hooks=True, pre_commit=True) == 0
    (tmp_path / "doc.md").write_text(
        "intro\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n", encoding="utf-8")
    assert _git(tmp_path, "add", "doc.md").returncode == 0
    r = _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "markers")
    assert r.returncode != 0
    assert "doc.md:2" in r.stdout + r.stderr


def test_doctor_sound_with_pre_commit_installed(tmp_path, monkeypatch, capsys):
    """Acceptance: with the hook installed, doctor stays green on hooks."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path, hooks=True, pre_commit=True) == 0
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


# --- H-6: run_pre_commit verifies and parses ONE read of gates.json ---

def _staged_config() -> dict:
    return {"gates": [{"id": "ok", "command": [sys.executable, "-c", "pass"],
                        "stages": ["pre-commit"]}]}


def test_pre_commit_single_read_verify_then_parse(tmp_path, monkeypatch, capsys):
    """H-6: the seal is judged over the SAME bytes the parser consumes —
    violations() gets the read overlay and the file-reading load_config()
    is never called again (the old second disk read)."""
    (tmp_path / "gates.json").write_text(json.dumps(_staged_config()),
                                         encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from gov import gates as gates_mod
    from gov import hookcmd
    from gov import verify_plane as vp

    seen = {}

    def fake_violations(root=None, overlays=None):
        seen["overlays"] = overlays
        return []

    monkeypatch.setattr(vp, "violations", fake_violations)

    def no_reread(*a, **k):
        raise AssertionError(
            "load_config re-read gates.json after the seal check (TOCTOU)")

    monkeypatch.setattr(gates_mod, "load_config", no_reread)

    assert hookcmd.run_pre_commit() == 0
    overlays = seen["overlays"]
    assert overlays and "gates.json" in overlays
    assert json.loads(overlays["gates.json"]) == _staged_config()
    assert "1 staged gate(s) ok" in capsys.readouterr().out


def test_pre_commit_missing_gates_json_exits_2(tmp_path, monkeypatch, capsys):
    """H-6: the missing-config path keeps its exit-2 contract, named."""
    monkeypatch.chdir(tmp_path)
    from gov import hookcmd
    assert hookcmd.run_pre_commit() == 2
    assert "no gates.json" in capsys.readouterr().err


def test_pre_commit_tampered_config_refuses(tmp_path, monkeypatch, capsys):
    """H-6 end to end: bytes edited after sealing are caught because the
    seal is checked over the very bytes about to be parsed."""
    _git_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(_staged_config()),
                                         encoding="utf-8")
    from gov import hookcmd
    from gov import verify_plane as vp
    vp.baseline(tmp_path)  # seal the current plane state
    monkeypatch.chdir(tmp_path)
    # tamper AFTER the seal: disable the stage without re-baselining
    tampered = json.dumps({"gates": [{"id": "ok",
                                      "command": [sys.executable, "-c", "pass"]}]})
    (tmp_path / "gates.json").write_text(tampered, encoding="utf-8")
    assert hookcmd.run_pre_commit() == 1
    err = capsys.readouterr().err
    assert "REFUSED" in err and "differs from its seal" in err
