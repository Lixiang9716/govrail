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


def _ci_pin_plan(root: Path, version: str) -> str:
    wf = root / ".github" / "workflows" / "gov.yml"
    if not wf.is_file():
        return "absent"
    text = wf.read_text(encoding="utf-8")
    n = sum(1 for line in text.splitlines()
            if "pip install govrail" in line)
    return (f"refresh {n} install line(s) to =={version}"
            if n else "no govrail install line found — nothing to refresh")


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
    lines = [".gov/history/", ".gov/last-run/"]
    if gi.exists():
        raw = gi.read_bytes()
        have = raw.decode("utf-8-sig", errors="replace").splitlines()
        missing = [ln for ln in lines if ln not in have]
        if not missing:
            return True
        sep = b"" if (not raw or raw.endswith(b"\n")) else b"\n"
        atomicio.write_bytes(
            gi, raw + sep
            + b"\n".join(ln.encode("utf-8") for ln in missing) + b"\n",
            root=root)
        return True
    atomicio.write_bytes(
        gi, b"".join(ln.encode("utf-8") + b"\n" for ln in lines), root=root)
    return True


def _update_left_pristine_drift(root: Path, adoptable: set[str]) -> bool:
    """#321: did an interrupted `gov update --apply` leave this drift?

    True when the manifest already names the RUNNING version and every
    drifted file is byte-identical to the shipped template it was
    adopted from (gov.yml compared as-written, with the version pin
    substituted). Only that exact shape may resume; anything else stays
    a launder refusal."""
    try:
        manifest = json.loads(
            (root / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if manifest.get("version") != __version__:
        return False
    from . import plane as plane_mod
    created = set(manifest.get("created", [])) | adoptable
    for rel in sorted(created):
        tpl = plane_mod._template_for(rel)
        if tpl is None:
            continue
        p = root / rel
        if not p.is_file():
            continue
        if p.name == "gov.yml":
            rendered = tpl.read_text(encoding="utf-8").replace(
                "__GOV_VERSION__", __version__).encode("utf-8")
            if p.read_bytes() != rendered:
                return False
        elif p.read_bytes() != tpl.read_bytes():
            return False
    return True


def _rewire_executed_hooks(root: Path) -> int:
    """#331: adoption refreshes ``.gov/hooks/<name>``; the EXECUTED copy
    (``core.hooksPath`` or the common dir's ``hooks/``) was never
    re-wired, so an upgraded plane kept running the old hook body —
    deprecation warnings today, dead command spellings the day the
    aliases go, and gates.json's stages/allowFailure contract bypassed
    the whole time. Same bytes as the tracked copy, same mode; a file
    that is NOT a gov hook (no ``# govrail:`` marker) is left alone.
    """
    resolved = gitutil.hooks_dir()
    if resolved is None:
        return 0
    dest_dir = Path(resolved)
    rewired = 0
    for name in ("pre-push", "pre-commit"):
        src = root / ".gov" / "hooks" / name
        if not src.is_file():
            continue
        dest = dest_dir / name
        data = src.read_bytes()
        if dest.is_file():
            try:
                if dest.read_bytes() == data:
                    continue
                foreign = "# govrail:" not in dest.read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                continue
            if foreign:
                continue  # someone replaced it — their hook, not ours
        dest_dir.mkdir(parents=True, exist_ok=True)
        atomicio.write_bytes(dest, data)
        dest.chmod(0o755)
        rewired += 1
    return rewired


def _refresh_tracked_hooks(root: Path) -> int:
    """#373: the drift note promised ``--apply`` re-wires the hook, but
    only the EXECUTED copy was ever touched (#331) — and it was re-wired
    from the tracked copy, which itself was still the old version's
    bytes. ``gov init --hooks`` always re-installs from the shipped
    template; the migration step now does the same for the tracked
    copies first, so both copies end on this version's template. The
    contract is init's own: a copy that is not a gov hook (no
    ``# govrail:`` marker) is someone else's — named skip, never
    overwritten.
    """
    from importlib.resources import files as _res_files
    refreshed = 0
    for name in ("pre-push", "pre-commit"):
        tracked = root / ".gov" / "hooks" / name
        if not tracked.is_file() or tracked.is_symlink():
            continue
        try:
            body = tracked.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "# govrail:" not in body:
            continue  # a foreign hook — none of our business
        tpl = _res_files("gov.templates").joinpath(name)
        try:
            current = tpl.read_bytes()
        except (OSError, FileNotFoundError):
            continue
        if tracked.read_bytes() == current:
            continue
        atomicio.write_bytes(tracked, current, root=root)
        refreshed += 1
    return refreshed


def _hook_drift_notes(root: Path) -> list[str]:
    """#324: installed gov hooks from an EARLIER plane keep invoking
    retired spellings — after the D57 renames, an unrefreshed pre-commit
    emitted a deprecation warning per commit on the canonical gates.
    Named here so the upgrade report says the one command that fixes it."""
    notes: list[str] = []
    from importlib.resources import files as _res_files
    resolved = gitutil.hooks_dir()
    if resolved is None:
        return notes
    hooks_dir = Path(resolved)
    for name in ("pre-push", "pre-commit"):
        installed = hooks_dir / name
        if not installed.is_file():
            continue
        try:
            body = installed.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "# govrail:" not in body:
            continue  # a foreign hook — none of our business
        tpl = _res_files("gov.templates").joinpath(name)
        try:
            current = tpl.read_text(encoding="utf-8")
        except (OSError, FileNotFoundError):
            continue
        if body != current:
            notes.append(
                f"hook drift: your installed {name} differs from this "
                "version's template — an older hook keeps calling retired "
                "command spellings; `--apply` re-wires it (or run `gov init --hooks"
                + (" --pre-commit" if name == "pre-commit" else "") + "`")
    return notes


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

    from . import plane as plane_mod
    files_out, old_version, _tpl = plane_mod.upgrade_files(root, manifest_path)
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

    # ── U-9: every step is TRIED at plan time — the dry run carries the
    # same information the apply will, so the two never diverge.
    gates_plan = "absent"
    if (root / "gates.json").is_file():
        try:
            from .gates import merge_gates_by_id, DriftRefused
            local = json.loads((root / "gates.json").read_text(
                encoding="utf-8"))
            # #320: the shipped template lives in the INSTALLED package,
            # not in <repo>/gov/templates — a repo-root-relative read
            # made the plan print WOULD REFUSE [Errno 2] in every
            # adopter checkout (only govrail's own repo has the path).
            from importlib.resources import files as _res_files
            tpl = json.loads(
                _res_files("gov.templates").joinpath("gates.json")
                .read_text(encoding="utf-8"))
            _merged, added, _note = merge_gates_by_id(
                local, tpl, what="the template", on_drift="refuse")
            gates_plan = (f"merge {len(added)} new shipped gate(s): "
                          f"{', '.join(g['id'] for g in added)}"
                          if added else "no new shipped gates to add")
        except DriftRefused as e:
            gates_plan = f"WOULD REFUSE — non-additive drift: {e}"
        except (OSError, ValueError) as e:
            gates_plan = f"WOULD REFUSE — {e}"

    pin_plan = _ci_pin_plan(root, __version__)

    print(f"gov update — migration plan for {root}")
    print(f"  initialized with govrail {old_version} · "
          f"this package {__version__}")
    print(f"  adopt: {len(adoptable)} file(s) "
          f"({', '.join(adoptable) if adoptable else 'none'})")
    print(f"  gates.json: {gates_plan}")
    print(f"  ci pin: {pin_plan}")
    print("  gitignore: ensure .gov/history/ is ignored")
    print("  seal: re-baseline over the migrated files (ritual, recorded "
          "in .gov/rituals.jsonl)")
    print(f"  manifest: version {old_version} → {__version__}")
    for note in _hook_drift_notes(root):
        print(f"  {note}")
    if not args.apply:
        print("gov update: dry run — pass --apply to execute")
        return 0

    # ── U-1: the seal must never launder pre-existing drift. With the
    # seal PRESENT, every drifted file must be one this migration writes;
    # with the seal ABSENT this is a first-time adoption and the ritual
    # consent IS the acceptance.
    seal = root / ".gov" / "plane-seal.json"
    if seal.exists():
        drifted = {v.split(":")[0].strip()
                   for v in verify_plane.violations() if ":" in v}
        planned = set(adoptable) | {"gates.json", ".gov/manifest.json"}
        unexpected = sorted(drifted - planned)
        if unexpected and _update_left_pristine_drift(root, set(adoptable)):
            # #321: a previous apply that died between adoption and
            # re-seal left exactly this shape — adopted files are
            # byte-identical to their shipped templates and the manifest
            # already names this version. That is update's own incomplete
            # run, not tampering: resuming is the remedy, refusing
            # bricked the choreography forever.
            print("gov update: note — the drift matches an interrupted "
                  "run of this same update (pristine templates, manifest "
                  "already at this version); resuming", file=sys.stderr)
            unexpected = []
        if unexpected:
            print("gov update: REFUSED — pre-existing drift would be "
                  "laundered by the re-baseline: "
                  f"{', '.join(unexpected)}; adopt or fix those first "
                  "(gov init --upgrade names them)", file=sys.stderr)
            return 2

    # ── U-8: serialize against concurrent updates and verify-plane
    # --write via the plane's own guard flock.
    steps_done = 0

    def _migrate() -> int:
        nonlocal steps_done
        if adoptable:
            rc = plane_mod.adopt_missing(root, manifest_path, adoptable,
                                preview=False)
            if rc != 0:
                return rc
        steps_done += 1
        # #373: refresh the TRACKED gov hook copies to this version's
        # templates first — #331's re-wire copies the tracked bytes to the
        # executed path, so without this the executed hook was re-wired
        # to the OLD body the drift note promised to fix.
        refreshed = _refresh_tracked_hooks(root)
        if refreshed:
            print(f"gov update: refreshed {refreshed} tracked hook "
                  "copy(ies) to this version's template", file=sys.stderr)
        # #331: the tracked hook templates were just refreshed — re-wire
        # the copies git actually executes, so the checkout runs what the
        # plane tracks (one source, both copies).
        rewired = _rewire_executed_hooks(root)
        if rewired:
            print(f"gov update: re-wired {rewired} executed hook copy(ies)",
                  file=sys.stderr)
        steps_done += 1
        if (root / "gates.json").is_file():
            rc = plane_mod.adopt_new_gates(root, manifest_path, "gates.json")
            if rc != 0:
                return rc
        steps_done += 1
        changed, _note = _ci_pin_refresh(root, __version__)
        print(f"gov update: ci pin — {changed} install line(s) refreshed",
              file=sys.stderr)
        steps_done += 1
        _gitignore_history(root)
        steps_done += 1
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = __version__
        atomicio.write_text(manifest_path,
                            json.dumps(manifest, indent=2) + "\n",
                            root=root)
        steps_done += 1
        # ── U-10: the ritual is recorded WRITE-AHEAD — the ledger entry
        # exists before the seal changes, so a crash can never leave an
        # unrecorded constitution change. A symlinked/unwritable ledger
        # refuses the whole migration here, before any mutation.
        files = verify_plane._sealed_files(root)
        # #311: the migration's re-baseline names its authority too —
        # the update flow itself, with the versions it moved between.
        reason = (f"gov update --apply migration "
                  f"({old_version} -> {__version__})")
        rituals.append(root, ritual="seal-rebaseline",
                       unattended=unattended,
                       files=sorted(files), reason=reason)
        steps_done += 1
        verify_plane.baseline(root, unattended=unattended, reason=reason)
        return 0

    unattended = args.confirm_unattended or not sys.stdin.isatty()
    from . import locks as locks_mod
    from . import rituals
    # #325: the guard flock belongs in the git COMMON dir (like every
    # lease); passing the worktree root created a gov-locks/ directory
    # of content-free guard files inside the tracked tree.
    common = Path(gitutil.common_dir() or root)
    try:
        rc = locks_mod._guarded(common, "plane/update", _migrate)
    except (OSError, RuntimeError) as e:
        print(f"gov update: FAILED after {steps_done}/7 step(s) — the "
              "plane may be half-migrated with a stale seal. Recover: "
              "`git restore . && git clean -fd`, then re-run. "
              f"Cause: {e}", file=sys.stderr)
        return 1
    if rc != 0:
        return rc

    try:
        from . import whatsnew
        whatsnew.main(["--since", old_version])
    except SystemExit:
        pass

    print("gov update: done — commit these changes now")
    return 0


    print("gov update: done — commit these changes now")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
