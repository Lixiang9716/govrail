#!/usr/bin/env python3
"""Verify bilingual pairing (the external-presentation layer).

Every human-facing document is a pair: the source ``foo.md`` plus a
counterpart translation, pinned by a record ``foo.i18n.yaml`` that stores
each side's git blob hash as of the last confirmed-consistent moment::

    pair:
      en: <sha>
      zh: <sha>
    counterpart: foo.zh.md

Editing either side without re-confirming goes red. ``--write <pair>``
re-records both hashes — the explicit "the pair was re-confirmed" act.
``--write en:<path> zh:<path>`` registers a pair whose counterpart does not
follow the naming convention (e.g. ``foo_CN.md``); the record's
``counterpart`` field then pins that name.

Naming conventions are configuration, not code — ``.gov/pairing.json``
(all keys optional)::

    {
      "include": ["docs/**/*.md", "README.md"],
      "counterparts": ["{stem}.zh.md"],
      "exclude": ["docs/decisions.md"]
    }

A ``counterparts`` pattern is ``{stem}`` plus a literal suffix (no ``/``);
a file ending in that suffix is a counterpart side, never a source.
``--staged`` narrows the check to the pairs the git index touches (source
side, counterpart side, or the record) — the cheap content gate the
optional pre-commit hook runs, so pairing drift is caught at ``git
commit`` instead of one stage later at push (issue #110).
AGENTS.md (agent instructions) and notes under ``.agents/notes/`` are
English-only and out of scope.

The record's field semantics used to live only in this code — an agent
re-stamping a sidecar by hand assumed ``en_commit``/``zh_commit`` were
HEAD and lost a force-push to the mismatch (issue #150). They are not:
the hashes are git blob hashes (``git hash-object``), ``en_commit``/
``zh_commit`` are the last commits that touched each side at
confirmation time, and ``last_confirmed`` is the UTC instant of that
confirmation. The generated record now says so in comment lines, the
``--write`` output names every field value it wrote, and ``--explain``
dumps the schema and the conventions read-only.
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import subprocess
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution (self-test runs files by path)
    from root import anchor_to_git_root

CONFIG_PATH = Path(".gov/pairing.json")
STEM = "{stem}"
DEFAULT_CONFIG: dict[str, list[str]] = {
    "include": ["docs/**/*.md", "README.md"],
    "counterparts": [f"{STEM}.zh.md"],
    "exclude": [],
}


def _blob_hash(path: Path) -> str:
    """Return the git blob SHA for a file (works on the working tree)."""
    proc = subprocess.run(
        ["git", "hash-object", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8", errors="replace",
        check=True,
    )
    return proc.stdout.strip()


def _parse_record(path: Path) -> dict[str, str]:
    """Parse ``pair: {en, zh}`` + ``counterpart:`` into a flat dict."""
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def _load_config() -> dict[str, list[str]] | None:
    """Load .gov/pairing.json over the defaults; None means fail loud."""
    cfg = {k: list(v) for k, v in DEFAULT_CONFIG.items()}
    if not CONFIG_PATH.exists():
        return cfg
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"verify_translation_pairing: cannot read {CONFIG_PATH}: {e}", file=sys.stderr)
        return None
    if not isinstance(raw, dict):
        print(f"verify_translation_pairing: {CONFIG_PATH} must be an object", file=sys.stderr)
        return None
    for key, value in raw.items():
        if key not in DEFAULT_CONFIG:
            known = ", ".join(sorted(DEFAULT_CONFIG))
            print(
                f"verify_translation_pairing: unknown key '{key}' in {CONFIG_PATH} "
                f"(known: {known})",
                file=sys.stderr,
            )
            return None
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            print(
                f"verify_translation_pairing: '{key}' in {CONFIG_PATH} "
                "must be an array of strings",
                file=sys.stderr,
            )
            return None
        cfg[key] = list(value)
    for key in ("include", "counterparts"):
        if not cfg[key]:
            print(f"verify_translation_pairing: '{key}' in {CONFIG_PATH} must not be empty", file=sys.stderr)
            return None
    for pattern in cfg["counterparts"]:
        literal = pattern[len(STEM):] if pattern.startswith(STEM) else None
        if literal is None or not literal or "/" in literal or "{" in literal or "}" in literal:
            print(
                f"verify_translation_pairing: counterpart pattern '{pattern}' must be "
                f"'{STEM}' followed by a non-empty literal without '/' or braces",
                file=sys.stderr,
            )
            return None
    return cfg


def _literals(cfg: dict[str, list[str]]) -> list[str]:
    return [p[len(STEM):] for p in cfg["counterparts"]]


def _pinned_sides(directory: Path) -> set[str]:
    """Counterpart names pinned by the .i18n.yaml records in one directory."""
    names: set[str] = set()
    if not directory.is_dir():
        return names
    for rec in directory.glob("*.i18n.yaml"):
        name = _parse_record(rec).get("counterpart", "")
        if name and "/" not in name:
            names.add(name)
    return names


def _sources(cfg: dict[str, list[str]]) -> list[Path]:
    """Every in-scope source .md: matched by include, not a side, not excluded."""
    files: dict[Path, None] = {}
    for pattern in cfg["include"]:
        for match in _glob.glob(pattern, recursive=True):
            p = Path(match)
            if p.is_file():
                files[p] = None
    excluded = set(cfg["exclude"])
    literals = _literals(cfg)
    pinned: dict[Path, set[str]] = {}
    out = []
    for f in sorted(files):
        if str(f) in excluded or f.suffix != ".md":
            continue
        if any(f.name.endswith(lit) for lit in literals):
            continue  # a counterpart side by naming convention
        if f.name in pinned.setdefault(f.parent, _pinned_sides(f.parent)):
            continue  # a counterpart side pinned by an explicit registration
        out.append(f)
    return out


def _record_path(src: Path) -> Path:
    return src.with_name(src.stem + ".i18n.yaml")


def _record_files(cfg: dict[str, list[str]]) -> list[Path]:
    """Every .i18n.yaml in the include scope (deduped, sorted)."""
    files: dict[Path, None] = {}
    for pattern in cfg["include"]:
        for match in _glob.glob(pattern.replace(".md", ".i18n.yaml"),
                                recursive=True):
            p = Path(match)
            if p.is_file():
                files[p] = None
    return sorted(files)


def _recorded_counterpart(src: Path) -> Path | None:
    """The counterpart a record explicitly pins, if any (may not exist)."""
    rec = _record_path(src)
    if not rec.exists():
        return None
    name = _parse_record(rec).get("counterpart", "")
    if not name or "/" in name:
        return None
    return src.parent / name


def _pattern_counterpart(src: Path, cfg: dict[str, list[str]]) -> Path | None:
    """The first existing counterpart derived from the naming conventions."""
    for literal in _literals(cfg):
        cand = src.with_name(src.stem + literal)
        if cand.exists():
            return cand
    return None


def _counterpart(src: Path, cfg: dict[str, list[str]]) -> Path | None:
    """Recorded counterpart wins; conventions derive it otherwise."""
    return _recorded_counterpart(src) or _pattern_counterpart(src, cfg)


def _resolve_source(arg: str, cfg: dict[str, list[str]]) -> Path:
    """Resolve a --write argument (bare stem or any side) to the source .md."""
    p = Path(arg)
    name = p.name
    if name.endswith(".i18n.yaml"):
        name = name[: -len(".i18n.yaml")]
    else:
        for lit in sorted(_literals(cfg), key=len, reverse=True):
            if name.endswith(lit):
                name = name[: -len(lit)]
                break
    if not name.endswith(".md"):
        name += ".md"
    p = p.with_name(name)
    if p.exists():
        return p
    alt = Path("docs") / name
    return alt if alt.exists() else p


def _last_commit(path: Path) -> str:
    """Short hash of the commit that last touched a path ('' if untracked)."""
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%h", "--", str(path)],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _record_fields(src: Path, zh: Path) -> dict[str, str]:
    """The fields one record carries, computed from the current tree."""
    from datetime import datetime, timezone

    return {
        "en": _blob_hash(src),
        "zh": _blob_hash(zh),
        "counterpart": zh.name,
        "last_confirmed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "en_commit": _last_commit(src),
        "zh_commit": _last_commit(zh),
    }


def _render_record(fields: dict[str, str]) -> str:
    """The record text. The comment lines state the field semantics
    (issue #150: they existed only in code, and an agent re-stamping a
    sidecar by hand read en_commit/zh_commit as HEAD). Comments are legal
    YAML and _parse_record skips them; they describe the record, so they
    cannot perturb the side hashes it pins."""
    return (
        "# Pairing record: the state at the moment this pair was last\n"
        "# confirmed consistent. Regenerated by `gov verify-pairing --write`.\n"
        "# pair.en/pair.zh are git blob hashes (`git hash-object`), not file\n"
        "# sha256 — they pin each side's exact content. en_commit/zh_commit\n"
        "# are the last commits that TOUCHED each side at that moment (not\n"
        "# HEAD, not this confirmation) — informational context; the gate\n"
        "# compares only the en/zh hashes. last_confirmed is the UTC ISO-8601\n"
        "# instant of the confirmation (datetime.isoformat(), +00:00).\n"
        "pair:\n"
        f"  en: {fields['en']}\n"
        f"  zh: {fields['zh']}\n"
        f"counterpart: {fields['counterpart']}\n"
        f"last_confirmed: {fields['last_confirmed']}\n"
        f"en_commit: {fields['en_commit']}\n"
        f"zh_commit: {fields['zh_commit']}\n"
    )


def _announce_wrote(record: Path, fields: dict[str, str]) -> None:
    """Issue #150: --write names the field values it wrote, not just the
    file — the hand-restamp failure was invisible until the gate went red."""
    print(f"wrote {record}")
    print(f"  en: {fields['en']}  zh: {fields['zh']}"
          "  (git blob hashes, not file sha256)")
    print(f"  en_commit: {fields['en_commit'] or 'untracked'}  "
          f"zh_commit: {fields['zh_commit'] or 'untracked'}"
          "  (last commit that touched each side — not HEAD)")
    print(f"  last_confirmed: {fields['last_confirmed']}  (UTC ISO-8601)")


def _register(src: Path, zh: Path) -> tuple[Path, dict[str, str]]:
    """Write the record pinning hashes, the counterpart's name, and when
    (and on which commits) the pair was last confirmed — so drift later
    shows who moved first (D30). Returns (path, fields) so --write can
    announce what it wrote (issue #150)."""
    fields = _record_fields(src, zh)
    record = _record_path(src)
    record.write_text(_render_record(fields), encoding="utf-8")
    return record, fields


def _staged_files() -> list[str] | None:
    """Paths staged in the index (deleted paths dropped); None = git failed."""
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=d"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        print(f"verify_translation_pairing: --staged failed: "
              f"{proc.stderr.strip()}", file=sys.stderr)
        return None
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _staged_sources(staged: list[str], cfg: dict[str, list[str]]) -> list[Path]:
    """In-scope pair sources a staged path belongs to (source side,
    counterpart side, or the ``.i18n.yaml`` record — editing any of the
    three is touching the pair)."""
    by_path = {str(s): s for s in _sources(cfg)}
    involved: dict[Path, None] = {}
    for path in staged:
        p = Path(path)
        hit: Path | None = None
        if path in by_path:
            hit = by_path[path]
        elif p.name.endswith(".i18n.yaml"):
            stem = p.name[: -len(".i18n.yaml")]
            hit = by_path.get(str(p.with_name(stem + ".md")))
        else:
            for lit in _literals(cfg):
                if p.name.endswith(lit):
                    stem = p.name[: -len(lit)]
                    hit = by_path.get(str(p.with_name(stem + ".md")))
                    break
        if hit is not None:
            involved[hit] = None
    return sorted(involved)


