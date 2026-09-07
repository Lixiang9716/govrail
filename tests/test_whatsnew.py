import json
import re
from pathlib import Path

import gov.whatsnew as wn


def test_whatsnew_since_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gov").mkdir()
    (tmp_path / ".gov" / "manifest.json").write_text(
        json.dumps({"version": "0.10.0"}), encoding="utf-8")
    assert wn.main([]) == 0
    out = capsys.readouterr().out
    assert "since 0.10.0" in out
    assert "0.12.1" in out and "0.11.0" in out
    assert "0.9.0" not in out  # not newer than 0.10.0


def test_whatsnew_no_project_prints_newest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert wn.main([]) == 0
    out = capsys.readouterr().out
    assert "newest section" in out
    assert re.search(r"## 0\.\d+", out)


def test_whatsnew_explicit_since(capsys):
    assert wn.main(["--since", "0.11.0"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"## 0\.1[2-9]", out) and "## 0.11.0" not in out


def test_every_released_tag_has_a_highlights_section():
    """Version alignment guard: a HIGHLIGHTS header written with a guessed
    number that release-please then versioned differently goes red here
    (the 0.12.3/0.13.0 mismatch, caught twice in the field)."""
    import re as _re
    import subprocess as _sp
    from gov import whatsnew as _wn
    tags = _sp.run(["git", "tag", "--list", "v*"], capture_output=True,
                   text=True).stdout.split()
    if not tags:
        import pytest as _pytest
        _pytest.skip("no tags available to check (CI fetch-tags race or a "
                     "fresh clone) — said, never silently passed")
    released = sorted(
        tuple(int(x) for x in t[1:].split("."))
        for t in tags if t.startswith("v")
    )
    floor = (0, 12, 0)  # highlights coverage begins here
    text = _wn._HIGHLIGHTS.read_text(encoding="utf-8")
    sections = {
        tuple(int(x) for x in v.split("."))
        for v in _re.findall(r"(?m)^## (\d+\.\d+\.\d+) ", text)
    }
    missing = [f"0.{v[0]}.{v[1]}.{v[2]}" if v[0] == 0 else str(v)
               for v in released if v >= floor and v not in sections]
    assert not missing, (
        f"released versions without a HIGHLIGHTS section: {', '.join(missing)} "
        "— align the section header with the wheel version"
    )


from unittest import mock


def test_mapping_note_when_wheel_lags(tmp_path, monkeypatch, capsys):
    """#92 wheel-lag residual: an unsectioned wheel says the mapping."""
    from unittest import mock
    import gov.whatsnew as wn
    with mock.patch("gov.whatsnew._pkg_version", "9.9.9"):
        assert wn.main(["--since", "9.9.8"]) == 0
    out = capsys.readouterr().out
    assert "govrail 9.9.9 installed" in out
    assert "wheel 9.9.9 has no dedicated highlights section" in out


def test_installed_version_always_stated(capsys):
    """The header names the wheel version — identity is explicit either way."""
    import gov.whatsnew as wn
    from gov import __version__ as v
    assert wn.main(["--since", "9.9.8"]) == 0
    assert f"govrail {v} installed" in capsys.readouterr().out
