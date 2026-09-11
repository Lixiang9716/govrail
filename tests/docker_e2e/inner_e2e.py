# The in-container E2E suite. Plain python, no pytest: the image carries
# only the interpreter, git, and the installed govrail — the same
# environment an adopter has. Run all scenarios or one:
#   python /usr/local/bin/inner_e2e.py            # all
#   python /usr/local/bin/inner_e2e.py lifecycle  # one
# Prints one "E2E <name>: PASS|FAIL" line per scenario; exit 1 on any FAIL.
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXPECTED_VERSION = os.environ.get("GOV_E2E_EXPECTED_VERSION", "")
PY = sys.executable or "python3"


def gov(*args, cwd, expect=0, env_extra=None, timeout=300):
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.pop("GOV_E2E_EXPECTED_VERSION", None)
    if env_extra:
        env.update(env_extra)
    for k in list(env):
        if k.startswith("GIT_"):
            del env[k]
    r = subprocess.run(
        ["gov", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=timeout)
    assert r.returncode == expect, (
        f"gov {' '.join(args)} -> {r.returncode}, expected {expect}\n"
        f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
    return r


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          check=check)


def commit_all(cwd, msg):
    git("add", "-A", cwd=cwd)
    git("-c", "commit.gpgsign=false", "commit", "-qm", msg, cwd=cwd)


_PROJECT_SEQ = 0


def fresh_project(base):
    global _PROJECT_SEQ
    _PROJECT_SEQ += 1
    p = Path(base) / f"proj-{_PROJECT_SEQ}"
    p.mkdir(parents=True)
    git("init", "-q", ".", cwd=p)
    git("config", "user.email", "t@t", cwd=p)
    git("config", "user.name", "t", cwd=p)
    (p / "README.md").write_text("# demo\n", encoding="utf-8")
    (p / "README.zh.md").write_text("# 演示\n", encoding="utf-8")
    commit_all(p, "init")
    return p


# ---------------------------------------------------------------- scenarios

def wheel_version(base):
    r = gov("--version", cwd=base)
    version = r.stdout.strip().split()[-1]
    assert version == EXPECTED_VERSION, (
        f"installed {version!r} != expected {EXPECTED_VERSION!r}")


def lifecycle(base):
    p = fresh_project(base)
    gov("init", cwd=p)
    r = gov("doctor", cwd=p)
    assert "environment sound" in r.stdout
    # pairing: a bilingual pair from birth, baselined
    docs = p / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("guide\n", encoding="utf-8")
    (docs / "guide.zh.md").write_text("指南\n", encoding="utf-8")
    gov("verify-pairing", "--write", cwd=p)
    commit_all(p, "baseline")
    # notes
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-a.md").write_text(
        "# Agent Note: a\n\nStatus: implemented\n\n## Problem\np\n\n"
        "## Decision\nd\n\n## Alternatives considered\na\n",
        encoding="utf-8")
    gov("verify-notes", cwd=p)
    commit_all(p, "note")
    # the template DAG is green
    r = gov("run", cwd=p)
    assert "7 gates" in r.stdout
    # conflict markers are red, then resolved
    (p / "tangled.md").write_text(
        "a\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> side\n", encoding="utf-8")
    gov("run", "--base", "HEAD", cwd=p, expect=1)
    (p / "tangled.md").write_text("resolved\n", encoding="utf-8")
    gov("run", "--base", "HEAD", cwd=p)
    # the task lifecycle with a receipt
    gov("task", "new", "Do the thing", cwd=p)
    gov("task", "claim", "T-0001", "--agent", "w1", cwd=p)
    gov("task", "claim", "T-0001", "--agent", "w2", cwd=p, expect=3)
    gov("task", "release", "T-0001", "--agent", "w1", cwd=p)
    commit_all(p, "card")
    gov("task", "close", "T-0001", cwd=p)
    # close wrote the receipt INTO the card; commit it so the tree is
    # clean — receipt verify demands a full clean green run on the tree
    commit_all(p, "card closed")
    gov("run", "--receipt", cwd=p)
    gov("receipt", "verify", "HEAD", cwd=p)
    # uninstall reverses exactly
    gov("uninstall", "--force", cwd=p)
    assert not (p / "gates.json").exists()
    assert not (p / ".gov").exists()


