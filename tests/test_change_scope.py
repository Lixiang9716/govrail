import json
import subprocess

import pytest

from gov import change_scope


def _git_repo(root):
    for cmd in (
        ["git", "init", "-q", "."],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(cmd, cwd=root, check=True)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "init"],
        cwd=root, check=True,
    )


def test_suggests_from_gates_paths(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps({
        "gates": [
            {"id": "docs-gate", "command": ["true"], "paths": ["docs/**"]},
            {"id": "code-gate", "command": ["true"], "paths": ["src/**"]},
        ]
    }), encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x\n", encoding="utf-8")
    assert change_scope.main(["--base", "HEAD"]) == 0
    out = capsys.readouterr().out
    assert "gates.json paths" in out
    assert "docs-gate" in out
    assert "code-gate" not in out
    assert "gov run --base HEAD" in out


def test_note_hint_when_code_changed_without_note(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps({"gates": []}), encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    assert change_scope.main(["--base", "HEAD"]) == 0
    assert "no Agent Note in this change" in capsys.readouterr().out


def test_no_ghost_gate_in_fallback(tmp_path, monkeypatch, capsys):
    """The fallback suggestion list must not name gates that do not exist."""
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")  # no gates.json at all
    assert change_scope.main(["--base", "HEAD"]) == 0
    out = capsys.readouterr().out
    assert "links" not in out


def test_surfaces_config_scopes_suggestion(tmp_path, monkeypatch, capsys):
    """D25 wish 4: eval/** → experiments → [source-limits] only."""
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    gov = tmp_path / ".gov"
    gov.mkdir()
    (gov / "surfaces.json").write_text(json.dumps({
        "eval/**": {"surface": "experiments", "gates": ["source-limits"]},
    }), encoding="utf-8")
    (tmp_path / "gates.json").write_text(json.dumps({"gates": []}), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)  # commit the
    subprocess.run(  # config itself, so the diff below is eval-only
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "config"],
        cwd=tmp_path, check=True,
    )
    (tmp_path / "eval").mkdir()
    (tmp_path / "eval" / "run.py").write_text("x = 1\n", encoding="utf-8")
    assert change_scope.main(["--base", "HEAD"]) == 0
    out = capsys.readouterr().out
    assert "experiments: 1 file(s)" in out
    assert "source-limits" in out
    assert "self-test" not in out  # configured matches replace the fallback
    assert ".gov/surfaces.json" in out


def test_surfaces_config_malformed_fails_loud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gov = tmp_path / ".gov"
    gov.mkdir()
    (gov / "surfaces.json").write_text(json.dumps({"x/**": {"surface": "s"}}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        change_scope.main(["--base", "HEAD"])
    assert exc.value.code == 2


def test_note_hint_matches_gate_exemptions(tmp_path, monkeypatch, capsys):
    """#149: the reminder gates the same surface as verify-note-presence."""
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps({"gates": []}), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "cfg"],
        cwd=tmp_path, check=True,
    )
    tasks = tmp_path / ".gov" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "T-0001-x.json").write_text("{}\n", encoding="utf-8")  # bookkeeping alone: no hint
    assert change_scope.main(["--base", "HEAD"]) == 0
    assert "no Agent Note" not in capsys.readouterr().out
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / ".gov" / "manifest.json").write_text(
        json.dumps({"note_presence_exempt": ["app.py"]}), encoding="utf-8")
    subprocess.run(["git", "add", ".gov/manifest.json"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "exempt"],
        cwd=tmp_path, check=True,
    )
    assert change_scope.main(["--base", "HEAD"]) == 0
    assert "no Agent Note" not in capsys.readouterr().out  # declared exempt
    (tmp_path / ".gov" / "manifest.json").write_text(json.dumps({}), encoding="utf-8")
    subprocess.run(["git", "add", ".gov/manifest.json"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "bare"],
        cwd=tmp_path, check=True,
    )
    assert change_scope.main(["--base", "HEAD"]) == 0
    assert "no Agent Note" in capsys.readouterr().out  # no exemption: warn


def test_note_hint_ill_shaped_manifest_fails_loud(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps({"gates": []}), encoding="utf-8")
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    gov = tmp_path / ".gov"
    gov.mkdir()
    (gov / "manifest.json").write_text(
        json.dumps({"note_presence_exempt": "app.py"}), encoding="utf-8")
    assert change_scope.main(["--base", "HEAD"]) == 2
    assert "note_presence_exempt" in capsys.readouterr().err
