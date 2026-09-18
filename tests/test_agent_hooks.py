"""Pin the agent-hooks surface: fail-loud stdin, PascalCase context,
and the exact reversibility of the .claude/settings.json install (D59).

The review of PR #286 caught the first shipping of this surface naming
the wrong command (`gov hooks`), swallowing malformed stdin into a
silent {}, deriving hookEventName from sys.argv in kebab-case the
framework ignores, and registering the install under a created[] entry
uninstall could never match. Each test here is the rejection case for
one of those failure modes: a guard that has never failed is decoration.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from gov import agent_hooks, cli


def _governed(tmp_path: Path) -> Path:
    (tmp_path / ".gov").mkdir()
    (tmp_path / ".gov" / "manifest.json").write_text("{}", encoding="utf-8")
    return tmp_path


def _manifest(tmp_path: Path) -> Path:
    (tmp_path / ".gov").mkdir(exist_ok=True)
    p = tmp_path / ".gov" / "manifest.json"
    p.write_text(json.dumps(
        {"version": "test", "created": [], "gitHooks": [], "templates": {}}),
        encoding="utf-8")
    return p


# ── the command surface ──────────────────────────────────────────────

def test_unknown_event_names_command_and_offender(capsys):
    rc = agent_hooks.main(["nope"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "gov agent-hooks: unknown event 'nope'" in err
    assert "session-start" in err  # the known set, for the next try


def test_help_exits_zero(capsys):
    assert agent_hooks.main(["--help"]) == 0


def test_malformed_stdin_is_named_not_swallowed(capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
    rc = agent_hooks.main(["pre-tool-use"])
    assert rc == 0  # loud fail-open: 0/2 contract intact (D59)
    assert "malformed hook payload on stdin" in capsys.readouterr().err


def test_empty_stdin_is_a_legitimate_no_payload(capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert agent_hooks.main(["stop"]) == 0
    assert capsys.readouterr().err == ""


# ── pre-tool-use: the deny path must actually deny ───────────────────

def test_deny_on_rm_rf_root(tmp_path, capsys):
    payload = {"cwd": str(_governed(tmp_path)),
               "tool_input": {"command": "rm -rf /"}}
    agent_hooks.handle_pre_tool_use(payload, "pre-tool-use")
    decision = json.loads(capsys.readouterr().out)
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "rm -rf /" in decision["hookSpecificOutput"][
        "permissionDecisionReason"]  # the offending name


def test_deny_on_git_reset_hard(tmp_path, capsys):
    payload = {"cwd": str(_governed(tmp_path)),
               "tool_input": {"command": "git reset --hard HEAD~3"}}
    agent_hooks.handle_pre_tool_use(payload, "pre-tool-use")
    assert "deny" in capsys.readouterr().out


def test_pass_through_benign_and_push(tmp_path, capsys):
    root = str(_governed(tmp_path))
    agent_hooks.handle_pre_tool_use(
        {"cwd": root, "tool_input": {"command": "gov run"}}, "pre-tool-use")
    agent_hooks.handle_pre_tool_use(
        {"cwd": root, "tool_input": {"command": "git push origin HEAD"}},
        "pre-tool-use")  # the pre-push git hook owns it — no double gate
    assert capsys.readouterr().out == ""


def test_silent_outside_governed_repo(tmp_path, capsys):
    agent_hooks.handle_pre_tool_use(
        {"cwd": str(tmp_path), "tool_input": {"command": "rm -rf /"}},
        "pre-tool-use")
    assert capsys.readouterr().out == ""


# ── context injection: the framework's event spelling ────────────────

def test_session_start_uses_pascal_case_event(tmp_path, capsys):
    payload = {"cwd": str(_governed(tmp_path))}
    agent_hooks.handle_session_start(payload, "session-start")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "additionalContext" in out["hookSpecificOutput"]


def test_user_prompt_submit_event_name(tmp_path, capsys):
    payload = {"cwd": str(_governed(tmp_path))}
    agent_hooks.handle_user_prompt_submit(payload, "user-prompt-submit")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"


# ── install + uninstall: exact reversal (D10/D59) ────────────────────

def test_add_ons_installs_template_bytes_and_bare_created_entry(tmp_path):
    manifest_path = _manifest(tmp_path)
    assert cli._add_ons(tmp_path, manifest_path, hooks=False, ci=False) == 0
    settings = tmp_path / ".claude" / "settings.json"
    assert settings.read_bytes() == \
        cli.TEMPLATES.joinpath("claude-settings.json").read_bytes()
    assert ".claude/settings.json" in \
        json.loads(manifest_path.read_text(encoding="utf-8"))["created"]


def test_add_ons_reports_existing_settings_and_leaves_it(
        tmp_path, capsys):
    manifest_path = _manifest(tmp_path)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks": {}}', encoding="utf-8")  # the adopter's
    assert cli._add_ons(tmp_path, manifest_path, hooks=False, ci=False) == 0
    assert settings.read_text() == '{"hooks": {}}'
    assert ".claude/settings.json" not in \
        json.loads(manifest_path.read_text(encoding="utf-8"))["created"]
    assert "already exists" in capsys.readouterr().out


def test_uninstall_removes_pristine_settings(tmp_path):
    manifest_path = _manifest(tmp_path)
    assert cli._add_ons(tmp_path, manifest_path, hooks=False, ci=False) == 0
    assert cli.uninstall(tmp_path) == 0
    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_uninstall_keeps_customized_settings_until_force(tmp_path, capsys):
    manifest_path = _manifest(tmp_path)
    assert cli._add_ons(tmp_path, manifest_path, hooks=False, ci=False) == 0
    settings = tmp_path / ".claude" / "settings.json"
    settings.write_text('{"hooks": {}, "model": "adopters-own"}',
                        encoding="utf-8")
    assert cli.uninstall(tmp_path) == 1  # refuses, names the file
    assert ".claude/settings.json" in capsys.readouterr().err
    assert settings.exists()
    assert cli.uninstall(tmp_path, force=True) == 0
    assert not settings.exists()
