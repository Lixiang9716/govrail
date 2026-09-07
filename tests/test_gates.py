import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gov import gates

# Portable gate commands (#168): the Unix coreutils true/false do not
# exist on Windows — "a command that exits 0/1" must not depend on PATH.
PASS = [sys.executable, "-c", "pass"]
FAIL = [sys.executable, "-c", "raise SystemExit(1)"]


def _write(tmp_path: Path, data) -> Path:
    p = tmp_path / "gates.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _git_repo(tmp_path: Path) -> None:
    for cmd in (
        ["git", "init", "-q", "."],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "init"],
                   cwd=tmp_path, check=True)


def test_load_config_valid(tmp_path):
    p = _write(tmp_path, {"gates": [{"id": "a", "command": PASS}]})
    modes, gs, concurrency, default_mode = gates.load_config(str(p))
    assert [g.id for g in gs] == ["a"]
    assert gs[0].command == PASS
    assert concurrency == 0
    assert default_mode is None
    assert gs[0].enabled is True


def test_load_config_parses_default_mode_and_enabled(tmp_path):
    p = _write(
        tmp_path,
        {
            "modes": {"all": ["a"]},
            "defaultMode": "all",
            "gates": [
                {"id": "a", "command": PASS},
                {"id": "b", "command": PASS, "enabled": False},
            ],
        },
    )
    modes, gs, concurrency, default_mode = gates.load_config(str(p))
    assert default_mode == "all"
    assert [g.enabled for g in gs] == [True, False]


@pytest.mark.parametrize(
    "data",
    [
        {"modes": {"all": ["a"]}, "defaultMode": "ghost",
         "gates": [{"id": "a", "command": PASS}]},
        {"modes": {"all": ["a"]}, "defaultMode": 3,
         "gates": [{"id": "a", "command": PASS}]},
        {"modes": {"all": ["a"]}, "defaultMode": "",
         "gates": [{"id": "a", "command": PASS}]},
        {"gates": [{"id": "a", "command": PASS, "enabled": "false"}]},
    ],
)
def test_load_config_rejects_bad_default_mode_or_enabled(tmp_path, data):
    p = _write(tmp_path, data)
    with pytest.raises(gates.ConfigError):
        gates.load_config(str(p))


@pytest.mark.parametrize(
    "data",
    [
        {"gates": [{"id": "a", "command": PASS}, {"id": "a", "command": PASS}]},
        {"gates": [{"id": "a", "command": PASS, "needs": ["ghost"]}]},
        {
            "gates": [
                {"id": "a", "command": PASS, "needs": ["b"]},
                {"id": "b", "command": PASS, "needs": ["a"]},
            ]
        },
        {"gates": [None]},
        {"gates": "nope"},
        {"concurrency": -1, "gates": [{"id": "a", "command": PASS}]},
        {"gates": [{"id": "a", "command": PASS, "timeoutMs": "x"}]},
        [],
    ],
)
def test_load_config_rejects(tmp_path, data):
    p = _write(tmp_path, data)
    with pytest.raises(gates.ConfigError):
        gates.load_config(str(p))


def test_run_gates_passes():
    gs = [gates.Gate(id="a", command=PASS), gates.Gate(id="b", command=PASS)]
    assert gates.run_gates(gs, None, 1, False) == 0


def test_run_gates_skips_transitively(capsys):
    gs = [
        gates.Gate(id="A", command=PASS, needs=["B"]),
        gates.Gate(id="B", command=PASS, needs=["C"]),
        gates.Gate(id="C", command=FAIL),
    ]
    assert gates.run_gates(gs, None, 1, False) == 1
    out = capsys.readouterr().out
    assert "SKIP A" in out
    assert "SKIP B" in out
    assert "PASS A" not in out


def test_run_gates_missing_command():
    gs = [gates.Gate(id="a", command=["no-such-cmd-xyz"])]
    assert gates.run_gates(gs, None, 1, False) == 1


def test_run_gates_reports_disabled_and_never_runs_them(capsys):
    gs = [
        gates.Gate(id="a", command=PASS),
        gates.Gate(id="b", command=FAIL, enabled=False),
    ]
    assert gates.run_gates(gs, None, 1, False) == 0
    out = capsys.readouterr().out
    assert "DISABLED b" in out
    assert "FAIL b" not in out


