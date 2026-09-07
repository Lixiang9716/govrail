import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from gov import task

# Portable gate command (#168): the Unix `true` does not exist on
# Windows — "a command that exits 0" must not depend on PATH.
PASS = [sys.executable, "-c", "pass"]


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".gov" / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gov" / "rules.md").write_text("# Rules\n", encoding="utf-8")
    (tmp_path / "gates.json").write_text(json.dumps({"gates": []}),
                                         encoding="utf-8")
    return tmp_path


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "gov", "task", *args],
        cwd=cwd, capture_output=True, text=True,
        env={"PYTHONPATH": str(Path(__file__).resolve().parent.parent),
             "PATH": "/usr/bin:/bin", "HOME": str(cwd)}, encoding="utf-8", errors="replace")


def test_new_writes_card_with_pin_and_checklist(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(_project(tmp_path))
    rc = task.main(["new", "Fix the flaky gate", "--check", "tests green",
                    "--check", "note written"])
    assert rc == 0
    card = json.loads(
        next((tmp_path / ".gov/tasks").glob("T-0001-*.json"))
        .read_text(encoding="utf-8"))
    assert card["id"] == "T-0001"
    assert card["status"] == "open"
    assert card["checklist"] == ["tests green", "note written"]
    combined, files = task.rules_hash(tmp_path)
    assert card["rules"]["hash"] == combined
    assert set(card["rules"]["files"]) == set(task.RULE_FILES)
    assert f"obey rules@{combined[:12]}" in capsys.readouterr().out


def test_check_flags_stale_pin_after_adoption(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.chdir(proj)
    assert task.main(["new", "Brief me"]) == 0
    # governance adoption: the rule set moves
    (proj / ".gov/rules.md").write_text("# Rules\n\nNew rule.\n", encoding="utf-8")
    assert task.main(["check"]) == 1


def test_new_rejects_mismatched_rules_pin(tmp_path, monkeypatch):
    monkeypatch.chdir(_project(tmp_path))
    rc = task.main(["new", "Pinned", "--rules", "deadbeef"])
    assert rc == 2


def test_rules_hash_fails_loud_without_rule_set(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    try:
        task.rules_hash()
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("missing .gov/rules.md must abort loud")


def test_check_rejects_done_card_without_green_receipt(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.chdir(proj)
    combined, _ = task.rules_hash(proj)
    (proj / ".gov/tasks/T-0001-x.json").write_text(json.dumps({
        "id": "T-0001", "title": "x",
        "rules": {"hash": combined}, "checklist": [],
        "status": "done", "receipt": None,
    }), encoding="utf-8")
    assert task.main(["check"]) == 1


def test_malformed_card_fails_loud(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.chdir(proj)
    (proj / ".gov/tasks/badname.json").write_text("{}", encoding="utf-8")
    try:
        task.main(["check"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("a badly named card must abort loud")


def test_close_runs_gates_and_records_receipt(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    (proj / "gates.json").write_text(json.dumps({
        "modes": {"all": ["noop"]},
        "gates": [{"id": "noop", "command": PASS}],
    }), encoding="utf-8")
    monkeypatch.chdir(proj)
    assert task.main(["new", "Close me"]) == 0
    # close shells out to `python -m gov run`; keep it in-process-cheap
    rc = task.main(["close", "T-0001", "--mode", "all", "--timeout", "60"])
    assert rc == 0
    card = json.loads(
        next((proj / ".gov/tasks").glob("T-0001-*.json")).read_text(encoding="utf-8"))
    assert card["status"] == "done"
    assert card["receipt"]["green"] is True
    assert all(g["outcome"] == "PASS" for g in card["receipt"]["gates"])
    assert card["receipt"]["rules"] == card["rules"]["hash"]
    assert task.main(["check"]) == 0


def test_close_refuses_stale_card(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.chdir(proj)
    assert task.main(["new", "Old pin"]) == 0
    (proj / ".gov/rules.md").write_text("# Rules v2\n", encoding="utf-8")
    assert task.main(["close", "T-0001"]) == 1


def test_close_ambiguous_prefix_fails_loud(tmp_path, monkeypatch):
    proj = _project(tmp_path)
    monkeypatch.chdir(proj)
    assert task.main(["new", "One"]) == 0
    assert task.main(["new", "Two"]) == 0
    assert task.main(["new", "Three"]) == 0
    try:
        task.main(["close", "T-0"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("an ambiguous prefix must abort loud")


def test_bare_task_fails_loud_naming_choices(tmp_path, monkeypatch, capsys):
    """#138: `required=True` on add_subparsers died under a shadowed
    pre-3.7 argparse backport, so the missing-subcommand rule is enforced
    by hand — it must still exit 2 with the choices named."""
    monkeypatch.chdir(_project(tmp_path))
    with pytest.raises(SystemExit) as exc:
        task.main([])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert ("a subcommand is required "
            "(new|check|close|claim|release|list)") in err


# --- claim semantics: leases on cards (D52 applied; card JSON untouched) ------
# These follow tests/test_locks.py's shape: the lease domain is the git
# common dir, so claim tests need a git repository, and the two-process
# race is the point of the exercise (an in-process call could never
# exercise cross-process exclusivity).

SCRUBBED = {k: v for k, v in os.environ.items()
            if not k.startswith("GIT_")}
REPO = Path(__file__).resolve().parent.parent


def _git_project(tmp_path: Path) -> Path:
    proj = _project(tmp_path)
    for cmd in (["git", "init", "-q", "."],
                ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=proj, check=True, capture_output=True,
                       env=SCRUBBED)
    return proj


def _lease_dir(proj: Path) -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], cwd=proj,
        capture_output=True, text=True, env=SCRUBBED, check=True, encoding="utf-8", errors="replace").stdout.strip()
    p = Path(out)
    return (p if p.is_absolute() else proj / p).resolve() / "gov-locks"


def _task_lease(proj: Path, cid: str = "T-0001") -> Path:
    return _lease_dir(proj) / (f"task__{cid}.json")


def test_claim_leases_open_card_and_announces(tmp_path, monkeypatch, capsys):
    proj = _git_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w1")
    assert task.main(["new", "Shared card"]) == 0
    before = json.loads(next(proj.joinpath(".gov/tasks").glob("T-0001-*.json"))
                        .read_text(encoding="utf-8"))
    capsys.readouterr()
    assert task.main(["claim", "T-0001", "--ttl", "120"]) == 0
    err = capsys.readouterr().err
    assert "w1" in err and "until" in err            # holder + expiry instant
    assert "task/T-0001" in err                      # the lease resource named
    data = json.loads(_task_lease(proj).read_text(encoding="utf-8"))
    assert data["resource"] == "task/T-0001"
    assert data["holder"] == "w1"
    # D43 boundary: the card JSON is byte-identical — the claim lives only
    # in the runtime domain
    after = json.loads(next(proj.joinpath(".gov/tasks").glob("T-0001-*.json"))
                       .read_text(encoding="utf-8"))
    assert after == before


def test_claim_missing_or_closed_card_exit2(tmp_path, monkeypatch, capsys):
    proj = _git_project(tmp_path)
    # the full gate set exists BEFORE the card is created: the card pins
    # the rule-set hash, and close refuses a card whose pin has drifted
    (proj / "gates.json").write_text(json.dumps({
        "modes": {"all": ["noop"]},
        "gates": [{"id": "noop", "command": PASS}],
    }), encoding="utf-8")
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w1")
    with pytest.raises(SystemExit) as exc:   # no card at all
        task.main(["claim", "T-0001"])
    assert exc.value.code == 2
    assert "no card matches 'T-0001'" in capsys.readouterr().err
    assert task.main(["new", "Will close"]) == 0
    # close it (green run with a noop gate), then claiming must be exit 2 —
    # a usage error, not a busy: waiting cannot reopen a closed card
    assert task.main(["claim", "T-0001", "--ttl", "600"]) == 0
    monkeypatch.setenv("GOV_CALLER", "boss")
    assert task.main(["close", "T-0001", "--timeout", "60"]) == 0
    monkeypatch.setenv("GOV_CALLER", "w9")
    assert task.main(["claim", "T-0001"]) == 2
    assert "is 'done', not open" in capsys.readouterr().err


def test_second_claim_busy_exit3_names_holder(tmp_path, monkeypatch, capsys):
    proj = _git_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w1")
    assert task.main(["new", "Contested"]) == 0
    assert task.main(["claim", "T-0001", "--ttl", "600"]) == 0
    monkeypatch.setenv("GOV_CALLER", "w2")
    capsys.readouterr()
    assert task.main(["claim", "T-0001"]) == 3
    err = capsys.readouterr().err
    assert "w1" in err and "until" in err
    assert json.loads(_task_lease(proj).read_text(encoding="utf-8"))["holder"] == "w1"


def test_release_non_holder_exit2_names_actual(tmp_path, monkeypatch, capsys):
    proj = _git_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w1")
    assert task.main(["new", "Held card"]) == 0
    assert task.main(["claim", "T-0001", "--ttl", "600"]) == 0
    monkeypatch.setenv("GOV_CALLER", "impostor")
    capsys.readouterr()
    assert task.main(["release", "T-0001"]) == 2
    err = capsys.readouterr().err
    assert "w1" in err
    assert _task_lease(proj).exists()
    monkeypatch.setenv("GOV_CALLER", "w1")
    assert task.main(["release", "T-0001"]) == 0
    assert not _task_lease(proj).exists()
    capsys.readouterr()
    assert task.main(["release", "T-0001"]) == 2   # no lease at all
    assert "not held" in capsys.readouterr().err


def test_expired_claim_is_taken_over(tmp_path, monkeypatch):
    proj = _git_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w2")
    assert task.main(["new", "Stale claim"]) == 0
    _lease_dir(proj).mkdir(parents=True, exist_ok=True)
    _task_lease(proj).write_text(json.dumps({
        "resource": "task/T-0001", "holder": "corpse",
        "acquired_at": "2020-01-01T00:00:00+00:00",
        "expires_at": "2020-01-01T00:01:00+00:00",
    }), encoding="utf-8")
    assert task.main(["claim", "T-0001", "--ttl", "300"]) == 0
    data = json.loads(_task_lease(proj).read_text(encoding="utf-8"))
    assert data["holder"] == "w2"


def test_two_processes_claim_same_card_exactly_one_wins(tmp_path):
    """The drill's headline failure — two workers take one card — is now a
    mechanical refusal: simultaneous claims on the SAME open card, one
    winner (exit 0), the loser exit 3 naming the holder. The go-file
    barrier makes the start simultaneous (same shape as
    tests/test_locks.py's takeover race)."""
    proj = _git_project(tmp_path)
    subprocess.run([sys.executable, "-m", "gov", "task", "new", "Race card"],
                   cwd=proj, check=True, capture_output=True,
                   env=dict(SCRUBBED, PYTHONPATH=str(REPO)))
    go = tmp_path / "go"
    env = dict(SCRUBBED, PYTHONPATH=str(REPO))
    procs = []
    for agent in ("race-a", "race-b"):
        procs.append(subprocess.Popen(
            [sys.executable, "-c",
             "import os, subprocess, sys, time\n"
             "go, cid, agent = sys.argv[1:4]\n"
             "while not os.path.exists(go):\n"
             "    time.sleep(0.005)\n"
             "# subprocess.call propagates the exit code on every OS;\n"
             "# os.execv loses it on Windows (#168 windows CI).\n"
             "raise SystemExit(subprocess.call(\n"
             "    [sys.executable, '-m', 'gov', 'task', 'claim', cid,\n"
             "      '--agent', agent, '--ttl', '300']))\n",
             str(go), "T-0001", agent],
            cwd=proj, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace"))
    go.write_text("go", encoding="utf-8")
    t0 = time.monotonic()
    outs = [p.communicate(timeout=30) for p in procs]
    elapsed = time.monotonic() - t0
    codes = [p.returncode for p in procs]
    assert sorted(codes) == [0, 3], (codes, outs)
    winner_out, loser_err = outs[codes.index(0)], outs[codes.index(3)]
    holder = json.loads(_task_lease(proj).read_text(encoding="utf-8"))["holder"]
    assert holder in ("race-a", "race-b")
    assert holder in loser_err[1]          # the loser names the actual holder
    assert "claimed by" in winner_out[1]   # the winner announces on stderr
    # timing sanity: the race itself is decided in-process-quickly — the
    # loser is refused at once (no --wait), not after any polling
    assert elapsed < 30


def test_list_json_claim_three_states(tmp_path, monkeypatch, capsys):
    """claim field: null (never claimed) / {claimed_by, expires_at} (live)
    / null again (expired — an expired lease reads as unclaimed)."""
    proj = _git_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w1")
    assert task.main(["new", "First"]) == 0     # T-0001: stays unclaimed
    assert task.main(["new", "Second"]) == 0    # T-0002: live claim
    assert task.main(["new", "Third"]) == 0     # T-0003: expired lease
    assert task.main(["claim", "T-0002", "--ttl", "600"]) == 0
    _lease_dir(proj).mkdir(parents=True, exist_ok=True)
    _task_lease(proj, "T-0003").write_text(json.dumps({
        "resource": "task/T-0003", "holder": "corpse",
        "acquired_at": "2020-01-01T00:00:00+00:00",
        "expires_at": "2020-01-01T00:01:00+00:00",
    }), encoding="utf-8")
    capsys.readouterr()
    assert task.main(["list", "--json"]) == 0
    records = json.loads(capsys.readouterr().out)
    by_id = {r["id"]: r for r in records}
    assert by_id["T-0001"]["claim"] is None
    live = by_id["T-0002"]["claim"]
    assert live["claimed_by"] == "w1"
    assert live["expires_at"]          # the expiry instant is named
    assert by_id["T-0003"]["claim"] is None     # expired reads as unclaimed
    # every record carries the pinned rules digest
    combined, _ = task.rules_hash(proj)
    assert by_id["T-0001"]["rules"] == combined[:12]


def test_list_text_appends_claim_column(tmp_path, monkeypatch, capsys):
    proj = _git_project(tmp_path)
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w1")
    assert task.main(["new", "Shown"]) == 0
    capsys.readouterr()
    assert task.main(["list"]) == 0
    plain = capsys.readouterr().out
    assert "open  T-0001 Shown" in plain        # unclaimed line unchanged
    assert task.main(["claim", "T-0001", "--ttl", "600"]) == 0
    capsys.readouterr()
    assert task.main(["list"]) == 0
    claimed = capsys.readouterr().out
    assert "[claimed by w1 until" in claimed


def test_close_clears_own_card_lease(tmp_path, monkeypatch, capsys):
    """close writes the receipt and best-effort clears the card's own task
    lease — holder-verified: only the lease naming the current caller."""
    proj = _git_project(tmp_path)
    (proj / "gates.json").write_text(json.dumps({
        "modes": {"all": ["noop"]},
        "gates": [{"id": "noop", "command": PASS}],
    }), encoding="utf-8")
    monkeypatch.chdir(proj)
    monkeypatch.setenv("GOV_CALLER", "w1")
    assert task.main(["new", "Finish me"]) == 0
    assert task.main(["claim", "T-0001", "--ttl", "600"]) == 0
    assert _task_lease(proj).exists()
    assert task.main(["close", "T-0001", "--timeout", "60"]) == 0
    assert not _task_lease(proj).exists()
    card = json.loads(next(proj.joinpath(".gov/tasks").glob("T-0001-*.json"))
                      .read_text(encoding="utf-8"))
    assert card["status"] == "done"


def test_list_outside_git_repo_claims_null(tmp_path, monkeypatch, capsys):
    """list is a display surface: without a git domain there is no claim
    state — null, never a crash (the lease-mutating commands refuse loud)."""
    proj = _project(tmp_path)                  # no git init
    monkeypatch.chdir(proj)
    assert task.main(["new", "No domain"]) == 0
    capsys.readouterr()
    assert task.main(["list"]) == 0
    assert "claimed by" not in capsys.readouterr().out
    assert task.main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["claim"] is None
    with pytest.raises(SystemExit) as exc:      # no lock domain: loud refusal
        task.main(["claim", "T-0001"])
    assert exc.value.code == 2
    assert "common dir" in capsys.readouterr().err
