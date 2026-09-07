import subprocess

from gov import review


def _git_repo(root, files):
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True)
    for name, text in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "base"],
                   cwd=root, check=True)


def test_dossier_four_sections_with_rubric(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path, {"src/app.py": "x=1\n"})
    (tmp_path / "src" / "app.py").write_text("x=2\n", encoding="utf-8")
    rub = tmp_path / "docs"
    rub.mkdir()
    (rub / "review-rubric.md").write_text(
        "### R1 — a\n\n- **Checks:** c\n- **Evidence:** e\n"
        "- **Anti-pattern:** a\n- **Gate candidate:** no\n", encoding="utf-8")
    assert review.main(["--base", "HEAD"]) == 0
    out = capsys.readouterr().out
    for section in ("## 1. change scope", "## 2. notes in this change",
                    "## 3. recall", "## 4. rubric"):
        assert section in out
    assert "R1 — a" in out
    assert "WARNING" in out  # behavior-bearing change, no note


def test_dossier_three_sections_without_rubric(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path, {"README.md": "# x\n"})
    (tmp_path / "README.md").write_text("# y\n", encoding="utf-8")
    assert review.main(["--base", "HEAD"]) == 0
    out = capsys.readouterr().out
    assert "## 3. recall" in out
    assert "## 4. rubric" not in out
    assert "reviewing without one" in out


def test_bad_ref_fails_loud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path, {"a.txt": "x\n"})
    assert review.main(["--base", "no-such-ref"]) == 2


def _rubric(root):
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "review-rubric.md").write_text(
        "### R1 — a\n\n- **Checks:** c\n- **Evidence:** e\n"
        "- **Anti-pattern:** a\n- **Gate candidate:** no\n\n"
        "### R2 — b\n\n- **Checks:** c\n- **Evidence:** e\n"
        "- **Anti-pattern:** a\n- **Gate candidate:** no\n", encoding="utf-8")


def test_grade_approve_and_request_changes(tmp_path, monkeypatch):
    import subprocess as sp
    import sys as _sys
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path, {"app.py": "v1\n"})
    (tmp_path / "app.py").write_text("v2\n", encoding="utf-8")
    _rubric(tmp_path)
    env = {"PYTHONPATH": "/home/lx/govrail,.", "PATH": "/usr/bin:/bin"}
    import os
    env = {**os.environ, "PYTHONPATH": "/home/lx/govrail"}
    approve = sp.run([_sys.executable, "-m", "gov.cli", "review", "--grade",
                      "--base", "HEAD"], cwd=tmp_path, env=env,
                     input="p\np\n", capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert approve.returncode == 0
    assert "verdict: approve" in approve.stdout
    changes = sp.run([_sys.executable, "-m", "gov.cli", "review", "--grade",
                      "--base", "HEAD"], cwd=tmp_path, env=env,
                     input="p\nf\napp.py:2 broken\ns\n", capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert changes.returncode == 1
    out = changes.stdout
    assert "R2 — fail — app.py:2 broken" in out
    assert "blockers:" in out and "R2: app.py:2 broken" in out
    assert "verdict: request changes (1 blocker(s))" in out


def test_grade_needs_rubric_and_quit(tmp_path, monkeypatch):
    import subprocess as sp
    import sys as _sys
    import os
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path, {"app.py": "v1\n"})
    (tmp_path / "app.py").write_text("v2\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": "/home/lx/govrail"}
    norubric = sp.run([_sys.executable, "-m", "gov.cli", "review", "--grade",
                       "--base", "HEAD"], cwd=tmp_path, env=env,
                      input="", capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert norubric.returncode == 2
    _rubric(tmp_path)
    quit_ = sp.run([_sys.executable, "-m", "gov.cli", "review", "--grade",
                    "--base", "HEAD"], cwd=tmp_path, env=env,
                   input="q\n", capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert quit_.returncode == 1
    assert "grade quit" in quit_.stdout
