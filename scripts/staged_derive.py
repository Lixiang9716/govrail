#!/usr/bin/env python3
"""Commit-stage derivation: derived truths regenerate, never reject.

The derive machinery (scripts/derive_all.py) owns the push and master
boundaries — CI re-derives on merge, the pre-push DAG catches drift.
This script owns the commit boundary (DSH's "regenerate rather than
reject" lefthook shape): when any staged file is an INPUT to a derived
truth — the CLI surface, the templates, the skills, the rules, the
rejection cases, the derivation tooling itself — the derived truths are
regenerated **now** and the outputs re-staged, so a forgotten
regeneration costs nothing instead of costing a red push.

The regeneration runs the repository's own ``scripts/derive_all.py``
relative to the working directory; a repo without that surface is a
named no-op (the gate is dogfood-only, but it must stay honest outside
its home). Exit codes follow D2: 0 regenerated-or-nothing-to-do, 1 the
derivation itself failed, 2 usage error. Accepts ``--staged`` (the
hook runner appends it to every pre-commit stage gate).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DERIVER = Path("scripts/derive_all.py")
INPUT_PREFIXES = ("gov/", "gov/templates/", ".agents/skills/",
                  ".gov/rules.md", ".gov/rejections/", "scripts/")


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"staged-derive: git {' '.join(args)} failed: {proc.stderr}",
              file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="staged_derive")
    parser.add_argument("--staged", action="store_true",
                        help="accepted from the hook runner; the script "
                             "always judges the index")
    parser.parse_args(argv)

    staged = _git("diff", "--cached", "--name-only",
                  "--diff-filter=ACM").splitlines()
    if not any(f.startswith(p) for f in staged for p in INPUT_PREFIXES):
        print("staged-derive: no derived-truth inputs staged — nothing "
              "to regenerate")
        return 0
    if not DERIVER.is_file():
        print("staged-derive: inputs staged but no scripts/derive_all.py "
              "in this repo — derivation surface absent, skipping "
              "(named, not silent)")
        return 0

    proc = subprocess.run([sys.executable, str(DERIVER)],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(proc.stdout, end="")
        print(proc.stderr, file=sys.stderr)
        print("staged-derive: derivation failed — fix the regenerator, "
              "not the commit", file=sys.stderr)
        return 1
    outputs = [f for f in ("README.md", "examples/demo-project",
                           "docs/i18n")
               if Path(f).exists()]
    changed = _git("status", "--porcelain", "--", *outputs).splitlines()
    if changed:
        _git("add", "--", *outputs)
        print(f"staged-derive: regenerated and restaged "
              f"{len(changed)} path(s)")
    else:
        print("staged-derive: derivation ran, outputs already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
