"""D34: provenance eras, adopt preview/disclosure, external D-references."""
import hashlib
import json
import subprocess
from pathlib import Path

from gov import cli


def _repo(root):
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True)


def test_external_d_reference_is_legal(tmp_path, monkeypatch, capsys):
    """govrail:D24 references the tool's table, never the local one."""
    monkeypatch.chdir(tmp_path)
    notes = tmp_path / ".agents" / "notes" / "implemented" / "process"
    notes.mkdir(parents=True)
    (notes / "x.md").write_text(
        "# Agent Note: x\n\nStatus: implemented\nRelated: govrail:D24\n\n"
        "## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n"
        "Locked by govrail:D32 too.\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text("## D1 — local\n\n- **选项**：y\n", encoding="utf-8")
    from gov import audit_notes, verify_decisions
    assert audit_notes.main([]) == 0  # no missing-D signal for govrail:D24/32
    assert verify_decisions.main([]) == 0
    out = capsys.readouterr().out
    # D1 is orphaned (the note references only EXTERNAL Ds) — informational
    assert "referenced by no note: D1" in out
    from gov import note as nt
    assert nt.main(["check"]) == 0
    # note new accepts an external ref without local validation
    assert nt.main(["new", "--class", "process", "--ref", "govrail:D24",
                    "External"]) == 0
    assert "external reference" in capsys.readouterr().out


def test_local_d_ref_still_validated(tmp_path, monkeypatch, capsys):
    """The namespace does not weaken local validation: a bare D99 still fails."""
    monkeypatch.chdir(tmp_path)
    notes = tmp_path / ".agents" / "notes" / "implemented" / "process"
    notes.mkdir(parents=True)
    (notes / "x.md").write_text(
        "# Agent Note: x\n\nStatus: implemented\n\n## Problem\np\n\n"
        "## Decision\nLocked by D99.\n\n## Alternatives considered\na\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text("## D1 — local\n\n- **选项**：y\n", encoding="utf-8")
    from gov import audit_notes
    assert audit_notes.main([]) == 0  # advisory
    assert "D99" in capsys.readouterr().out  # ...but named


def test_manifest_records_template_hashes(tmp_path):
    _repo(tmp_path)
    assert cli.init(tmp_path) == 0
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    hashes = manifest.get("templates", {})
    assert ".gov/rules.md" in hashes
    assert "gates.json" in hashes
    tpl = Path(__file__).resolve().parent.parent / "gov" / "templates"
    expect = hashlib.sha256((tpl / "rules.md").read_bytes()).hexdigest()
    assert hashes[".gov/rules.md"] == expect
