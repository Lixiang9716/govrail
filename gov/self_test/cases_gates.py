"""gate-DAG rejection cases: config schema, selection, execution, receipts-adjacent runner behavior.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ._harness import (
    HERE,
    _case,
    _classify_tool_failure,
    _fail_cmd,
    _fixture_env,
    _git_repo,
    _pass_cmd,
    _probe_always_fails,
    _probe_env_only_failure,
    _run,
    case,
)




@case
def test_gates_rejects_duplicate_id() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": ["true"]},
                        {"id": "a", "command": ["true"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "duplicate gate ids must fail loud")



@case
def test_gates_rejects_cycle() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": ["true"], "needs": ["b"]},
                        {"id": "b", "command": ["true"], "needs": ["a"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "a needs cycle must fail loud")



@case
def test_gates_rejects_unknown_needs() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {"gates": [{"id": "a", "command": ["true"], "needs": ["ghost"]}]}
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "an unknown needs reference must fail loud")



@case
def test_gates_skips_transitively() -> None:
    """A gate whose need was skipped must itself skip, never pass."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "A", "command": _pass_cmd(), "needs": ["B"]},
                        {"id": "B", "command": _pass_cmd(), "needs": ["C"]},
                        {"id": "C", "command": _fail_cmd()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 1, "a blocking failure must exit 1"
        assert "SKIP B" in result.stdout, "B must be skipped when C fails"
        assert "SKIP A" in result.stdout, "A must be skipped when B is skipped"
        assert "PASS A" not in result.stdout, "A must never pass through a skipped need"



@case
def test_gates_rejects_non_object_gate() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(json.dumps({"gates": [None]}), encoding="utf-8")
        _case("gates.py", root, 2, "a null gate must be a config error, not a crash")



@case
def test_gates_default_mode_scopes_run() -> None:
    """defaultMode must scope the no-flag run; gates outside it never run."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "modes": {"all": ["a"], "also": ["b"]},
                    "defaultMode": "all",
                    "gates": [
                        {"id": "a", "command": _pass_cmd()},
                        {"id": "b", "command": _fail_cmd()},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0, "a gate outside the default mode must not run"
        assert "PASS a" in result.stdout
        assert "FAIL b" not in result.stdout



@case
def test_gates_rejects_unknown_default_mode() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "modes": {"all": ["a"]},
                    "defaultMode": "ghost",
                    "gates": [{"id": "a", "command": ["true"]}],
                }
            ),
            encoding="utf-8",
        )
        _case("gates.py", root, 2, "a defaultMode naming no known mode must fail loud")



@case
def test_gates_disabled_gate_never_runs() -> None:
    """enabled:false parks a gate visibly outside every run (P0 defect 1)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": _pass_cmd()},
                        {"id": "b", "command": _fail_cmd(), "enabled": False},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0, "a disabled gate must not affect the run"
        assert "DISABLED b" in result.stdout
        assert "FAIL b" not in result.stdout



@case
def test_gates_advisory_failure_reports_without_blocking() -> None:
    """allowFailure must report the failure output yet keep exit code 0."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "a", "command": _fail_cmd(), "allowFailure": True},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0, "an advisory gate must never block"
        assert "FAIL a" in result.stdout
        assert "advisory" in result.stdout, "an advisory failure must be visible"



@case
def test_run_base_scopes_gates_by_paths() -> None:
    """--base must select gates by paths; out-of-scope gates never run."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        # docs-gate would PASS, code-gate would FAIL — only the in-scope one runs.
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "docs-gate", "command": _pass_cmd(), "paths": ["docs/**"]},
                        {"id": "code-gate", "command": _fail_cmd(), "paths": ["src/**"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "docs").mkdir()
        (root / "docs" / "a.md").write_text("x\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(HERE / "gates.py"), "--base", "HEAD"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 0, (
            "the failing gate is out of scope; the run must be green\n"
            f"{result.stdout}\n{result.stderr}"
        )
        assert "PASS docs-gate" in result.stdout
        assert "out of scope: code-gate" in result.stdout
        assert "FAIL code-gate" not in result.stdout



@case
def test_run_failure_summary_and_gate_flag() -> None:
    """A blocking failure must end with a summary and a single-gate rerun hint."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "boom", "command": [sys.executable, "-c",
                                                   "import sys; print('boom', file=sys.stderr); raise SystemExit(3)"]},
                        {"id": "ok", "command": _pass_cmd()},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 1
        assert "--- summary: 1 blocking failure(s) ---" in result.stdout
        assert "boom: boom" in result.stdout
        # #109: the failure line itself names the per-gate rerun command.
        assert "rerun: gov run --gate boom" in result.stdout
        single = subprocess.run(
            [sys.executable, str(HERE / "gates.py"), "--gate", "ok"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert single.returncode == 0
        assert "PASS boom" not in single.stdout



@case
def test_passing_gate_output_stays_visible() -> None:
    """A pass that printed a warning must not be silenced (P1-2)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "warny", "command": [sys.executable, "-c",
                                                    "print('heads up')"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 0
        assert "passed with output" in result.stdout
        assert "heads up" in result.stdout



@case
def test_gates_rejects_gate_in_no_mode() -> None:
    """D24: a gate parked by mode omission silently never runs — fail loud."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "modes": {"all": ["a"]},
                    "gates": [
                        {"id": "a", "command": ["true"]},
                        {"id": "stranded", "command": ["true"]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 2, "an enabled gate in no mode is a config error"
        assert "stranded" in result.stderr



@case
def test_gates_rejects_unknown_keys() -> None:
    """D29: "enable": false is a typo'd park that silently parks nothing."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "gates.json").write_text(
            json.dumps({"gates": [{"id": "a", "command": ["true"],
                                   "enable": False}]}),
            encoding="utf-8",
        )
        result = _run("gates.py", root)
        assert result.returncode == 2, "an unknown gate key must abort loud"
        assert "unknown key(s): enable" in result.stderr



@case
def test_run_merge_rejects_text_conflict() -> None:
    """D51: `gov run --merge` must catch a textual merge conflict before
    landing — the step fails loud, names the branch, the already-merged
    set, and the conflicted file, and keeps the scratch scene. A real,
    subprocess-reproducible failure (no fault injection, #24's lesson)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "host"
        root.mkdir()
        env = _fixture_env(root)

        def git(*argv: str, check: bool = True):
            return subprocess.run(["git", *argv], cwd=root, check=check,
                                  capture_output=True, text=True, env=env,
                                  encoding="utf-8", errors="replace")

        git("init", "-q", "-b", "main", ".")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (root / "gates.json").write_text(
            json.dumps({"gates": [{"id": "ok", "command": _pass_cmd()}]}),
            encoding="utf-8")
        (root / ".gitignore").write_text(".gov/history/\n", encoding="utf-8")
        (root / "f.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-qm", "base")
        for name, first in (("a", "A1"), ("b", "B1")):
            git("checkout", "-q", "-b", name)
            (root / "f.txt").write_text(f"{first}\ntwo\nthree\n",
                                        encoding="utf-8")
            git("commit", "-qam", name)
            git("checkout", "-q", "main")
        result = _run("gates.py", root,
                      extra=["--merge", "a", "b", "--base", "main"])
        assert result.returncode == 1, (
            "a textual conflict must fail the preflight\n"
            f"{result.stdout}\n{result.stderr}")
        assert ("branch 2 (b) conflicts with already-merged set (a)"
                in result.stdout), result.stdout
        assert "f.txt" in result.stdout, "the conflicted file must be named"
        kept = [l for l in result.stdout.splitlines()
                if "kept for inspection: " in l]
        assert kept, "the scratch scene must be kept for inspection"
        scene = Path(kept[0].split("kept for inspection: ", 1)[1].strip())
        assert scene.is_dir() and "<<<<<<<" in (scene / "f.txt").read_text(
            encoding="utf-8"), "the live conflict must be inspectable"
        # the scene is kept BY DESIGN; this case tidies it up
        subprocess.run(["git", "-C", str(root), "worktree", "remove",
                        "--force", str(scene)], capture_output=True)
        shutil.rmtree(scene, ignore_errors=True)
        subprocess.run(["git", "-C", str(root), "worktree", "prune"],
                       capture_output=True)



@case
def test_failure_classifier_labels_tool_vs_environment() -> None:
    """#139/D47: a FAIL's label is earned from evidence, not guessed.

    A probe that genuinely breaks only under a polluted import path must
    replay green (environment-suspect); one that breaks everywhere must
    replay red (tool-defect). The probes double as ``--case`` fixtures.
    """
    # First prove the env-only probe's failure is real: under the shadow
    # path it reproduces; this is the #138 shape (a promoted site dir).
    # The old form caught its own sentinel AssertionError in the same
    # except that judged the probe's — the "proof" was vacuously true on
    # the success path and inverted on the failure path. A distinct
    # sentinel type makes each branch honest.
    class _ProbeDidNotReproduce(Exception):
        pass

    saved = os.environ.get("PYTHONPATH")
    try:
        os.environ["PYTHONPATH"] = "/tmp/gov-selftest-shadow-probe/x"
        try:
            _probe_env_only_failure()
        except Exception:  # noqa: BLE001 — any failure IS the reproduction
            pass
        else:
            raise _ProbeDidNotReproduce(
                "the env-only probe did NOT fail under a shadowed "
                "PYTHONPATH — its classification as environment-suspect "
                "is vacuous, the probe is broken (rule 6)")
    except _ProbeDidNotReproduce:
        raise
    finally:
        if saved is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = saved
    env_lines = _classify_tool_failure(_probe_env_only_failure)
    assert any("environment-suspect" in l for l in env_lines), env_lines
    tool_lines = _classify_tool_failure(_probe_always_fails)
    assert any("tool-defect" in l for l in tool_lines), tool_lines
