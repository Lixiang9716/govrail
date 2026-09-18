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


def _deny(reason: str) -> None:
    """Output a blocking decision (PreToolUse exit 2 also blocks)."""
    _output({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })


def _context(event: str, text: str) -> None:
    """Inject governance context into the agent's conversation."""
    _output({
        "hookSpecificOutput": {
            "hookEventName": _pascal(event),
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


def handle_session_start(payload: dict, event: str) -> None:
    """Session begins in a govrail-governed repo: check the plane."""
    root = _governed(payload)
    if root is None:
        return
    seal = root / ".gov" / "plane-seal.json"
    if seal.is_file():
        _context(event, f"govrail {__version__}: plane sealed and intact. "
                        "Follow .gov/rules.md. Run `gov run` before pushing.")
    else:
        _context(event, f"govrail {__version__}: plane present but unsealed. "
                        "Run `gov verify-plane --write` to seal it.")


def handle_pre_tool_use(payload: dict, event: str) -> None:
    """The core gate: decide whether the agent's tool call is allowed."""
    root = _governed(payload)
    if root is None:
        return
    tool_input = payload.get("tool_input", {})
    command = ""
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")

    # git push → the pre-push git hook handles governance; no double-gate
    if "git push" in command:
        return

    # destructive commands that bypass the plane
    if "rm -rf /" in command or "git reset --hard" in command:
        _deny(f"govrail: destructive command blocked by the governance "
              f"plane — '{command.strip()}' would bypass the plane's "
              "audit trail. Use `gov update --apply` for migrations or "
              "`git revert` for undos.")


def handle_post_tool_use(payload: dict, event: str) -> None:
    """Record what happened (audit trail). Pass-through for now."""
    pass


def handle_user_prompt_submit(payload: dict, event: str) -> None:
    """Inject governance context when the user submits a prompt."""
    root = _governed(payload)
    if root is None:
        return
    _context(event, "govrail: this repo is governed. Follow .gov/rules.md.")


def handle_stop(payload: dict, event: str) -> None:
    """The agent is finishing. Final checks."""
    pass


HANDLERS = {
    "session-start": handle_session_start,
    "pre-tool-use": handle_pre_tool_use,
    "post-tool-use": handle_post_tool_use,
    "user-prompt-submit": handle_user_prompt_submit,
    "stop": handle_stop,
}


def main(argv: list[str] | None = None) -> int:
    if not argv:
        event = sys.argv[1] if len(sys.argv) > 1 else ""
        argv = [event]
    event = argv[0]
    if event in ("-h", "--help"):
        print("usage: gov agent-hooks <event>")
        print("agent lifecycle hooks — govrail's presence at every point "
              "of the agent's workflow")
        print("events: session-start, pre-tool-use, post-tool-use, "
              "user-prompt-submit, stop")
        print("reads JSON on stdin from the agent framework; outputs JSON "
              "to control the agent")
        return 0
    handler = HANDLERS.get(event)
    if handler is None:
        print(f"gov agent-hooks: unknown event '{event}' "
              f"(known: {', '.join(sorted(HANDLERS))})", file=sys.stderr)
        return 2
    payload, err = _read_stdin_json()
    if err:
        print(f"gov agent-hooks: {event}: {err} — continuing without it",
              file=sys.stderr)
    handler(payload, event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
