"""Pin the agent-hooks surface: fail-loud stdin, PascalCase context,
and the exact reversibility of the .claude/settings.json install (D59).

The review of PR #286 caught the first shipping of this surface naming
the wrong command (`gov hooks`), swallowing malformed stdin into a
silent {}, deriving hookEventName from sys.argv in kebab-case the
framework ignores, and registering the install under a created[] entry
uninstall could never match. Each test here is the rejection case for
one of those failure modes: a guard that has never failed is decoration.

D60 adds the multi-platform half: one handler core, one DIALECT per
platform (the output contract each one actually parses), and the
`--platforms` install surface whose templates must stay exactly
reversible through the same _inventory/_template_for/uninstall readers.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from gov import agent_hooks, cli, plane


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


# ── dialects: the contract each platform actually parses (D60) ────────

def _deny_reason(out: dict) -> str:
    """The reason field wherever the dialect put it."""
    if "hookSpecificOutput" in out:  # claude/codex
        return out["hookSpecificOutput"]["permissionDecisionReason"]
    return out["permissionDecisionReason"]  # copilot


def test_codex_deny_shares_the_claude_shape(tmp_path, capsys):
    payload = {"cwd": str(_governed(tmp_path)),
               "tool_input": {"command": "git reset --hard"}}
    assert agent_hooks.handle_pre_tool_use(
        payload, "pre-tool-use", dialect="codex") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "git reset --hard" in _deny_reason(out)


def test_copilot_deny_reads_top_level_permission_keys(tmp_path, capsys):
    payload = {"cwd": str(_governed(tmp_path)),
               "toolArgs": {"command": "rm -rf /"}}  # its camelCase payload
    assert agent_hooks.handle_pre_tool_use(
        payload, "pre-tool-use", dialect="copilot") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["permissionDecision"] == "deny"
    assert "rm -rf /" in _deny_reason(out)


def test_gemini_deny_is_exit_two_with_stderr_reason(tmp_path, capsys):
    payload = {"cwd": str(_governed(tmp_path)),
               "tool_input": {"command": "rm -rf /"}}
    assert agent_hooks.handle_pre_tool_use(
        payload, "pre-tool-use", dialect="gemini") == 2
    captured = capsys.readouterr()
    assert captured.out == ""  # no JSON a non-speaker could misparse
    assert "rm -rf /" in captured.err  # stderr IS the rejection reason


def test_codex_context_is_plain_text_developer_context(tmp_path, capsys):
    agent_hooks.handle_session_start(
        {"cwd": str(_governed(tmp_path))}, "session-start", dialect="codex")
    out = capsys.readouterr().out
    assert not out.lstrip().startswith("{")  # plain text, not JSON
    assert "govrail" in out


def test_copilot_context_is_top_level_additional_context(tmp_path, capsys):
    agent_hooks.handle_session_start(
        {"cwd": str(_governed(tmp_path))}, "session-start", dialect="copilot")
    out = json.loads(capsys.readouterr().out)
    assert "additionalContext" in out


def test_gemini_context_spells_gemini_event_names(tmp_path, capsys):
    agent_hooks.handle_user_prompt_submit(
        {"cwd": str(_governed(tmp_path))}, "user-prompt-submit",
        dialect="gemini")
    out = json.loads(capsys.readouterr().out)
    # gemini fires BeforeAgent where claude fires UserPromptSubmit — the
    # hookSpecificOutput must name the event the CLI actually fired.
    assert out["hookSpecificOutput"]["hookEventName"] == "BeforeAgent"


def test_every_dialect_maps_every_event():
    for event in agent_hooks.HANDLERS:
        assert event in agent_hooks.GEMINI_EVENT_NAMES


def test_unknown_dialect_exits_two_naming_known_set(capsys):
    assert agent_hooks.main(["stop", "--dialect", "windsurf"]) == 2
    err = capsys.readouterr().err
    assert "unknown dialect 'windsurf'" in err
    assert "gemini" in err  # the known set, for the next try


def test_dialect_without_value_exits_two(capsys):
    assert agent_hooks.main(["stop", "--dialect"]) == 2
    assert "--dialect requires a name" in capsys.readouterr().err


def test_unexpected_flag_exits_two(capsys):
    assert agent_hooks.main(["stop", "--json"]) == 2
    assert "unexpected argument '--json'" in capsys.readouterr().err


def test_help_lists_dialect_flag_in_options_block(capsys):
    assert agent_hooks.main(["--help"]) == 0
    out = capsys.readouterr().out
    options_at = out.index("options:")
    assert "--dialect" in out[options_at:]  # the registry-synced surface


# ── install + uninstall: exact reversal (D10/D59) ────────────────────

def test_add_ons_installs_template_bytes_and_bare_created_entry(tmp_path):
    manifest_path = _manifest(tmp_path)
    assert plane._add_ons(tmp_path, manifest_path, hooks=False, ci=False,
                          platforms=["claude"]) == 0  # #373: explicit opt-in
    settings = tmp_path / ".claude" / "settings.json"
    assert settings.read_bytes() == \
        plane.TEMPLATES.joinpath("claude-settings.json").read_bytes()
    assert ".claude/settings.json" in \
        json.loads(manifest_path.read_text(encoding="utf-8"))["created"]


def test_add_ons_reports_existing_settings_and_leaves_it(
        tmp_path, capsys):
    manifest_path = _manifest(tmp_path)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks": {}}', encoding="utf-8")  # the adopter's
    assert plane._add_ons(tmp_path, manifest_path, hooks=False, ci=False,
                          platforms=["claude"]) == 0  # #373: explicit opt-in
    assert settings.read_text() == '{"hooks": {}}'
    assert ".claude/settings.json" not in \
        json.loads(manifest_path.read_text(encoding="utf-8"))["created"]
    assert "already exists" in capsys.readouterr().out


def test_uninstall_removes_pristine_settings(tmp_path):
    manifest_path = _manifest(tmp_path)
    assert plane._add_ons(tmp_path, manifest_path, hooks=False, ci=False,
                          platforms=["claude"]) == 0  # #373: explicit opt-in
    assert plane.uninstall(tmp_path) == 0
    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_uninstall_keeps_customized_settings_until_force(tmp_path, capsys):
    manifest_path = _manifest(tmp_path)
    assert plane._add_ons(tmp_path, manifest_path, hooks=False, ci=False,
                          platforms=["claude"]) == 0  # #373: explicit opt-in
    settings = tmp_path / ".claude" / "settings.json"
    settings.write_text('{"hooks": {}, "model": "adopters-own"}',
                        encoding="utf-8")
    assert plane.uninstall(tmp_path) == 1  # refuses, names the file
    assert ".claude/settings.json" in capsys.readouterr().err
    assert settings.exists()
    assert plane.uninstall(tmp_path, force=True) == 0
    assert not settings.exists()


# ── --platforms: one template per platform, exact reversal (D60) ──────

def _add_ons_with_platforms(tmp_path, platforms):
    manifest_path = _manifest(tmp_path)
    rc = plane._add_ons(tmp_path, manifest_path, hooks=False, ci=False,
                      platforms=platforms)
    return rc, manifest_path


def test_platforms_install_template_bytes_and_created_entries(tmp_path):
    rc, manifest_path = _add_ons_with_platforms(tmp_path, ["codex", "gemini"])
    assert rc == 0
    for name, (rel, tpl) in plane.PLATFORM_TARGETS.items():
        if name in ("codex", "gemini"):
            assert (tmp_path / rel).read_bytes() == \
                plane.TEMPLATES.joinpath(tpl).read_bytes()
            assert rel in json.loads(
                manifest_path.read_text(encoding="utf-8"))["created"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["platforms"] == ["codex", "gemini"]


def test_platforms_all_installs_every_target(tmp_path):
    rc, _ = _add_ons_with_platforms(tmp_path, list(plane.PLATFORM_TARGETS))
    assert rc == 0
    for rel, _tpl in plane.PLATFORM_TARGETS.values():
        assert (tmp_path / rel).exists()


def test_platforms_install_only_what_was_named(tmp_path):
    rc, _ = _add_ons_with_platforms(tmp_path, ["codex"])
    assert rc == 0
    assert (tmp_path / ".codex" / "hooks.json").exists()
    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_existing_platform_config_is_named_and_skipped(tmp_path, capsys):
    existing = tmp_path / ".gemini" / "settings.json"
    existing.parent.mkdir()
    existing.write_text('{"model": "adopters-own"}', encoding="utf-8")
    rc, manifest_path = _add_ons_with_platforms(tmp_path, ["gemini"])
    assert rc == 0
    assert existing.read_text() == '{"model": "adopters-own"}'
    assert ".gemini/settings.json" not in json.loads(
        manifest_path.read_text(encoding="utf-8"))["created"]
    assert "already exists" in capsys.readouterr().out


def test_platform_configs_uninstall_and_drift_like_any_template(tmp_path):
    rc, _ = _add_ons_with_platforms(tmp_path, ["codex", "copilot"])
    assert rc == 0
    # drift classification knows the files (the _inventory reader)
    classified = {f["path"] for f in
                  plane.upgrade_files(tmp_path, tmp_path / ".gov" /
                                     "manifest.json")[0]}
    assert ".codex/hooks.json" in classified
    assert ".github/hooks/govrail.json" in classified
    assert plane.uninstall(tmp_path) == 0  # pristine → exact reversal (D10)
    for rel, _tpl in plane.PLATFORM_TARGETS.values():
        if rel in (".codex/hooks.json", ".github/hooks/govrail.json"):
            assert not (tmp_path / rel).exists()


def test_parse_platforms_validates_names_and_dedupes(capsys):
    assert cli._parse_platforms("codex, gemini") == ["codex", "gemini"]
    assert cli._parse_platforms("codex,codex") == ["codex"]
    assert cli._parse_platforms("all") == list(plane.PLATFORM_TARGETS)
    assert cli._parse_platforms("windsurf") is None
    assert "unknown platform 'windsurf'" in capsys.readouterr().err
    assert cli._parse_platforms("codex,") is None
    assert "empty name" in capsys.readouterr().err


def test_fresh_init_records_platforms_and_installs_exactly_them(tmp_path):
    assert plane.init(tmp_path, platforms=["codex"]) == 0
    assert (tmp_path / ".codex" / "hooks.json").exists()
    assert not (tmp_path / ".claude" / "settings.json").exists()
    data = json.loads((tmp_path / ".gov" / "manifest.json")
                      .read_text(encoding="utf-8"))
    assert data["platforms"] == ["codex"]


def test_upgrade_report_names_platforms_still_available(tmp_path, capsys):
    assert plane.init(tmp_path, platforms=["codex"]) == 0
    assert plane.init(tmp_path, upgrade=True) == 0
    out = capsys.readouterr().out
    assert "agent platforms not installed: claude, copilot, gemini" in out
    assert "gov init --platforms claude,copilot,gemini" in out


# ── capture: seeing what the platform actually sends ─────────────────

def test_capture_writes_the_payload_verbatim(tmp_path, monkeypatch, capsys):
    """`--capture PATH`: one JSON line per invocation carrying what the
    platform SENT — and the hook's own output contract is untouched."""
    monkeypatch.chdir(_governed(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "ls"},
         "session_id": "s-1"})))
    target = tmp_path / "cap" / "hooks.jsonl"
    assert agent_hooks.main(["pre-tool-use", "--capture", str(target)]) == 0
    capsys.readouterr()          # stdout is the handler's contract, not ours
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"] == "pre-tool-use" and rec["dialect"] == "claude"
    assert rec["payload"]["tool_name"] == "Bash"
    assert rec["payload"]["session_id"] == "s-1"     # unknown keys survive
    assert rec["argv"] == ["pre-tool-use", "--capture", str(target)]
    assert rec["cwd"].endswith(str(tmp_path.name))
    assert "v" in rec and "ts" in rec


