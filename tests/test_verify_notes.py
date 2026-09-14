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
