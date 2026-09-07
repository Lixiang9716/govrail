import json

from gov import trend


def _history(root, runs):
    h = root / ".gov" / "history"
    h.mkdir(parents=True)
    with (h / "gates.jsonl").open("w", encoding="utf-8") as f:
        for gates in runs:
            f.write(json.dumps({"ts": "2026-09-01T00:00:00+00:00", "gates": gates}) + "\n")


def test_trend_names_duration_movers(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _history(tmp_path, [
        [{"gate": "tests", "outcome": "PASS", "duration_ms": 1000, "blocking": False, "detail": ""}],
        [{"gate": "tests", "outcome": "PASS", "duration_ms": 1000, "blocking": False, "detail": ""}],
        [{"gate": "tests", "outcome": "PASS", "duration_ms": 4000, "blocking": False, "detail": ""}],
    ])
    assert trend.main([]) == 0
    out = capsys.readouterr().out
    assert "tests" in out and "↑" in out
    assert "×2.5" in out  # p50 1.0s → 2.5s


def test_trend_stable_and_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert trend.main([]) == 0
    assert "no history" in capsys.readouterr().out
    _history(tmp_path, [
        [{"gate": "a", "outcome": "PASS", "duration_ms": 100, "blocking": False, "detail": ""}],
        [{"gate": "a", "outcome": "PASS", "duration_ms": 110, "blocking": False, "detail": ""}],
    ])
    assert trend.main([]) == 0
    assert "stable" in capsys.readouterr().out


def test_trend_gate_filter_and_base_split(tmp_path, monkeypatch, capsys):
    import subprocess
    monkeypatch.chdir(tmp_path)
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "base"],
                   cwd=tmp_path, check=True)
    _history(tmp_path, [
        [{"gate": "a", "outcome": "PASS", "duration_ms": 100, "blocking": False, "detail": ""}],
        [{"gate": "b", "outcome": "PASS", "duration_ms": 500, "blocking": False, "detail": ""}],
        [{"gate": "a", "outcome": "PASS", "duration_ms": 900, "blocking": False, "detail": ""}],
    ])
    assert trend.main(["--gate", "a"]) == 0
    out = capsys.readouterr().out
    assert "a" in out and " b" not in out.replace("gate", " ")
    # split at the first commit (before all runs) -> everything is "late"
    assert trend.main(["--gate", "a", "--base", "HEAD"]) == 0
    assert "split at HEAD" in capsys.readouterr().out


def _history_tagged(root, runs):
    h = root / ".gov" / "history"
    h.mkdir(parents=True)
    with (h / "gates.jsonl").open("w", encoding="utf-8") as f:
        for caller, gates in runs:
            rec = {"ts": "2026-09-01T00:00:00+00:00", "gates": gates}
            if caller:
                rec["caller"] = caller
            f.write(json.dumps(rec) + "\n")


def test_trend_by_tag_splits_callers(tmp_path, monkeypatch, capsys):
    """#120/D42: two tagged callers report separately; untagged runs group
    under (untagged); plain `gov trend` is unchanged by tags."""
    monkeypatch.chdir(tmp_path)
    g = lambda ms: [{"gate": "tests", "outcome": "PASS",
                     "duration_ms": ms, "blocking": False, "detail": ""}]
    _history_tagged(tmp_path, [
        ("alpha", g(1000)), ("alpha", g(1000)), ("alpha", g(4000)),
        ("beta", g(100)), ("beta", g(100)), ("beta", g(100)),
        (None, g(500)), (None, g(500)),
    ])
    assert trend.main(["--by-tag"]) == 0
    out = capsys.readouterr().out
    assert "caller alpha: 3 run(s)" in out
    assert "caller beta: 3 run(s)" in out
    assert "caller (untagged): 2 run(s)" in out
    assert "×2.5 ↑" in out          # alpha's mover computed within its runs
    assert "stable" in out          # beta stable
    # untagged output stays identical in shape: tags never leak into it
    assert trend.main([]) == 0
    out = capsys.readouterr().out
    assert "caller" not in out and "×2.5" not in out


