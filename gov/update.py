#!/usr/bin/env python3
"""`gov update` — one deliberate, documented migration step (#259's ask).

The pieces of a plane migration already existed as separate commands
(`gov init --upgrade` reports, `--adopt` lands templates, `--adopt-new`
merges new shipped gates, `gov verify-plane --write` re-baselines the
seal) — but the dsh-mobile migration proved the step LIST is fixed and
mechanical: adopt → merge → refresh the CI pin → ignore the trend
ledger → re-seal (the ritual) → align the manifest → commit. This
command performs exactly that list, in that order, with the seal
re-baseline behind the same consent verify-plane always required.

Dry run by default: without ``--apply`` it prints the plan and changes
nothing. Never touches customized gates content (the merge is additive
by id), customized workflow files (only the ``pip install govrail``
install line is rewritten), or history (dated records keep their
vocabulary).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from . import atomicio
    from . import gitutil, verify_plane
    from .version import __version__
except ImportError:  # direct script execution
    import atomicio
    import gitutil, verify_plane
    from version import __version__


def _ci_pin_refresh(root: Path, version: str) -> tuple[int, str]:
    """Rewrite the workflow's `pip install govrail` line(s) to the new
    version — in place, line-level, so a customized-but-pinned workflow
    keeps its comments. Returns (count, note)."""
    wf = root / ".github" / "workflows" / "gov.yml"
    if not wf.is_file():
        return 0, "absent"
    lines = wf.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    for i, line in enumerate(lines):
        if "pip install govrail" in line:
            new = re.sub(r"(pip install govrail)\S*",
                         rf"\1=={version}", line)
            if new != line:
                lines[i] = new
                changed += 1
    if changed:
        atomicio.write_bytes(wf, "".join(lines).encode("utf-8"), root=root)
    return changed, "refreshed"


def _gitignore_history(root: Path) -> bool:
    """Append the trend-ledger ignore line when missing (#254). False
    when .gitignore is a symlink (N13: never write through a link)."""
    gi = root / ".gitignore"
    if gi.is_symlink():
        print("gov update: .gitignore is a symlink — add '.gov/history/' "
              "to the file it points at yourself", file=sys.stderr)
        return False
    line = ".gov/history/"
    if gi.exists():
        raw = gi.read_bytes()
        if line in raw.decode("utf-8-sig", errors="replace").splitlines():
            return True
        sep = b"" if (not raw or raw.endswith(b"\n")) else b"\n"
        atomicio.write_bytes(gi, raw + sep + line.encode("utf-8") + b"\n",
                             root=root)
        return True
    atomicio.write_bytes(gi, line.encode("utf-8") + b"\n", root=root)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gov update",
        description="One deliberate migration step: adopt missing/moved "
                    "templates, merge newly shipped gates, refresh the CI "
                    "pin, re-seal the plane. Dry run by default; --apply "
                    "executes.")
    parser.add_argument("--apply", action="store_true",
                        help="execute the migration (default: dry run)")
    parser.add_argument("--confirm-unattended", action="store_true",
                        help="consent to the seal re-baseline from a "
                             "non-interactive shell (agents)")
    args = parser.parse_args(argv)

    from .gitutil import toplevel
    root = toplevel()
    if root is None:
        print("gov update: not a git repository — the migration needs a "
              "checkout so its changes are reviewable in isolation",
              file=sys.stderr)
        return 2
    root = Path(root)
    manifest_path = root / ".gov" / "manifest.json"
    if not manifest_path.is_file():
        print(f"gov update: no {manifest_path.relative_to(root).as_posix()} "
              "— nothing to update (gov init first)", file=sys.stderr)
        return 2

    from . import cli as cli_mod
    files_out, old_version, _tpl = cli_mod._upgrade_files(root, manifest_path)
    if files_out is None:
        print("gov update: the manifest is unreadable — see "
              "`gov init --upgrade`", file=sys.stderr)
        return 2
    adoptable = [f["path"] for f in files_out if f["adoptable"]]

    # preconditions, BEFORE any mutation
    status = gitutil.git("status", "--porcelain",
                         "--untracked-files=no")
    if status.returncode != 0 or status.stdout.strip():
        print("gov update: REFUSED — the worktree has uncommitted tracked "
              "changes; commit or stash first so this migration's own "
              "changes are reviewable in isolation", file=sys.stderr)
        return 2
    if args.apply and not (args.confirm_unattended
                           or sys.stdin.isatty()):
        print("gov update: REFUSED — the seal re-baseline needs consent: "
              "run from an interactive terminal, or pass "
              "--confirm-unattended", file=sys.stderr)
        return 2

    # the plan (always printed — the dry run IS the deliverable until
    # --apply says otherwise)
    print(f"gov update — migration plan for {root}")
    print(f"  initialized with govrail {old_version} · "
          f"this package {__version__}")
    print(f"  adopt: {len(adoptable)} file(s) "
          f"({', '.join(adoptable) if adoptable else 'none'})")
    print("  gates.json: adopt-new merge (additive — new shipped gate ids "
          "only, your gates untouched)")
    print("  ci pin: rewrite `pip install govrail...` to "
          f"=={__version__} (line-level; custom files keep their shape)")
    print("  gitignore: ensure .gov/history/ is ignored")
    print("  seal: re-baseline over the migrated files (ritual, recorded "
          "in .gov/rituals.jsonl)")
    print(f"  manifest: version {old_version} → {__version__}")
    if not args.apply:
        print("gov update: dry run — pass --apply to execute")
        return 0

    if adoptable:
        rc = cli_mod._adopt(root, manifest_path, adoptable, preview=False)
        if rc != 0:
            return rc

    # additive-only merge of newly shipped gates (D39's mechanism)
    gates_path = root / "gates.json"
    if gates_path.is_file():
        rc = cli_mod._adopt_new(root, manifest_path, "gates.json")
        if rc not in (0,):
            return rc

    changed, _note = _ci_pin_refresh(root, __version__)
    print(f"gov update: ci pin — {changed} install line(s) refreshed")
    _gitignore_history(root)

    # manifest version LAST before the seal: the re-baseline snapshots
    # the migrated state, version stamp included
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = __version__
    atomicio.write_text(manifest_path,
                        json.dumps(manifest, indent=2) + "\n", root=root)

    files = verify_plane._sealed_files(root)
    unattended = args.confirm_unattended or not sys.stdin.isatty()
    verify_plane.baseline(root, unattended=unattended)
    from . import rituals
    try:
        rituals.append(root, ritual="seal-rebaseline",
                       unattended=unattended,
                       files=sorted(files))
    except OSError as e:
        print(f"gov update: WARNING — the re-baseline could not be "
              f"recorded in the tracked ledger: {e}; the seal itself "
              "is updated, but the audit trail needs a manual entry",
              file=sys.stderr)

    try:
        from . import whatsnew
        whatsnew.main(["--since", old_version])
    except SystemExit:
        pass

    print("gov update: done — commit these changes now")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