def test_run_gates_selection_skips_disabled(capsys):
    gs = [
        gates.Gate(id="a", command=PASS),
        gates.Gate(id="b", command=FAIL, enabled=False),
    ]
    assert gates.run_gates(gs, ["a", "b"], 1, False) == 0
    out = capsys.readouterr().out
    assert "DISABLED b" in out
    assert "FAIL b" not in out


def test_run_gates_advisory_failure_reports_but_does_not_block(capsys):
    gs = [gates.Gate(id="a", command=FAIL, allow_failure=True)]
    assert gates.run_gates(gs, None, 1, False) == 0
    out = capsys.readouterr().out
    assert "FAIL a" in out
    assert "advisory" in out


def test_main_default_mode_scopes_run(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path,
        {
            "modes": {"all": ["a"], "also": ["b"]},
            "defaultMode": "all",
            "gates": [
                {"id": "a", "command": PASS},
                {"id": "b", "command": FAIL},
            ],
        },
    )
    assert gates.main([]) == 0
    out = capsys.readouterr().out
    assert "PASS a" in out
    assert "FAIL b" not in out  # b is outside the default mode; it must not run


def test_main_mode_overrides_default_mode(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path,
        {
            "modes": {"all": ["a"], "just-b": ["b"]},
            "defaultMode": "all",
            "gates": [
                {"id": "a", "command": PASS},
                {"id": "b", "command": PASS},
            ],
        },
    )
    assert gates.main(["--mode", "just-b"]) == 0
    out = capsys.readouterr().out
    assert "PASS b" in out
    assert "PASS a" not in out


def test_load_config_parses_paths(tmp_path):
    p = _write(tmp_path, {"gates": [{"id": "a", "command": PASS,
                                     "paths": ["gov/**", "gates.json"]}]})
    modes, gs, concurrency, default_mode = gates.load_config(str(p))
    assert gs[0].paths == ["gov/**", "gates.json"]


@pytest.mark.parametrize("paths", ["gov/", [""], [1]])
def test_load_config_rejects_bad_paths(tmp_path, paths):
    p = _write(tmp_path, {"gates": [{"id": "a", "command": PASS, "paths": paths}]})
    with pytest.raises(gates.ConfigError):
        gates.load_config(str(p))


def test_glob_regex_span_and_depth():
    assert gates._glob_regex("gov/**").match("gov/cli.py")
    assert gates._glob_regex("gov/**").match("gov/templates/gates.json")
    assert not gates._glob_regex("gov/*").match("gov/templates/gates.json")
    assert gates._glob_regex("*.i18n.yaml").match("README.i18n.yaml")
    assert not gates._glob_regex("*.i18n.yaml").match("docs/x.i18n.yaml")


def test_select_by_paths():
    gs = [
        gates.Gate(id="unpathed", command=PASS),
        gates.Gate(id="docs-gate", command=PASS, paths=["docs/**"]),
        gates.Gate(id="off", command=PASS, enabled=False, paths=["docs/**"]),
    ]
    selected, out = gates._select_by_paths(gs, ["docs/a.md", "README.md"])
    assert selected == ["unpathed", "docs-gate"]
    assert out == []


def test_main_base_scopes_run(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    _write(
        tmp_path,
        {
            "gates": [
                {"id": "docs-gate", "command": PASS, "paths": ["docs/**"]},
                {"id": "code-gate", "command": PASS, "paths": ["src/**"]},
                {"id": "unpathed", "command": PASS},
            ]
        },
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x\n", encoding="utf-8")
    assert gates.main(["--base", "HEAD"]) == 0
    out = capsys.readouterr().out
    assert "out of scope: code-gate" in out
    assert "PASS docs-gate" in out
    assert "PASS code-gate" not in out
    assert "PASS unpathed" in out  # unpathed gates always run


def test_main_gate_flag_runs_one(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path,
        {"gates": [{"id": "a", "command": PASS},
                   {"id": "b", "command": PASS}]},
    )
    assert gates.main(["--gate", "b"]) == 0
    out = capsys.readouterr().out
    assert "PASS b" in out
    assert "PASS a" not in out


def test_main_rejects_gate_and_mode_combo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"modes": {"all": ["a"]},
                      "gates": [{"id": "a", "command": PASS}]})
    assert gates.main(["--gate", "a", "--mode", "all"]) == 2


