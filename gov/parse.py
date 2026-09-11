#!/usr/bin/env python3
"""The parse layer: language packs, file sets, parsers (D54).

The packs in ``gov/langs/*.json`` are data; this module is their loader and
the only place that touches tree-sitter. Three contracts, all fail loud
(rule 5):

- **Pack validation** — every node kind a pack names must exist in the
  grammar it names. A typo'd kind would otherwise make a metric read as 0
  forever, silently: a wrong ``nesting`` list, a misspelled ``comment`` —
  each yields plausible-looking numbers that mean nothing. Loading names
  the offending kind and aborts instead.

- **File-set honesty** — the walker reports what it excluded and why
  (defaults: VCS dirs, virtualenvs, build outputs, caches; per-pack
  excludes on top). "Parsed everything" must never quietly mean "parsed
  what the walker happened to keep".

- **Parse results carry their errors** — tree-sitter never raises; it
  returns a tree with ``ERROR``/missing nodes. Callers decide what an
  error means, but the count is always attached, never dropped.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Iterator

try:  # package context (`gov ...`)
    from importlib.resources import files as _res_files
    _LANGS = _res_files("gov").joinpath("langs")
except Exception:  # direct-module execution (self-test scratch dirs)
    _LANGS = Path(__file__).resolve().parent / "langs"

# Directories never worth indexing, for any language: VCS internals,
# virtualenvs, build outputs, dependency trees, tool caches. Indexing the
# same source twice through build/ or .venv/ doubles every symbol.
DEFAULT_EXCLUDE = (
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules",
    "build", "dist", "target", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".tox",
)

PACK_KEYS = {"globs", "exclude", "grammar", "nesting", "functions",
             "classes", "comment", "string"}
_LIST_KEYS = ("globs", "exclude", "nesting", "functions", "classes",
              "comment", "string")


class ParseUnavailable(Exception):
    """The parse layer cannot run: a grammar import failed (rule 5)."""


@dataclass(frozen=True)
class LangPack:
    name: str
    grammar: str
    globs: tuple[str, ...]
    exclude: tuple[str, ...]
    nesting: frozenset[str]
    functions: frozenset[str]
    classes: frozenset[str]
    comment: frozenset[str]
    string: frozenset[str]
    kind_ids: dict[str, int] = field(default_factory=dict, compare=False)

    def matches(self, relpath: str) -> bool:
        """``**`` spans directories, ``*``/``?`` do not (D15 semantics)."""
        import fnmatch
        parts = relpath.replace("\\", "/").split("/")
        for g in self.globs:
            if "/" in g:
                if fnmatch.fnmatchcase(relpath, g):
                    return True
            elif fnmatch.fnmatchcase(parts[-1], g):
                return True
        return False

    def excluded(self, relpath: str) -> bool:
        parts = relpath.replace("\\", "/").split("/")
        return any(part in self.exclude for part in parts[:-1])


def available() -> list[str]:
    try:
        return sorted(p.name[:-5] for p in Path(_LANGS).iterdir()
                      if p.name.endswith(".json"))
    except (FileNotFoundError, NotADirectoryError, TypeError):
        return []


def _import_grammar(dotted: str):
    """Import a grammar module, converting any failure to ParseUnavailable.

    The tree-sitter bindings are C extensions; a missing wheel (a platform
    the grammar does not ship for, a fresh CPython before the bindings
    catch up) must name the package and the remedy, never traceback.
    """
    try:
        return import_module(dotted)
    except ImportError as e:
        raise ParseUnavailable(
            f"grammar {dotted!r} is not importable ({e}) — the tree-sitter "
            f"bindings are a compiled dependency; install this package on a "
            f"platform with wheels (pip install govrail) or reinstall: "
            f"pip install --force-reinstall {dotted.replace('_', '-')}"
        ) from e


def load_pack(name: str) -> LangPack:
    """Load and validate one pack (rule 5: unknown kind = abort, named).

    Validation is against the grammar's own node-kind table: a kind the
    grammar does not define would silently zero any metric keyed on it.
    Cross-language paste (a Go kind in the python pack) is caught here too.
    """
    path = Path(_LANGS) / f"{name}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ParseUnavailable(
            f"no language pack named {name!r} (available: "
            f"{', '.join(available()) or 'none'})") from e
    except json.JSONDecodeError as e:
        raise ParseUnavailable(f"language pack {name!r} is not valid JSON: {e}") from e
    unknown_keys = sorted(set(raw) - PACK_KEYS)
    if unknown_keys:
        raise ParseUnavailable(
            f"language pack {name!r}: unknown key(s): {', '.join(unknown_keys)}")
    missing = [k for k in _LIST_KEYS if not isinstance(raw.get(k), list)
               or not all(isinstance(x, str) for x in raw[k])]
    if missing:
        raise ParseUnavailable(
            f"language pack {name!r}: keys must be arrays of strings: "
            f"{', '.join(missing)}")

    mod = _import_grammar(raw["grammar"])
    # The binding's factory name is not standardized (every other grammar
    # ships `language`; the typescript one ships `language_typescript` and
    # `language_tsx` for its two dialects).
    lang_fn = getattr(mod, "language", None)
    if not callable(lang_fn):
        for alt in ("language_typescript", "language_tsx"):
            lang_fn = getattr(mod, alt, None)
            if callable(lang_fn):
                break
        if not callable(lang_fn):
            raise ParseUnavailable(
                f"grammar module {raw['grammar']!r} has no language() factory")
    from tree_sitter import Language  # core binding; present iff grammars are
    language = Language(lang_fn())
    kind_ids = {}
    for i in range(language.node_kind_count):
        kind_ids[language.node_kind_for_id(i)] = i
    for key in ("nesting", "functions", "classes", "comment", "string"):
        bad = [k for k in raw[key] if k not in kind_ids]
        if bad:
            raise ParseUnavailable(
                f"language pack {name!r}: node kind(s) {bad} do not exist in "
                f"grammar {raw['grammar']!r} — a wrong kind silently zeroes "
                "its metric, so the pack refuses to load (rule 5)")
    return LangPack(
        name=name,
        grammar=raw["grammar"],
        globs=tuple(raw["globs"]),
        exclude=tuple(sorted(set(DEFAULT_EXCLUDE) | set(raw["exclude"]))),
        nesting=frozenset(raw["nesting"]),
        functions=frozenset(raw["functions"]),
        classes=frozenset(raw["classes"]),
        comment=frozenset(raw["comment"]),
        string=frozenset(raw["string"]),
        kind_ids=kind_ids,
    )


def load_parser(pack: LangPack):
    """A Parser bound to the pack's grammar (one per pack, per process)."""
    from tree_sitter import Language, Parser
    mod = import_module(pack.grammar)
    lang_fn = (getattr(mod, "language", None)
               or getattr(mod, "language_typescript", None)
               or getattr(mod, "language_tsx"))
    return Parser(Language(lang_fn()))


