#!/usr/bin/env python3
"""The command-name registries, in one home.

Every surface that names gov commands reads from here, so the vocabularies
can never drift apart:

- ``COMMANDS`` — the top-level command panel: ``gov --help`` renders it,
  ``gov <unknown>`` points back at it, audit-notes treats it as the set of
  known commands, and the exit-code contract test
  (``tests/test_exit_code_contract.py``) walks it as its mother list.
- ``DEPRECATED_ALIASES`` — the D57 Wave-1 absorbed commands, still working
  with one deprecation line; audit-notes counts them as known (a note
  citing ``gov verify-notes`` describes a run that can still happen).
- ``HELP_FLAGS`` / ``VERSION_FLAGS`` / ``NO_FORWARD`` — the help/version
  contract shared by the dispatcher's intercept paths.
- ``COMMAND_FLAGS`` — the declared flag surface of the hand-parsed
  commands (no argparse to print their options): ``gov <cmd> --help``
  renders it and audit-notes' flag registry is pinned to it (issue #101).

Was ``gov/cli.py`` internals (``_COMMANDS`` and friends) until the
registry moved here — cli.py is the dispatcher, not the vocabulary.
"""
from __future__ import annotations

HELP_FLAGS = ("-h", "--help", "help")
VERSION_FLAGS = ("-v", "--version", "version")
# Commands whose args are NOT forwarded to an argparse parser: they must
# intercept help/version themselves so a trailing flag never runs the action.
NO_FORWARD = ("init", "uninstall", "verify-notes")

# Wave-1 consolidation (D57): the 13 absorbed top-level commands keep
# working as aliases — same behavior, one deprecation line on stderr.
# The alias goes away after a full deprecation window (two minors).
DEPRECATED_ALIASES = {
    "verify-notes": ["note", "verify"],
    "verify-note-presence": ["note", "presence"],
    "audit-notes": ["note", "audit"],
    "archive-notes": ["note", "archive"],
    "verify-archive": ["note", "archive-verify"],
    "verify-decisions": ["decision", "verify"],
    "verify-pairing": ["verify", "pairing"],
    "verify-rubric": ["verify", "rubric"],
    "verify-conflict-markers": ["verify", "conflict-markers"],
    "verify-doc-sync": ["verify", "doc-sync"],
    "acquire": ["lease", "acquire"],
    "release": ["lease", "release"],
    "locks": ["lease", "list"],
}

def deprecated_in(command: list[str]) -> tuple[str, list[str]] | None:
    """The deprecated alias a gate command uses, or None (#274).

    Scans for a ``gov`` token (command[0] in the common shape, but a
    ``python -m gov …`` wrapper is equally governed) and names the alias
    that follows it, together with its replacement — the migration-assist
    surfaces (``gov init --upgrade``, ``gov doctor``) read this so a
    renamed command can never silently strand an adopter's gates.json.
    """
    for i, tok in enumerate(command[:3]):
        if tok == "gov" and i + 1 < len(command) \
                and command[i + 1] in DEPRECATED_ALIASES:
            return command[i + 1], list(DEPRECATED_ALIASES[command[i + 1]])
    return None


