import json

import pytest

from gov import cli

from gov import archive_notes as an


def test_seals_nothing_without_crashing(tmp_path, monkeypatch, capsys):
    """A fresh init has no archived/ dir — sealing must not traceback."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents" / "notes" / "implemented").mkdir(parents=True)
    assert an.main([]) == 0
    assert "nothing to seal" in capsys.readouterr().out
    assert not (tmp_path / ".agents" / "notes" / "archived" / "manifest.json").exists()


def test_seals_real_notes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    arch = tmp_path / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    (arch / "2026-01-01-x.md").write_text("# Agent Note: x\n", encoding="utf-8")
    assert an.main([]) == 0
    manifest = tmp_path / ".agents" / "notes" / "archived" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "process/2026-01-01-x.md" in data["files"]


def test_rejects_unknown_args(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents" / "notes").mkdir(parents=True)
    with pytest.raises(SystemExit) as exc:
        an.main(["--bogus"])
    assert exc.value.code == 2  # argparse: unknown args abort loud


def test_fails_loud_outside_governed_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert an.main([]) == 2


def test_cli_dispatch_forwards_args(tmp_path, monkeypatch):
    """`gov archive-notes --bogus` must abort loud, not swallow the flag."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".agents" / "notes").mkdir(parents=True)
    with pytest.raises(SystemExit) as exc:
        cli.main(["archive-notes", "--bogus"])
    assert exc.value.code == 2  # argparse aborts loud (same as verify-pairing)
    assert cli.main(["archive-notes"]) == 0


def test_reseal_refuses_tampering_and_laundering(tmp_path, monkeypatch, capsys):
    """F7: a drifted seal blocks re-sealing; --rebaseline is explicit consent."""
    monkeypatch.chdir(tmp_path)
    arch = tmp_path / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    note = arch / "2026-01-01-x.md"
    note.write_text("# Agent Note: x\n", encoding="utf-8")
    assert an.main([]) == 0  # first seal
    note.write_text("# Agent Note: x  # tampered\n", encoding="utf-8")
    assert an.main([]) == 1  # re-seal refuses
    assert "refusing to re-seal" in capsys.readouterr().out
    from gov import verify_archive as va
    assert va.main([]) == 1  # the detector sees it
    assert "differs from its seal" in capsys.readouterr().out
    assert an.main(["--rebaseline"]) == 0  # explicit consent
    out = capsys.readouterr().out
    assert "RE-BASELINED 1" in out
    assert va.main([]) == 0  # seal now matches reality (consented)


def test_verify_archive_clean_and_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from gov import verify_archive as va
    assert va.main([]) == 0  # nothing archived
    arch = tmp_path / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    (arch / "a.md").write_text("a\n", encoding="utf-8")
    (arch / "b.md").write_text("b\n", encoding="utf-8")
    assert va.main([]) == 1  # files but no seal
    assert "no seal" in capsys.readouterr().out
    assert an.main([]) == 0
    (arch / "c.md").write_text("c\n", encoding="utf-8")  # new note, not yet sealed
    assert va.main([]) == 1
    out = capsys.readouterr().out
    assert "not in the seal" in out
    assert an.main([]) == 0  # extends the seal; existing verified


def test_verify_archive_sealed_but_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from gov import verify_archive as va
    arch = tmp_path / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    (arch / "gone.md").write_text("g\n", encoding="utf-8")
    assert an.main([]) == 0
    (arch / "gone.md").unlink()
    assert va.main([]) == 1
    assert "sealed but the file is gone" in capsys.readouterr().out
