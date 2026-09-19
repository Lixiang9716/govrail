#!/usr/bin/env python3
"""Tamper-evidence for the governance plane itself (the constitution).

The plane sha256-seals archived notes (verify-archive) but used to leave
the two files that define the plane's own behavior — ``.gov/rules.md``
and ``gates.json`` — unsealed: an agent could delete a gate, commit, and
sail through every remaining gate, with review as the only backstop.
This gate gives the constitution the same freeze the archive has:

- ``gov verify-plane`` compares each sealed file's current sha256
  against ``.gov/plane-seal.json``; edits, deletions, and an unsealed
  new config are all named violations (exit 1);
- ``gov verify-plane --write`` re-baselines — explicit, loudly-printed
  consent, the same contract as ``archive-notes --rebaseline``;
- ``gov init`` writes the initial seal, so a fresh install is sealed
  from its first commit.

Exit codes: 0 = sealed and intact (or nothing to seal); 1 = the plane
drifted from its seal; 2 = unreadable seal (fail loud, never silently
pass a tampered constitution).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:  # package context (`gov ...`)
    from .gitutil import scrubbed_env
except ImportError:  # direct script execution (self-test runs files by path)
    from gitutil import scrubbed_env

try:  # package context (`gov ...`)
    from . import atomicio
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    import atomicio
    from root import anchor_to_git_root

PROG = "verify_plane"
SEALED = (Path(".gov/rules.md"), Path("gates.json"))
OPTIONAL = (Path(".gov/pairing.json"), Path(".gov/decisions.json"),
            Path(".gov/surfaces.json"))
# Governance-behavior DIRECTORIES: everything under them is sealed when
# present (.gov/rejections carries the rejection cases — deleting one
# silences "every gate ships a rejection case" at its root).
SEAL_DIRS = (Path(".gov/rejections"),)
SEAL_PATH = Path(".gov/plane-seal.json")


def _sha256(path: Path) -> str:
    # EOL-insensitive: a Windows checkout smudges LF to CRLF
    # (core.autocrlf), and the seal must judge CONTENT — an eol
    # translation the checkout chose is not a semantic edit.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _sealed_files(root: Path) -> dict[str, Path]:
    """The plane's config files that exist right now (core + optional +
    every file under the governance-behavior directories)."""
    files: dict[str, Path] = {}
    for rel in (*SEALED, *OPTIONAL):
        p = root / rel
        if p.is_file():
            files[rel.as_posix()] = p
    for d in SEAL_DIRS:
        base = root / d
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    files[(d / p.relative_to(base)).as_posix()] = p
    return files


def _identity() -> str:
    """Who is accepting the constitution: $GOV_CALLER, else user@host
    (uid-fallback for uid-less container users, as locks does)."""
    import getpass
    import socket

    caller = os.environ.get("GOV_CALLER", "")
    if caller.strip():
        return caller.strip()
    try:
        user = getpass.getuser()
    except (KeyError, OSError):
        user = f"uid{os.getuid()}"
    return f"{user}@{socket.gethostname()}"


def baseline(root: Path | None = None, *, caller: str | None = None,
             unattended: bool = False, reason: str | None = None) -> None:
    """Write the seal for the current plane state (init's first stamp).

    Programmatic callers (init, preset apply) land through here too —
    they extend an intact chain by construction; the calling flow's own
    record carries their receipt."""
    root = root or Path.cwd()
    files = _sealed_files(root)
    if not files:
        return
    rebaseline: dict = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "caller": caller or _identity(),
        "unattended": bool(unattended),
    }
    if reason:
        # #311: an unattended re-baseline must name its authority — the
        # reason rides inside the seal itself, not only in the ledger.
        rebaseline["reason"] = reason
    payload = {
        "files": {rel: {"sha256": _sha256(p)}
                  for rel, p in sorted(files.items())},
        "last_rebaseline": rebaseline,
    }
    atomicio.write_text(root / SEAL_PATH,
                        json.dumps(payload, indent=2) + "\n", root=root)


REBASELINE_WINDOW_DAYS = 7


def recent_rebaselines(root: Path | None = None,
                       days: int = REBASELINE_WINDOW_DAYS) -> list[dict]:
    """Re-baseline rituals recorded in the tracked ledger within ``days``
    (#311): a seal reset that no runner mentions is a reset nobody sees.
    Read-only; an unreadable ledger yields [] — the seal check itself is
    the enforcement, this is the visibility channel."""
    root = root or Path.cwd()
    from .rituals import LEDGER
    ledger = root / LEDGER
    if not ledger.is_file():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    out: list[dict] = []
    try:
        for line in ledger.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("ritual") != "seal-rebaseline":
                continue
            try:
                ts = datetime.fromisoformat(
                    str(rec.get("ts", ""))).timestamp()
            except ValueError:
                continue
            if ts >= cutoff:
                out.append(rec)
    except OSError:
        return []
    return out


def _seal_in_history(root: Path) -> bool:
    """True when git history contains the seal file — the adoption record
    an attacker cannot rewrite without rewriting history itself."""
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=off", "log", "--oneline", "-n", "1",
         "--", SEAL_PATH.as_posix()],
        cwd=str(root), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=scrubbed_env(),
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def _governed_artifacts(root: Path) -> bool:
    markers = (
        root / ".gov" / "rules.md",
        root / ".gov" / "manifest.json",
        root / ".gov" / "rejections",
        root / ".agents" / "notes",
    )
    return any(m.exists() for m in markers)


def violations(root: Path | None = None,
               overlays: dict[str, bytes] | None = None) -> list[str]:
    """Current drift against the seal; empty = intact (or unsealed).

    ``overlays`` maps a sealed rel path to the caller's in-memory bytes
    (N8): the seal is then judged over THOSE bytes, so the runner can
    verify-then-parse one single read — closing the window where a
    concurrent writer lets tampered bytes get parsed while clean bytes
    get seal-checked.

    The machine behind main()'s verdicts, shared with the flows that
    legitimately mutate plane config (preset apply, init --adopt): they
    may extend an INTACT seal chain, never launder accumulated drift.
    """
    root = root or Path.cwd()
    overlays = overlays or {}
    files = _sealed_files(root)
    seal = root / SEAL_PATH
    if not seal.is_file():
        # N2/N7: deleting the seal file is the same attack as disabling
        # the gate, one level up — and stripping the constitution too does
        # NOT reclassify the repository as "never adopted". The state is
        # drift when ANY of these says the plane was ever here:
        # - the seal itself exists in git history (the strongest anchor:
        #   init's seal is committed, so history is the attacker-external
        #   record);
        # - the constitution (.gov/rules.md) is present;
        # - other init-laid plane artifacts survive (.gov/manifest.json,
        #   .gov/rejections/, .agents/notes/).
        # Only a repository with NONE of those (scratch configs, tests,
        # tools that never adopted the plane) runs unsealed by design.
        if _seal_in_history(root):
            return [f"{SEAL_PATH.as_posix()}: the seal is GONE but this "
                    "repository's history contains it — restore it "
                    "(git checkout) or accept the current state explicitly "
                    "(gov verify-plane --write)"]
        if _governed_artifacts(root):
            return [f"{SEAL_PATH.as_posix()}: the plane config exists but its "
                    "seal is GONE — restore it (git checkout) or accept the "
                    "current state explicitly (gov verify-plane --write)"]
        return []  # genuinely never adopted: nothing sealed, nothing to judge
    if not files:
        return []  # nothing left to judge (config deleted post-seal)
    try:
        seal_doc = json.loads(seal.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return [f"cannot read the seal {seal}: {e}"]
    if not isinstance(seal_doc, dict) or not isinstance(
            seal_doc.get("files", {}), dict):
        # `[]`, `42`, or a non-object "files" is legal JSON but not a
        # seal — a named unreadable-seal prerequisite (exit 2 downstream),
        # never an AttributeError traceback (rule 5).
        return [f"cannot read the seal {seal}: the seal and its 'files' "
                "must be JSON objects"]
    sealed = seal_doc.get("files", {})
    out: list[str] = []
    for rel, p in files.items():
        entry = sealed.get(rel)
        if entry is None:
            out.append(f"{rel}: plane config is not sealed")
        elif not isinstance(entry, dict):
            out.append(f"{rel}: seal entry is malformed")
        else:
            if rel in overlays:
                # EOL-normalized, same policy as _sha256
                digest = hashlib.sha256(
                    overlays[rel].replace(b"\r\n", b"\n")).hexdigest()
            else:
                digest = _sha256(p)
            if digest != entry.get("sha256"):
                out.append(f"{rel}: differs from its seal")
    for rel in sealed:
        if rel not in files:
            out.append(f"{rel}: sealed but the file is gone")
    return out


def _report_drift(drift: list[str]) -> int:
    """Print violations() output; 2 = unreadable seal, 1 = named drift."""
    # An unreadable seal is a broken prerequisite (2), not a verdict (1).
    if any(d.startswith("cannot read") for d in drift):
        print(f"{PROG}: {drift[0]}", file=sys.stderr)
        return 2
    for v in drift:
        print(v)
    print(f"{PROG}: {len(drift)} violation(s) — the constitution is "
          "tamper-evident, not tamper-proof; a seal change must be a "
          "reviewed decision")
    return 1


def main(argv: list[str] | None = None) -> int:
    # #8: an unexpected OSError/decode/JSON failure is a broken
    # prerequisite (exit 2, named), never a bare traceback.
    try:
        return _run(argv)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"{PROG}: unexpected failure reading the plane state: {e}",
              file=sys.stderr)
        return 2


def _run(argv: list[str] | None = None) -> int:
    anchor_to_git_root(PROG)
    parser = argparse.ArgumentParser(
        prog="gov verify-plane",
        description="Tamper-evidence for the governance plane's own config "
                    "(.gov/rules.md + gates.json).",
    )
    parser.add_argument("--write", action="store_true",
                        help="re-baseline the seal over the current state "
                             "(interactive consent; the diff and the caller "
                             "are recorded into the seal)")
    parser.add_argument("--confirm-unattended", action="store_true",
                        help="allow --write without a terminal (agents, CI) — "
                             "recorded as UNATTENDED machine consent under the "
                             "caller identity; never a silent one-flag act")
    parser.add_argument("--reason", default=None, metavar="TEXT",
                        help="#311: the authority for this re-baseline "
                             "(decision/note/issue naming who reviewed it). "
                             "REQUIRED with --confirm-unattended; recorded "
                             "into the seal and the ritual ledger")
    args = parser.parse_args(argv)
    if args.confirm_unattended and not args.write:
        parser.error("--confirm-unattended is only meaningful with --write")
    if args.reason and not args.write:
        parser.error("--reason is only meaningful with --write")
    root = Path.cwd()
    files = _sealed_files(root)

    if not files:
        # #5: "no sealed file survived" is NOT automatically green — that
        # judgment belongs to violations() (N2/N7: a seal in git history,
        # or surviving plane artifacts like .gov/manifest.json, is drift).
        # The old unconditional exit 0 here short-circuited that verdict,
        # so stripping every sealed file silenced the gate one level up.
        drift = violations(root)
        if drift:
            return _report_drift(drift)
        print(f"{PROG}: no plane config found (no .gov/rules.md, no gates.json)")
        return 0

    seal = root / SEAL_PATH
    if args.write:
        interactive = sys.stdin.isatty()
        if not interactive and not args.confirm_unattended:
            print(
                f"{PROG}: REFUSED — accepting a new constitution is a "
                "recorded decision, and this shell has no terminal to hold "
                "it. Re-run from an interactive terminal, or pass "
                "--confirm-unattended to record it as UNATTENDED machine "
                "consent under your caller identity.", file=sys.stderr)
            return 2
        if args.confirm_unattended and not (args.reason or "").strip():
            # #311: an unattended re-baseline is the one move this plane
            # cannot forgive, so it must at least say WHO authorized it.
            # A machine consent without a named authority is exactly the
            # "reset is neither costly nor visible" gap this closes.
            print(
                f"{PROG}: REFUSED — UNATTENDED machine consent needs "
                "--reason naming the authority for this re-baseline "
                "(the decision, note, or issue that reviewed the new "
                "constitution). The reason is recorded into the seal "
                "and the ritual ledger.", file=sys.stderr)
            return 2
        previous: dict[str, str] = {}
        if seal.is_file():
            unreadable: str | None = None
            try:
                seal_doc = json.loads(seal.read_text(encoding="utf-8-sig"))
                # #4: a non-object seal (or a non-object entry) contributes
                # nothing instead of raising an AttributeError.
                seal_files = seal_doc.get("files", {}) \
                    if isinstance(seal_doc, dict) else {}
                previous = {
                    rel: (meta.get("sha256", "?")
                          if isinstance(meta, dict) else "?")
                    for rel, meta in seal_files.items()
                }
                if not isinstance(seal_doc, dict):
                    unreadable = "the seal is not a JSON object"
            except (OSError, ValueError, UnicodeDecodeError) as e:
                unreadable = str(e)
                previous = {}
            if unreadable is not None:
                # --write is explicit consent to re-baseline, so the flow
                # continues — but an unreadable previous seal must never be
                # swallowed silently: the diff below would read "(absent)"
                # for every file with no explanation why.
                previous = {}
                print(f"{PROG}: WARNING — the previous seal {seal} is "
                      f"unreadable ({unreadable}); re-baselining over it "
                      "anyway", file=sys.stderr)
        # #311: the transition is computed BEFORE anything is written, so
        # the consent question is about facts, and a decline leaves the
        # old seal byte-identical on disk.
        transitions = []
        for rel in sorted(set(files) | set(previous)):
            old_h = previous.get(rel, "(absent)")
            p = files.get(rel)
            new_h = _sha256(p) if p else "(gone)"
            transitions.append((rel, old_h, new_h))
        if interactive:
            print(f"{PROG}: accepting a new constitution is a recorded "
                  "decision — confirm each change:")
            for rel, old_h, new_h in transitions:
                mark = " " if old_h == new_h else "+"
                print(f"{mark} {rel}: {old_h[:12]} -> {new_h[:12]}")
            changed = [rel for rel, old_h, new_h in transitions
                       if old_h != new_h]
            if not changed:
                print(f"{PROG}: no sealed file differs from the seal — "
                      "nothing to accept")
            for rel in changed:
                try:
                    answer = input(f"{PROG}: accept the new state of "
                                   f"{rel}? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    answer = ""
                if answer not in ("y", "yes"):
                    print(f"{PROG}: ABORTED — '{rel}' not accepted; "
                          "nothing was written, the seal is unchanged")
                    return 1
        baseline(root, unattended=not interactive,
                 reason=(args.reason or "").strip() or None)
        try:
            from . import rituals
        except ImportError:  # direct-script execution
            import rituals
        ritual_details: dict = {"unattended": not interactive,
                                "files": sorted(files)}
        if (args.reason or "").strip():
            ritual_details["reason"] = args.reason.strip()
        try:
            rituals.append(root, ritual="seal-rebaseline", **ritual_details)
        except OSError as e:
            print(f"{PROG}: WARNING — the re-baseline could not be "
                  f"recorded in the tracked ledger: {e}; the seal itself "
                  "is updated, but the audit trail needs a manual entry",
                  file=sys.stderr)
        for rel, old_h, new_h in transitions:
            mark = " " if old_h == new_h else "+"
            print(f"{mark} {rel}: {old_h[:12]} -> {new_h[:12]}")
        caller = _identity()
        mode = "interactive" if interactive else "UNATTENDED machine consent"
        print(f"{PROG}: sealed {len(files)} file(s) — recorded by "
              f"{caller} ({mode})")
        # #200: the consent record must be auditable — say where it lives
        print(f"{PROG}: consent recorded in {root / '.gov' / 'rituals.jsonl'} "
              "(tracked; git history keeps past entries)")
        return 0

    drift = violations(root)
    if not drift:
        print(f"{PROG}: {len(files)} plane file(s) sealed and intact")
        return 0
    return _report_drift(drift)


if __name__ == "__main__":
    raise SystemExit(main())
