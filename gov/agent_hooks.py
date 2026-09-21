#!/usr/bin/env python3
"""`gov agent-hooks` — the plane's presence at every agent lifecycle event.

Claude Code (and compatible frameworks) fire hooks at lifecycle events:
SessionStart, PreToolUse, PostToolUse, UserPromptSubmit, Stop, etc.
Each hook invokes `gov agent-hooks <event>` with a JSON payload on stdin.
govrail reads the payload, runs the event's handler, and outputs JSON
to control the agent (allow / deny / inject context).

The handlers form the governance pipeline:
- session-start: check the plane's state, inject status context
- pre-tool-use:  the core gate — decide allow / block per governance rules
- post-tool-use: record what happened (audit trail)
- user-prompt-submit: inject governance context into the conversation
- stop:          final checks (notes written? cards closed?)

Handlers start as pass-through and grow logic as governance rules land.
The STRUCTURE is the point: govrail has a presence at every lifecycle
event from the moment `gov init` installs the hooks config.

One protocol, several platforms (D60): the handler core is shared, but
each platform hears a different DIALECT — the deny/context output keys
it parses, or (Gemini, Windsurf-style) a bare exit 2 with the reason on
stderr. `--dialect` names the calling platform; `gov init --platforms`
writes the matching spelling into each platform's hook config, so the
flag is always explicit in what runs — never inferred from a payload.

This is a presence, not a fence (D59): the pre-tool-use deny matches
strings, not semantics — `gov run` and the pre-push gate remain the
enforcement. A malformed payload is named on stderr and the handler
runs without it: loud fail-open, because an exit 2 here would block
every PreToolUse call for a framework that doesn't speak JSON.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    from .version import __version__
except ImportError:
    from version import __version__

#: The output dialects `--dialect` accepts (order = help/report order).
DIALECTS = ("claude", "codex", "copilot", "gemini")

# Gemini renames two of the five events; hookSpecificOutput.hookEventName
# is validated against the firing event's own name, so context output
# must spell it the way the CLI fired it.
GEMINI_EVENT_NAMES = {
    "session-start": "SessionStart",
    "pre-tool-use": "BeforeTool",
    "post-tool-use": "AfterTool",
    "user-prompt-submit": "BeforeAgent",
    "stop": "AfterAgent",
}

# The built-in deny rules (#312): regex with a reason and an optional
# allow list, replacing the two string literals this handler used to
# match (`rm -rf /` and `git reset --hard` — `rm -fr /`, `sudo rm -rf /`
# and friends sailed past them). Still a presence, not a fence (D59):
# deterministic commands only, and `.gov/hook-deny.json` extends (or,
# with "replace_builtin", replaces) this table.
BUILTIN_DENY_RULES = [
    {
        "pattern": (r"\brm\b(?=.*\s-{1,2}[a-z]*r[a-z]*(\s|$))"
                    r"(?=.*\s-{1,2}[a-z]*f[a-z]*(\s|$))"),
        "reason": "destructive command blocked by the governance plane — "
                  "a recursive, forced `rm` bypasses the plane's audit "
                  "trail. Scope the deletion to your scratch paths, or "
                  "record an exemption in .gov/hook-deny.json.",
        "allow": [],
    },
    {
        "pattern": r"\bgit\s+(?:\S+\s+){0,3}reset\s+--hard\b",
        "reason": "destructive command blocked by the governance plane — "
                  "`git reset --hard` discards work outside the plane's "
                  "audit trail. Use `git revert` for undos, or record an "
                  "exemption in .gov/hook-deny.json for scratch worktrees.",
        "allow": [],
    },
]

HOOK_DENY_CONFIG = Path(".gov/hook-deny.json")


def _read_stdin_json() -> tuple[str, dict, str | None]:
    """Read the hook payload from stdin (Claude Code sends JSON).

    Returns (raw, payload, error). An empty stdin is a legitimate
    no-payload call; a MALFORMED one comes back as a named error for the
    caller to print — never a silently swallowed {} (rule 5). ``raw`` is
    the bytes as the platform sent them, which is what a capture wants to
    keep: a payload the parser rejected is exactly the one worth seeing.
    """
    try:
        raw = sys.stdin.read()
    except OSError as e:
        return "", {}, f"stdin unreadable ({e})"
    if not raw.strip():
        return raw, {}, None
    try:
        return raw, json.loads(raw), None
    except json.JSONDecodeError as e:
        return raw, {}, f"malformed hook payload on stdin ({e})"


#: Opt-in capture of hook invocations (see `_capture`).
CAPTURE_ENV = "GOV_AGENT_HOOK_CAPTURE"
CAPTURE_LEDGER = "agent-hooks.jsonl"
CAPTURE_TRUTHY = ("1", "true", "yes", "on")


def _capture_target(explicit: str | None) -> Path | None:
    """Where this invocation's payload goes, or None when capture is off.

    OFF by default, deliberately: these payloads carry the user's own
    prompts and the exact commands an agent runs — worth inspecting,
    not something to accumulate behind the operator's back. Two opt-ins:

    - ``--capture PATH`` — this one invocation (debugging a hook that
      fires when the platform says it does);
    - ``GOV_AGENT_HOOK_CAPTURE=1`` (or a path) — every invocation, to
      the default target ``.gov/history/agent-hooks.jsonl``: local,
      ensure-ignored runtime state, never the tracked tree.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get(CAPTURE_ENV, "").strip()
    if not env:
        return None
    if env.lower() in CAPTURE_TRUTHY:
        try:
            from .anchor import history_path
        except ImportError:  # direct script execution
            from anchor import history_path
        return history_path(CAPTURE_LEDGER)
    return Path(env)