def _pair_errors(src: Path, cfg: dict[str, list[str]]) -> list[str]:
    """The violation lines for one pair (shared by full and --staged runs)."""
    zh = _counterpart(src, cfg)
    if zh is None:
        return [
            f"{src}: no counterpart found (conventions: {_convention_hint(cfg)}) — "
            f"translate it, or register one: --write en:{src} zh:<path>"
        ]
    if not zh.exists():
        return [
            f"{src}: recorded counterpart '{zh.name}' is missing — "
            "re-register with --write en:" + str(src) + " zh:<path>"
        ]
    rec = _record_path(src)
    if not rec.exists():
        return [f"{src}: missing record {rec.name} — baseline with --write {src}"]
    recorded = _parse_record(rec)
    current = {"en": _blob_hash(src), "zh": _blob_hash(zh)}
    errors: list[str] = []
    for side, expect in (("en", src), ("zh", zh)):
        if side not in recorded or not recorded[side]:
            errors.append(f"{rec.name}: missing recorded hash for {side}")
        elif recorded[side] != current[side]:
            moved = _last_commit(expect) or "uncommitted"
            errors.append(
                f"{expect}: out of sync — re-confirm: "
                f"gov verify-pairing --write {src} "
                f"(the {side} side last moved in {moved}, "
                f"confirmed {recorded.get('last_confirmed', 'unknown time')})"
            )
    return errors


