"""#414: the code-size scan takes a per-path filter — a parallel worker
gets a verdict for ITS files without paying the whole-tree scan;
whole-tree stays the default and the CI mode."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_size_limits  # noqa: E402


@pytest.fixture()
def tiny_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "big.py").write_text("x = 0\n" * 30,
                                             encoding="utf-8")
    (tmp_path / "src" / "small.py").write_text("x = 0\n", encoding="utf-8")
    cfg = tmp_path / "limits.json"
    cfg.write_text(json.dumps({
        "default": 10,
        "scan": ["src/**/*.py"],
    }), encoding="utf-8")
    return tmp_path, cfg


def test_only_judges_the_named_file(tiny_repo, capsys):
    tmp_path, cfg = tiny_repo
    assert check_size_limits.main(
        ["--root", str(tmp_path), "--config", str(cfg),
         "--only", "src/big.py"]) == 1
    err = capsys.readouterr().err
    assert "src/big.py: 30 lines (limit 10" in err
    assert "small.py" not in err, "the unrequested file is not judged"


def test_only_basename_glob_and_no_match_refusal(tiny_repo, capsys):
    tmp_path, cfg = tiny_repo
    # slash-less filter matches a basename
    assert check_size_limits.main(
        ["--root", str(tmp_path), "--config", str(cfg),
         "--only", "small.py"]) == 0
    out = capsys.readouterr().out
    assert "within limits" in out and "1 of 2 file(s)" in out
    # a filter matching nothing is a typo, not a pass (rule 5)
    with pytest.raises(SystemExit) as exc:
        check_size_limits.main(
            ["--root", str(tmp_path), "--config", str(cfg),
             "--only", "nope/*.py"])
    assert exc.value.code == 2
    assert "matched none" in capsys.readouterr().err