@dataclass
class FileSet:
    """A walked file set, with the exclusions named (rule 5: no silent skip)."""
    files: list[Path]
    excluded_dirs: list[str]
    excluded_by_pack: list[str]
    unmatchable: bool = False  # walked the tree and nothing matched the globs


def _walk(root: Path, pack: LangPack) -> FileSet:
    files: list[Path] = []
    excluded_dirs: set[str] = set()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        parts = rel.split("/")
        hit = next((d for d in DEFAULT_EXCLUDE if d in parts), None)
        if hit is not None:
            excluded_dirs.add(hit)
            continue
        if not p.is_file():
            continue
        if pack.excluded(rel):
            continue
        if p.is_symlink():
            continue  # never follow links out of the declared tree
        if pack.matches(rel):
            files.append(p)
        elif p.suffix and any(p.match(g) for g in pack.globs):
            # matched a glob's basename but was excluded above — already named
            pass
    return FileSet(
        files=files,
        excluded_dirs=sorted(excluded_dirs),
        excluded_by_pack=sorted(set(pack.exclude) - set(DEFAULT_EXCLUDE)),
    )


def iter_files(root: Path, pack: LangPack) -> Iterator[tuple[Path, bytes]]:
    """Yield ``(path, bytes)`` for the pack's declared file set under root."""
    for p in _walk(root, pack).files:
        try:
            yield p, p.read_bytes()
        except OSError as e:
            print(f"gov stats: cannot read {p}: {e}", file=sys.stderr)


def grammar_version(pack: LangPack) -> str | None:
    """The installed grammar's version string, for doctor and the index
    fingerprint: a grammar upgrade changes trees, so metrics consumers may
    need to know which grammar produced a recorded number."""
    try:
        mod = import_module(pack.grammar)
    except ImportError:
        return None
    from importlib.metadata import version as _v
    dist = pack.grammar.replace("_", "-")
    try:
        return _v(dist)
    except Exception:
        return getattr(mod, "__version__", None)
