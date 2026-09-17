"""atomicio: one atomic-write policy — umask-aware for new files."""
import os
import stat

import pytest

from gov import atomicio

posix_only = pytest.mark.skipif(
    os.name == "nt",
    reason="umask and POSIX mode bits are not enforced on Windows")


@posix_only
def test_rewrite_preserves_existing_mode(tmp_path):
    p = tmp_path / "ledger.jsonl"
    p.write_text("x\n", encoding="utf-8")
    p.chmod(0o640)
    atomicio.write_text(p, "y\n")
    assert stat.S_IMODE(p.stat().st_mode) == 0o640


@posix_only
def test_new_file_respects_umask(tmp_path):
    """A hardcoded 0644 leaked ledgers global-readable on shared machines
    running a tighter umask (N5)."""
    old = os.umask(0o137)  # results in 0640 for new files
    try:
        p = tmp_path / "ledger.jsonl"
        atomicio.write_text(p, "x\n")
        assert stat.S_IMODE(p.stat().st_mode) == 0o640
    finally:
        os.umask(old)


def test_replace_is_atomic_content(tmp_path):
    p = tmp_path / "f.txt"
    atomicio.write_text(p, "v1\n")
    atomicio.write_text(p, "v2\n")
    assert p.read_text(encoding="utf-8") == "v2\n"


# --- N10: the append refuses a symlinked final component --------------

def test_append_line_writes_and_appends(tmp_path):
    p = tmp_path / "ledger.jsonl"
    atomicio.append_line(p, '{"a": 1}\n')
    atomicio.append_line(p, '{"a": 2}\n')
    assert p.read_text(encoding="utf-8") == '{"a": 1}\n{"a": 2}\n'


@pytest.mark.skipif(os.name == "nt",
                    reason="creating symlinks needs privileges on Windows")
def test_append_line_refuses_symlink(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("mine\n", encoding="utf-8")
    ledger = tmp_path / "ledger.jsonl"
    ledger.symlink_to(outside)
    with pytest.raises(atomicio.SymlinkRefused, match="symlink"):
        atomicio.append_line(ledger, '{"stolen": true}\n')
    assert outside.read_text(encoding="utf-8") == "mine\n", \
        "the external file must not gain a byte"


def test_write_bytes_is_atomic_and_exact(tmp_path):
    p = tmp_path / "hook"
    atomicio.write_bytes(p, b"#!/bin/sh\nexit 0\n")
    assert p.read_bytes() == b"#!/bin/sh\nexit 0\n"
    atomicio.write_bytes(p, b"#!/bin/sh\nexit 1\n")
    assert p.read_bytes() == b"#!/bin/sh\nexit 1\n"


def test_append_line_refuses_a_symlinked_parent_directory(tmp_path,
                                                          monkeypatch):
    """The round-10 review's probe: O_NOFOLLOW and a final-component
    lstat are blind to a LINKED DIRECTORY — `.gov/history` pointing
    outside turned every ledger open into an outside write. Containment
    walks the parent chain (the owning work-tree root is the boundary)."""
    import subprocess as sp
    sp.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (tmp_path / ".gov").mkdir()
    (tmp_path / ".gov" / "history").symlink_to(outside_dir,
                                               target_is_directory=True)
    ledger = tmp_path / ".gov" / "history" / "gates.jsonl"
    with pytest.raises(atomicio.SymlinkRefused, match="symlink"):
        atomicio.append_line(ledger, '{"run": 1}\n')
    assert list(outside_dir.iterdir()) == [], "the external dir gained a file"


def test_contained_deep_unlinked_chain_writes(tmp_path, monkeypatch):
    """Positive control: a real directory chain under the work-tree
    root writes fine — containment refuses links, not depth."""
    monkeypatch.chdir(tmp_path)
    import subprocess as sp
    sp.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    deep = tmp_path / ".gov" / "history" / "deeper"
    deep.mkdir(parents=True)
    ledger = deep / "ledger.jsonl"
    atomicio.append_line(ledger, '{"ok": true}\n')
    assert ledger.read_text(encoding="utf-8") == '{"ok": true}\n'
