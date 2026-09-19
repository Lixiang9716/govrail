"""Docs ↔ CLI consistency — the command reference cannot drift again.

The README's command block is GENERATED from `gov --help` (one truth:
the descriptions live in gov/commands.py). These tests turn every drift red
in CI: a stale block, a doc citing a command/subcommand/flag that does
not exist, a help description whose subcommand list lags the parser,
or the Chinese README referencing commands the surface no longer has.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gov import audit_notes as an  # noqa: E402
from gov import commands  # noqa: E402

README = REPO / "README.md"
BEGIN = "<!-- gov:commands BEGIN"
END = "<!-- gov:commands END -->"

# The doc set whose `gov ...` citations must resolve. Notes are audited
# by `gov audit-notes` itself (same registry, different lifecycle); this
# set is the hand-maintained prose.
DOCS = [
    "README.md", "README.zh.md", "CONTRIBUTING.md", "CONTRIBUTING.zh.md",
    ".gov/rules.md", "gov/templates/rules.md",
    "gov/templates/notes-README.md", "gov/templates/rejections-README.md",
]
DOCS += glob.glob(str(REPO / ".agents/skills/*/SKILL.md"))
DOCS += glob.glob(str(REPO / "gov/templates/skills/*/SKILL.md"))

SUBS = {
    "note": {"new", "check", "list", "show", "verify", "presence",
             "audit", "archive", "archive-verify"},
    "decision": {"next", "add", "verify"},
    "lease": {"acquire", "release", "list"},
    "verify": {"pairing", "rubric", "conflict-markers", "doc-sync"},
    "task": {"new", "check", "close", "claim", "release", "list"},
    "preset": {"list", "show", "apply"},
    "receipt": {"verify", "show"},
    "hooks": {"pre-commit"},
}
SUB_WORDS = {w for subs in SUBS.values() for w in subs}


def test_readme_command_block_matches_help():
    """The block is the rendered `gov --help` — byte for byte. A stale
    block names the fix: run scripts/update_readme_commands.py."""
    text = README.read_text(encoding="utf-8")
    assert BEGIN in text and END in text, (
        "README lost its generated command block — run "
        "scripts/update_readme_commands.py to insert it")
    env = {**os.environ, "COLUMNS": "80", "PYTHONPATH": str(REPO)}
    proc = subprocess.run(
        [sys.executable, "-m", "gov", "--help"],
        capture_output=True, text=True, encoding="utf-8", env=env)
    rendered = proc.stderr[proc.stderr.find("commands:"):].strip()
    i = text.index(BEGIN)
    j = text.index(END)
    block = text[i:j]
    assert rendered in block, (
        "README's command block is stale against `gov --help` — run "
        "scripts/update_readme_commands.py (never edit the block by hand)")
    for line in rendered.splitlines()[1:]:
        name = line.split()[0]
        assert re.search(rf"^\s+{name}\b", block, re.M), f"missing row: {name}"


def test_readme_carries_exactly_one_command_block():
    """Exactly ONE gov:commands block. The marker text has evolved (it
    names generator/regenerator/verifier) and the regenerator once
    matched markers by exact text — a marker change orphaned the old
    block and INSERTED a duplicate; the derive bot accumulated four on
    master before the fix (recorded in the surprise ledger as
    generated-marker-drift)."""
    text = README.read_text(encoding="utf-8")
    n = text.count(BEGIN)
    assert n == 1, (
        f"README carries {n} gov:commands blocks — duplicates grow when "
        "the marker text changes and the old block is orphaned; collapse "
        "them to one (scripts/update_readme_commands.py now does this "
        "automatically)")


def test_docs_cite_only_real_commands_flags_and_subcommands():
    """Every `gov ...` citation in the doc set resolves: command in the
    CLI table, subcommand in the parser, flags in the registry."""
    # D57 Wave 1: absorbed commands remain REAL (deprecated aliases with
    # identical behavior) — citations of them are valid until Wave 2
    # flips the docs and retires the aliases.
    known = set(commands.COMMANDS) | set(commands.DEPRECATED_ALIASES)
    problems = []
    for rel in DOCS:
        text = (REPO / rel).read_text(encoding="utf-8")
        for m in re.finditer(r"`gov ([a-z][a-z0-9-]*)((?: [^`]*)?)`", text):
            cmd, rest = m.group(1), m.group(2)
            line = text[:m.start()].count("\n") + 1
            where = f"{rel}:{line}"
            if cmd not in known:
                problems.append(f"{where}: unknown command `gov {cmd}`")
                continue
            toks = rest.split()
            if cmd in SUBS and toks and toks[0] in SUB_WORDS:
                if toks[0] not in SUBS[cmd]:
                    problems.append(
                        f"{where}: `gov {cmd} {toks[0]}` — no such subcommand")
                continue
            flags = {t for t in re.findall(
                r"(?<!\w)(?:--[a-z][a-z0-9-]*|-h|-v)", rest) if "<" not in t}
            bad = flags - (an.FLAGS.get(cmd, set()) | an.UNIVERSAL_FLAGS)
            if bad:
                problems.append(f"{where}: unknown flag(s) {sorted(bad)}")
    assert not problems, "\n".join(problems)


def test_help_descriptions_list_the_real_subcommands():
    """A command's one-line help names its subcommands — `note` shipped
    "(new/check)" for two releases after list/show landed; the machine
    catches what the reviewer cannot be expected to count."""
    for cmd, subs in SUBS.items():
        desc = commands.COMMANDS[cmd]
        # every subcommand word must appear in the one-line description
        claimed_words = {w for w in SUB_WORDS if re.search(rf"\b{w}\b", desc)}
        missing = subs - claimed_words
        assert not missing, (
            f"`gov --help`'s {cmd} line omits subcommand(s) "
            f"{sorted(missing)} — update commands.COMMANDS, then run "
            "scripts/update_readme_commands.py")


def test_zh_readme_cites_only_the_real_surface():
    """The Chinese README's curated list cannot outlive the CLI: every
    command it mentions must exist in the generated block too."""
    zh = (REPO / "README.zh.md").read_text(encoding="utf-8")
    en_block = README.read_text(encoding="utf-8")
    i, j = en_block.index(BEGIN), en_block.index(END)
    en_cmds = set(re.findall(r"^  ([a-z][a-z0-9-]*)\b",
                             en_block[i:j], re.M))
    cited = set(re.findall(r"`gov ([a-z][a-z0-9-]*)", zh))
    unknown = {c for c in cited if c not in {"-C", "m"}} - en_cmds
    assert not unknown, (
        f"README.zh.md cites command(s) absent from the generated block: "
        f"{sorted(unknown)}")