def ascii_locale(base):
    """The #168/#172 wall on a C-locale host: Chinese content everywhere,
    an ASCII-only locale, and every tool stays alive with UTF-8 output."""
    p = fresh_project(base)
    env = {"LANG": "C", "LC_ALL": "C"}
    gov("init", cwd=p, env_extra=env)
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-中文笔记.md").write_text(
        "# Agent Note: 中文决策\n\nStatus: implemented\n\n"
        "## Problem\n中文问题描述\n\n## Decision\n中文决定\n\n"
        "## Alternatives considered\n别的方案\n", encoding="utf-8")
    (p / "docs").mkdir(exist_ok=True)
    (p / "docs" / "decisions.md").write_text(
        "## D1 — 采用本平面\n\n- **选项**：gov init\n\n- **状态**：已决\n",
        encoding="utf-8")
    gov("verify-notes", cwd=p, env_extra=env)
    r = gov("verify-decisions", cwd=p, env_extra=env)
    assert "中文" in r.stdout or "D1" in r.stdout
    r = gov("stats", "--json", "--lang", "python", cwd=p, env_extra=env)
    value = json.loads(r.stdout)
    assert "python" in value["languages"]
    gov("check", cwd=p, env_extra=env)
    gov("run", "--mode", "quick", cwd=p, env_extra=env)


def concurrency(base):
    """Eight real processes race for one lease: exactly one wins."""
    p = fresh_project(base)
    gov("acquire", "res/race", "--agent", "warm", cwd=p)
    gov("release", "res/race", "--agent", "warm", cwd=p)
    procs = []
    env = dict(os.environ)
    for i in range(8):
        procs.append(subprocess.Popen(
            ["gov", "acquire", "res/race", "--agent", f"racer-{i}"],
            cwd=p, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env))
    outs = [pr.communicate() for pr in procs]
    codes = [pr.returncode for pr in procs]
    winners = [i for i, c in enumerate(codes) if c == 0]
    losers = [i for i, c in enumerate(codes) if c == 3]
    assert len(winners) == 1, f"exactly one winner, got {codes}"
    assert len(losers) == 7, f"everyone else is busy (3), got {codes}"
    gov("release", "res/race", "--agent", f"racer-{winners[0]}", cwd=p)


def crash_recovery(base):
    """A holder that dies still holds until its TTL expires; the next
    taker-over succeeds exactly at expiry."""
    p = fresh_project(base)
    gov("acquire", "res/crash", "--agent", "crasher", "--ttl", "2", cwd=p)
    # the holder is gone (the process exited); the lease file remains
    gov("acquire", "res/crash", "--agent", "early", cwd=p, expect=3)
    time.sleep(2.3)
    gov("acquire", "res/crash", "--agent", "late", cwd=p)  # takeover
    gov("release", "res/crash", "--agent", "late", cwd=p)