def test_main_rejects_unknown_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS}]})
    assert gates.main(["--gate", "ghost"]) == 2


def test_failure_summary_names_gate_and_rerun(capsys):
    gs = [
        gates.Gate(id="boom", command=[sys.executable, "-c",
                                       "import sys; print('boom', file=sys.stderr); raise SystemExit(3)"]),
        gates.Gate(id="ok", command=PASS),
    ]
    assert gates.run_gates(gs, None, 1, False) == 1
    out = capsys.readouterr().out
    assert "--- summary: 1 blocking failure(s) ---" in out
    assert "boom: boom" in out
    # #109: the failure line itself carries the per-gate rerun command.
    assert "boom: boom (rerun: gov run --gate boom)" in out


def test_failed_gate_output_is_failure_first_uncapped(capsys):
    """#109: a failing gate's evidence is never truncated at capture time.

    A gate late in the stream that fails with more output than the old
    2000-char tail must still have its full block emitted; passing gates
    with output keep the display-side tail-3 budget (D20).
    """
    long_text = "\n".join(f"evidence line {i}" for i in range(300))
    gs = [
        # earlier-stream passing gate with output → stays capped
        gates.Gate(id="chatty-ok", command=[
            sys.executable, "-c",
            "print('w1'); print('w2'); print('w3'); print('w4'); print('tail')"
        ]),
        # late-stream failing gate with output far beyond any tail budget
        gates.Gate(id="late-boom", command=[
            sys.executable, "-c",
            "import sys\n"
            "for i in range(300):\n"
            "    print(f'evidence line {i}')\n"
            "raise SystemExit(1)"
        ]),
    ]
    assert gates.run_gates(gs, None, 1, False) == 1
    out = capsys.readouterr().out
    # full failed-gate evidence: head and tail both present, no clip marker
    assert "evidence line 0" in out
    assert "evidence line 299" in out
    assert "truncated" not in out
    # passing gate still subject to the normal budget
    assert "earlier line(s) not shown" in out
    assert "w1" not in out
    assert "tail" in out


def test_usage_prog_names_the_subcommand(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": []})
    with pytest.raises(SystemExit) as exc:
        gates.main(["--help"])
    assert exc.value.code == 0
    assert "usage: gov run" in capsys.readouterr().out


def test_pass_with_output_stays_visible(capsys):
    """A passing gate that printed a warning must not be silenced (P1-2)."""
    gs = [gates.Gate(id="warny", command=[sys.executable, "-c",
                                          "print('line1'); print('line2'); print('line3'); "
                                          "print('heads up'); print('last warning')"])]
    assert gates.run_gates(gs, None, 1, False) == 0
    out = capsys.readouterr().out
    assert "PASS warny" in out
    assert "passed with output" in out
    assert "last warning" in out
    assert "earlier line(s) not shown" in out  # the cap dropped earlier lines
    assert "line1" not in out
    # the omission note reads after the shown content, not before it
    assert out.index("last warning") < out.index("earlier line(s) not shown")


def test_load_config_rejects_gate_in_no_mode(tmp_path):
    """D24: mode omission is not a parking mechanism — it silently never runs."""
    p = _write(tmp_path, {
        "modes": {"all": ["a"]},
        "gates": [{"id": "a", "command": PASS},
                  {"id": "ghost-gate", "command": PASS}],
    })
    with pytest.raises(gates.ConfigError) as e:
        gates.load_config(str(p))
    assert "ghost-gate" in str(e.value)
    assert "enabled\": false" in str(e.value)


def test_disabled_gate_may_omit_modes(tmp_path):
    p = _write(tmp_path, {
        "modes": {"all": ["a"]},
        "gates": [{"id": "a", "command": PASS},
                  {"id": "parked", "command": PASS, "enabled": False}],
    })
    modes, gs, concurrency, default_mode = gates.load_config(str(p))
    assert [g.id for g in gs] == ["a", "parked"]


def test_gate_on_disabled_gate_fails_loud(tmp_path, capsys, monkeypatch):
    """N4: naming a parked gate is operator error, not a silent green."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS, "enabled": False}]})
    assert gates.main(["--gate", "a"]) == 2
    assert "disabled" in capsys.readouterr().err


def test_every_gate_ignores_default_mode(tmp_path, capsys, monkeypatch):
    """D24: the explicit full matrix for CI."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {
        "modes": {"all": ["a"], "also": ["b"]},
        "defaultMode": "all",
        "gates": [{"id": "a", "command": PASS},
                  {"id": "b", "command": PASS}],
    })
    assert gates.main(["--every-gate"]) == 0
    out = capsys.readouterr().out
    assert "PASS a" in out and "PASS b" in out
    # and the default run still scopes to `all`
    assert gates.main([]) == 0
    out = capsys.readouterr().out
    assert "PASS b" not in out


