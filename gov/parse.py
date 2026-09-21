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
import os
import sys
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Iterator

try:  # package context (`gov ...`)
    from .pathmatch import glob_to_regex
    from importlib.resources import files as _res_files
    _LANGS = _res_files("gov").joinpath("langs")
except Exception:  # direct-module execution (self-test scratch dirs)
    from pathmatch import glob_to_regex
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
             "classes", "comment", "string", "factory"}
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
    factory: str | None = None
    kind_ids: dict[str, int] = field(default_factory=dict, compare=False)

    def matches(self, relpath: str) -> bool:
        """The plane's one glob grammar (pathmatch): ``**`` spans
        directories including zero of them, ``*``/``?`` never span a
        separator. fnmatch used to serve here and translated ``*`` to
        ``.*``, so a slash-less glob silently crossed directories and the
        parse layer's file sets disagreed with the gate engine's.
        """
        norm = relpath.replace("\\", "/")
        parts = norm.split("/")
        for g in self.globs:
            if "/" in g:
                if glob_to_regex(g).match(norm):
                    return True
            elif glob_to_regex(g).match(parts[-1]):
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
    # The binding's factory name is not standardized: most ship
    # `language`; the typescript one ships `language_typescript` and
    # `language_tsx` (two dialects), php and ocaml ship ONLY
    # dialect-named factories — those packs declare theirs explicitly
    # with the optional `factory` key rather than guessing here.
    lang_fn = getattr(mod, raw.get("factory") or "language", None)
    if not callable(lang_fn):
        for alt in ("language", "language_typescript", "language_tsx"):
            lang_fn = getattr(mod, alt, None)
            if callable(lang_fn):
                break
        if not callable(lang_fn):
            raise ParseUnavailable(
                f"grammar module {raw['grammar']!r} has no language() factory")
    from tree_sitter import Language  # core binding; present iff grammars are
    try:
        language = Language(lang_fn())
        kind_ids = {}
        for i in range(language.node_kind_count):
            kind_ids[language.node_kind_for_id(i)] = i
    except Exception as e:  # noqa: BLE001 — a wheel this interpreter cannot
        # load (an ABI the platform build disagrees with, a broken binary)
        # must be NAMED: the plane's answer to "this grammar is unusable
        # here" is a declared skip of that language, never a bare traceback
        # out of a command (rule 5's naming side).
        raise ParseUnavailable(
            f"language pack {name!r}: grammar {raw['grammar']!r} cannot be "
            f"loaded by this interpreter ({type(e).__name__}: {e})") from e
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
        factory=raw.get("factory"),
        kind_ids=kind_ids,
    )


_PARSER_CACHE: dict = {}


def load_parser(pack: LangPack, tsx: bool = False):
    """A Parser bound to the pack's grammar (cached per pack+variant).

    ``tsx`` selects the typescript grammar's TSX dialect: the binding
    ships both factories, but the naive factory chain always lands on
    ``language_typescript``, so every ``.tsx`` file parsed as plain TS —
    JSX and angle generics produced ERROR nodes and the metrics lied
    (U-11). The caller picks the dialect from the FILE suffix; a pack
    that ships only one factory ignores the flag."""
    from tree_sitter import Language, Parser
    key = (pack.grammar, tsx)
    cached = _PARSER_CACHE.get(key)
    if cached is not None:
        return cached
    mod = import_module(pack.grammar)
    declared = getattr(pack, "factory", None)
    if tsx:
        lang_fn = (getattr(mod, "language_tsx", None)
                   or getattr(mod, "language_typescript", None)
                   or (getattr(mod, declared) if declared else None)
                   or getattr(mod, "language", None))
    else:
        lang_fn = ((getattr(mod, declared) if declared else None)
                   or getattr(mod, "language", None)
                   or getattr(mod, "language_typescript", None)
                   or getattr(mod, "language_tsx", None))
    parser = Parser(Language(lang_fn()))
    _PARSER_CACHE[key] = parser
    return parser


def parser_for(pack: LangPack, path: Path):
    """The parser for one file of this pack: typescript splits its
    dialect by suffix (.tsx → TSX), every other pack is single-dialect."""
    if pack.grammar == "tree_sitter_typescript" and path.suffix == ".tsx":
        return load_parser(pack, tsx=True)
    return load_parser(pack)


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
    # os.walk with in-place pruning: rglob("*") enumerated the entire tree
    # first — every file under node_modules/build/.venv — and only filtered
    # afterwards, so "excluded" named the directory but never saved the walk.
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        kept: list[str] = []
        for d in sorted(dirnames):
            if d in DEFAULT_EXCLUDE or d in pack.exclude:
                excluded_dirs.add(d)
                continue
            kept.append(d)
        dirnames[:] = kept
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.is_symlink():
                continue  # never follow links out of the declared tree
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            if pack.matches(rel):
                files.append(p)
    files.sort()
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
            print(f"gov parse/stats: cannot read {p}: {e}",
                  file=sys.stderr)


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