def _capture(path: Path | None, event: str, dialect: str, argv: list[str],
             raw: str, payload: dict, err: str | None) -> None:
    """Append one invocation record — a ledger, not a verdict.

    The record is what the PLATFORM sent (event, dialect, cwd, argv, and
    the payload verbatim), so a hook author can see the real shape per
    event per platform instead of guessing it. A capture that cannot be
    written never changes the hook's answer: the exit code is a contract
    with the caller, the ledger is bookkeeping (a named warning says the
    write failed, rule 5's naming side).
    """
    if path is None:
        return
    from datetime import datetime, timezone
    record: dict = {
        "v": 1,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "dialect": dialect,
        "cwd": str(Path.cwd()),
        "argv": list(argv),
    }
    if err is not None:
        record["payload_error"] = err
        record["payload_raw"] = raw
    else:
        record["payload"] = payload
    line = json.dumps(record, ensure_ascii=False) + "\n"
    try:
        try:
            from . import atomicio
            from .anchor import ledger_root
        except ImportError:  # direct script execution
            import atomicio
            from anchor import ledger_root
        path.parent.mkdir(parents=True, exist_ok=True)
        atomicio.append_line(path, line, root=ledger_root(path))
    except Exception as e:  # noqa: BLE001 — capture never breaks a hook
        print(f"gov agent-hooks: capture failed ({path}: {e}) — the hook's "
              "verdict is unchanged", file=sys.stderr)


def _output(data: dict | None = None) -> None:
    """Output JSON to stdout (Claude Code parses it when it starts with {)."""
    if data is not None:
        print(json.dumps(data, ensure_ascii=False))


def _pascal(event: str) -> str:
    """session-start → SessionStart — the framework's own event spelling
    (the settings.json keys); hookSpecificOutput is validated against it."""
    return "".join(part.capitalize() for part in event.split("-"))


