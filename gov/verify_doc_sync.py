#!/usr/bin/env python3
"""CHANGELOG ↔ HIGHLIGHTS pairing (D37): one updates, the other follows.

The bilingual pairing gate enforces ``foo.md`` ↔ ``foo.zh.md``; this gate
applies the same axiom to the version-facing docs — release-please
updates CHANGELOG.md automatically from commit messages, and the
usage-oriented HIGHLIGHTS.md must carry a section for every released
version, with the version number read FROM CHANGELOG (never guessed).

The gate that catches a missing section is the release workflow itself:
release-please opens the release PR (CHANGELOG gains a section), this
gate goes red, and the fix is pushing the HIGHLIGHTS entry — version
number copied from CHANGELOG — to the same PR. ``--write`` performs that
fix mechanically (a draft section per missing version: bullets copied
verbatim, the heading self-declared as a draft pending the usage
rewrite); the release workflow runs it on the release PR branch, so the
section ships in the release merge and master never sees the red.

Exit codes: 0 = paired; 1 = violations; 2 = unreadable source.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from . import atomicio
    from .root import anchor_to_git_root
except ImportError:  # direct script execution
    import atomicio
    from root import anchor_to_git_root

CHANGELOG = Path("CHANGELOG.md")
# govrail's own layout is the DEFAULT target; a project adopting the gate
# without this layout declares its own file in .gov/docsync.json
# ({"highlights": "<path>"}). The default path MISSING with no config is
# "the gate is not set up here" (named exit 0) — the old hard default
# meant every adopter ate a permanent exit 2 they could never turn green.
HIGHLIGHTS = Path("gov/HIGHLIGHTS.md")
DOC_SYNC_CONFIG = Path(".gov/docsync.json")
# Coverage begins where HIGHLIGHTS was born (0.12.0).
FLOOR = (0, 12, 0)


def _configured_highlights() -> tuple[Path, bool, str | None]:
    """(path, explicitly_configured, error) from .gov/docsync.json."""
    if not DOC_SYNC_CONFIG.is_file():
        return HIGHLIGHTS, False, None
    try:
        cfg = json.loads(DOC_SYNC_CONFIG.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return HIGHLIGHTS, False, f"cannot read {DOC_SYNC_CONFIG}: {e}"
    if not isinstance(cfg, dict):
        return HIGHLIGHTS, False, f"{DOC_SYNC_CONFIG} must be a JSON object"
    p = cfg.get("highlights")
    if not isinstance(p, str) or not p:
        return HIGHLIGHTS, False, (
            f"'highlights' in {DOC_SYNC_CONFIG} must be a path string")
    return Path(p), True, None


def _versions_from_changelog(text: str) -> list[tuple]:
    return sorted(
        tuple(int(x) for x in v.split("."))
        for v in re.findall(r"(?m)^## \[(\d+\.\d+\.\d+)\]", text)
    )


def _versions_from_highlights(text: str) -> set[tuple]:
    return {
        tuple(int(x) for x in v.split("."))
        for v in re.findall(r"(?m)^## (\d+\.\d+\.\d+) ", text)
    }


def _section_text(changelog_text: str, v: tuple) -> str:
    """The CHANGELOG body of version ``v``, as a draft HIGHLIGHTS section.

    The draft is an honest mechanical copy: bullets verbatim from the
    release notes (provenance link groups stripped, HTML entities the
    release notes escaped unescaped), under a heading that says so — the
    usage rewrite stays human, the version pairing (what this gate
    guards, D37) is satisfied the moment the section exists.
    """
    block = _changelog_block(changelog_text, v)
    bullets = []
    for line in block.splitlines():
        m = re.match(r"^[*-] (.*)$", line.strip())
        if not m:
            continue
        bullets.append("- " + _strip_provenance(m.group(1)))
    body = "\n".join(bullets)
    return (f"## {_fmt(v)} — (draft: copied from CHANGELOG, rewrite "
            f"for usage)\n\n"
            + (body + "\n" if bullets else "(no release notes found — "
                                         "write the section by hand)\n"))


def _changelog_block(changelog_text: str, v: tuple) -> str:
    """The lines of CHANGELOG's `## [v]` section, up to the next `## `."""
    pattern = re.compile(
        r"(?ms)^## \[" + re.escape(_fmt(v)) + r"\][^\n]*\n(.*?)(?=^## |\Z)")
    m = pattern.search(changelog_text)
    return m.group(1) if m else ""