def test_capture_appends_and_env_turns_it_on(tmp_path, monkeypatch, capsys):
    """Two invocations, two lines; the env form defaults to the
    gitignored history ledger and takes a path when given one."""
    monkeypatch.chdir(_governed(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"a": 1}'))
    target = tmp_path / "cap.jsonl"
    monkeypatch.setenv("GOV_AGENT_HOOK_CAPTURE", str(target))
    assert agent_hooks.main(["stop"]) == 0
    assert agent_hooks.main(["stop"]) == 0
    assert len(target.read_text(encoding="utf-8").splitlines()) == 2
    # the truthy form writes .gov/history/agent-hooks.jsonl
    monkeypatch.setenv("GOV_AGENT_HOOK_CAPTURE", "1")
    assert agent_hooks.main(["stop"]) == 0
    ledger = tmp_path / ".gov" / "history" / "agent-hooks.jsonl"
    assert ledger.exists() and "stop" in ledger.read_text(encoding="utf-8")


def test_capture_off_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(_governed(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"a": 1}'))
    monkeypatch.delenv("GOV_AGENT_HOOK_CAPTURE", raising=False)
    assert agent_hooks.main(["stop"]) == 0
    assert not list(tmp_path.rglob("*.jsonl"))


def test_malformed_payload_is_captured_raw(tmp_path, monkeypatch):
    """The payload a parser rejected is the one worth keeping: the record
    carries the raw text and the named error."""
    monkeypatch.chdir(_governed(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
    target = tmp_path / "cap.jsonl"
    assert agent_hooks.main(["pre-tool-use", "--capture", str(target)]) == 0
    rec = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
    assert rec["payload_raw"] == "{not json"
    assert "malformed hook payload" in rec["payload_error"]


def test_capture_failure_never_changes_the_verdict(tmp_path, monkeypatch,
                                                   capsys):
    """A capture that cannot be written is a named warning; the deny
    contract stays what the platform reads."""
    monkeypatch.chdir(_governed(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"command": "rm -rf /"}})))
    blocked = tmp_path / "adir"
    blocked.mkdir()
    rc = agent_hooks.main(["pre-tool-use", "--capture", str(blocked)])
    cap = capsys.readouterr()
    assert rc == 0
    assert "deny" in cap.out          # the verdict is intact
    assert "capture failed" in cap.err


def test_capture_requires_a_path(capsys):
    assert agent_hooks.main(["stop", "--capture"]) == 2
    assert "--capture requires a path" in capsys.readouterr().err