def _deny(reason: str, dialect: str = "claude") -> int:
    """Output a blocking decision; returns the process exit code.

    claude/codex parse hookSpecificOutput (Codex's contract is the same
    shape); copilot reads top-level permissionDecision keys; gemini has
    no deny JSON on the verified path — exit 2 with the reason on stderr
    IS its block ("System Block; stderr becomes the rejection reason"),
    already inside the 0/2 exit-code contract.
    """
    if dialect == "copilot":
        _output({
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        })
        return 0
    if dialect == "gemini":
        print(f"govrail: {reason}", file=sys.stderr)
        return 2
    _output({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })
    return 0


def _context(event: str, text: str, dialect: str = "claude") -> None:
    """Inject governance context into the agent's conversation."""
    if dialect == "codex":
        # Codex adds plain-text stdout as developer context on
        # SessionStart/UserPromptSubmit; a hookSpecificOutput wrapper is
        # its PreToolUse shape, not its context shape.
        print(text)
        return
    if dialect == "copilot":
        _output({"additionalContext": text})
        return
    name = _pascal(event) if dialect == "claude" else GEMINI_EVENT_NAMES[event]
    _output({
        "hookSpecificOutput": {
            "hookEventName": name,
            "additionalContext": text,
        }
    })


# ── handlers ─────────────────────────────────────────────────────────

def _governed(payload: dict) -> Path | None:
    """The governed root, or None if this isn't a govrail repo."""
    cwd = payload.get("cwd", "")
    p = Path(cwd) if cwd else Path.cwd()
    if (p / ".gov" / "manifest.json").is_file():
        return p
    return None


def _command_of(payload: dict) -> str:
    """The shell command a pre-tool-use payload carries, across the key
    spellings the wired platforms use (claude/codex: tool_input.command;
    copilot's camelCase mode: toolArgs.command)."""
    for holder in ("tool_input", "toolArgs"):
        v = payload.get(holder)
        if isinstance(v, dict):
            command = v.get("command", "")
            if isinstance(command, str):
                return command
    return ""


def _load_deny_rules(root: Path) -> tuple[list[dict], str | None]:
    """``(rules, warning)`` — the effective deny table (#312).

    ``.gov/hook-deny.json`` adds rules to (or, with ``"replace_builtin":
    true``, replaces) the built-in table; each rule carries a ``pattern``
    regex, a ``reason``, and optional ``allow`` exemption regexes. A
    malformed config is named on stderr and the built-ins run alone —
    loud fail-open, the same contract as a malformed hook payload: an
    exit 2 here would block every tool call for a platform that cannot
    fix the config from inside the hook."""
    rules = [dict(r) for r in BUILTIN_DENY_RULES]
    path = root / HOOK_DENY_CONFIG
    if not path.is_file():
        return rules, None
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return rules, f"{HOOK_DENY_CONFIG} is unreadable ({e}) — built-in " \
                      "deny rules only"
    if not isinstance(doc, dict):
        return rules, f"{HOOK_DENY_CONFIG} must be a JSON object — " \
                      "built-in deny rules only"
    unknown = sorted(set(doc) - {"deny", "replace_builtin"})
    if unknown:
        return rules, f"{HOOK_DENY_CONFIG}: unknown key(s) " \
                      f"{', '.join(unknown)} (known: deny, replace_builtin) " \
                      "— built-in deny rules only"
    extra = doc.get("deny", [])
    if not isinstance(extra, list) or any(not isinstance(r, dict) for r in extra):
        return rules, f"{HOOK_DENY_CONFIG}: 'deny' must be an array of " \
                      "rule objects — built-in deny rules only"
    parsed: list[dict] = []
    for i, r in enumerate(extra):
        pattern = r.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return rules, f"{HOOK_DENY_CONFIG}: deny[{i}] needs a " \
                          "'pattern' regex — built-in deny rules only"
        try:
            re.compile(pattern)
        except re.error as e:
            return rules, f"{HOOK_DENY_CONFIG}: deny[{i}] pattern does " \
                          f"not compile ({e}) — built-in deny rules only"
        allow = r.get("allow", [])
        if not isinstance(allow, list) or \
                any(not isinstance(a, str) for a in allow):
            return rules, f"{HOOK_DENY_CONFIG}: deny[{i}] 'allow' must be " \
                          "an array of regex strings — built-in deny rules only"
        for a in allow:
            try:
                re.compile(a)
            except re.error as e:
                return rules, f"{HOOK_DENY_CONFIG}: deny[{i}] allow regex " \
                              f"does not compile ({e}) — built-in deny rules only"
        parsed.append({"pattern": pattern,
                       "reason": r.get("reason") or
                                 "blocked by the governance plane's "
                                 "hook-deny rules",
                       "allow": allow})
    if doc.get("replace_builtin"):
        rules = []
    rules.extend(parsed)
    return rules, None


