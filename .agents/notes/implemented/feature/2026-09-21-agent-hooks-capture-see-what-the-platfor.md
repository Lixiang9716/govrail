# Agent Note: agent-hooks capture: see what the platform actually sends

Status: implemented

Related: D59

## Problem

The plane's agent-hook layer reads a JSON payload from stdin and answers
in each platform's own dialect — but the payload itself was invisible.
`_read_stdin_json` parsed it, the handler used a few keys, and the rest
was discarded: nobody could see what a given platform actually sends for
a given event (which keys exist, what `tool_input` looks like per tool,
whether the framework's event name matches the one we were told), and
debugging a hook that "did not fire" or "denied the wrong call" meant
guessing at the shapes. Test fixtures encode our BELIEF about the
payload; nothing checked it against the real thing. It is also the one
payload in the plane that is genuinely sensitive — `user-prompt-submit`
carries the user's own prompt, `pre-tool-use` the exact command an agent
is about to run — so the fix could not be "log everything always".

## Decision

- **`--capture PATH`** appends one JSON line per invocation to PATH: the
  event, dialect, cwd, argv, and the stdin payload **verbatim** (unknown
  keys included). Off by default.
- **`GOV_AGENT_HOOK_CAPTURE=1`** (or a path) turns it on for every
  invocation; the truthy form writes to
  `.gov/history/agent-hooks.jsonl` — local, ensure-ignored runtime state,
  never the tracked tree. The env knob is what makes a real session
  observable; the flag is what makes a single hook call observable.
- **The capture runs BEFORE the handler**, so a call that ends in a deny
  (or in "not a governed repo, return early") still leaves the evidence —
  the deny is exactly when you want to know what arrived.
- **A rejected payload is captured raw**: `payload_error` names the parse
  failure and `payload_raw` carries the bytes. The payload a parser
  rejected is the one worth keeping.
- **Capture never changes a verdict**: the exit code and stdout are the
  hook's contract with the platform, the ledger is bookkeeping, so a
  write that fails is a named stderr warning and nothing else.
- Discovery surfaces follow the command: `--help` documents both opt-ins
  (and states the privacy reason for the off-by-default), the flag
  registry pins `--capture`, the router skill routes it, and six tests
  pin the behaviour (verbatim payload, append + env forms, off by
  default, malformed raw, failure-does-not-change-verdict, missing path).

## Alternatives considered

- **Capture on by default** — rejected: prompts and commands would
  accumulate silently in every adopter's checkout, which is surveillance
  dressed as debugging; the ledger is one environment variable away for
  anyone who wants it.
- **A `gov agent-hooks dump`/`show` reader** — not yet: the record is one
  JSON line per invocation, and `jq`/`tail` already read a JSONL file
  better than a bespoke viewer would; a reader is worth building when a
  recurring question ("which events fired in this session?") makes it
  cheaper than the pipe.
- **Capturing into the run history (`gates.jsonl`) or a tracked file** —
  rejected: run history is about gate verdicts (D44's metrics/evidence
  line), and a tracked ledger would commit the user's prompts into the
  repository.
- **Redacting keys before writing** — rejected as the default: a
  redaction list would silently drop the very fields a hook author is
  trying to inspect, and the honest boundary is "off unless asked" plus
  a gitignored target. A project that wants redaction can post-process
  the JSONL.
- **Reusing the surprise/rituals ledgers' append path by hand** —
  rejected: `atomicio.append_line` already owns containment, symlink
  refusal and fsync, and the capture is exactly a ledger write.
