# Receipt behavior tests (issue #124/D42): chain integrity, green bar,
# tree binding, and the no-flag path staying byte-for-byte unchanged.
import json
import subprocess
import sys

import pytest

from gov import receipt as receipt_mod

# Portable gate command (#168): the Unix `true` does not exist on
# Windows — "a command that exits 0" must not depend on PATH.
PASS = [sys.executable, "-c", "pass"]


def _git(tmp_path, *args):
    subprocess.run(["git", *args], cwd=tmp_path, check=True,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")


def _init_repo(tmp_path):
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")


def _receipt_path(tmp_path):
    return tmp_path / ".gov" / "history" / "receipts.jsonl"


def _append(tmp_path, record):
    p = _receipt_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def _green_record(commit, tree=None, prev="GENESIS", dirty=False,
                  selection=None, gates=None):
    record = {
        "v": 1, "id": "", "ts": "2026-09-04T00:00:00+00:00",
        "commit": commit, "tree": tree, "dirty": dirty, "tag": "",
        "selection": selection or {"kind": "all", "value": None},
        "gates": gates or [{"gate": "a", "outcome": "PASS", "blocking": False}],
        "prev": prev,
    }
    record["id"] = "r-" + receipt_mod.compute_hash(record)[:12]
    record["hash"] = receipt_mod.compute_hash(record)
    return record


def test_chain_append_and_verify_green(tmp_path, monkeypatch, capsys):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    _append(tmp_path, _green_record(commit))
    assert receipt_mod.main(["verify", commit]) == 0
    assert "all PASS" in capsys.readouterr().out


def test_verify_fails_without_receipt(tmp_path, monkeypatch, capsys):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    assert receipt_mod.main(["verify", commit]) == 1
    assert "no receipt" in capsys.readouterr().err


def test_tampered_line_breaks_loudly(tmp_path, monkeypatch, capsys):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    good = _green_record(commit)
    _append(tmp_path, good)
    # An editor's lie: flip an outcome without re-signing.
    bad = dict(good)
    bad["gates"] = [{"gate": "a", "outcome": "FAIL", "blocking": True}]
    bad["id"] = good["id"]
    bad["hash"] = good["hash"]
    _append(tmp_path, bad)
    with pytest.raises(receipt_mod.ReceiptError, match="hash mismatch"):
        receipt_mod.load_chain(_receipt_path(tmp_path))
    assert receipt_mod.main(["verify", commit]) == 2
    assert "hash mismatch" in capsys.readouterr().err


def test_broken_prev_link_named(tmp_path, monkeypatch, capsys):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    first = _green_record(commit)
    _append(tmp_path, first)
    # History reordered/rewritten: second receipt's prev no longer chains.
    orphan = _green_record(commit, prev="GENESIS")
    _append(tmp_path, orphan)
    with pytest.raises(receipt_mod.ReceiptError, match="chain broken"):
        receipt_mod.load_chain(_receipt_path(tmp_path))


def test_partial_or_dirty_run_never_verifies(tmp_path, monkeypatch, capsys):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    r1 = _green_record(commit, selection={"kind": "gate", "value": "a"})
    _append(tmp_path, r1)
    r2 = _green_record(commit, dirty=True, prev=r1["hash"])
    _append(tmp_path, r2)
    r3 = _green_record(commit, prev=r2["hash"], gates=[
        {"gate": "a", "outcome": "PASS", "blocking": False},
        {"gate": "b", "outcome": "FAIL", "blocking": True}])
    _append(tmp_path, r3)
    assert receipt_mod.main(["verify", commit]) == 1
    err = capsys.readouterr().err
    assert "partial run" in err and "dirty" in err and "not all green" in err


def test_prefix_commit_and_record_verification(tmp_path, monkeypatch, capsys):
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    record = _green_record(commit)
    assert receipt_mod.main(["verify", commit[:8],
                             "--record", json.dumps(record)]) == 0
    # A cited record whose content was edited breaks its own hash.
    forged = dict(record)
    forged["tag"] = "forged-by-reviewer"
    assert receipt_mod.main(["verify", commit[:8],
                             "--record", json.dumps(forged)]) == 2


def test_run_receipt_end_to_end_and_no_flag_unchanged(tmp_path, monkeypatch, capsys):
    """`gov run --receipt` records and verifies; without the flag, no
    receipts file appears (runs behave exactly as today)."""
    _init_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"gates": [{"id": "ok", "command": PASS}]}), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "gates")
    from gov import gates
    monkeypatch.chdir(tmp_path)
    assert gates.main(["--receipt", "--tag", "agent"]) == 0
    out = capsys.readouterr().out
    assert "receipt: r-" in out
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    assert receipt_mod.main(["verify", commit]) == 0
    lines = _receipt_path(tmp_path).read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["tag"] == "agent"  # #120's caller rides along

    _receipt_path(tmp_path).unlink()
    assert gates.main([]) == 0
    capsys.readouterr()
    assert not _receipt_path(tmp_path).exists()  # no flag -> no receipt


def test_run_receipt_selection_scoping(tmp_path, monkeypatch, capsys):
    """A --gate run records kind=gate; verification refuses to call it full."""
    _init_repo(tmp_path)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"gates": [{"id": "ok", "command": PASS},
                    {"id": "two", "command": PASS}]}), encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "gates")
    from gov import gates
    monkeypatch.chdir(tmp_path)
    assert gates.main(["--gate", "ok", "--receipt"]) == 0
    capsys.readouterr()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    assert receipt_mod.main(["verify", commit]) == 1
    assert "partial run" in capsys.readouterr().err