def handle_session_start(payload: dict, event: str,
                         dialect: str = "claude") -> int:
    """Session begins in a govrail-governed repo: check the plane."""
    root = _governed(payload)
    if root is None:
        return 0
    seal = root / ".gov" / "plane-seal.json"
    if seal.is_file():
        _context(event, f"govrail {__version__}: plane sealed and intact. "
                        "Follow .gov/rules.md. Run `gov run` before pushing.",
                 dialect)
    else:
        _context(event, f"govrail {__version__}: plane present but unsealed. "
                        "Run `gov verify-plane --write` to seal it.", dialect)
    return 0


def handle_pre_tool_use(payload: dict, event: str,
                        dialect: str = "claude") -> int:
    """The core gate: decide whether the agent's tool call is allowed.

    #312: judgment comes from a deny-rules table — built-ins shipped in
    code, extended (or replaced) by ``.gov/hook-deny.json``. Each rule is
    a regex with a reason; an ``allow`` regex on a rule exempts a command
    (e.g. `git reset --hard` inside a scratch worktree).
    """
    root = _governed(payload)
    if root is None:
        return 0
    command = _command_of(payload)
    if not command:
        return 0

    # git push → the pre-push git hook handles governance; no double-gate
    if "git push" in command:
        return 0

    rules, warning = _load_deny_rules(root)
    if warning:
        print(f"govrail: {warning}", file=sys.stderr)
    for rule in rules:
        if not re.search(rule["pattern"], command):
            continue
        if any(re.search(a, command) for a in rule.get("allow", [])):
            continue
        return _deny(f"{rule['reason']} Offending command: "
                     f"'{command.strip()}'.", dialect)
    return 0


def handle_post_tool_use(payload: dict, event: str,
                         dialect: str = "claude") -> int:
    """Record what happened (audit trail). Pass-through for now."""
    return 0


def handle_user_prompt_submit(payload: dict, event: str,
                              dialect: str = "claude") -> int:
    """Inject governance context when the user submits a prompt."""
    root = _governed(payload)
    if root is None:
        return 0
    _context(event, "govrail: this repo is governed. Follow .gov/rules.md.",
             dialect)
    return 0


def _git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args], cwd=str(root),
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def handle_stop(payload: dict, event: str, dialect: str = "claude") -> int:
    """The agent is finishing (#312): the plane's closing advisory.

    Cheap, read-only checks over the state the plane itself owns — an
    open task card, a dirty worktree — surfaced as context, never as a
    block (the enforcement remains `gov run` and the pre-push gate)."""
    root = _governed(payload)
    if root is None:
        return 0
    reminders: list[str] = []
    tasks = root / ".gov" / "tasks"
    if tasks.is_dir():
        open_cards: list[str] = []
        for p in sorted(tasks.glob("*.json")):
            try:
                card = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if card.get("status") in ("open", "claimed"):
                open_cards.append(str(card.get("id") or p.stem))
        if open_cards:
            reminders.append(
                "open task card(s): " + ", ".join(open_cards[:5])
                + " — close them (`gov task close`) or defer before push")
    status = _git(root, "status", "--porcelain")
    if status.strip():
        lines = [ln for ln in status.splitlines() if ln.strip()]
        reminders.append(
            f"worktree has {len(lines)} uncommitted file(s) — run "
            "`gov run` before pushing (rule 2: a non-trivial change "
            "carries a note)")
    if reminders:
        _context(event, f"govrail {__version__} (stop): " + "; ".join(reminders),
                 dialect)
    return 0


