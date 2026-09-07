from gov import audit_notes


def _note(root, name, body):
    d = root / ".agents" / "notes" / "implemented" / "architecture"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def test_clean_note_passes_silently(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-clean.md",
          "# Agent Note: clean\n\nStatus: implemented\n\n"
          "## Decision\nUses `gov run` and `gov recall`; see D-ref none.\n")
    assert audit_notes.main([]) == 0
    out = capsys.readouterr().out
    assert "clean" in out and "signal" not in out


def test_unknown_command_flagged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-stale.md",
          "# Agent Note: stale\n\nStatus: implemented\n\n"
          "## Decision\nGuarded by `gov verify-links`.\n")
    assert audit_notes.main([]) == 0  # advisory: report, not block
    out = capsys.readouterr().out
    assert "`gov verify-links`" in out


def test_d_reference_without_entry_flagged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-dref.md",
          "# Agent Note: dref\n\nStatus: implemented\n\n"
          "## Decision\nLocked by D99.\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text("## D1 — real\n\n- **状态**：已决\n", encoding="utf-8")
    assert audit_notes.main([]) == 0
    out = capsys.readouterr().out
    assert "D99" in out


def test_unresolved_path_flagged_placeholders_ignored(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-paths.md",
          "# Agent Note: paths\n\nStatus: implemented\n\n"
          "## Decision\nSee docs/real.md via `docs/real.md` and example `docs/foo.md`.\n")
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "real.md").write_text("x\n", encoding="utf-8")
    assert audit_notes.main([]) == 0
    out = capsys.readouterr().out
    assert "`docs/missing" not in out  # sanity
    assert "unresolved path `docs/real.md`" not in out
    assert "foo" not in out  # placeholder paths are not flagged


def test_unresolved_real_path_flagged(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-gone.md",
          "# Agent Note: gone\n\nStatus: implemented\n\n"
          "## Decision\nLives in `gov/legacy_runner.py`.\n")
    assert audit_notes.main([]) == 0
    out = capsys.readouterr().out
    assert "unresolved path `gov/legacy_runner.py`" in out


def test_archived_exempt(tmp_path, monkeypatch, capsys):
    arch = tmp_path / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    (arch / "2026-01-01-frozen.md").write_text(
        "# Agent Note: frozen\n\n`gov verify-ancient` and `gone/old.py`.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # implemented/ missing entirely → exit 2, so add one clean implemented note
    _note(tmp_path, "2026-01-01-clean.md",
          "# Agent Note: clean\n\nStatus: implemented\n\n## Decision\nfine.\n")
    assert audit_notes.main([]) == 0
    out = capsys.readouterr().out
    assert "frozen" not in out and "1 implemented note(s), 0 skill file(s), clean" in out


def test_no_tree_fails_loud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert audit_notes.main([]) == 2


def test_summary_distinguishes_missing_from_malformed_decisions(tmp_path, monkeypatch, capsys):
    """decisions.md exists but parses to zero sections — the summary must
    say format, not claim the file is missing."""
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-d.md",
          "# Agent Note: d\n\nStatus: implemented\n\n## Decision\nLocked by D1.\n\n"
          "## Problem\np\n\n## Alternatives considered\na\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text("- D1: colon list format\n", encoding="utf-8")
    assert audit_notes.main([]) == 0
    out = capsys.readouterr()
    assert "has no '## Dn — ' sections" in out.out
    assert "no docs/decisions.md" not in out.out
    assert "D1" not in out.out  # unchecked, not false-flagged


def test_summary_missing_decisions_still_reported(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-c.md",
          "# Agent Note: c\n\nStatus: implemented\n\n## Decision\nfine.\n\n"
          "## Problem\np\n\n## Alternatives considered\na\n")
    assert audit_notes.main([]) == 0
    out = capsys.readouterr()
    assert "no decisions source; D-refs unchecked" in out.out


def test_skills_command_and_flag_drift(tmp_path, monkeypatch, capsys):
    """Wish 11: typos in skill text are named; legal refs stay silent."""
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-c.md",
          "# Agent Note: c\n\nStatus: implemented\n\n## Decision\nfine.\n\n"
          "## Problem\np\n\n## Alternatives considered\na\n")
    skills = tmp_path / ".agents" / "skills" / "x"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "run `gov run --every-gat` then `gov verife-pairing`, "
        "legally `gov run --every-gate` and `gov archive-notes --rebaseline`.\n", encoding="utf-8")
    assert audit_notes.main([]) == 0  # advisory report
    out = capsys.readouterr().out
    assert "unknown flag `--every-gat` on `gov run`" in out
    assert "unknown command `gov verife-pairing`" in out
    assert "--rebaseline" not in out  # legal refs: zero false positives
    assert "--every-gate`" not in out.replace("--every-gat`", "")


def test_real_flags_are_not_drift_dead_flags_are(tmp_path, monkeypatch, capsys):
    """Issue #101: a note documenting WORKING commands must not read as a
    dead command. --adopt/--preview/--json are real init flags (D29/D34);
    a genuinely unknown flag is still named."""
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-init.md",
          "# Agent Note: init\n\nStatus: implemented\n\n"
          "## Decision\n`gov init --adopt .gov/hooks/pre-push` then "
          "`gov init --adopt .gov/hooks/pre-push --preview`; drift report via "
          "`gov init --upgrade --json`; scheduling with `gov run --no-record`, "
          "`gov review --grade`, `gov trend --gate x --base y`, "
          "`gov note new --class feature`, `gov whatsnew --since 0.12.2`; "
          "dead: `gov init --nonexistent`.\n\n"
          "## Problem\np\n\n## Alternatives considered\na\n")
    assert audit_notes.main([]) == 0  # advisory report
    out = capsys.readouterr().out
    assert "unknown flag `--nonexistent` on `gov init`" in out
    for real in ("--adopt", "--preview", "--json", "--no-record",
                 "--grade", "--class", "--since"):
        assert real not in out, f"{real} is a real flag — false signal"


def test_registry_covers_exactly_the_command_set():
    """Every CLI command must carry a flag entry (possibly empty): a
    missing entry would silently skip flag checks for it (rule 5)."""
    from gov import cli
    assert set(audit_notes.FLAGS) == set(cli._COMMANDS)


def test_registry_mismatch_fails_loud(tmp_path, monkeypatch, capsys):
    """A registry that lags cli._COMMANDS is a tool defect, not a tree
    finding — named on stderr, exit 2 (rule 5)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delitem(audit_notes.FLAGS, "doctor")
    assert audit_notes.main([]) == 2
    err = capsys.readouterr().err
    assert "missing 'doctor'" in err


def test_json_mode_pure_stdout(tmp_path, monkeypatch, capsys):
    """#119: audit-notes --json — stdout is exactly one JSON object; the
    human report (findings included) moves to stderr."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    _note(tmp_path, "2026-01-01-stale.md",
          "# Agent Note: stale\n\nStatus: implemented\n\n"
          "## Decision\nGuarded by `gov verify-links`.\n")
    assert audit_notes.main(["--json"]) == 0
    captured = capsys.readouterr()
    payload = _json.loads(captured.out)
    assert payload["notes"] == 1
    assert payload["state"] == "dirty"
    assert any("verify-links" in f["signal"] for f in payload["findings"])
    assert "verify-links" in captured.err  # human findings on stderr