def _strip_provenance(text: str) -> str:
    """Drop trailing provenance groups: `([#123](url))` / `([abc1234](url))`."""
    text = (text.replace("&lt;", "<").replace("&gt;", ">")
                .replace("&amp;", "&").replace("&quot;", '"'))
    while True:
        m = re.search(r"\s+\((\[[^\]]*\]\([^)]*\)|[0-9a-f]{7,40})\)$", text)
        if not m:
            return text
        text = text[:m.start()]


def _write_missing(changelog_text: str, highlights_text: str,
                   missing: list[tuple]) -> str:
    """HIGHLIGHTS text with a draft section prepended for each missing
    version, newest first, ahead of the current first section heading."""
    drafts = []
    for v in sorted(missing, reverse=True):
        drafts.append(_section_text(changelog_text, v))
    insertion = "\n".join(drafts) + "\n"
    m = re.search(r"(?m)^## ", highlights_text)
    if m:
        return highlights_text[:m.start()] + insertion + highlights_text[m.start():]
    return highlights_text.rstrip("\n") + "\n\n" + insertion


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("verify_doc_sync")
    parser = argparse.ArgumentParser(
        prog="gov verify-doc-sync",
        description="CHANGELOG ↔ HIGHLIGHTS pairing: every released version "
                    "has a usage-oriented section.",
    )
    parser.add_argument("--write", action="store_true",
                        help="draft the missing sections from CHANGELOG "
                        "(verbatim bullets, heading marked as draft) and "
                        "re-run the gate — same fix --write, as "
                        "verify-pairing's")
    args = parser.parse_args(argv)

    highlights_path, configured, err = _configured_highlights()
    if err is not None:
        print(f"verify_doc_sync: {err}", file=sys.stderr)
        return 2

    if not CHANGELOG.is_file():
        print("verify_doc_sync: no CHANGELOG.md — the pairing has no "
              "released side; nothing to sync (the gate goes green only "
              "because there is provably nothing to pair)")
        return 0
    try:
        changelog_text = CHANGELOG.read_text(encoding="utf-8-sig")
        highlights_text = highlights_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        if configured and not highlights_path.exists():
            # Configured means intended: a declared file that does not
            # exist is a broken prerequisite, not a silent pass.
            print(f"verify_doc_sync: configured highlights file "
                  f"{highlights_path} does not exist", file=sys.stderr)
        else:
            print(f"verify_doc_sync: cannot read a pairing input: {e}",
                  file=sys.stderr)
        return 2
    if not configured and highlights_path == HIGHLIGHTS:
        print(f"verify_doc_sync: syncing {CHANGELOG} against {highlights_path} "
              f"(govrail's default layout; declare your own in "
              f"{DOC_SYNC_CONFIG}: {{\"highlights\": \"<path>\"}})")

    released = [v for v in _versions_from_changelog(changelog_text) if v >= FLOOR]
    covered = _versions_from_highlights(highlights_text)

    missing = [v for v in released if v not in covered]
    ahead = [v for v in covered if v not in released and v > (max(released) if released else (0, 0, 0))]

    if args.write and missing:
        atomicio.write_text(
            highlights_path,
            _write_missing(changelog_text, highlights_text, missing))
        for v in missing:
            print(f"verify_doc_sync: drafted the '{_fmt(v)}' section from "
                  "CHANGELOG — rewrite it for usage before it reads as one")
        highlights_text = highlights_path.read_text(encoding="utf-8-sig")
        missing = [v for v in released if v not in _versions_from_highlights(highlights_text)]

    for v in missing:
        print(f"verify_doc_sync: CHANGELOG has [{_fmt(v)}] but {highlights_path} has "
              f"no section for it — copy the version FROM CHANGELOG and add "
              f"a '## {_fmt(v)}' section")
    for v in ahead:
        print(f"verify_doc_sync: HIGHLIGHTS has {_fmt(v)} but CHANGELOG does "
              f"not — the section shipped before its release; fix the header "
              f"to the released version")

    if missing or ahead:
        print(f"verify_doc_sync: {len(missing)} missing, {len(ahead)} ahead")
        return 1
    print(f"verify_doc_sync: {len(released)} version(s) paired (CHANGELOG ↔ HIGHLIGHTS)")
    return 0


def _fmt(v: tuple) -> str:
    return ".".join(str(x) for x in v)


if __name__ == "__main__":
    raise SystemExit(main())
