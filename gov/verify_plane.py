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
    # EOL-insensitive: a Windows checkout smudges LF to CRLF
    # (core.autocrlf), and the seal must judge CONTENT — an eol
    # translation the checkout chose is not a semantic edit.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


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
    if not seal.is_file():
        # N2: deleting the seal file is the same attack as disabling the
        # gate, one level up. The discriminator is the CONSTITUTION
        # (.gov/rules.md): init seals automatically, so a governed project
        # never sits in "constitution without seal" — that state is drift.
        # A bare gates.json (scratch configs, tests, tools that never
        # adopted the plane) was never sealed and never will be.
        constitution = root / ".gov" / "rules.md"
        if not constitution.is_file():
            return []
        return [f"{SEAL_PATH.as_posix()}: the plane config exists but its "
                "seal is GONE — restore it (git checkout) or accept the "
                "current state explicitly (gov verify-plane --write)"]
    if not files:
        return []  # nothing left to judge (config deleted post-seal)
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

    drift = violations(root)
    if not drift:
        print(f"{PROG}: {len(files)} plane file(s) sealed and intact")
        return 0
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


if __name__ == "__main__":
    raise SystemExit(main())