def test_trend_by_tag_without_any_tag(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _history_tagged(tmp_path, [(None, [{"gate": "a", "outcome": "PASS",
                                        "duration_ms": 1, "blocking": False,
                                        "detail": ""}])] * 2)
    assert trend.main(["--by-tag"]) == 0
    out = capsys.readouterr().out
    assert "no run carries a caller tag" in out
    assert "--tag" in out


def test_trend_cost_splits_by_caller(tmp_path, monkeypatch, capsys):
    """#126 acceptance: two tools' costs appear split by tag in
    `gov trend --cost`; untagged and non-reporting runs stay out of the
    way of the roll-up."""
    monkeypatch.chdir(tmp_path)
    h = (tmp_path / ".gov/history"); h.mkdir(parents=True)
    lines = [
        {"ts": "2026-09-01T00:00:00+00:00", "caller": "bridge",
         "cost": {"tokens": 100, "calls": 2}, "gates": []},
        {"ts": "2026-09-01T01:00:00+00:00", "caller": "adjudicator",
         "cost": {"tokens": 50, "calls": 1}, "gates": []},
        {"ts": "2026-09-01T02:00:00+00:00", "caller": "bridge",
         "cost": {"tokens": 300, "calls": 6}, "gates": []},
        {"ts": "2026-09-01T03:00:00+00:00", "gates": []},    # no cost: absent
        {"ts": "2026-09-01T04:00:00+00:00", "cost": {"calls": 3},
         "gates": []},                                       # untagged bucket
    ]
    with (h / "gates.jsonl").open("w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")
    assert trend.main(["--cost"]) == 0
    out = capsys.readouterr().out
    assert "5 run(s)" in out and "4 reporting cost" in out
    assert "caller bridge" in out
    assert "tokens 400 (100 early → 300 late)" in out
    assert "calls 8 (2 early → 6 late)" in out
    assert "caller adjudicator" in out and "tokens 50" in out
    assert "(untagged)" in out and "calls 3" in out
    # durations view is untouched by the cost flags
    assert trend.main([]) == 0


def test_trend_cost_absent_and_malformed(tmp_path, monkeypatch, capsys):
    """A cost-less window points at the opt-in; a malformed history cost
    field is named on stderr and never silently summed."""
    monkeypatch.chdir(tmp_path)
    _history(tmp_path, [
        [{"gate": "a", "outcome": "PASS", "duration_ms": 1,
          "blocking": False, "detail": ""}],
        [{"gate": "a", "outcome": "PASS", "duration_ms": 1,
          "blocking": False, "detail": ""}],
    ])
    assert trend.main(["--cost"]) == 0
    out = capsys.readouterr().out
    assert "no cost reported" in out and "GOV_COST" in out
    with (tmp_path / ".gov/history/gates.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": "2026-09-02T00:00:00+00:00",
                            "caller": "bad", "cost": "1200",
                            "gates": []}) + "\n")
    assert trend.main(["--cost", "--last", "10"]) == 0
    captured = capsys.readouterr()
    assert "malformed cost" in captured.err
    assert "bad" not in captured.out


def test_trend_cost_flag_conflicts_fail_loud(tmp_path, monkeypatch, capsys):
    """--cost vs --by-tag / --gate: different views, named refusal."""
    monkeypatch.chdir(tmp_path)
    _history(tmp_path, [
        [{"gate": "a", "outcome": "PASS", "duration_ms": 1,
          "blocking": False, "detail": ""}],
        [{"gate": "a", "outcome": "PASS", "duration_ms": 1,
          "blocking": False, "detail": ""}],
    ])
    assert trend.main(["--cost", "--by-tag"]) == 2
    assert "cannot be combined" in capsys.readouterr().err
    assert trend.main(["--cost", "--gate", "a"]) == 2
    assert "--gate" in capsys.readouterr().err
