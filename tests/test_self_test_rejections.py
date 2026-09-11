import os
import subprocess
import sys
from pathlib import Path

import pytest

from gov import self_test as st

# The project family executes arbitrary scripts directly; a POSIX shebang
# script cannot run on Windows (WinError 193). Teaching self-test to run
# .sh cases through a host bash — or to report a named SKIP for
# OS-unrunnable cases — is the rule-6 semantics decision deferred in the
# #168 note; until then these tests pin the POSIX side only.
needs_posix_exec = pytest.mark.skipif(
    sys.platform == "win32",
    reason="project rejection cases are POSIX shebang scripts")


def _rejection(root, name, body, executable=True):
    d = root / ".gov" / "rejections"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    if executable:
        p.chmod(0o755)
    return p


@needs_posix_exec
def test_project_rejection_failure_names_the_case(tmp_path, monkeypatch, capsys):
    """A local rejection case that cannot prove rejection fails the self-test."""
    monkeypatch.chdir(tmp_path)
    _rejection(tmp_path, "case-broken.sh", "#!/bin/sh\nexit 1\n")
    assert st.main([]) == 1
    out = capsys.readouterr().out
    assert "FAIL .gov/rejections/case-broken.sh" in out
    assert "exit 1" in out


@needs_posix_exec
def test_project_rejection_pass_and_scope(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _rejection(tmp_path, "case-good.sh", "#!/bin/sh\nexit 0\n")
    (tmp_path / ".gov" / "rejections" / "README.md").write_text("docs\n", encoding="utf-8")
    assert st.main([]) == 0
    out = capsys.readouterr().out
    assert "PASS .gov/rejections/case-good.sh" in out
    assert f"tools {len(st.CASES)} + project 1" in out  # every tool case ran
    # scope filters families
    assert st.main(["--scope", "project"]) == 0
    assert "tools 29" not in capsys.readouterr().out
    assert st.main(["--scope", "tools"]) == 0
    assert "project 1" not in capsys.readouterr().out


@needs_posix_exec
def test_non_executable_case_is_named(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _rejection(tmp_path, "case-dead.sh", "#!/bin/sh\nexit 0\n", executable=False)
    assert st.main(["--scope", "project"]) == 1
    assert "not executable" in capsys.readouterr().out


def test_readme_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _rejection(tmp_path, "README.md", "not a case\n")
    assert st.main(["--scope", "project"]) == 0


@needs_posix_exec
def test_parallel_reports_all_failures(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _rejection(tmp_path, "case-a.sh", "#!/bin/sh\nexit 1\n")
    _rejection(tmp_path, "case-b.sh", "#!/bin/sh\nexit 2\n")
    assert st.main(["--scope", "project"]) == 1
    out = capsys.readouterr().out
    assert "case-a.sh" in out and "case-b.sh" in out  # both, not just the first


@needs_posix_exec
def test_runaway_case_times_out_fast(tmp_path, monkeypatch, capsys):
    """Wish 5: a sleep-30 case fails as TIMEOUT within the 10s budget."""
    import time
    monkeypatch.chdir(tmp_path)
    _rejection(tmp_path, "case-hang.sh", "#!/bin/sh\nsleep 30\n")
    _rejection(tmp_path, "case-fine.sh", "#!/bin/sh\nexit 0\n")
    t0 = time.monotonic()
    assert st.main(["--scope", "project"]) == 1
    wall = time.monotonic() - t0
    out = capsys.readouterr().out
    assert "FAIL .gov/rejections/case-hang.sh (timed out after 10s)" in out
    assert "PASS .gov/rejections/case-fine.sh" in out  # the run continues
    assert wall < 20, f"a runaway case must not hold the run ({wall:.1f}s)"


def test_coverage_ledger_and_bad_shebang(tmp_path, monkeypatch, capsys):
    """Wish 4: gate x case matrix; a shebang-less case is named, not fatal."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gov").mkdir()
    (tmp_path / "gates.json").write_text(_json.dumps(
        {"modes": {"all": ["alpha", "beta"]},
         "gates": [{"id": "alpha", "command": ["true"]},
                   {"id": "beta", "command": ["true"]}]}), encoding="utf-8")
    rej = tmp_path / ".gov" / "rejections"
    rej.mkdir()
    good = rej / "case-alpha.sh"
    good.write_text("#!/bin/sh\n# gate: alpha\nexit 0\n", encoding="utf-8")
    good.chmod(0o755)
    bad = rej / "case-noshebang.sh"
    bad.write_text("# gate: ghost\nexit 0\n", encoding="utf-8")  # no shebang, unknown gate
    bad.chmod(0o755)
    assert st.main(["--scope", "project"]) == 1  # the bad case fails, named
    out = capsys.readouterr().out
    assert "missing shebang" in out
    assert "alpha(1)" in out and "beta(NONE — rule 6)" in out
    assert "case names unknown gate(s): ghost" in out


def test_coverage_pointer_when_uncovered(tmp_path, monkeypatch, capsys):
    import json as _json
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gov").mkdir()
    (tmp_path / "gates.json").write_text(_json.dumps(
        {"modes": {"all": ["x"]}, "gates": [{"id": "x", "command": ["true"]}]}), encoding="utf-8")
    assert st.main(["--scope", "project"]) == 0  # no cases at all
    out = capsys.readouterr().out
    assert "x(NONE — rule 6)" in out
    assert "write one: .gov/rejections/case-<gate-id>.sh" in out


@needs_posix_exec
def test_coverage_remedy_reaches_a_full_run(tmp_path, monkeypatch, capsys):
    """#167 end to end: a real run's ledger prints the fix beside the file
    it names. The function-level proof — including a marker inside a
    module docstring being credited — is the shipped tools case
    ``test_coverage_warning_names_the_marker_fix``; this one pins the
    wiring from ``main()`` down to it."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gov").mkdir()
    (tmp_path / "gates.json").write_text(_json.dumps(
        {"modes": {"all": ["x"]}, "gates": [{"id": "x", "command": ["true"]}]}), encoding="utf-8")
    _rejection(tmp_path, "case-legacy.sh", "#!/bin/sh\nexit 0\n")
    assert st.main(["--scope", "project"]) == 0
    out = capsys.readouterr().out
    assert "case-legacy.sh" in out, "the undeclared case must be named"
    assert "fix: add '# gate: <id>' within the first 5 lines" in out, out


def test_classifier_labels_probes_by_clean_env_replay():
    """#139/D47: the verdict comes from the replay, not from a guess.

    The always-broken probe replays red (tool-defect); the env-only probe
    — which genuinely breaks under a shadowed PYTHONPATH, the #138 shape
    — replays green once the host's site layer is gone (environment-
    suspect).
    """
    saved = os.environ.get("PYTHONPATH")
    try:
        os.environ["PYTHONPATH"] = "/tmp/gov-selftest-shadow-probe/x"
        try:
            st._probe_env_only_failure()
            raise AssertionError("env-only probe did not reproduce under "
                                 "a shadowed PYTHONPATH")
        except AssertionError as e:
            assert "shadowed PYTHONPATH" in str(e)
    finally:
        if saved is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = saved
    env_lines = st._classify_tool_failure(st._probe_env_only_failure)
    assert any("environment-suspect" in l for l in env_lines), env_lines
    tool_lines = st._classify_tool_failure(st._probe_always_fails)
    assert any("tool-defect" in l for l in tool_lines), tool_lines


def test_unrunnable_replay_is_unclassified_not_tool_defect(tmp_path, monkeypatch):
    """#139: a replay that cannot run (case unknown to the staged copy,
    exit 2) classifies nothing — a crash is not a verdict."""
    monkeypatch.chdir(tmp_path)

    def not_in_staged_copy():
        raise AssertionError("boom")

    lines = st._classify_tool_failure(not_in_staged_copy)
    assert any("unclassified" in l for l in lines), lines


def test_case_flag_runs_one_case_and_names_unknown(tmp_path, monkeypatch, capsys):
    """--case NAME is the replay's building block: one case, one line;
    an unknown name aborts loud with the offending name (rule 5)."""
    monkeypatch.chdir(tmp_path)

    def ok_case():
        pass

    monkeypatch.setattr(st, "CASES", [ok_case])
    assert st.main(["--case", "ok_case"]) == 0
    assert "PASS ok_case" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        st.main(["--case", "ghost"])
    assert exc.value.code == 2
    assert "unknown case 'ghost'" in capsys.readouterr().err


def test_project_failure_carries_hand_repro_hint(tmp_path, monkeypatch, capsys):
    """#139: project cases are arbitrary scripts — their FAIL gets the
    reproduce-by-hand hint, never an automatic replay verdict."""
    monkeypatch.chdir(tmp_path)
    _rejection(tmp_path, "case-broken.sh", "#!/bin/sh\nexit 1\n")
    assert st.main(["--scope", "project"]) == 1
    out = capsys.readouterr().out
    assert "reproduce by hand" in out
    assert "clean-env replay" not in out
    assert "unclassified 1" in out


def test_run_text_survives_non_utf8_child_bytes(tmp_path):
    """#172: the harness's text spawns decode pinned UTF-8/replace — a
    child emitting non-UTF-8 (GBK) bytes comes back as mojibake, never a
    UnicodeDecodeError in a reader thread. This is the GBK-locale Windows
    crash made deterministic on every OS: the child writes GBK bytes
    directly, the way a UTF-8-speaking child's output hit a GBK decoder."""
    script = ("import sys; "
              "sys.stdout.buffer.write('中文“引号”'.encode('gbk'))")
    r = st._run_text(
        [sys.executable, "-c", script],
        cwd=tmp_path, capture_output=True,
        env=st._case_env(),
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout, "the bytes must decode to something, not raise"
    assert "\ufffd" in r.stdout  # bounded to replacement, not a crash


def test_scanner_rejects_unpinned_text_spawn():
    """Rule 6: the #172 pin scan must be able to fail — an unpinned
    text=True spawn is named by file:line; a pinned one passes clean."""
    bad = 'subprocess.run(cmd, capture_output=True, text=True)'
    good = ('subprocess.run(cmd, capture_output=True, text=True, '
            'encoding="utf-8")')
    multiline = 'subprocess.run(\n    cmd,\n    text=True,\n)'
    assert st._unpinned_text_spawns(bad, "x.py") == ["x.py:1"]
    assert st._unpinned_text_spawns(multiline, "x.py") == ["x.py:1"]
    assert st._unpinned_text_spawns(good, "x.py") == []
    assert st._unpinned_text_spawns('subprocess.run(cmd, capture_output=True)',
                                    "x.py") == []  # binary: nothing to decode


def test_thread_crash_fails_loud(tmp_path, monkeypatch, capsys):
    """Rule 5 / #172: a harness thread crash must fail the run — it used
    to print a traceback and leave the exit code (and the PASS) intact."""
    import threading
    crash = threading.ExceptHookArgs((
        RuntimeError, RuntimeError("boom"), None, threading.current_thread(),
    ))
    monkeypatch.setattr(st, "CASES", [])
    monkeypatch.chdir(tmp_path)  # no project cases; the crash alone must fail it
    st._THREAD_CRASHES.append(crash)
    assert st.main(["--scope", "project"]) == 1  # no failures, still loud
    out = capsys.readouterr().out
    assert "HARNESS-ERROR" in out
    assert "RuntimeError: boom" in out
    assert st._THREAD_CRASHES == []  # cleared for the next in-process run