def test_json_mode_pure_stdout(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS},
                                {"id": "off", "command": FAIL, "enabled": False}]})
    assert gates.main(["--json", "--every-gate"]) == 0
    import json as _json
    captured = capsys.readouterr()
    records = _json.loads(captured.out)  # stdout is exactly the JSON array
    assert [r["gate"] for r in records] == ["a", "off"]
    assert records[0]["outcome"] == "PASS"
    assert records[1]["outcome"] == "DISABLED"
    assert isinstance(records[0]["duration_ms"], int) and records[0]["duration_ms"] >= 0
    assert sorted(records[0].keys()) == ["blocking", "detail", "duration_ms",
                                         "gate", "outcome", "scoped_out",
                                         "selected_by"]
    assert records[0]["selected_by"] == "every-gate"  # #119
    assert records[0]["scoped_out"] is False
    assert "PASS a" in captured.err  # the human report moved to stderr


def test_json_mode_names_unselected_and_scoped_out(tmp_path, capsys, monkeypatch):
    """#119: one invocation answers the whole gate-set question — gates the
    mode did not pick (NOT_SELECTED) and gates the diff did not touch
    (SCOPED_OUT, scoped_out: true) appear in the record, not as absence."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {
        "modes": {"quick": ["a"], "slow": ["a", "b"]},
        "gates": [{"id": "a", "command": PASS},
                  {"id": "b", "command": PASS, "paths": ["docs/**"]}],
    })
    assert gates.main(["--json", "--mode", "quick"]) == 0
    import json as _json
    records = {r["gate"]: r for r in _json.loads(capsys.readouterr().out)}
    assert records["a"]["outcome"] == "PASS"
    assert records["a"]["selected_by"] == "mode:quick"
    assert records["b"]["outcome"] == "NOT_SELECTED"
    assert records["b"]["scoped_out"] is False
    assert records["b"]["blocking"] is False
    # path scoping (--base against a commit touching nothing)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-q", "-m", "empty"],
                   check=True, env={**os.environ, "GIT_AUTHOR_NAME": "t",
                                    "GIT_AUTHOR_EMAIL": "t@t",
                                    "GIT_COMMITTER_NAME": "t",
                                    "GIT_COMMITTER_EMAIL": "t@t"})
    assert gates.main(["--json", "--base", "HEAD"]) == 0
    records = {r["gate"]: r for r in _json.loads(capsys.readouterr().out)}
    # a has no paths -> always runs; b is path-scoped and nothing matched
    assert records["a"]["outcome"] == "PASS"
    assert records["b"]["outcome"] == "SCOPED_OUT"
    assert records["b"]["scoped_out"] is True
    assert records["b"]["selected_by"] == "base:HEAD"


@pytest.mark.parametrize("selector", [
    [], ["--mode", "quick"], ["--every-gate"], ["--gate", "notes"],
])
def test_json_stdout_is_pure_for_every_selector(tmp_path, capsys, monkeypatch, selector):
    """D26: with --json, stdout is exactly one JSON value — no leaks."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    _git_repo(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x\n", encoding="utf-8")  # gives --base something
    _write(tmp_path, {
        "modes": {"quick": ["notes"], "all": ["notes", "scope-gate"]},
        "defaultMode": "quick",
        "gates": [{"id": "notes", "command": PASS, "paths": ["docs/**"]},
                  {"id": "scope-gate", "command": PASS, "paths": ["other/**"]}],
    })
    rc = gates.main(["--json", *selector])
    assert rc == 0
    records = _json.loads(capsys.readouterr().out)  # must parse as pure JSON
    assert records and all("duration_ms" in r for r in records)
    # --base is its own exclusive selector; its scope line must not leak
    rc = gates.main(["--json", "--base", "HEAD"])
    assert rc == 0
    records = _json.loads(capsys.readouterr().out)
    assert records


