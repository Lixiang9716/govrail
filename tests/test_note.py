from gov import note as nt


def test_new_scaffold_and_bad_ref(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text("## D6 — x\n\n- **选项**：y\n", encoding="utf-8")
    assert nt.main(["new", "--class", "misc", "--ref", "D6", "T"]) == 2  # closed set
    assert nt.main(["new", "--class", "process", "--ref", "D99", "T"]) == 2  # bad ref
    assert nt.main(["new", "--class", "process", "--ref", "D6", "Adopt Flow"]) == 0
    capsys.readouterr()
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


def _seed_notes(root):
    impl = root / ".agents" / "notes" / "implemented" / "bug-fix"
    impl.mkdir(parents=True)
    (impl / "2026-01-01-lock.md").write_text(
        "# Agent Note: the lock fix\n\nStatus: implemented\n\n"
        "## Problem\np\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")
    test_dir = root / ".agents" / "notes" / "implemented" / "testing"
    test_dir.mkdir(parents=True)
    (test_dir / "2026-01-02-e2e.md").write_text(
        "# Agent Note: the e2e batch\n\nStatus: implemented\n\n"
        "## Problem\np\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")


def test_list_lists_and_filters(tmp_path, monkeypatch, capsys):
    import json as _json
    from gov import note as note_mod
    _seed_notes(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert note_mod.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "2026-01-01-lock.md — Agent Note: the lock fix" in out
    assert "2026-01-02-e2e.md" in out
    capsys.readouterr()
    assert note_mod.main(["list", "--class", "testing"]) == 0
    out = capsys.readouterr().out
    assert "2026-01-02-e2e.md" in out and "2026-01-01-lock.md" not in out
    capsys.readouterr()
    assert note_mod.main(["list", "--json"]) == 0
    rows = _json.loads(capsys.readouterr().out)
    assert {r["class"] for r in rows} == {"bug-fix", "testing"}


def test_show_resolves_prefix_and_refuses_ambiguity(tmp_path, monkeypatch, capsys):
    from gov import note as note_mod
    _seed_notes(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert note_mod.main(["show", "2026-01-01-lock"]) == 0
    assert "the lock fix" in capsys.readouterr().out
    # a prefix that matches nothing is a named exit 2
    import pytest
    with pytest.raises(SystemExit) as exc:
        note_mod.main(["show", "no-such-note"])
    assert exc.value.code == 2
    assert "no implemented note matches" in capsys.readouterr().err
    # a prefix matching several is ambiguous, named (rule 5)
    with pytest.raises(SystemExit) as exc:
        note_mod.main(["show", "2026-01-0"])
    assert exc.value.code == 2
    assert "ambiguous" in capsys.readouterr().err