HANDLERS = {
    "session-start": handle_session_start,
    "pre-tool-use": handle_pre_tool_use,
    "post-tool-use": handle_post_tool_use,
    "user-prompt-submit": handle_user_prompt_submit,
    "stop": handle_stop,
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    event = ""
    dialect = "claude"
    capture: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            print("usage: gov agent-hooks <event> [--dialect NAME]")
            print("agent lifecycle hooks — govrail's presence at every point "
                  "of the agent's workflow")
            print("events: session-start, pre-tool-use, post-tool-use, "
                  "user-prompt-submit, stop")
            print(f"dialects: {', '.join(DIALECTS)} — the output contract "
                  "of the calling platform (which deny/context keys it "
                  "parses, or exit 2 + stderr)")
            print()
            print("options:")
            print("  --dialect NAME   output dialect of the installed "
                  "platform (default: claude);")
            print("                   `gov init --platforms` writes the "
                  "matching spelling")
            print("                   into that platform's hook config")
            print("  --capture PATH   append this invocation's payload "
                  "(event, dialect, cwd, argv,")
            print("                   the stdin JSON verbatim) to PATH as "
                  "one JSON line —")
            print("                   off by default: payloads carry the "
                  "user's prompts and the")
            print("                   commands an agent runs. Always-on "
                  f"form: {CAPTURE_ENV}=1")
            print("                   (default target "
                  ".gov/history/agent-hooks.jsonl, gitignored).")
            print("  -h, --help       show this help and exit")
            return 0
        if a == "--dialect":
            if i + 1 >= len(args):
                print("gov agent-hooks: --dialect requires a name "
                      f"(known: {', '.join(DIALECTS)})", file=sys.stderr)
                return 2
            dialect = args[i + 1]
            i += 2
            continue
        if a == "--capture":
            if i + 1 >= len(args):
                print("gov agent-hooks: --capture requires a path",
                      file=sys.stderr)
                return 2
            capture = args[i + 1]
            i += 2
            continue
        if a.startswith("--"):
            print(f"gov agent-hooks: unexpected argument '{a}'", file=sys.stderr)
            return 2
        if event:
            print(f"gov agent-hooks: unexpected extra event '{a}' "
                  f"(already: '{event}')", file=sys.stderr)
            return 2
        event = a
        i += 1
    if dialect not in DIALECTS:
        print(f"gov agent-hooks: unknown dialect '{dialect}' "
              f"(known: {', '.join(DIALECTS)})", file=sys.stderr)
        return 2
    if not event:
        print("gov agent-hooks: no event given "
              f"(known: {', '.join(sorted(HANDLERS))})", file=sys.stderr)
        return 2
    handler = HANDLERS.get(event)
    if handler is None:
        print(f"gov agent-hooks: unknown event '{event}' "
              f"(known: {', '.join(sorted(HANDLERS))})", file=sys.stderr)
        return 2
    raw, payload, err = _read_stdin_json()
    if err:
        print(f"gov agent-hooks: {event}: {err} — continuing without it",
              file=sys.stderr)
    # Capture BEFORE the handler runs: what the platform sent is the
    # question being asked, and a handler that returns early (no repo,
    # denied tool) must not lose the evidence.
    _capture(_capture_target(capture), event, dialect,
             list(sys.argv[1:] if argv is None else argv),
             raw, payload, err)
    return handler(payload, event, dialect)


if __name__ == "__main__":
    raise SystemExit(main())