COMMANDS = {
    "init": "inject the plane into a project (--hooks/--ci add runners; --hooks "
            "--pre-commit adds the opt-in commit-stage gates; --adopt-new "
            "merges new shipped gates; --upgrade shows template drift; "
            "installs .claude/settings.json agent hooks unless one exists)",
    "uninstall": "reverse init",
    "run": "run the project's gate DAG (args forwarded to gates.py; "
           "--receipt records a tamper-evident run receipt, #124; "
           "--merge preflights the union of parallel branches in a "
           "scratch worktree before landing)",
    "gate": "gate-set surgery (add): wire a product gate into gates.json "
            "with schema validation and a verification run — no "
            "hand-edited JSON (#309)",
    "self-test": "run governance rejection cases",
    "receipt": "verifiable run receipts (verify/show): verify a cited "
               "receipt against a commit (issue #124/D42)",
    "agent-hooks": "agent lifecycle hooks (session-start/pre-tool-use/"
                   "post-tool-use/user-prompt-submit/stop — context "
                   "injection, a configurable deny set, an advisory on "
                   "stop; a presence, not the enforcement; claude/codex/"
                   "copilot/gemini dialects)",
    "verify-plane": "tamper-evidence for the plane's own config "
                    "(rules.md, gates.json, pairing/decisions/surfaces, "
                    ".gov/rejections/**; --write re-baselines — interactive "
                    "consent, --confirm-unattended for agents)",
    "hooks": "git-hook gate runners (the installed hooks delegate here; "
             "'hooks pre-commit' runs the gates whose 'stages' include "
             "'pre-commit' under their configured advisory/blocking contract)",
    "doctor": "environment self-check (PATH, python, hooks, gates schema)",
    "note": "note scaffold, read side, and the notes gates "
            "(new/check/list/show/verify/presence/audit/archive/"
            "archive-verify; list --stale marks audit signals)",
    "decision": "decision-row tooling (next/add/verify: next free D-number; "
                "atomic validated add; table structure guard)",
    "lease": "lease locks for parallel agents (acquire/release/list; "
             "busy exits 3; --wait S polls, --ttl S bounds the lease)",
    "verify": "content gates without a family hub (pairing/rubric/"
              "conflict-markers/doc-sync)",
    "check": "syntax-class static checks over the parse layer (shipped + "
             ".gov/checks/ rules; suppressions counted; --strict makes "
             "warnings block)",
    "parse": "per-file structure facts from the parse layer (function "
             "spans, line counts, nesting depth) — facts, not verdicts; "
             "the primitive a size/complexity gate reads (#265)",
    "review": "assemble the review dossier for a diff (scope, notes, recall, rubric)",
    "trend": "gate duration trends from .gov/history/ (p50 per window; --by-tag splits per caller, --cost rolls up caller-reported cost)",
    "stats": "structural facts per language (lines, symbols, nesting depth) from the parse layer — facts, not verdicts; --record appends to the stats ledger",
    "whatsnew": "usage-oriented highlights since a version",
    "recall": "retrieve notes, decisions, and postmortems (all terms, ranked)",
    "change-scope": "report touched surfaces (e.g. --base <ref>)",
    "surprise": "the surprise ledger (record/list): expectation vs reality, counted per signature; rule 11 — the third occurrence of a signature escalates into a process improvement",
    "task": "task cards for subagent briefs (new/check/close/claim/release/"
            "list; rules@hash pin + checklist + green-run receipt; claim/"
            "release lease a card so two workers cannot take one)",
    "preset": "typed adoption bundles (list/show/apply): a project type's "
              "gates, skills, and manifest hints — additive, never "
              "overwriting (D53)",
    "update": "one deliberate migration step: adopt missing/moved "
              "templates, merge newly shipped gates, refresh the CI pin, "
              "re-seal the plane (dry run by default; --apply executes; "
              "the seal needs --confirm-unattended or a TTY)",
}

# The hand-parsed commands have no argparse to print their options, so the
# surface is declared here as data: `gov <cmd> --help` shows it, and
# audit-notes' flag registry is pinned to it (tests/test_flag_registry.py,
# issue #101 — the terse one-line summary in COMMANDS is a description,
# never the machine-checked surface).
COMMAND_FLAGS: dict[str, tuple[tuple[str, str], ...]] = {
    "init": (
        ("--project DIR", "target project root (default: current directory)"),
        ("--hooks", "add the git hooks runner (needs a git repository)"),
        ("--pre-commit", "with --hooks: also install the optional pre-commit "
                         "hook — cheap content gates (pairing sidecar freshness, "
                         "conflict markers) on the staged files (#110)"),
        ("--ci", "add the CI runner (.github/workflows/gov.yml)"),
        ("--platforms LIST", "install agent-hook configs for the named "
                             "platforms (claude, codex, copilot, gemini; "
                             "'all' = every one) — fresh or retrofitted, "
                             "create-if-missing (D60)"),
        ("--upgrade", "report template drift; reads, never writes"),
        ("--json", "with --upgrade: exactly one machine-readable report"),
        ("--adopt [FILE...]", "land MISSING template files, never overwrite "
                              "a customized one ('all' = every missing file)"),
        ("--adopt-new FILE", "merge only the NEW shipped entries of a "
                             "customized gates.json into yours (additive by "
                             "gate id; non-additive drift is refused)"),
        ("--preset NAME", "with init (fresh or already-initialized): apply "
                          "the preset right after — typed gates, skills, "
                          "and manifest hints, additive (see `gov preset "
                          "list`; D53)"),
        ("--preview", "with --adopt: show what would land, write nothing"),
    ),
    "uninstall": (
        ("--project DIR", "target project root (default: current directory)"),
        ("--force", "also delete customized files that differ from the "
                    "shipped template (without it, nothing is deleted)"),
    ),
    "verify-notes": (),
}