def test_unknown_gate_key_rejects_loud(tmp_path, monkeypatch, capsys):
    """D29: "enable": false is a typo'd park that silently parks nothing."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS, "enable": False}]})
    assert gates.main([]) == 2
    assert "unknown key(s): enable" in capsys.readouterr().err


def test_unknown_top_level_key_rejects_loud(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"concurrencyy": 4, "gates": [{"id": "a", "command": PASS}]})
    assert gates.main([]) == 2
    assert "unknown top-level key(s): concurrencyy" in capsys.readouterr().err


def test_record_writes_history_by_default(tmp_path, monkeypatch):
    """D29: recording is the default; --no-record opts out."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS}]})
    assert gates.main([]) == 0
    hist = tmp_path / ".gov" / "history" / "gates.jsonl"
    lines = hist.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert _json.loads(lines[0])["gates"][0]["gate"] == "a"
    assert gates.main(["--no-record"]) == 0
    assert len(hist.read_text(encoding="utf-8").strip().splitlines()) == 1  # unchanged


def test_caller_tag_recorded_when_given(tmp_path, monkeypatch):
    """#120/D42: --tag / GOV_CALLER land as caller in gates.jsonl; absent
    keeps the record byte-shaped exactly as before (no caller key)."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS}]})
    assert gates.main([]) == 0
    assert gates.main(["--tag", "subagent-3"]) == 0
    monkeypatch.setenv("GOV_CALLER", "supervisor")
    assert gates.main([]) == 0
    assert gates.main(["--tag", "flag-wins"]) == 0
    monkeypatch.setenv("GOV_CALLER", "   ")  # whitespace-only = absent
    assert gates.main([]) == 0
    hist = tmp_path / ".gov" / "history" / "gates.jsonl"
    recs = [_json.loads(l) for l in hist.read_text(encoding="utf-8").splitlines()]
    assert len(recs) == 5
    assert "caller" not in recs[0]            # untagged: anonymous, as before
    assert recs[1]["caller"] == "subagent-3"  # --tag
    assert recs[2]["caller"] == "supervisor"  # GOV_CALLER fallback
    assert recs[3]["caller"] == "flag-wins"   # --tag wins over env
    assert "caller" not in recs[4]            # whitespace env = absent


def test_cost_recorded_alongside_caller(tmp_path, monkeypatch):
    """#126/D43: --cost / $GOV_COST land as a cost object on the run line,
    coexisting with D42's caller key; absent = record shape unchanged."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS}]})
    assert gates.main(["--tag", "bridge", "--cost", "tokens=1200,calls=4"]) == 0
    monkeypatch.setenv("GOV_COST", "tokens=10.5")
    assert gates.main([]) == 0  # env fallback, no flag
    monkeypatch.delenv("GOV_COST")
    assert gates.main([]) == 0
    recs = [_json.loads(l)
            for l in (tmp_path / ".gov/history/gates.jsonl").read_text(encoding="utf-8").splitlines()]
    assert recs[0]["cost"] == {"tokens": 1200, "calls": 4}
    assert recs[0]["caller"] == "bridge"  # one line carries both dimensions
    assert recs[1]["cost"] == {"tokens": 10.5}
    assert "cost" not in recs[2]  # unreported runs: pre-#126 shape


def test_cost_malformed_fails_loud_before_any_gate(tmp_path, monkeypatch, capsys):
    """#126/D43: bad cost input exits 2 naming the fragment — and a run
    that would otherwise be green must not run, so nothing lands uncosted."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"gates": [{"id": "a", "command": PASS}]})
    monkeypatch.setenv("GOV_COST", "tokens=lots")
    assert gates.main([]) == 2
    assert "tokens=lots" in capsys.readouterr().err
    monkeypatch.delenv("GOV_COST")
    assert gates.main(["--cost", "calls"]) == 2
    assert "unit=value" in capsys.readouterr().err
    assert gates.main(["--cost", "tokens=-1"]) == 2
    hist = tmp_path / ".gov/history/gates.jsonl"
    assert not hist.exists(), "a rejected run recorded nothing"
