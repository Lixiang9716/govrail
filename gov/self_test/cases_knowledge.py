"""knowledge-plane rejection cases: pairing, change-scope, rubric, decisions, doc-sync, conflict markers.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ._harness import (
    HERE,
    _case,
    _fixture_env,
    _git_repo,
    _run,
    _run_text,
    case,
)




@case
def test_pairing_rejects_missing_record() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo.zh.md").write_text("# foo 中文\n", encoding="utf-8")
        _case(
            "verify_translation_pairing.py",
            root,
            1,
            "a pair with no .i18n.yaml record must fail",
        )



@case
def test_pairing_write_resolves_bare_stem_and_zh_side() -> None:
    """--write must resolve a bare stem and a .zh.md side to the source .md."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo.zh.md").write_text("# foo 中文\n", encoding="utf-8")
        for arg in ("foo", "docs/foo.zh.md"):
            result = _run_text(
                [sys.executable, str(HERE / "verify_translation_pairing.py"), "--write", arg],
                cwd=root,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"--write {arg} must exit 0: {result.stderr}"
        assert (docs / "foo.i18n.yaml").exists(), "--write must create the record"



@case
def test_pairing_custom_counterpart_convention() -> None:
    """A .gov/pairing.json convention must be enforced, not ignored."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        gov = root / ".gov"
        gov.mkdir()
        (gov / "pairing.json").write_text(
            json.dumps({"counterparts": ["{stem}_CN.md"]}), encoding="utf-8"
        )
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo_CN.md").write_text("# foo 中文\n", encoding="utf-8")
        _case(
            "verify_translation_pairing.py",
            root,
            1,
            "a custom-convention pair with no record must fail",
        )



@case
def test_pairing_explicit_registration_sticks() -> None:
    """--write en:.. zh:.. registers any name; verification then pins it."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# foo\n", encoding="utf-8")
        (docs / "foo_CN.md").write_text("# foo 中文\n", encoding="utf-8")
        register = subprocess.run(
            [
                sys.executable,
                str(HERE / "verify_translation_pairing.py"),
                "--write", "en:docs/foo.md", "zh:docs/foo_CN.md",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",
        )
        assert register.returncode == 0, f"explicit registration must exit 0: {register.stderr}"
        (docs / "foo_CN.md").write_text("# 单边修改\n", encoding="utf-8")
        _case(
            "verify_translation_pairing.py",
            root,
            1,
            "a one-sided edit of a registered pair must fail",
        )



@case
def test_pairing_staged_rejects_stale_sidecar() -> None:
    """--staged (the optional pre-commit gate's check, #110) must reject a
    staged pair whose sidecar is stale — naming the scoped fix command —
    and stay quiet on an index with no paired files staged."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        docs = root / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("hello\n", encoding="utf-8")
        (docs / "a.zh.md").write_text("nihao\n", encoding="utf-8")
        script = str(HERE / "verify_translation_pairing.py")
        env = _fixture_env(root)
        wrote = subprocess.run(
            [sys.executable, script, "--write", "docs/a.md"], cwd=root,
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace",
        )
        assert wrote.returncode == 0, wrote.stderr
        subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "baseline"],
            cwd=root, check=True, env=env,
        )
        # An index with nothing paired staged: quiet pass (cheap gate).
        (root / "code.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "code.py"], cwd=root, check=True, env=env)
        quiet = subprocess.run(
            [sys.executable, script, "--staged"], cwd=root,
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace",
        )
        assert quiet.returncode == 0, quiet.stdout + quiet.stderr
        assert "no staged file belongs to a pair" in quiet.stdout
        # The issue's evidence: edit one side, stage it — drift must go red
        # with the scoped fix command inline.
        (docs / "a.zh.md").write_text("nihao v2\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs/a.zh.md"], cwd=root, check=True, env=env)
        bad = subprocess.run(
            [sys.executable, script, "--staged"], cwd=root,
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace",
        )
        assert bad.returncode == 1, "a stale sidecar passed --staged"
        assert "gov verify-pairing --write docs/a.md" in bad.stdout, bad.stdout



@case
def test_change_scope_suggests_from_paths() -> None:
    """change-scope must read gate suggestions from gates.json paths, not prose."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        (root / "gates.json").write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": "docs-gate", "command": ["true"], "paths": ["docs/**"]},
                        {"id": "code-gate", "command": ["true"], "paths": ["src/**"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (root / "docs").mkdir()
        (root / "docs" / "a.md").write_text("x\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(HERE / "change_scope.py"), "--base", "HEAD"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert "gates.json paths" in result.stdout, result.stdout + result.stderr
        assert "docs-gate" in result.stdout
        assert "code-gate" not in result.stdout



@case
def test_rubric_rejects_broken_structure() -> None:
    """verify-rubric must catch missing fields and bilingual id drift."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        good = (
            "### R1 — a\n\n"
            "- **Checks:** c\n- **Evidence:** e\n"
            "- **Anti-pattern:** a\n- **Gate candidate:** no — judgment\n"
        )
        (docs / "review-rubric.md").write_text(good, encoding="utf-8")
        (docs / "review-rubric.zh.md").write_text(
            good.replace("R1 — a", "R1 — 甲"), encoding="utf-8"
        )
        script = str(HERE / "verify_rubric.py")
        ok = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert ok.returncode == 0, ok.stderr
        (docs / "review-rubric.md").write_text(
            good.replace("- **Evidence:** e\n", ""), encoding="utf-8"
        )
        broken = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert broken.returncode == 1, "a rubric item missing a field must fail"
        assert "Evidence" in broken.stdout
        (docs / "review-rubric.md").write_text(good, encoding="utf-8")
        (docs / "review-rubric.zh.md").write_text(
            "### R2 — 乙\n\n- **查什么：** x\n", encoding="utf-8"
        )
        drift = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert drift.returncode == 1, "bilingual id drift must fail"
        assert "R2" in drift.stdout



@case
def test_rubric_rejects_zero_items() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "review-rubric.md").write_text(
            "# Review rubric\n\ngarbage content, no items\n", encoding="utf-8"
        )
        _case(
            "verify_rubric.py",
            root,
            1,
            "a rubric with zero items is a vacuous pass (rule 6)",
        )



@case
def test_verify_decisions_rejects_broken_table() -> None:
    """Wish 9: duplicate ids, gaps, and alternative-less decisions fail loud."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        docs = root / "docs"
        docs.mkdir()
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n\n## D1 — b\n\n- **选项**：x\n\n"
            "## D3 — c\n\n- **状态**：已决\n",
            encoding="utf-8",
        )
        result = _run("verify_decisions.py", root)
        assert result.returncode == 1, "a broken decisions table must fail"
        assert "duplicate" in result.stdout
        assert "missing: D2" in result.stdout
        assert "D3: records no options" in result.stdout



@case
def test_verify_decisions_rejects_base_collision() -> None:
    """#107: --base must refuse a number two branches both allocated."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        env = _fixture_env(root)

        def git(*argv: str, check: bool = True):
            return subprocess.run(
                list(argv), cwd=root, check=check, capture_output=True,
                text=True, env=env,
                encoding="utf-8", errors="replace",
            )

        git("git", "branch", "-q", "-m", "main")
        docs = root / "docs"
        docs.mkdir()
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n", encoding="utf-8")
        git("git", "add", "-A")
        git("git", "-c", "commit.gpgsign=false", "commit", "-qm", "fork")
        git("git", "checkout", "-q", "-b", "topic")
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n\n## D2 — mine\n\n- **选项**：x\n",
            encoding="utf-8")
        git("git", "add", "-A")
        git("git", "-c", "commit.gpgsign=false", "commit", "-qm", "branch D2")
        git("git", "checkout", "-q", "main")
        (docs / "decisions.md").write_text(
            "## D1 — a\n\n- **选项**：x\n\n## D2 — theirs\n\n- **选项**：x\n",
            encoding="utf-8")
        git("git", "add", "-A")
        git("git", "-c", "commit.gpgsign=false", "commit", "-qm", "sibling")
        git("git", "checkout", "-q", "topic")
        result = _run("verify_decisions.py", root, ["--base", "main"])
        assert result.returncode == 1, \
            "a number both branches allocated must be a named collision"
        assert "D2: number collision" in result.stdout



@case
def test_doc_sync_rejects_changelog_without_highlights() -> None:
    """D37: CHANGELOG gains a version, HIGHLIGHTS hasn't followed — red."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.14.0] (2026-09-04)\n\n### Features\n\n* x\n",
            encoding="utf-8",
        )
        gov = root / "gov"
        gov.mkdir()
        (gov / "HIGHLIGHTS.md").write_text(
            "## 0.13.0 — old\n\n- y\n", encoding="utf-8")
        _case(
            "verify_doc_sync.py",
            root,
            1,
            "a CHANGELOG version without a HIGHLIGHTS section must fail",
        )



@case
def test_conflict_markers_rejects_marked_file() -> None:
    """#104/D38: a staged conflicted file must fail loud, naming file:line,
    while the escape hatch tolerates a deliberate literal."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        script = str(HERE / "verify_conflict_markers.py")
        conflicted = root / "doc.md"
        conflicted.write_text(
            "# doc\n\n"
            + "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert result.returncode == 1, (
            "a file with conflict markers must fail the gate\n"
            f"{result.stdout}\n{result.stderr}"
        )
        assert "doc.md:3" in result.stdout, "the finding must name file and line"
        assert "doc.md:5" in result.stdout and "doc.md:7" in result.stdout, (
            "start, separator, and end markers are all named"
        )
        conflicted.write_text(
            "# doc\n\n"
            + "<<<<<<< HEAD " + "gov:ignore-marker" + "\n",
            encoding="utf-8",
        )
        clean = subprocess.run(
            [sys.executable, script], cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        assert clean.returncode == 0, (
            "the ignore token must exempt a deliberate literal\n" + clean.stdout
        )



@case
def test_conflict_markers_bare_separator_needs_sibling() -> None:
    """#104: a bare ======= alone (a Markdown H1 underline) must pass."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _git_repo(root)
        (root / "README.md").write_text(
            "Title\n=======\n\nbody\n", encoding="utf-8")
        _case("verify_conflict_markers.py", root, 0,
              "a setext underline with no sibling marker must pass")
