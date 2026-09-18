# Agent Note: multi-platform agent hooks — one core, one dialect per platform

Status: implemented
Related: D59, D60

## Problem

D59 wired the plane into agent lifecycle events, but only for Claude
Code: `.claude/settings.json` was the single install target and the
handlers spoke only Claude's output dialect (`hookSpecificOutput`).
Meanwhile hooks went mainstream — Codex CLI, GitHub Copilot CLI, and
Gemini CLI all shipped hook systems, and an adopter whose team standard
on Codex got no presence at all: no pre-tool-use deny, no context
injection, nothing at session start. Researching the official docs
showed why one template could not fit all: the platforms agree that a
hook is "a command fed JSON on stdin," then disagree on the config file
(`.codex/hooks.json` vs `.github/hooks/*.json` vs `.gemini/settings.json`),
the event names (Codex keeps Claude's PascalCase; Copilot is camelCase;
Gemini renames two events), the deny mechanism (Copilot wants top-level
`permissionDecision` keys; Gemini's documented block is exit 2 with the
reason on stderr), and the trust model (Codex silently skips untrusted
project hooks until a human approves them in `/hooks`).

## Decision

One handler core, one DIALECT per platform (D60). `gov agent-hooks
<event> --dialect claude|codex|copilot|gemini` keeps the shared
pipeline; the dialect chooses only the output contract: claude/codex
deny through `hookSpecificOutput.permissionDecision` (Codex's documented
shape is byte-identical to Claude's), codex context as plain-text stdout
(its developer-context channel), copilot deny/context as top-level
`permissionDecision`/`additionalContext` keys, gemini deny as exit 2
with the reason on stderr (its "System Block" — still inside the 0/2
exit-code contract) and gemini context spelling `hookEventName` the way
Gemini fires it (`BeforeAgent`, not `UserPromptSubmit`). Payload
parsing tolerates the two known command-key spellings (`tool_input`
and Copilot's `toolArgs`). `gov init --platforms <list>` (fresh or
retrofitted, `all` allowed, unknown names exit 2) installs one shipped
template per platform — `codex-hooks.json` → `.codex/hooks.json`,
`copilot-hooks.json` → `.github/hooks/govrail.json`,
`gemini-settings.json` → `.gemini/settings.json` — through the same
create-if-missing/named-skip contract, with the D59 four-reader
property intact: init's write, `_inventory`'s drift classification,
uninstall's customized check, and `_template_for` all read the same
template bytes, so every platform's config is exactly reversible
without new uninstall machinery. The manifest records the selection in
a merged `platforms[]` key. Explicit-over-inferred everywhere: the
dialect is written into each platform's hook command at install time,
never guessed from a payload; an explicit `--platforms` list replaces
the claude-only default (today's `--hooks` retrofit behavior is
unchanged), and a bare init installs no platform configs, exactly as
before. Codex's trust step is named at install time because an
untrusted hook is a silent no-op.

## Alternatives considered

Riding Copilot's undocumented Claude-compat mode (it also reads
`.claude/settings.json`) instead of shipping `.github/hooks/govrail.json`
— rejected: the compat path's deny-decision handling is not documented,
so a deny could silently fail open; a first-class file with the
documented top-level keys is checkable. Inferring the dialect from the
payload shape instead of a flag — rejected: two platforms could share a
shape and diverge tomorrow; an explicit flag written by init fails loud
on drift (rule 5). One merged `hooks.json` for all platforms —
impossible: no platform reads another's config, and a translator shim
would add a moving part to every deny. Installing every platform's
config on every init — rejected: files for agents a project doesn't use
are clutter in `_inventory` drift reports; the upgrade report names
what is available instead and `--platforms` stays the deliberate act.
Supporting Cursor/Windsurf/OpenCode in the same batch — deferred: their
contracts need event fan-in (Cursor splits tools across
`beforeShellExecution`/`beforeFileEdit`/…) or an in-process plugin shim
(OpenCode), which is a second design step, not a template.

## Consequences

Adopters on Codex/Copilot/Gemini get the same five-event presence as
Claude Code, and each new platform is now a template plus one
`PLATFORM_TARGETS` entry plus dialect output cases — the structure, not
any single platform, is the deliverable. The gemini deny path exercises
exit 2 as a *deliberate* verdict for the first time; the 0/2 contract
holds, but self-test and the exit-code tests now pin that this specific
exit 2 carries a stderr reason. Windsurf-style platforms that speak no
JSON at all would need only a dialect whose deny is the same exit-2
path — the extension point is deliberately narrow.
