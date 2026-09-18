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


def _read_stdin_json() -> tuple[dict, str | None]:
    """Read the hook payload from stdin (Claude Code sends JSON).

    Returns (payload, error). An empty stdin is a legitimate no-payload
    call; a MALFORMED one comes back as a named error for the caller to
    print — never a silently swallowed {} (rule 5).
    """
    try:
        raw = sys.stdin.read()
    except OSError as e:
        return {}, f"stdin unreadable ({e})"
    if not raw.strip():
        return {}, None
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return {}, f"malformed hook payload on stdin ({e})"


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
    """The core gate: decide whether the agent's tool call is allowed."""
    root = _governed(payload)
    if root is None:
        return 0
    command = _command_of(payload)

    # git push → the pre-push git hook handles governance; no double-gate
    if "git push" in command:
        return 0

    # destructive commands that bypass the plane
    if "rm -rf /" in command or "git reset --hard" in command:
        return _deny(f"destructive command blocked by the governance "
                     f"plane — '{command.strip()}' would bypass the plane's "
                     "audit trail. Use `gov update --apply` for migrations or "
                     "`git revert` for undos.", dialect)
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


def handle_stop(payload: dict, event: str, dialect: str = "claude") -> int:
    """The agent is finishing. Final checks."""
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
    payload, err = _read_stdin_json()
    if err:
        print(f"gov agent-hooks: {event}: {err} — continuing without it",
              file=sys.stderr)
    return handler(payload, event, dialect)


if __name__ == "__main__":
    raise SystemExit(main())