def _pair_is_stale(src: Path, cfg: dict[str, list[str]]) -> bool:
    """A pair needs re-baselining: unrecorded, drifted, or missing a side."""
    zh = _counterpart(src, cfg)
    rec = _record_path(src)
    if zh is None or not zh.exists() or not rec.exists():
        return True
    recorded = _parse_record(rec)
    return (recorded.get("en") != _blob_hash(src)
            or recorded.get("zh") != _blob_hash(zh))


def _convention_hint(cfg: dict[str, list[str]]) -> str:
    return ", ".join(cfg["counterparts"])


def _write(items: list[str], cfg: dict[str, list[str]]) -> int:
    explicit = [a for a in items if a.startswith(("en:", "zh:"))]
    if explicit:
        if len(explicit) != len(items):
            print(
                "verify_translation_pairing: cannot mix bare pairs with en:/zh: forms",
                file=sys.stderr,
            )
            return 2
        sides: dict[str, Path] = {}
        for a in explicit:
            key, _, path = a.partition(":")
            if key in sides or not path:
                print(f"verify_translation_pairing: duplicated or empty '{key}:' side", file=sys.stderr)
                return 2
            sides[key] = Path(path)
        if set(sides) != {"en", "zh"}:
            print(
                "verify_translation_pairing: explicit registration needs exactly "
                "en:<path> and zh:<path>",
                file=sys.stderr,
            )
            return 2
        en, zh = sides["en"], sides["zh"]
        if not en.exists():
            print(f"verify_translation_pairing: no such source: {en}", file=sys.stderr)
            return 2
        if not zh.exists():
            print(f"verify_translation_pairing: no such counterpart: {zh}", file=sys.stderr)
            return 2
        if en.suffix != ".md":
            print(f"verify_translation_pairing: source must be a .md file: {en}", file=sys.stderr)
            return 2
        if en.parent != zh.parent:
            print("verify_translation_pairing: counterpart must sit next to the source", file=sys.stderr)
            return 2
        _announce_wrote(*_register(en, zh))
        if str(en) not in {str(p) for p in _sources(cfg)}:
            print(
                f"note: {en} is outside the pairing include scope; the record is "
                "written but verification will not check it",
                file=sys.stderr,
            )
        return 0

    if items:
        sources = sorted({_resolve_source(a, cfg) for a in items})
    else:
        # #32/D32: the bare form baselines only what is currently OUT OF
        # SYNC — green pairs keep the confirmation they earned; forcing a
        # green pair is the named-path form's job.
        sources = [src for src in _sources(cfg) if _pair_is_stale(src, cfg)]
        if not sources:
            print("verify_translation_pairing: nothing out of sync — bare "
                  "--write touches nothing; use --write <path> to force a "
                  "specific pair")
            return 0
    wrote = 0
    unpairable = 0
    for src in sources:
        if not src.exists():
            print(f"verify_translation_pairing: no such pair source: {src}", file=sys.stderr)
            return 2  # a named path that does not exist is a typo, not a pair state
        zh = _counterpart(src, cfg)
        problem = None
        if zh is None:
            problem = (
                f"no counterpart for {src} (conventions: {_convention_hint(cfg)}) — "
                f"translate it, or register explicitly: --write en:{src} zh:<path>"
            )
        elif not zh.exists():
            problem = (
                f"recorded counterpart '{zh.name}' for {src} is missing — "
                "re-register: --write en:" + str(src) + " zh:<path>"
            )
        if problem is not None:
            # One unpaired file must not block the baseline of the rest
            # (F3): record what can be recorded, report what cannot.
            print(f"verify_translation_pairing: {problem}", file=sys.stderr)
            unpairable += 1
            continue
        _announce_wrote(*_register(src, zh))
        wrote += 1
    if unpairable:
        print(
            f"verify_translation_pairing: wrote {wrote}, left {unpairable} "
            "unpairable (see above)",
            file=sys.stderr,
        )
        return 1
    return 0


