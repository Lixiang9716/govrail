#!/usr/bin/env python3
"""Derive every derived truth — one entry point, idempotent, checkable.

The truth-source register (docs/truth-sources.md) names the copies that
are MECHANICAL derivations of their truth source. This script
regenerates all of them; it is the single command CI runs:

- README's command block     <- `gov --help`            (update_readme_commands)
- the demo specimen           <- live/template copies     (sync_demo_specimen)
- the i18n pairing examples   <- DEFAULT_CONFIG           (inline below)

`--check` regenerates everything and exits 1 if any tracked file
changed — the CI drift probe. Without it, the regenerated state is
left in the working tree (and the master-push CI job commits it).

Deliberately NOT here: pairing baselines (semantic, human-judged),
seal re-baselines and the ritual ledger (governed acts, not
derivations), and any prose whose judgment a machine cannot own.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

I18N_DOCS = [REPO / "docs/i18n/README.md",
             REPO / "docs/i18n/README.zh.md"]


def _changed_files() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain"],
                         cwd=REPO, capture_output=True, text=True,
                         encoding="utf-8").stdout
    return [line[3:] for line in out.splitlines() if line.strip()]


def derive_i18n_examples() -> int:
    """The pairing example blocks are a COPY of DEFAULT_CONFIG — rewrite
    them in place whenever the constant moves (the pin test catches
    drift; this is the mechanical fix)."""
    sys.path.insert(0, str(REPO))
    from gov.verify_translation_pairing import DEFAULT_CONFIG
    canonical = json.dumps(DEFAULT_CONFIG, indent=2) + "\n"
    changed = 0
    for doc in I18N_DOCS:
        text = doc.read_text(encoding="utf-8")
        def repl(m: re.Match) -> str:
            return f"```json\n{canonical}```"
        new = re.sub(r"```json\n\{.*?\"counterparts\".*?\}\n```",
                     repl, text, count=1, flags=re.S)
        if new != text:
            doc.write_text(new, encoding="utf-8")
            print(f"derived: {doc.name}'s pairing example <- DEFAULT_CONFIG")
            changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (argv or [])
    before = set(_changed_files())

    for script in ("update_readme_commands.py", "sync_demo_specimen.py"):
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / script)],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8")
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            return 2
    derive_i18n_examples()

    drift = [f for f in _changed_files() if f not in before]
    if drift:
        print("derived content changed:")
        for f in sorted(drift):
            print(f"  {f}")
        if check:
            print("derive: REFUSED — derived truths drifted from their "
                  "sources. Run `python scripts/derive_all.py` and commit "
                  "the result (CI on master does this automatically for "
                  "merge pushes).", file=sys.stderr)
            return 1
        print(f"derive: regenerated {len(drift)} file(s)")
    else:
        print("derive: nothing to do — every derived truth is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
