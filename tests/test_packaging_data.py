"""Pin the wheel's package-data against the tree it ships from.

``pyproject.toml`` [tool.setuptools.package-data] enumerates the data
files a wheel carries; a new shipped file missing from the globs works
in every editable/dev layout and breaks every wheel install — found
live when python-lib's ``note-presence.json`` (#310) made
``gov preset list`` exit 2 under the docker e2e shadow install while
the dev suite stayed green. The docker cells are the runtime catch;
this module is the fast structural catch: every file on disk under a
shipped data directory must be matched by at least one declared glob,
expanded relative to the package directory with the same glob machinery
a wheel build applies (directories are not shipped; __pycache__ is not
shipped).
"""
from __future__ import annotations

import glob
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _package_data() -> dict[str, list[str]]:
    raw = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return raw["tool"]["setuptools"]["package-data"]


def _matched_files(base: Path, patterns: list[str]) -> set[Path]:
    matched: set[Path] = set()
    for pattern in patterns:
        for hit in glob.glob(str(base / pattern), recursive=True):
            p = Path(hit)
            if p.is_file() and "__pycache__" not in p.parts:
                matched.add(p)
    return matched


def _tree(base: Path) -> set[Path]:
    # *.py files ship through the package mechanism (modules), not
    # package-data — only data files answer to the globs.
    return {p for p in base.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
            and p.suffix != ".py"}


def _missing(base: Path, judged: set[Path],
             patterns: list[str]) -> list[str]:
    missing = sorted(
        f.relative_to(REPO).as_posix() for f in judged - _matched_files(
            base, patterns))
    assert not missing, (
        "shipped data file(s) missing from the pyproject package-data "
        "globs — they work in editable installs and break every wheel "
        "install: " + ", ".join(missing)
        + " (extend [tool.setuptools.package-data])")
    return []


@pytest.mark.parametrize(
    "row, base_rel, judged_rel",
    [
        # every file under gov/templates ships (the presets/*/… lesson:
        # one new bundle file, one broken wheel install per adopter)
        ("gov.templates", "gov/templates", "gov/templates"),
        # the parse-layer packs and the shipped check rules ship
        ("gov", "gov", "gov/langs"),
        ("gov", "gov", "gov/checks"),
    ],
)
def test_package_data_row_covers_its_tree(
        row: str, base_rel: str, judged_rel: str) -> None:
    patterns = _package_data().get(row)
    assert patterns, f"the {row!r} package-data row disappeared"
    _missing(REPO / base_rel, _tree(REPO / judged_rel), patterns)


def test_base_row_covers_the_highlights_ledger() -> None:
    patterns = _package_data().get("gov")
    assert "HIGHLIGHTS.md" in patterns, (
        "gov/HIGHLIGHTS.md must stay shipped — whatsnew and doc-sync "
        "read it from the installed package")
