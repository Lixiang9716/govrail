"""gov verify-conflict-markers — issue #104's content gate, unit-pinned.

The rejection cases in gov/self_test.py prove the gate can go red; these
tests pin the contract's edges: the sibling rule for a bare =======, the
ignore-token escape hatch, binary and deleted files, --staged, and the
fail-loud exit on an unusable base.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "gov" / "verify_conflict_markers.py"

MARKED = (
    "# doc\n\n"
    + "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _repo(root: Path) -> None:
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "-c", "commit.gpgsign=false", "commit", "-qm", "init")


def _gate(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=root, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")


def test_marked_file_fails_naming_file_and_line(tmp_path):
    _repo(tmp_path)
    (tmp_path / "doc.md").write_text(MARKED, encoding="utf-8")
    r = _gate(tmp_path)
    assert r.returncode == 1
    assert "doc.md:3" in r.stdout
    assert "doc.md:5" in r.stdout   # the bare separator, flagged beside kin
    assert "doc.md:7" in r.stdout
    assert "gov:ignore-marker" in r.stdout  # the escape hatch is named


def test_clean_tree_passes(tmp_path):
    _repo(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    assert _gate(tmp_path).returncode == 0


def test_bare_separator_alone_is_not_a_marker(tmp_path):
    """A Markdown setext underline with no sibling marker stays legal."""
    _repo(tmp_path)
    (tmp_path / "README.md").write_text("Title\n=======\n\nbody\n", encoding="utf-8")
    assert _gate(tmp_path).returncode == 0


def test_ignore_token_exempts_deliberate_literal(tmp_path):
    _repo(tmp_path)
    (tmp_path / "t.py").write_text(
        'snippet = ("<<<<<<< HEAD gov:ignore-marker\n"\n'
        '           "<<<<<<< deeper  gov:ignore-marker\n")\n',
        encoding="utf-8",
    )
    assert _gate(tmp_path).returncode == 0


def test_diff3_base_marker_is_primary(tmp_path):
    _repo(tmp_path)
    (tmp_path / "c.txt").write_text(
        "a\n" + "||||||| merged common ancestors\nx\n=======\ny\n>>>>>>> z\n",
        encoding="utf-8",
    )
    r = _gate(tmp_path)
    assert r.returncode == 1
    assert "c.txt:2" in r.stdout


def test_eight_markers_do_not_match(tmp_path):
    """Only exactly seven marker characters count (#104's precision)."""
    _repo(tmp_path)
    (tmp_path / "wide.txt").write_text(
        "<<<<<<<< eight\n" + ">>>>>>>> eight\n", encoding="utf-8")
    assert _gate(tmp_path).returncode == 0


def test_binary_and_deleted_files_are_skipped(tmp_path):
    _repo(tmp_path)
    (tmp_path / "gone.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "two")
    _git(tmp_path, "rm", "-q", "gone.txt")
    (tmp_path / "blob.bin").write_bytes(b"<<<<<<< \x00 =======\n")
    assert _gate(tmp_path).returncode == 0


def test_staged_scans_the_index_and_is_quiet_when_clean(tmp_path):
    _repo(tmp_path)
    assert _gate(tmp_path, "--staged").returncode == 0
    (tmp_path / "s.md").write_text("<<<<<<< HEAD\n", encoding="utf-8")
    _git(tmp_path, "add", "s.md")
    r = _gate(tmp_path, "--staged")
    assert r.returncode == 1
    assert "s.md:1" in r.stdout


def test_explicit_base_pins_the_range(tmp_path):
    _repo(tmp_path)
    (tmp_path / "a.md").write_text("clean\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "commit.gpgsign=false", "commit", "-qm", "two")
    (tmp_path / "b.md").write_text("<<<<<<< HEAD\n", encoding="utf-8")
    r = _gate(tmp_path, "--base", "HEAD")
    assert r.returncode == 1
    assert "b.md:1" in r.stdout


def test_bad_base_fails_loud(tmp_path):
    _repo(tmp_path)
    r = _gate(tmp_path, "--base", "no-such-ref")
    assert r.returncode == 2
    assert "no-such-ref" in r.stderr