def _explain(cfg: dict[str, list[str]]) -> int:
    """Issue #150: dump the expected schema and this project's conventions,
    read-only — nothing is checked, nothing is modified, nothing is judged."""
    sources = _sources(cfg)
    print("gov verify-pairing — expected schema and conventions "
          "(read-only: nothing checked, nothing modified)")
    print()
    print("A human-facing document is a three-file pair:")
    print("  <stem>.md            the source side")
    for pattern in cfg["counterparts"]:
        print(f"  <stem>{pattern[len(STEM):]}".ljust(21)
              + "the counterpart translation (naming convention)")
    print("  <stem>.i18n.yaml     the pairing record pinning both sides")
    include = ", ".join(cfg["include"])
    exclude = ", ".join(cfg["exclude"]) or "(none)"
    print(f"in scope: {include} — counterparts configured as "
          f"{_convention_hint(cfg)} — excluded: {exclude}")
    print(f"this project currently has {len(sources)} pair(s) in scope")
    print()
    print("The record's schema (a subset of YAML; comment lines are allowed")
    print("and ignored — the verifier reads it line-wise, not with a YAML lib):")
    print()
    print("  pair:")
    print("    en: <git blob hash of the source side>")
    print("    zh: <git blob hash of the counterpart side>")
    print("  counterpart: <counterpart file name>")
    print("  last_confirmed: <UTC ISO-8601 instant>")
    print("  en_commit: <short commit hash>")
    print("  zh_commit: <short commit hash>")
    print()
    print("Field semantics (the part that used to live only in code):")
    print("  - en/zh are git blob hashes (`git hash-object`), NOT file sha256;")
    print("    the gate compares them against the sides' current content, so a")
    print("    one-sided edit goes red.")
    print("  - en_commit/zh_commit are the LAST COMMITS THAT TOUCHED each side")
    print("    at confirmation time — not HEAD, not the confirmation commit.")
    print("    They are informational context; never stamp HEAD into them.")
    print("  - last_confirmed is datetime.isoformat() in UTC (+00:00).")
    print("  - Do not hand-edit the record: re-confirm with --write instead.")
    print()
    print("Commands:")
    print("  gov verify-pairing                    # the gate: full check")
    print("  gov verify-pairing --write <stem>     # re-confirm one pair")
    print("  gov verify-pairing --write            # baseline every out-of-sync pair")
    print("  gov verify-pairing --write en:<p> zh:<p>  # register any naming")
    return 0


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("verify_translation_pairing")
    parser = argparse.ArgumentParser(
        prog="gov verify-pairing", description="Verify bilingual pairing."
    )
    parser.add_argument("--write", nargs="*", metavar="PAIR",
                        help="re-record pairs (bare stem or any side); or register an "
                             "explicitly named pair with en:<path> zh:<path>")
    parser.add_argument("--staged", action="store_true",
                        help="check only the pairs the index touches (the cheap "
                             "pre-commit gate; issue #110) — quiet on an index "
                             "with no paired files staged")
    parser.add_argument("--explain", action="store_true",
                        help="print the expected record schema and this project's "
                             "conventions, read-only (issue #150); overrides "
                             "--write/--staged")
    args = parser.parse_args(argv)

    cfg = _load_config()
    if cfg is None:
        return 2

    if args.explain:
        return _explain(cfg)

    if args.write is not None:
        return _write(args.write, cfg)

    if args.staged:
        staged = _staged_files()
        if staged is None:
            return 2
        sources = _staged_sources(staged, cfg)
        if not sources:
            print("verify_translation_pairing: no staged file belongs to a "
                  "pair — nothing to check")
            return 0
        errors = [e for src in sources for e in _pair_errors(src, cfg)]
        if errors:
            for e in errors:
                print(e)
            print(f"verify_translation_pairing: {len(errors)} violation(s) in "
                  f"{len(sources)} staged pair(s)")
            return 1
        print(f"verify_translation_pairing: {len(sources)} staged pair(s) ok")
        return 0

    errors: list[str] = []
    pairs = _sources(cfg)
    for src in pairs:
        errors.extend(_pair_errors(src, cfg))
    # Wish 14/D28: a record whose both sides are gone is garbage that
    # nothing ever reported — count it.
    for rec in sorted(_record_files(cfg)):
        src = rec.with_suffix("").with_suffix(".md")  # foo.i18n.yaml -> foo.md
        pinned = _parse_record(rec).get("counterpart", "")
        counterpart = rec.parent / pinned if pinned else None
        if not src.exists() and (counterpart is None or not counterpart.exists()):
            errors.append(
                f"{rec}: dangling record — both sides are gone; delete it, or "
                "re-create the source and re-register with --write"
            )

    if errors:
        for e in errors:
            print(e)
        print(f"verify_translation_pairing: {len(errors)} violation(s)")
        return 1
    print(f"verify_translation_pairing: {len(pairs)} pair(s) ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