def prepush_hook(base):
    """The pre-push hook actually executes on a POSIX host (the host
    suite skips this): a red gate blocks the push, a green one lands."""
    p = fresh_project(base)
    remote = Path(base) / "remote.git"
    remote.mkdir()
    git("init", "-q", "--bare", str(remote), cwd=base)
    gov("init", "--hooks", cwd=p)
    git("remote", "add", "origin", str(remote), cwd=p)
    # the shipped DAG is green on the baselined tree -> push lands
    docs = p / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("g\n", encoding="utf-8")
    (docs / "guide.zh.md").write_text("指\n", encoding="utf-8")
    gov("verify-pairing", "--write", cwd=p)
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-a.md").write_text(
        "# Agent Note: a\n\nStatus: implemented\n\n## Problem\np\n\n"
        "## Decision\nd\n\n## Alternatives considered\na\n",
        encoding="utf-8")
    commit_all(p, "clean work")
    env = dict(os.environ)
    env["GOV_BIN"] = f"{PY} -m gov"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    r = subprocess.run(["git", "push", "-q", "origin",
                        "HEAD:refs/heads/main"], cwd=p, env=env,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"green push blocked: {r.stderr}"
    # now a red gate: conflict markers in a pushed file
    (p / "tangled.md").write_text("a\n<<<<<<< HEAD\nx\n=======\ny\n"
                                  ">>>>>>> side\n", encoding="utf-8")
    git("add", "-A", cwd=p)
    git("-c", "commit.gpgsign=false", "commit", "-qm", "tangled", cwd=p)
    r = subprocess.run(["git", "push", "-q", "origin",
                        "HEAD:refs/heads/main"], cwd=p, env=env,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode != 0, "a push carrying conflict markers must block"


def worktree_history(base):
    """D32: a linked worktree's runs land in the MAIN checkout's ledger."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    before = sum(1 for _ in (p / ".gov" / "history" / "gates.jsonl")
                 .open(encoding="utf-8")) \
        if (p / ".gov" / "history" / "gates.jsonl").exists() else 0
    git("worktree", "add", "-q", str(p.parent / "wt"), "HEAD", cwd=p)
    wt = p.parent / "wt"
    gov("run", "--mode", "quick", cwd=wt)
    main_ledger = p / ".gov" / "history" / "gates.jsonl"
    assert main_ledger.exists(), "the run recorded into the main checkout"
    after = sum(1 for _ in main_ledger.open(encoding="utf-8"))
    assert after > before, "the worktree run landed in the main ledger"
    assert not (wt / ".gov" / "history" / "gates.jsonl").exists(), \
        "ledgers do not fragment per worktree"


def perf_smoke(base):
    """120 generated files; stats stays well inside its time budget."""
    p = fresh_project(base)
    pkg = p / "src"
    pkg.mkdir()
    body = ("\n".join(f"def fn_{i}(a, b):\n"
                      f"    total = a + b\n"
                      f"    if total > {i}:\n"
                      "        return total\n"
                      "    return 0\n" for i in range(6)))
    for i in range(120):
        (pkg / f"mod_{i}.py").write_text(body, encoding="utf-8")
    t0 = time.monotonic()
    r = gov("stats", "--json", "--lang", "python", cwd=p, timeout=120)
    dt = time.monotonic() - t0
    value = json.loads(r.stdout)
    assert value["languages"]["python"]["files"] == 120
    assert value["languages"]["python"]["symbols"]["functions"] == 720
    assert dt < 60, f"stats took {dt:.1f}s — outside the budget"


def locale_bites(base):
    """The anti-vacuous probe for every cell. Under a GBK LC_ALL (the
    gbk cell) the host MUST actually decode GBK — preferred encoding
    GBK-family AND an unpinned decode of a UTF-8 child must mojibake —
    else the cell proves nothing. On UTF-8 cells the same probe asserts
    the #168 wall from the other side: Chinese round-trips every tool
    with no crash."""
    import locale
    lc = os.environ.get("LC_ALL", "")
    if "gbk" in lc.lower() or "gb2312" in lc.lower():
        enc = locale.getpreferredencoding(False)
        assert enc.lower() in ("gbk", "cp936", "gb2312"), (
            f"LC_ALL={lc!r} but preferred encoding is {enc!r} — the "
            "hostile locale did not take; this cell would be vacuous")
        r = subprocess.run(
            [PY, "-c", "print('中文')"], capture_output=True,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            text = r.stdout.decode(enc)
        except UnicodeDecodeError:
            pass  # crashes on the first non-ASCII byte — hostile, good
        else:
            assert text.strip() != "中文", (
                "child UTF-8 survived the unpinned GBK decode — the "
                "locale is not hostile, this cell proves nothing")
    # The #168 wall from the other side: Chinese survives every tool.
    p = fresh_project(base)
    env = dict(os.environ)
    gov("init", cwd=p, env_extra=env)
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-中文.md").write_text(
        "# Agent Note: 中文\n\nStatus: implemented\n\n"
        "## Problem\n中文问题\n\n## Decision\n中文决定\n\n"
        "## Alternatives considered\n其他\n", encoding="utf-8")
    gov("verify-notes", cwd=p, env_extra=env)
    r = gov("stats", "--json", "--lang", "python", cwd=p, env_extra=env)
    value = json.loads(r.stdout)
    assert "python" in value["languages"]
    gov("check", cwd=p, env_extra=env)


SCENARIOS = {
    "locale_bites": locale_bites,
    "wheel_version": wheel_version,
    "lifecycle": lifecycle,
    "ascii_locale": ascii_locale,
    "concurrency": concurrency,
    "crash_recovery": crash_recovery,
    "prepush_hook": prepush_hook,
    "worktree_history": worktree_history,
    "perf_smoke": perf_smoke,
}


def main(argv):
    names = argv or list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(ies): {', '.join(unknown)}; "
              f"known: {', '.join(SCENARIOS)}")
        return 2
    failures = 0
    with tempfile.TemporaryDirectory(prefix="gov-e2e-") as base:
        for name in names:
            try:
                SCENARIOS[name](base)
                print(f"E2E {name}: PASS", flush=True)
            except Exception as e:  # noqa: BLE001 — the report IS the product
                failures += 1
                print(f"E2E {name}: FAIL — {type(e).__name__}: {e}",
                      flush=True)
    print(f"inner e2e: {len(names) - failures}/{len(names)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
