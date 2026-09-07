import subprocess

from gov import verify_decisions as vd


def _table(*sections):
    return "# 决策\n\n" + "\n".join(sections)


def _d(n, body="- **选项**：x\n- **被否**：y\n"):
    return f"## D{n} — t{n}\n\n{body}\n"


def _git_repo(root):
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True)


def test_clean_table_passes_d0_or_d1_start(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text(_table(_d(1), _d(2), _d(3)), encoding="utf-8")
    assert vd.main([]) == 0
    assert "3 decision(s) ok" in capsys.readouterr().out


def test_duplicate_and_gap_named(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    # D1, D1 (duplicate), then D3 with D2 missing
    (docs / "decisions.md").write_text(_table(_d(1), _d(1), _d(3)), encoding="utf-8")
    assert vd.main([]) == 1
    out = capsys.readouterr().out
    assert "D1: duplicate decision entry" in out
    assert "missing: D2" in out


def test_missing_alternatives_named(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text(_table(
        _d(1), _d(2, body="- **状态**：已决\n- **决定**：就这么办。\n")), encoding="utf-8")
    assert vd.main([]) == 1
    out = capsys.readouterr().out
    assert "D2: records no options or rejected alternatives" in out


def test_orphans_informational_not_blocking(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text(_table(_d(1), _d(2)), encoding="utf-8")
    notes = tmp_path / ".agents" / "notes" / "implemented" / "architecture"
    notes.mkdir(parents=True)
    (notes / "x.md").write_text("locked by D1\n", encoding="utf-8")
    assert vd.main([]) == 0  # D2 orphaned but that is information
    out = capsys.readouterr().out
    assert "referenced by no note: D2 (informational)" in out
    assert "2 decision(s) ok, 1 orphan(s)" in out


def test_no_table_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert vd.main([]) == 0


def test_review_by_overdue_and_future(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text(_table(
        _d(1, body="- **选项**：x\n- **review-by**: 2020-01-01\n"),
        _d(2, body="- **选项**：x\n- **review-by**: 2099-01-01\n"),
        _d(3, body="- **选项**：x\n- **review-by**: not-a-date\n"),
    ), encoding="utf-8")
    assert vd.main([]) == 1  # the unparseable date is a real violation
    out = capsys.readouterr().out
    assert "D3: unparseable review-by date 'not-a-date'" in out
    assert "review due — context may have drifted: D1 (review-by 2020-01-01)" in out
    assert "D2 (review-by" not in out  # future date stays silent


def test_json_mode_pure_stdout(tmp_path, monkeypatch, capsys):
    """#119: verify-decisions --json — stdout is exactly one JSON object;
    the human report moves to stderr."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text(_table(
        _d(1),
        _d(2, body="nothing rejected here\n"),
        _d(4),  # gap -> numbering violation too
    ), encoding="utf-8")
    assert vd.main(["--json"]) == 1
    captured = capsys.readouterr()
    payload = _json.loads(captured.out)
    assert payload["status"] == "violations"
    assert payload["decisions"] == 3
    assert any("D2" in v and "alternatives" in v for v in payload["violations"])  # en word
    assert any("D2" in v for v in payload["violations"])
    assert any("contiguous" in v for v in payload["violations"])
    assert "verify_decisions" in captured.err  # human report on stderr
    # the ok path also reports JSON
    (docs / "decisions.md").write_text(_table(_d(1), _d(2)), encoding="utf-8")
    assert vd.main(["--json"]) == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok" and payload["violations"] == []
