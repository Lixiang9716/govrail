from pathlib import Path

from gov import verify_notes

VALID = (
    "# Agent Note: t\n\n"
    "Status: implemented\n\n"
    "## Problem\np\n\n"
    "## Decision\nd\n\n"
    "## Alternatives considered\na\n"
)


def _note(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "n.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_note_passes(tmp_path):
    assert verify_notes.check_note(_note(tmp_path, VALID)) == []


def test_missing_alternatives_fails(tmp_path):
    text = VALID.replace("## Alternatives considered\na\n", "")
    errs = verify_notes.check_note(_note(tmp_path, text))
    assert any("Alternatives considered" in e for e in errs)


def test_missing_decision_fails(tmp_path):
    text = VALID.replace("## Decision\nd\n", "")
    errs = verify_notes.check_note(_note(tmp_path, text))
    assert any("Decision" in e for e in errs)


def test_missing_title_fails(tmp_path):
    text = "Status: implemented\n\n## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n"
    errs = verify_notes.check_note(_note(tmp_path, text))
    assert any("title" in e for e in errs)


def test_bom_prefixed_note_passes(tmp_path, monkeypatch):
    """A UTF-8 BOM is a legal encoding artifact Windows editors add —
    the memory plane decodes it away instead of failing the title
    check with a violation the author cannot see."""
    d = tmp_path / ".agents" / "notes" / "implemented" / "feature"
    d.mkdir(parents=True)
    (d / "2026-01-01-b.md").write_bytes(
        "\ufeff".encode("utf-8") + VALID.encode("utf-8"))
    monkeypatch.chdir(tmp_path)
    assert verify_notes.main([]) == 0


GARBAGE = "not a note at all\n"


def test_uppercase_extension_note_is_checked_in_class_dir(tmp_path, monkeypatch, capsys):
    """H-7: BYPASS.MD under implemented/<class>/ is a note whatever the
    extension's case — garbage content must fail the gate, not buy a
    silent exemption from the case-sensitive *.md scan."""
    d = tmp_path / ".agents" / "notes" / "implemented" / "feature"
    d.mkdir(parents=True)
    (d / "BYPASS.MD").write_text(GARBAGE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert verify_notes.main([]) == 1
    err = capsys.readouterr().out
    assert "BYPASS.MD" in err and "violation" in err


def test_uppercase_extension_loose_note_is_flagged(tmp_path, monkeypatch, capsys):
    """H-7: BYPASS.MD sitting loose at the notes root used to be
    invisible to the placement check (suffix == ".md" is case-sensitive)
    — it must be named like any other loose note."""
    (tmp_path / ".agents" / "notes").mkdir(parents=True)
    (tmp_path / ".agents" / "notes" / "BYPASS.MD").write_text(
        VALID, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert verify_notes.main([]) == 1
    assert "BYPASS.MD" in capsys.readouterr().out


def test_uppercase_extension_valid_note_still_passes(tmp_path, monkeypatch):
    """H-7: the case-insensitive scan is not a crackdown — a well-formed
    note with an uppercase extension passes placement and format."""
    d = tmp_path / ".agents" / "notes" / "implemented" / "feature"
    d.mkdir(parents=True)
    (d / "2026-01-01-c.MD").write_text(VALID, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert verify_notes.main([]) == 0


def _scaffold() -> str:
    from gov import note as nt
    return nt.SKELETON.format(
        title="t", related="",
        ph_problem=nt.PLACEHOLDERS["## Problem"],
        ph_decision=nt.PLACEHOLDERS["## Decision"],
        ph_alternatives=nt.PLACEHOLDERS["## Alternatives considered"])


def test_note_new_scaffold_fails_as_written(tmp_path):
    """The D3 flip: `gov note new`'s own output no longer passes the
    gate unfilled — every hollow section is named."""
    errs = verify_notes.check_note(_note(tmp_path, _scaffold()))
    assert len(errs) == 3 and all("placeholder" in e for e in errs), errs


def test_partial_fill_names_only_hollow_sections(tmp_path):
    text = _scaffold()
    text = text.replace("(pain, stated to stand without the solution)",
                        "the gate could not tell a real note from an empty one")
    errs = verify_notes.check_note(_note(tmp_path, text))
    assert len(errs) == 2, errs
    assert all("## Decision" in e or "## Alternatives considered" in e
               for e in errs)


def test_empty_section_fails(tmp_path):
    text = VALID.replace("## Problem\np\n", "## Problem\n")
    errs = verify_notes.check_note(_note(tmp_path, text))
    assert any("'## Problem' section is empty" in e for e in errs), errs


def test_gate_rejects_scaffold_in_tree(tmp_path, monkeypatch):
    """Through main(): a scaffold dropped into implemented/ turns the
    gate red naming the note — the pre-push hook cannot be slept past."""
    d = tmp_path / ".agents" / "notes" / "implemented" / "process"
    d.mkdir(parents=True)
    (d / "2026-01-01-s.md").write_text(_scaffold(), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert verify_notes.main([]) == 1
