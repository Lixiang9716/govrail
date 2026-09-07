import json
import os
import subprocess
import sys
from pathlib import Path

from gov import doctor

# Portable gate command (#168): the Unix `true` does not exist on
# Windows — "a command that exits 0" must not depend on PATH.
PASS = [sys.executable, "-c", "pass"]


def _git_repo(root):
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True)


def test_healthy_environment(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": ["a"]}, "gates": [{"id": "a", "command": PASS}]}))
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\n")
    (hooks / "pre-push").chmod(0o755)
    assert doctor.main([]) in (0, 1)  # gov-on-PATH depends on the host
    out = capsys.readouterr().out
    assert "ok: gates.json passes the strict schema" in out
    import re
    assert re.search(r"ok: .*(/|\\)hooks(/|\\)pre-push is executable", out)
    assert "ok: python" in out


def test_bad_gates_schema_is_a_problem(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"gates": [{"id": "a", "command": PASS, "enable": False}]}))
    assert doctor.main([]) == 1
    out = capsys.readouterr().out
    assert "problem: gates.json:" in out
    assert "unknown key(s): enable" in out


def test_non_executable_hook_is_a_problem(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\n")  # no +x
    assert doctor.main([]) == 1
    assert "not executable" in capsys.readouterr().out


def test_missing_gate_command_is_a_problem(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": ["x", "y"]},
         "gates": [{"id": "x", "command": ["no-such-bin-xyz"]},
                   {"id": "y", "command": PASS}]}))
    assert doctor.main([]) == 1
    out = capsys.readouterr().out
    assert "gate 'x': command 'no-such-bin-xyz' not found on PATH" in out
    assert "ok: gate 'y' command resolves" in out


def test_unadopted_shipped_gates_are_named(tmp_path, monkeypatch, capsys):
    """#147: a gate this govrail version ships but the project never wired
    is invisible to every run — doctor names it (a note: adoption is
    deliberate), with the mechanical adoption path for template gates and
    the tool to wire for the hand ones (verify-decisions sat unadopted in
    the issue's report, so the one check that would have named the
    collision never ran)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": ["a"]}, "gates": [{"id": "a", "command": PASS}]}))
    doctor.main([])  # exit code depends on the host (gov-on-PATH)
    out = capsys.readouterr().out
    assert "note: shipped gate(s) not adopted here" in out
    assert "conflict-markers" in out  # a template gate this version ships
    assert "gov init --adopt-new gates.json lands them" in out
    # #147's motivating case: the hand-adoption tools are named too
    assert "`gov verify-decisions`, decisions table guard" in out
    assert "wire one into a mode by hand" in out


def test_adopted_by_command_shape_counts(tmp_path, monkeypatch, capsys):
    """A gate wired under a project-local id still counts as adopted when
    its command runs the shipped tool (#147: identity is the tool, not
    the id govrail's own repo happens to use)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": ["spine"]},
         "gates": [{"id": "spine",
                    "command": ["gov", "verify-decisions"]}]}))
    doctor.main([])
    out = capsys.readouterr().out
    assert "`gov verify-decisions`" not in out  # not named as missing


def test_all_shipped_gates_adopted_is_ok(tmp_path, monkeypatch, capsys):
    """Every template gate id plus the hand tools (one deliberately
    parked via enabled:false — parking is adoption, the loud mechanism)
    and the check goes quiet-ok."""
    monkeypatch.chdir(tmp_path)
    gates_ = [{"id": i, "command": PASS} for i in
              ("self-test", "notes", "pairing", "note-presence",
               "conflict-markers", "archive", "task", "rubric")]
    gates_.append({"id": "decisions",
                   "command": ["gov", "verify-decisions"]})
    gates_.append({"id": "doc-sync", "command": PASS,
                   "enabled": False})  # parked = a visible choice
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": [g["id"] for g in gates_ if g.get("enabled", True)]},
         "gates": gates_}))
    doctor.main([])
    out = capsys.readouterr().out
    assert "ok: every gate this govrail version ships is wired" in out
    assert "not adopted" not in out


def test_json_mode_pure_stdout(tmp_path, monkeypatch, capsys):
    """#119: doctor --json — stdout is exactly one JSON object; the human
    report moves to stderr."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"modes": {"all": ["x", "y"]},
         "gates": [{"id": "x", "command": ["no-such-bin-xyz"]},
                   {"id": "y", "command": PASS}]}))
    import json as _json
    assert doctor.main(["--json"]) == 1
    captured = capsys.readouterr()
    payload = _json.loads(captured.out)  # exactly one JSON value
    assert payload["status"] == "problems"
    assert any(c["name"] == "gate:x" and c["state"] == "problem"
               for c in payload["checks"])
    assert "gate:x" in payload["problems"]
    assert all(c["state"] in ("ok", "note", "problem") for c in payload["checks"])
    assert "gov doctor" in captured.err  # the human report moved to stderr
    assert payload["problems"][0] == "gate:x"


_SHADOW_ARGPARSE = (
    "#138: a faithful-enough stand-in for the py2-era backport (PyPI\n"
    "# argparse 1.4.0): real stdlib argparse with pre-3.7 add_subparsers\n"
    "# restored — `required` is refused.\n"
    "import importlib.util, os, sysconfig\n"
    "_dir = os.path.dirname(os.path.abspath(__file__))\n"
    "_p = os.path.join(sysconfig.get_paths()['stdlib'], 'argparse.py')\n"
    "_s = importlib.util.spec_from_file_location('_stdlib_argparse', _p)\n"
    "_m = importlib.util.module_from_spec(_s)\n"
    "_s.loader.exec_module(_m)\n"
    "globals().update(vars(_m))\n"
    "__file__ = os.path.join(_dir, 'argparse.py')\n"
    "__name__ = 'argparse'\n"
    "_real = _m.ArgumentParser.add_subparsers\n"
    "def _old(self, **kw):\n"
    "    if 'required' in kw:\n"
    "        raise TypeError(\"_SubParsersAction.__init__() got an \"\n"
    "                        \"unexpected keyword argument 'required'\")\n"
    "    return _real(self, **kw)\n"
    "ArgumentParser.add_subparsers = _old\n")


def test_argparse_backport_shadow_is_named(tmp_path):
    """#138: an argparse backport beside an installed gov shadows the
    stdlib when PYTHONPATH promotes that dir — doctor must name it as a
    problem with the fix spelled out, and still run (it never needed the
    modern argparse surface itself). The clean run reports ok."""
    repo = Path(__file__).resolve().parent.parent
    clean = subprocess.run(
        [sys.executable, "-m", "gov", "doctor"], cwd=tmp_path,
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(repo)})
    assert "argparse resolves to the stdlib" in clean.stdout

    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "argparse.py").write_text(_SHADOW_ARGPARSE, encoding="utf-8")
    env = {**os.environ,
           "PYTHONPATH": os.pathsep.join([str(shadow), str(repo)])}
    r = subprocess.run(
        [sys.executable, "-m", "gov", "doctor"], cwd=tmp_path,
        capture_output=True, text=True, env=env)
    assert r.returncode == 1, r.stdout
    assert "argparse resolves to" in r.stdout
    assert "pip uninstall argparse" in r.stdout
