"""The shared git plumbing: quotepath, NUL listings, index reads, empty tree.

H1's whole class of failures came from listings that mangled non-ASCII
names into git's quoted octal escapes — names no matcher could match.
These tests pin the fix with a REAL quoted-path repository, not mocks.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from gov import gitutil


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", ".")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")


def test_changed_files_lists_non_ascii_paths_unquoted(tmp_path, monkeypatch):
    """A Chinese filename reaches the caller as itself — not as git's
    default quoted octal escape, which silently scoped path-matched
    gates out and made scanners open files that do not exist."""
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    name = "docs/中文文档.md"
    (tmp_path / "docs").mkdir()
    (tmp_path / name).write_text("# zh\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    (tmp_path / name).write_text("# zh changed\n", encoding="utf-8")
    (tmp_path / "docs").joinpath("plain.md").write_text("new\n", encoding="utf-8")

    files, err = gitutil.changed_files("HEAD")
    assert err is None
    assert name in files
    assert "docs/plain.md" in files  # untracked listing also NUL-split


def test_index_blob_oid_matches_hash_object(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    p = tmp_path / "f.md"
    p.write_text("content\n", encoding="utf-8")
    _git(tmp_path, "add", "f.md")
    want = _git(tmp_path, "hash-object", "f.md").stdout.strip()
    assert gitutil.index_blob_oid("f.md") == want
    p.write_text("changed\n", encoding="utf-8")  # worktree moved ahead
    # the INDEX oid is still the staged content, not the worktree
    assert gitutil.index_blob_oid("f.md") == want


def test_index_content_reads_staged_bytes_not_worktree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    (tmp_path / "f.txt").write_text("bad\n", encoding="utf-8")
    _git(tmp_path, "add", "f.txt")
    (tmp_path / "f.txt").write_text("restored\n", encoding="utf-8")
    assert gitutil.index_content("f.txt") == b"bad\n"
    assert gitutil.index_content("missing.txt") is None


def test_staged_files_and_absent_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    files, err = gitutil.staged_files()
    assert err is None and files == []
    _git(tmp_path, "add", "a.txt")
    files, _ = gitutil.staged_files()
    assert files == ["a.txt"]


def test_zero_oid_follows_object_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)  # sha1 by default
    assert gitutil.zero_oid() == "0" * 40
    assert len(gitutil.empty_tree()) == 40
    # the empty tree is a real object git can resolve
    out = _git(tmp_path, "cat-file", "-t", gitutil.empty_tree())
    assert out.stdout.strip() == "tree"


def test_scrubbed_env_drops_git_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/somewhere/else")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    env = gitutil.scrubbed_env()
    assert "GIT_DIR" not in env
    assert "GIT_AUTHOR_NAME" not in env


def test_hooks_dir_prefers_configured_path(tmp_path):
    _repo(tmp_path)
    import os
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        fallback = gitutil.hooks_dir()
        assert fallback is not None and fallback.endswith("hooks")
        _git(tmp_path, "config", "core.hooksPath", ".githooks")
        assert gitutil.hooks_dir() == str((tmp_path / ".githooks").resolve())
    finally:
        os.chdir(cwd)


def test_tracked_names_nul_safe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "中文.md").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "i")
    names, err = gitutil.tracked_names("HEAD", "docs")
    assert err is None
    assert names == ["docs/中文.md"]


def test_changed_files_outside_a_repository_reports_an_error(tmp_path, monkeypatch):
    """A non-repository answers with git's words, never a traceback.

    The zero-commit path consults git for the empty tree before diffing,
    and that consult is where a decode crash took the gbk-locale job
    down: the caller's own error report (which prints whatever git said)
    never got the chance to run."""
    monkeypatch.chdir(tmp_path)
    files, err = gitutil.changed_files("HEAD")
    assert files == []
    assert err  # git's message, handed to the caller — not raised here


_GBK_DIAGNOSTIC = b"\xd6\xc2\xc3\xfc\xb4\xed\xce\xf3"  # "致命错误", GBK


def _hostile_git(bindir: Path) -> None:
    """A `git` first on PATH whose diagnostics come back in GBK.

    That is what git does by itself on a zh-CN host: its messages follow
    the LOCALE, not the plane's pins. The shim is the locale, nothing
    else — it fails every invocation the way localized git fails one."""
    bindir.mkdir(parents=True, exist_ok=True)
    shim = bindir / "git"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.stderr.buffer.write({_GBK_DIAGNOSTIC!r})\n"
        "sys.exit(128)\n",
        encoding="utf-8")
    shim.chmod(0o755)


@pytest.mark.skipif(
    os.name == "nt",
    reason="shadowing a console app on PATH needs a .cmd shim; the class "
           "this pins is locale-driven and covered by the POSIX jobs")
def test_empty_tree_survives_a_locale_encoded_diagnostic(tmp_path, monkeypatch):
    """git's stderr is not always UTF-8, and the empty tree must still
    answer: ``mktree`` refusing is the DOCUMENTED path (read-only stores,
    non-repositories) whose fallback is the format's constant. A strict
    decode turned it into UnicodeDecodeError inside subprocess."""
    bindir = tmp_path / "bin"
    _hostile_git(bindir)
    monkeypatch.setenv(
        "PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))

    # Anti-vacuous probe: if the shim is not the `git` this process
    # spawns, the assertion below proves nothing about the plane's spawn.
    probe = subprocess.run(["git", "rev-parse", "--show-object-format"],
                           capture_output=True)
    assert probe.returncode == 128, "the PATH shim is not shadowing git"

    gitutil.empty_tree.cache_clear()
    try:
        assert gitutil.empty_tree() == "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    finally:
        gitutil.empty_tree.cache_clear()


def test_ranged_base_excludes_untracked_working_tree_keeps_them(tmp_path,
                                                                monkeypatch):
    """#363: an untracked file is part of the WORKING TREE, not of any
    commit range — a push (or a ranged review) cannot carry a file that
    is in no commit, so it must not be able to block one."""
    monkeypatch.chdir(tmp_path)
    _repo(tmp_path)
    (tmp_path / "tracked.md").write_text("v1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    (tmp_path / "tracked.md").write_text("v1.5\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "second")   # HEAD~1 needs two commits
    (tmp_path / "scratch.txt").write_text("someone else's probe\n",
                                          encoding="utf-8")
    (tmp_path / "tracked.md").write_text("v2\n", encoding="utf-8")

    ranged, err = gitutil.changed_files("HEAD~1")
    assert err is None
    assert "tracked.md" in ranged
    assert "scratch.txt" not in ranged, (
        "a commit range carries committed content only")

    worktree, err = gitutil.changed_files("HEAD")
    assert err is None
    assert "scratch.txt" in worktree, (
        "the working-tree scope still reviews untracked files")
