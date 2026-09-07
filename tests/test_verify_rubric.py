from pathlib import Path

from gov import verify_rubric as vr


def _rubric(*items: str) -> str:
    return "# Review rubric\n\n" + "\n".join(items)


def _item(n: int, gate_candidate: str = "no — judgment") -> str:
    return (
        f"### R{n} — item {n}\n\n"
        f"- **Checks:** something real to examine {n}.\n"
        f"- **Evidence:** the observed proof {n}.\n"
        f"- **Anti-pattern:** the failure shape {n}.\n"
        f"- **Gate candidate:** {gate_candidate}\n"
    )


def test_valid_rubric_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "review-rubric.md").write_text(_rubric(_item(1), _item(2)), encoding="utf-8")
    (docs / "review-rubric.zh.md").write_text(_rubric(_item(1), _item(2)), encoding="utf-8")
    assert vr.main([]) == 0
    assert "2 item(s) ok + zh" in capsys.readouterr().out


def test_missing_field_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    broken = _item(1).replace("- **Evidence:** the observed proof 1.\n", "")
    (docs / "review-rubric.md").write_text(_rubric(broken), encoding="utf-8")
    assert vr.main([]) == 1
    out = capsys.readouterr().out
    assert "R1" in out and "Evidence" in out


def test_gap_in_numbering_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "review-rubric.md").write_text(_rubric(_item(1), _item(3)), encoding="utf-8")
    assert vr.main([]) == 1
    assert "contiguous from R1" in capsys.readouterr().out


def test_gate_candidate_yes_needs_destination(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "review-rubric.md").write_text(_rubric(_item(1, gate_candidate="yes")), encoding="utf-8")
    assert vr.main([]) == 1
    assert "graduates" in capsys.readouterr().out


def test_zh_id_parity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "review-rubric.md").write_text(_rubric(_item(1), _item(2)), encoding="utf-8")
    (docs / "review-rubric.zh.md").write_text(_rubric(_item(1)), encoding="utf-8")  # missing R2
    assert vr.main([]) == 1
    assert "missing on zh side: R2" in capsys.readouterr().out


def test_zh_side_fields_are_translators_freedom(tmp_path, monkeypatch):
    """Only id parity is enforced on the translated side, not English labels."""
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "review-rubric.md").write_text(_rubric(_item(1)), encoding="utf-8")
    (docs / "review-rubric.zh.md").write_text("### R1 — 中文条目\n\n- **查什么：** 中文内容。\n", encoding="utf-8")
    assert vr.main([]) == 0


def test_missing_file_fails_loud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert vr.main([]) == 2


def test_path_flag(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "my-rubric.md"
    p.write_text(_rubric(_item(1)), encoding="utf-8")
    assert vr.main(["--path", str(p)]) == 0
    assert "1 item(s) ok" in capsys.readouterr().out
