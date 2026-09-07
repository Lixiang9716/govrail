"""CHANGELOG ↔ HIGHLIGHTS pairing (D37)."""
import subprocess
import sys
from pathlib import Path

from gov import verify_doc_sync as vds


def test_paired_versions_pass():
    assert vds.main([]) == 0


def test_changelog_gains_version_highlights_missing(tmp_path, monkeypatch, capsys):
    """The release-please flow: CHANGELOG gains a section, HIGHLIGHTS
    hasn't followed yet — the gate goes red, naming the version to copy."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.14.0] (2026-09-04)\n\n### Features\n\n* new thing\n", encoding="utf-8")
    gov = tmp_path / "gov"
    gov.mkdir()
    (gov / "HIGHLIGHTS.md").write_text(
        "## 0.13.2 — old\n\n- something\n", encoding="utf-8")
    assert vds.main([]) == 1
    out = capsys.readouterr().out
    assert "CHANGELOG has [0.14.0] but HIGHLIGHTS has no section" in out
    assert "copy the version FROM CHANGELOG" in out


def test_highlights_ahead_of_changelog(tmp_path, monkeypatch, capsys):
    """A section written for a version that hasn't released yet — the gate
    catches the direction too (section shipped before its release)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.13.0] (2026-09-03)\n\n### Features\n\n* something\n", encoding="utf-8")
    gov = tmp_path / "gov"
    gov.mkdir()
    (gov / "HIGHLIGHTS.md").write_text(
        "## 0.14.0 — guessed\n\n- not released yet\n\n## 0.13.0 — real\n\n- something\n", encoding="utf-8")
    assert vds.main([]) == 1
    assert "HIGHLIGHTS has 0.14.0 but CHANGELOG does not" in capsys.readouterr().out


def test_floor_excludes_pre_012_versions(tmp_path, monkeypatch):
    """Versions before 0.12.0 (HIGHLIGHTS' birth) are exempt."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [0.11.0] (2026-09-01)\n\n### Features\n\n* old\n"
        "\n## [0.12.0] (2026-09-02)\n\n### Features\n\n* new\n", encoding="utf-8")
    gov = tmp_path / "gov"
    gov.mkdir()
    (gov / "HIGHLIGHTS.md").write_text("## 0.12.0 — birth\n\n- here\n", encoding="utf-8")
    assert vds.main([]) == 0  # 0.11.0 exempt; 0.12.0 paired


CHANGELOG_TWO = ("# Changelog\n\n"
                 "## [0.15.0] (2026-09-04)\n\n### Features\n\n"
                 "* gov task &lt;cmd&gt; pins rules ([#125](https://x/125)) "
                 "([abc12345](https://x/abc12345))\n"
                 "\n## [0.14.0] (2026-09-03)\n\n### Bug Fixes\n\n"
                 "* fail loud on missing rules ([#121](https://x/121))\n")

HIGHLIGHTS_AT = "header text\n\n## 0.13.0 — old\n\n- something\n"


def _write_pair(tmp_path, changelog=CHANGELOG_TWO, highlights=HIGHLIGHTS_AT):
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    gov = tmp_path / "gov"
    gov.mkdir(exist_ok=True)
    (gov / "HIGHLIGHTS.md").write_text(highlights, encoding="utf-8")


def test_write_drafts_missing_sections_and_gate_turns_green(tmp_path, monkeypatch, capsys):
    """--write is the mechanical half of D37's fix: draft every missing
    section from CHANGELOG, then the gate's own check passes (exit 0)."""
    monkeypatch.chdir(tmp_path)
    _write_pair(tmp_path)
    assert vds.main(["--write"]) == 0
    text = (tmp_path / "gov" / "HIGHLIGHTS.md").read_text(encoding="utf-8")
    # newest first, inserted ahead of the first existing section
    assert text.index("## 0.15.0") < text.index("## 0.14.0") < text.index("## 0.13.0")
    # the draft declares itself; the gate's coverage regex accepts it
    assert "## 0.15.0 — (draft: copied from CHANGELOG" in text
    # provenance stripped, HTML entities unescaped — content otherwise verbatim
    assert "- gov task <cmd> pins rules\n" in text
    assert "abc12345" not in text and "](https" not in text
    assert "- fail loud on missing rules\n" in text
    # verbatim copy, not invention: the usage rewrite stays human
    assert "rewrite" in text
    capsys.readouterr()


def test_write_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_pair(tmp_path)
    assert vds.main(["--write"]) == 0
    after = (tmp_path / "gov" / "HIGHLIGHTS.md").read_text(encoding="utf-8")
    assert vds.main(["--write"]) == 0
    assert (tmp_path / "gov" / "HIGHLIGHTS.md").read_text(encoding="utf-8") == after


def test_write_fails_loud_without_highlights(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG_TWO, encoding="utf-8")
    assert vds.main(["--write"]) == 2


def test_write_ignores_versions_below_floor(tmp_path, monkeypatch):
    """The gate exempts pre-0.12.0 versions; the writer must not draft them."""
    monkeypatch.chdir(tmp_path)
    _write_pair(
        tmp_path,
        changelog="# Changelog\n\n## [0.11.0] (2026-09-01)\n\n### Features\n\n* old\n",
        highlights="header text only, no sections yet\n")
    assert vds.main(["--write"]) == 0
    assert "draft" not in (tmp_path / "gov" / "HIGHLIGHTS.md").read_text(encoding="utf-8")


def test_write_replaces_nothing_existing(tmp_path, monkeypatch):
    """A version already covered is never touched by --write."""
    monkeypatch.chdir(tmp_path)
    covered = "header\n\n## 0.15.0 — hand-written\n\n- already here\n"
    _write_pair(
        tmp_path,
        changelog="# Changelog\n\n## [0.15.0] (2026-09-04)\n\n### Features\n\n* x\n",
        highlights=covered)
    assert vds.main(["--write"]) == 0
    assert "hand-written" in (tmp_path / "gov" / "HIGHLIGHTS.md").read_text(encoding="utf-8")
