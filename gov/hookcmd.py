#!/usr/bin/env python3
"""The git-hook gate runners behind the installed hooks.

``gov hooks pre-commit`` is what the pre-commit hook actually executes.
The hook used to hand-wire two gates with ``run_gov <gate> --staged ||
status=1``, which had two defects: it ignored gates.json's
``allowFailure`` (an advisory gate blocked every commit), and it ran
whether or not the project's gate set still contained the gate. Now the
hook delegates to the CONFIGURED contract: every enabled gate that
declares ``"stages": ["pre-commit"]`` runs here against the INDEX (the
gates shipped for this stage all honor ``--staged``), with the same
advisory/blocking semantics the DAG reports.

Exit codes: 0 = green (or nothing configured — a named no-op, never a
silent one); 1 = a blocking gate failed; 2 = gates.json is missing or
invalid (fail loud: a broken constitution is not a green light).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace as _dc_replace

try:  # package context (`gov ...`)
    from . import gates as gates_mod
    from .root import anchor_to_git_root, force_utf8_stdio
except ImportError:  # direct script execution (self-test scratch dirs)
    import gates as gates_mod
    from root import anchor_to_git_root, force_utf8_stdio

PROG = "hooks"


def run_pre_commit() -> int:
    anchor_to_git_root(f"{PROG} pre-commit")
    try:
        _modes, gate_list, _concurrency, _default = gates_mod.load_config("gates.json")
    except gates_mod.ConfigError as e:
        print(f"{PROG} pre-commit: gates.json is invalid: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"{PROG} pre-commit: no gates.json — is this a governed "
              "project? (gov init creates it)", file=sys.stderr)
        return 2

    staged_gates = [g for g in gate_list
                    if g.enabled and "pre-commit" in g.stages]
    if not staged_gates:
        print(f"{PROG} pre-commit: no pre-commit gates configured — add "
              "\"stages\": [\"pre-commit\"] to a gate in gates.json")
        return 0

    failed: list[str] = []
    for g in staged_gates:
        # The hook's domain is the index; the shipped staged gates take
        # --staged. A gate configured for the stage that lacks the flag
        # fails its own run — visible below, not silently skipped.
        gate = _dc_replace(g, command=[*g.command, "--staged"])
        _g, outcome, detail, is_blocking, _duration = gates_mod._run_one(gate)
        blocking = is_blocking and not g.allow_failure
        tag = " (advisory; allowFailure)" if is_blocking and g.allow_failure else ""
        print(f"{outcome} {g.id}{tag}", flush=True)
        if detail and outcome in gates_mod.BLOCKING_OUTCOMES:
            print(f"--- output of {g.id} ---", flush=True)
            print(detail, flush=True)
        if blocking:
            failed.append(g.id)

    if failed:
        print(f"{PROG} pre-commit: {len(failed)} blocking failure(s): "
              + ", ".join(failed), flush=True)
        return 1
    print(f"{PROG} pre-commit: {len(staged_gates)} staged gate(s) ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()
    parser = argparse.ArgumentParser(
        prog="gov hooks",
        description="Git-hook gate runners (installed by gov init --hooks).",
    )
    sub = parser.add_subparsers(dest="subcommand")
    sub.add_parser("pre-commit", help="run the gates whose 'stages' include "
                   "'pre-commit' — the pre-commit hook's entire body")
    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.error("a subcommand is required (pre-commit)")
    if args.subcommand == "pre-commit":
        return run_pre_commit()
    return 2  # unreachable: argparse rejects unknown subcommands


if __name__ == "__main__":
    raise SystemExit(main())
