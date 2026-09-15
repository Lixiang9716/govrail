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
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from . import atomicio
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    import atomicio
    from root import anchor_to_git_root

PROG = "verify_plane"
SEALED = (Path(".gov/rules.md"), Path("gates.json"))
OPTIONAL = (Path(".gov/pairing.json"),)
SEAL_PATH = Path(".gov/plane-seal.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sealed_files(root: Path) -> dict[str, Path]:
    """The plane's config files that exist right now (core + optional)."""
    files: dict[str, Path] = {}
    for rel in (*SEALED, *OPTIONAL):
        p = root / rel
        if p.is_file():
            files[rel.as_posix()] = p
    return files


def baseline(root: Path | None = None) -> None:
    """Write the seal for the current plane state (init's first stamp)."""
    root = root or Path.cwd()
    files = _sealed_files(root)
    if not files:
        return
    payload = {"files": {rel: {"sha256": _sha256(p)} for rel, p in sorted(files.items())}}
    atomicio.write_text(root / SEAL_PATH, json.dumps(payload, indent=2) + "\n")


def violations(root: Path | None = None) -> list[str]:
    """Current drift against the seal; empty = intact (or unsealed).

    The machine behind main()'s verdicts, shared with the flows that
    legitimately mutate plane config (preset apply, init --adopt): they
    may extend an INTACT seal chain, never launder accumulated drift.
    """
    root = root or Path.cwd()
    files = _sealed_files(root)
    seal = root / SEAL_PATH
    if not files or not seal.is_file():
        return []
    try:
        sealed = json.loads(seal.read_text(encoding="utf-8-sig")).get("files", {})
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return [f"cannot read the seal {seal}: {e}"]
    out: list[str] = []
    for rel, p in files.items():
        entry = sealed.get(rel)
        if entry is None:
            out.append(f"{rel}: plane config is not sealed")
        elif not isinstance(entry, dict):
            out.append(f"{rel}: seal entry is malformed")
        elif _sha256(p) != entry.get("sha256"):
            out.append(f"{rel}: differs from its seal")
    for rel in sealed:
        if rel not in files:
            out.append(f"{rel}: sealed but the file is gone")
    return out


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root(PROG)
    parser = argparse.ArgumentParser(
        prog="gov verify-plane",
        description="Tamper-evidence for the governance plane's own config "
                    "(.gov/rules.md + gates.json).",
    )
    parser.add_argument("--write", action="store_true",
                        help="re-baseline the seal over the current state "
                             "(explicit, loudly-printed consent)")
    args = parser.parse_args(argv)
    root = Path.cwd()

    files = _sealed_files(root)
    if not files:
        print(f"{PROG}: no plane config found (no .gov/rules.md, no gates.json)")
        return 0

    seal = root / SEAL_PATH
    if args.write:
        changed = []
        if seal.is_file():
            try:
                previous = set(json.loads(
                    seal.read_text(encoding="utf-8-sig")).get("files", {}))
            except (OSError, ValueError, UnicodeDecodeError):
                previous = set()
            changed = sorted(set(files) - previous)
        baseline(root)
        detail = f" (added to the seal: {', '.join(changed)})" if changed else ""
        print(f"{PROG}: sealed {len(files)} file(s){detail}")
        return 0

    if not seal.is_file():
        print(f"{PROG}: no seal at {SEAL_PATH} — baseline it once: "
              f"gov verify-plane --write (gov init writes it automatically)")
        return 0

    try:
        sealed = json.loads(seal.read_text(encoding="utf-8-sig")).get("files", {})
    except (OSError, ValueError, UnicodeDecodeError) as e:
        print(f"{PROG}: cannot read the seal {SEAL_PATH}: {e}", file=sys.stderr)
        return 2

    violations: list[str] = []
    for rel, p in files.items():
        entry = sealed.get(rel)
        if entry is None:
            violations.append(
                f"{rel}: plane config is not sealed — baseline it explicitly "
                f"(gov verify-plane --write)")
        elif not isinstance(entry, dict):
            violations.append(f"{rel}: seal entry is malformed — re-seal "
                              f"(gov verify-plane --write)")
        elif _sha256(p) != entry.get("sha256"):
            violations.append(
                f"{rel}: DIFFERS from its seal — the plane's own rules or gate "
                "set moved without a recorded re-baseline; restore it "
                "(git checkout) or accept the new constitution explicitly "
                "(gov verify-plane --write)")
    for rel in sealed:
        if rel not in files:
            violations.append(f"{rel}: sealed but the file is GONE — the plane's "
                              "config was deleted")

    if violations:
        for v in violations:
            print(v)
        print(f"{PROG}: {len(violations)} violation(s) — the constitution is "
              "tamper-evident, not tamper-proof; a seal change must be a "
              "reviewed decision")
        return 1
    print(f"{PROG}: {len(files)} plane file(s) sealed and intact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
