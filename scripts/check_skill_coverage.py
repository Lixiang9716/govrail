#!/usr/bin/env python3
"""Skill-coverage gate: the router skill must name every shipped command.

Rule 9's third discovery-surface home is the ``govrail`` skill's stage
table — the one surface agents actually enumerate. Its coverage was the
last command-vocabulary relation held together by prose discipline, and
the stragglers rule 9's note predicted did appear (eight shipped commands
were invisible to the skill when this gate landed). The pre-agreed fix
was this gate: every key of ``COMMANDS`` in ``gov/commands.py`` must
appear as ``gov <cmd>`` in the skill, or carry an explicit exclusion with
a reason in ``scripts/skill-coverage.json`` — a reasoned, visible
declaration, never a silent omission.

Like its sibling checkers (size-limits, import-layers) this script reads
both truths from ``--root`` — the checkout under judgment, not the
installed package — so a rejection case can prove the gate red on a
scratch tree. The registry is read with ``ast`` (a data literal, no gov
import needed); a registry this checker cannot parse fails loud (rule 5).
Exit codes follow D2: 0 routed, 1 missing coverage (each gap named with
its fix), 2 config/usage error.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / "skill-coverage.json"


def load_config(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"skill-coverage: unreadable config {path}: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(raw, dict):
        print(f"skill-coverage: {path} must be a JSON object", file=sys.stderr)
        raise SystemExit(2)
    unknown = set(raw) - {"registry", "skill", "exclusions"}
    if unknown:
        # rule 5: a misspelled key would silently stop meaning anything.
        print(f"skill-coverage: {path}: unknown key(s) "
              f"{', '.join(sorted(unknown))}", file=sys.stderr)
        raise SystemExit(2)
    for key in ("registry", "skill"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            print(f"skill-coverage: {path}: '{key}' must be a non-empty "
                  f"repo-relative path", file=sys.stderr)
            raise SystemExit(2)
    exclusions = raw.get("exclusions")
    if not isinstance(exclusions, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip()
            for k, v in exclusions.items()):
        print(f"skill-coverage: {path}: 'exclusions' must map command "
              f"names to non-empty reasons", file=sys.stderr)
        raise SystemExit(2)
    return raw


def read_commands(path: Path) -> dict:
    """The COMMANDS panel, ast-read from the registry under judgment."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as e:
        print(f"skill-coverage: cannot read registry {path}: {e}",
              file=sys.stderr)
        raise SystemExit(2)
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else (node.target,) if isinstance(node, ast.AnnAssign)
                   else ())
        if not any(isinstance(t, ast.Name) and t.id == "COMMANDS"
                   for t in targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and value.func is not None:
            value = value.args[0] if value.args else value
        try:
            commands = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            commands = None
        if (not isinstance(commands, dict) or not commands
                or not all(isinstance(k, str) for k in commands)):
            print(f"skill-coverage: {path}: COMMANDS is not a readable "
                  f"non-empty dict of names — the registry grew a form "
                  f"this checker cannot judge; extend the checker in the "
                  f"same change (rule 5)", file=sys.stderr)
            raise SystemExit(2)
        return commands
    print(f"skill-coverage: {path}: no top-level COMMANDS assignment found",
          file=sys.stderr)
    raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_skill_coverage")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root to judge (default: this checkout)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    root = Path(args.root)
    config = load_config(Path(args.config))

    commands = read_commands(root / config["registry"])
    skill_path = root / config["skill"]
    try:
        skill_text = skill_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"skill-coverage: cannot read skill {skill_path}: {e}",
              file=sys.stderr)
        raise SystemExit(2)

    exclusions = config["exclusions"]
    stale = sorted(set(exclusions) - set(commands))
    if stale:
        print(f"skill-coverage: exclusion(s) {', '.join(stale)} name no "
              f"COMMANDS entry — a stale exclusion silently stops meaning "
              f"anything; remove it", file=sys.stderr)
        return 2

    missing = []
    for cmd in sorted(commands):
        if cmd in exclusions:
            continue
        if not re.search(rf"\bgov {re.escape(cmd)}(?![\w-])", skill_text):
            missing.append(cmd)

    if missing:
        for cmd in missing:
            print(f"skill-coverage: command '{cmd}' is not routed in "
                  f"{config['skill']} — add a stage-table line, or declare "
                  f"a reasoned exclusion in scripts/skill-coverage.json",
                  file=sys.stderr)
        print(f"skill-coverage: {len(missing)} of {len(commands)} shipped "
              f"command(s) invisible to the router skill (rule 9)",
              file=sys.stderr)
        return 1
    routed = len(commands) - len(exclusions)
    print(f"skill-coverage: {routed}/{len(commands)} commands routed in "
          f"{config['skill']} ({len(exclusions)} excluded with reason)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
