"""Pin audit-notes' flag registry to each command's real ``--help`` surface.

D28 chose a static registry over deriving flags from argparse at run time,
on the promise that tests would pin the table. The pin was never written
for the flag side, and the registry drifted: init gained ``--adopt`` /
``--preview`` / ``--json`` while the table still described 0.12-era init,
so notes documenting *working* runs were reported as dead commands
(issue #101). This module is the missing pin: for every command,
``gov <cmd> --help`` must list exactly the registered flags — no more
(false signals), no fewer (silent skips).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from gov import audit_notes, cli

REPO = Path(__file__).resolve().parent.parent
# Option-entry lines: exactly two spaces of indent, then the flag. Help-text
# continuations indent to the help column, and prose like "git diff
# --cached" lives there — only entry lines count (issue #101's probe).
OPTION_LINE_RX = re.compile(r"^  (?:-h |--help |--[\w-]+)")
LEADING_DASH_RX = re.compile(r"((?:-h|--[\w-]+)(?:,\s*(?:-h|--[\w-]+))*)(?=\s|$)")
# Commands whose flags live on a subparser: probe that parser's help.
# A command may split flags across several subcommands (decision's --count
# lives on `next`, --from/--id on `add`) — every listed surface is probed
# and the registry must equal the union (#107).
HELP_ARGV: dict[str, list[list[str]]] = {
    "note": [["note", "new", "--help"]],  # --class/--ref are `note new` flags
    "decision": [["decision", "next", "--help"],
                 ["decision", "add", "--help"]],
    # --check/--rules live on `new`; --mode/--timeout on `close`;
    # --agent/--ttl/--wait on `claim` and --agent on `release`; --json on
    # `list` (#125's claim semantics)
    "task": [["task", "new", "--help"], ["task", "close", "--help"],
             ["task", "claim", "--help"], ["task", "release", "--help"],
             ["task", "list", "--help"]],
    "receipt": [["receipt", "verify", "--help"],   # --record is verify's
                ["receipt", "show", "--help"]],    # --commit is show's
    "preset": [["preset", "apply", "--help"]],     # --project is apply's
}


def _listed_flags(cmd: str) -> tuple[set[str], str]:
    surfaces = HELP_ARGV.get(cmd, [[cmd, "--help"]])
    listed: set[str] = set()
    outs: list[str] = []
    for argv in surfaces:
        proc = subprocess.run(
            [sys.executable, "-m", "gov", *argv],
            cwd=REPO, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        assert proc.returncode == 0, f"gov {argv} --help failed: {proc.stderr}"
        outs.append(proc.stdout)
        in_options = False
        for line in proc.stdout.splitlines():
            if re.fullmatch(r"(options|optional arguments):", line.strip()):
                in_options = True
                continue
            if in_options and OPTION_LINE_RX.match(line):
                m = LEADING_DASH_RX.match(line[2:])
                if m:
                    listed.update(t.strip() for t in m.group(1).split(","))
    return listed - audit_notes.UNIVERSAL_FLAGS, "\n".join(outs)


@pytest.mark.parametrize("cmd", sorted(cli._COMMANDS))
def test_registry_matches_help_options(cmd):
    """`gov <cmd> --help` options == audit_notes.FLAGS[cmd].

    Both directions are regressions: a listed-but-unregistered flag means
    false `unknown flag` signals on working commands (issue #101); a
    registered-but-unlisted flag means the check silently misses typos.
    """
    listed, out = _listed_flags(cmd)
    registered = audit_notes.FLAGS[cmd]
    assert listed == registered, (
        f"`gov {cmd} --help` lists {sorted(listed)} but the registry has "
        f"{sorted(registered)} — move the flag in both places "
        f"(gov/audit_notes.py and the command's help). Help output:\n{out}"
    )


@pytest.mark.parametrize("cmd, flags", sorted(cli.COMMAND_FLAGS.items()))
def test_hand_parsed_help_lists_every_flag(cmd, flags):
    """The hand-parsed trio's help table must not lag its own parser:
    every flag the parser accepts appears in `gov <cmd> --help` output."""
    _, out = _listed_flags(cmd)
    for name, _ in flags:
        flag = name.split()[0]  # drop the metavar ("--project DIR" → --project)
        assert flag in out, f"`gov {cmd} --help` does not list {flag}"


def test_init_accepts_every_registered_flag(tmp_path):
    """The registry's init entry is not just plausible prose: the hand
    parser accepts each registered flag in one run (and still rejects an
    unknown one) — the acceptance probe behind issue #101's report."""
    import subprocess as sp
    sp.run(["git", "init", "-q", "."], cwd=tmp_path, capture_output=True)
    ok = sp.run(
        [sys.executable, "-m", "gov", "init",
         "--project", ".", "--hooks", "--ci", "--upgrade", "--json",
         "--adopt", "all", "--preview"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
        env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin",
             "HOME": str(tmp_path)}, encoding="utf-8", errors="replace")
    assert "unexpected argument" not in ok.stderr, ok.stderr
    dead = sp.run(
        [sys.executable, "-m", "gov", "init", "--nonexistent"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60,
        env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin",
             "HOME": str(tmp_path)}, encoding="utf-8", errors="replace")
    assert dead.returncode == 2
    assert "unexpected argument '--nonexistent'" in dead.stderr
