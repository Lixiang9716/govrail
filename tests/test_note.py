from gov import note as nt


def test_new_scaffold_and_bad_ref(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text("## D6 — x\n\n- **选项**：y\n", encoding="utf-8")
    assert nt.main(["new", "--class", "misc", "--ref", "D6", "T"]) == 2  # closed set
    assert nt.main(["new", "--class", "process", "--ref", "D99", "T"]) == 2  # bad ref
    assert nt.main(["new", "--class", "process", "--ref", "D6", "Adopt Flow"]) == 0
    out = capsys.readouterr().out
    p = tmp_path / ".agents" / "notes" / "implemented" / "process"
    created = list(p.glob("*-adopt-flow.md"))
    assert created and "Related: D6" in created[0].read_text(encoding="utf-8")
    for sec in ("## Problem", "## Decision", "## Alternatives considered"):
        assert sec in created[0].read_text(encoding="utf-8")


def test_check_catches_dangling_ref(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    d = tmp_path / ".agents" / "notes" / "implemented" / "process"
    d.mkdir(parents=True)
    (d / "2026-01-01-x.md").write_text(
        "# Agent Note: x\n\nStatus: implemented\n\n## Problem\np\n\n"
        "## Decision\nd\n\n## Alternatives considered\na\n\nLocked by D42.\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text("## D6 — x\n\n- **选项**：y\n", encoding="utf-8")
    assert nt.main(["check"]) == 1
    assert "D42" in capsys.readouterr().out


def test_new_without_decisions_table_announces_unchecked(tmp_path, monkeypatch, capsys):
    """Rule 5: 'nothing to validate against' is said, never silently skipped."""
    monkeypatch.chdir(tmp_path)
    assert nt.main(["new", "--class", "process", "--ref", "D99", "T"]) == 0
    captured = capsys.readouterr()
    assert "no decisions table found — D99 left unchecked" in captured.err
    p = tmp_path / ".agents" / "notes" / "implemented" / "process"
    assert "Related: D99" in next(p.glob("*.md")).read_text(encoding="utf-8")
