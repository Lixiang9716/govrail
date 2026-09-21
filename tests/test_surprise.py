"""The surprise ledger: record/list, escalation at the threshold, gate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gov import surprise  # noqa: E402


def _run(argv: list[str], tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return surprise.main(argv)


def test_record_appends_and_list_counts(tmp_path, monkeypatch, capsys):
    assert _run(["record", "the register said 8 rules",
                 "--reality", "it has 10",
                 "--sig", "register-stale",
                 "--surface", "docs/truth-sources.md"],
                tmp_path, monkeypatch) == 0
    assert _run(["record", "row drifted again", "--reality", "stale row",
                 "--sig", "register-stale"], tmp_path, monkeypatch) == 0
    entries = [json.loads(line)
               for line in (tmp_path / ".gov/surprises.jsonl")
               .read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 2
    assert entries[0]["surface"] == "docs/truth-sources.md"
    assert entries[1]["surface"] is None
    capsys.readouterr()
    assert _run(["list", "--json"], tmp_path, monkeypatch) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 2


def test_sig_derived_from_expectation(tmp_path, monkeypatch):
    assert _run(["record", "the CI pin drifted silently",
                 "--reality", "master ran stale config"],
                tmp_path, monkeypatch) == 0
    entry = json.loads((tmp_path / ".gov/surprises.jsonl")
                       .read_text(encoding="utf-8"))
    assert entry["sig"] == "the-pin-drifted-silently"


def test_one_sided_record_is_usage_error(tmp_path, monkeypatch, capsys):
    assert _run(["record", "only an expectation", "--reality", "  "],
                tmp_path, monkeypatch) == 2


def test_third_strike_is_loud_but_zero(tmp_path, monkeypatch, capsys):
    for i in range(3):
        code = _run(["record", f"surprise {i}", "--reality", "same kind",
                     "--sig", "recurrent"], tmp_path, monkeypatch)
        assert code == 0
    captured = capsys.readouterr()
    assert "ESCALATION OWED" in captured.err
    assert "surprise:recurrent" in captured.err


def test_similar_earlier_surprises_are_shown(tmp_path, monkeypatch, capsys):
    _run(["record", "the lint gate was invisible to the summary",
          "--reality", "auto-merge landed a red job", "--sig", "ci-blind"],
         tmp_path, monkeypatch)
    capsys.readouterr()
    _run(["record", "a second lint job was invisible to the summary",
          "--reality", "auto-merge landed it again"], tmp_path, monkeypatch)
    out = capsys.readouterr().out
    assert "ci-blind" in out


def test_corrupt_ledger_fails_loud(tmp_path, monkeypatch, capsys):
    (tmp_path / ".gov").mkdir()
    (tmp_path / ".gov/surprises.jsonl").write_text("not json\n",
                                                  encoding="utf-8")
    try:
        _run(["list"], tmp_path, monkeypatch)
        raised = False
    except SystemExit as e:
        raised = e.code == 2
    assert raised
    assert "corrupt entry" in capsys.readouterr().err


def test_gate_escalates_and_satisfies(tmp_path):
    gov_dir = tmp_path / ".gov"
    notes_dir = tmp_path / ".agents/notes/implemented/process"
    notes_dir.mkdir(parents=True)
    lines = "".join(
        json.dumps({"ts": f"2026-09-19T00:0{i}:00+00:00", "sig": "drift",
                    "expectation": f"e{i}", "reality": "r",
                    "surface": None}) + "\n"
        for i in range(3))
    (gov_dir.mkdir(exist_ok=True) if not gov_dir.exists() else None)
    (gov_dir / "surprises.jsonl").write_text(lines, encoding="utf-8")
    script = REPO / "scripts/check_surprises.py"
    red = subprocess.run([sys.executable, str(script), "--root",
                          str(tmp_path)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    assert red.returncode == 1
    assert "sig 'drift' has 3" in red.stderr
    note = notes_dir / "2026-09-19-fix.md"
    note.write_text("## Decision\ncovers surprise:drift.\n",
                    encoding="utf-8")
    green = subprocess.run([sys.executable, str(script), "--root",
                            str(tmp_path)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    assert green.returncode == 0
    assert "1 escalated with linked improvement" in green.stdout


def test_escalation_owed_then_discharged(tmp_path, monkeypatch, capsys):
    """#354: the marker must distinguish owed from discharged — the one
    state an operator acts on, and the one the count-only surface could
    not show."""
    for i in range(3):
        assert _run(["record", "the release strip covers nothing",
                     "--reality", f"it strips the banner ({i})",
                     "--sig", "release-strip"], tmp_path, monkeypatch) == 0
    capsys.readouterr()
    assert _run(["list"], tmp_path, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "ESCALATION OWED" in out
    assert "process note citing surprise:release-strip" in out
    # ship the process note the message asks for
    notes = tmp_path / ".agents" / "notes" / "implemented" / "process"
    notes.mkdir(parents=True)
    (notes / "2026-01-01-release-strip.md").write_text(
        "# Agent Note: the release strip is a process defect\n\n"
        "Status: implemented\n\nSupersedes surprise:release-strip findings.\n",
        encoding="utf-8")
    capsys.readouterr()
    assert _run(["list"], tmp_path, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "ESCALATION DISCHARGED" in out
    assert "2026-01-01-release-strip.md" in out


def test_similar_hint_requires_two_shared_content_terms(tmp_path, monkeypatch,
                                                        capsys):
    """#356: an unrelated signature must not be named as 'similar' — the
    hint is the have-I-seen-this-before lookup, and one that always finds
    something teaches the reader to ignore it."""
    assert _run(["record", "gov task close stamps an all-green receipt",
                 "--reality", "the task gate then rejects it",
                 "--sig", "task-close-stamps"], tmp_path, monkeypatch) == 0
    capsys.readouterr()
    assert _run(["record", "the release strip covers the banner",
                 "--reality", "the strip is compiled away",
                 "--sig", "release-strip"], tmp_path, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "similar earlier" not in out, out


def test_similar_hint_surfaces_a_real_match(tmp_path, monkeypatch, capsys):
    assert _run(["record", "the lease root is per checkout",
                 "--reality", "linked worktrees share the lock root",
                 "--sig", "lease-root"], tmp_path, monkeypatch) == 0
    capsys.readouterr()
    assert _run(["record", "the lease root note names clones",
                 "--reality", "worktrees share the lock directory too",
                 "--sig", "lease-root-second"], tmp_path, monkeypatch) == 0
    out = capsys.readouterr().out
    assert "similar earlier" in out and "lease-root" in out
