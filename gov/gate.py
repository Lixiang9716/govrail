#!/usr/bin/env python3
"""`gov gate` — gate-set surgery: wire a product gate without hand-editing
JSON (issue #309).

The shipped gates police the governance plane; the gates that make the
plane worth adopting — the project's own test/lint/build commands — are
the one part of the DAG every adopter must author, and until now the
only way to author them was hand-writing JSON against a schema only
``gates.load_config`` knew. ``gov gate add`` makes wiring a gate a
command: validate the pieces (id, command, globs, stages), merge
atomically, validate the merged config through the SAME loader the
runner uses, and prove the gate can run — a red first run is
information, not a wiring error.

The command writes ``gates.json``; in a governed repository that file
is sealed, so the write intentionally does NOT re-baseline the seal
(that is ``gov verify-plane --write``'s recorded decision, never this
command's side effect). The verification run below names the ritual
when the precheck refuses a now-unsealed config.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:  # package context (`gov ...`)
    from . import atomicio
    from .gates import ConfigError, _glob_regex, load_config
except ImportError:  # direct-module execution (self-test scratch dirs)
    import atomicio
    from gates import ConfigError, _glob_regex, load_config

ID_RX = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
STAGES = ("pre-commit", "pre-push")


def _gov_invocation() -> list[str]:
    """How to invoke this same CLI (the verification run)."""
    gov_bin = os.environ.get("GOV_BIN", "")
    if gov_bin:
        return [*gov_bin.split()]
    resolved = shutil.which("gov")
    if resolved:
        return [resolved]
    return [sys.executable, "-m", "gov"]


def cmd_add(args: argparse.Namespace) -> int:
    path = Path("gates.json")
    if not path.is_file():
        print("gate add: no gates.json here — run `gov init` first (or cd "
              "to the project root)", file=sys.stderr)
        return 2
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"gate add: cannot read gates.json: {e}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict) or not isinstance(doc.get("gates", []), list):
        print("gate add: gates.json must be an object with a 'gates' array",
              file=sys.stderr)
        return 2
    if not ID_RX.match(args.id):
        print(f"gate add: invalid gate id {args.id!r} — lowercase "
              "letters/digits, then letters/digits/dots/underscores/hyphens",
              file=sys.stderr)
        return 2
    if any(g.get("id") == args.id for g in doc["gates"] if isinstance(g, dict)):
        print(f"gate add: gate id '{args.id}' already exists in gates.json "
              "(gate id is identity; pick a new one)", file=sys.stderr)
        return 2
    if not args.command:
        print("gate add: a command is required after '--' (the argv the "
              "gate runs)", file=sys.stderr)
        return 2
    for g in args.paths:
        try:
            _glob_regex(g)
        except re.error as e:
            print(f"gate add: invalid glob {g!r}: {e}", file=sys.stderr)
            return 2

    gate: dict = {"id": args.id, "command": list(args.command)}
    if args.description:
        gate["description"] = args.description
    if args.allow_failure:
        gate["allowFailure"] = True
    if args.paths:
        gate["paths"] = list(args.paths)
    if args.stage:
        gate["stages"] = list(args.stage)
    if args.timeout is not None:
        gate["timeoutMs"] = args.timeout
    doc["gates"].append(gate)

    # Mode membership: a gate in no mode never runs in a normal `gov run`
    # — wiring it silently out of the DAG would be the quietest possible
    # regression. Default: the config's own defaultMode. `--mode none`
    # opts out explicitly.
    modes = doc.get("modes") or {}
    default_mode = doc.get("defaultMode")
    wanted = list(args.mode) if args.mode else (
        [default_mode] if default_mode else [])
    for m in wanted:
        if m == "none":
            continue
        if m not in modes:
            print(f"gate add: --mode {m!r}: no such mode in gates.json "
                  f"(known: {', '.join(sorted(modes)) or '(none)'})",
                  file=sys.stderr)
            return 2
    for m in dict.fromkeys(wanted):  # dedupe, keep order
        if m != "none" and args.id not in modes[m]:
            modes[m].append(args.id)
    if wanted:
        doc["modes"] = modes

    if args.dry_run:
        # #366: reporting the exact wiring command in a PR body, and
        # confirming it, must not drift a sealed gates.json. Everything
        # above validated the same pieces the real run validates; this
        # stops short of the write and the verification run.
        print("gate add: dry run — gates.json is untouched, nothing ran")
        print(f"  entry: {json.dumps(gate, ensure_ascii=False)}")
        memberships = [m for m in dict.fromkeys(wanted) if m != "none"]
        print("  modes: " + (", ".join(memberships) if memberships
                             else "(none — the gate runs only via "
                                  "--gate/--every-gate)"))
        print(f"  verify with: {' '.join(_gov_invocation())} run --gate "
              f"{args.id}")
        return 0

    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    # Rule 6 in spirit: the merged config must pass the runner's own
    # schema loader BEFORE it lands — never write a gates.json the next
    # `gov run` would refuse to parse.
    fd, tmp = tempfile.mkstemp(dir=".", suffix=".gates.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        load_config(tmp)
    except ConfigError as e:
        print(f"gate add: refused — merged gates.json fails schema "
              f"validation: {e}", file=sys.stderr)
        return 2
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    atomicio.write_text(path, text)
    where = f", mode(s): {', '.join(dict.fromkeys(wanted))}" if wanted else ""
    print(f"gate add: wired '{args.id}' into gates.json{where}")
    print(f"  runs: {' '.join(args.command)}")

    # Prove the gate can run — the wiring is not done until the DAG has
    # executed it once (a red verdict is information, not a wiring error;
    # a refusal is the seal speaking, and the ritual is named).
    proc = subprocess.run(
        [*_gov_invocation(), "run", "--gate", args.id],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode == 0:
        print(f"gate add: verification run green — '{args.id}' is live in "
              "the DAG")
        return 0
    if "drifted from its seal" in (proc.stderr or ""):
        print("gate add: the verification run was REFUSED by the plane's "
              "out-of-band seal check — editing gates.json in a governed "
              "repo is a constitution change. Review the diff, then accept "
              "it explicitly: gov verify-plane --write", file=sys.stderr)
    else:
        print(f"gate add: gate '{args.id}' is wired and its verification "
              "run is RED — the output above is the evidence; fix the "
              "command or the code it judges", file=sys.stderr)
    return 1 if proc.returncode == 1 else proc.returncode or 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gov gate",
        description="Gate-set surgery: wire a product gate into gates.json "
                    "with schema validation and a verification run, never "
                    "hand-editing JSON.",
    )
    sub = parser.add_subparsers(dest="cmd", metavar="<subcommand>")
    p_add = sub.add_parser(
        "add", help="add a gate to gates.json (validated, verified)",
        # #366: the grammar was documented only in a source comment, so
        # `--help` did not say where the command goes — and agents and CI
        # wrappers enumerate help output, not source.
        usage="gov gate add <id> [options] -- <command...>",
        epilog="The gate's own argv goes after a standalone '--' (or after "
               "--command):\n"
               "  gov gate add tests --paths 'tests/**' -- pytest -q\n"
               "  gov gate add lint --mode quick -- ruff check .\n"
               "Options before the separator configure the gate; everything "
               "after it is the argv the gate runs, verbatim. "
               "--dry-run validates and prints without writing.")
    p_add.add_argument("id", help="gate id (lowercase; identity in the DAG)")
    p_add.add_argument("--paths", action="append", default=[], metavar="GLOB",
                       help="scope the gate to files matching this glob "
                            "(repeatable; unset = always run)")
    p_add.add_argument("--stage", action="append", default=[],
                       choices=list(STAGES), metavar="STAGE",
                       help="also ride this git-hook stage "
                            f"({', '.join(STAGES)}; repeatable)")
    p_add.add_argument("--description", default="", metavar="TEXT",
                       help="one-line contract shown on the failure line")
    p_add.add_argument("--mode", action="append", default=[], metavar="MODE",
                       help="join this mode (repeatable; default: the "
                            "config's defaultMode; 'none' skips modes)")
    p_add.add_argument("--allow-failure", action="store_true",
                       help="advisory: failures are reported, never block")
    p_add.add_argument("--timeout", type=int, default=None, metavar="MS",
                       help="kill the gate after this many milliseconds")
    p_add.add_argument("--dry-run", action="store_true",
                       help="validate and PRINT the gate entry, the mode "
                            "changes and the verification argv — write "
                            "nothing, run nothing (nothing touches a "
                            "sealed gates.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    # Split at the first standalone '--' BEFORE argparse: everything after
    # it is the gate's raw argv (the issue's grammar puts the command last),
    # and argparse must never see a REMAINDER positional — it swallows the
    # options that follow the positional id.
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    elif "--command" in argv:
        # #366: a caller that builds argv programmatically cannot always
        # emit a bare '--' positionally; the named separator is the same
        # grammar with an explicit spelling.
        split = argv.index("--command")
        argv, command = argv[:split], argv[split + 1:]
    else:
        command = []
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help(sys.stderr)
        print("gov gate: a subcommand is required (add)", file=sys.stderr)
        return 2
    if args.cmd == "add":
        args.command = command
        return cmd_add(args)
    print(f"gov gate: unknown subcommand '{args.cmd}' (known: add)",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
