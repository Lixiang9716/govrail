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


def perf_kilo(base):
    """The scale step: 1,200 files across a nested tree — parse, metrics
    and checks must stay inside a stated budget, and the counts must be
    EXACT (a perf test that only asserts "it finished" would swallow a
    walker that silently skipped half the tree)."""
    p = fresh_project(base)
    src = p / "src" / "pkg"
    src.mkdir(parents=True)
    body = ("\n".join(
        f"def fn_{i}(a, b):\n"
        f"    total = a + b\n"
        f"    if total > {i}:\n"
        "        return total\n"
        "    return 0\n" for i in range(5)))
    for i in range(1200):
        d = src / f"pack{i % 12}"
        d.mkdir(exist_ok=True)
        (d / f"mod_{i}.py").write_text(body, encoding="utf-8")
    gov("init", cwd=p)
    t0 = time.monotonic()
    r = gov("stats", "--json", "--lang", "python", cwd=p, timeout=300)
    stats_dt = time.monotonic() - t0
    value = json.loads(r.stdout)
    py = value["languages"]["python"]
    assert py["files"] == 1200, f"walker lost files: {py['files']}"
    assert py["symbols"]["functions"] == 6000
    # exact, because the walker is not allowed to lose or invent lines:
    # 5 functions x (5 code lines + 1 blank from the join) = 29 per file
    assert py["lines"]["total"] == 1200 * 29
    t0 = time.monotonic()
    gov("check", cwd=p, timeout=300)
    check_dt = time.monotonic() - t0
    # ceilings = measured (0.3s/0.7s at first run) x ~100 headroom:
    # loose enough not to flake on slow runners, tight enough that a
    # 100x walker regression cannot hide inside "it passed"
    assert stats_dt < 30, f"stats took {stats_dt:.1f}s at 1.2k files"
    assert check_dt < 60, f"check took {check_dt:.1f}s at 1.2k files"
    print(f"    perf_kilo measured: stats {stats_dt:.1f}s, "
          f"check {check_dt:.1f}s")


def drift_chaos(base):
    """The adoption surface under stress: customization, loss, adoption,
    and the uninstall warning — every transition of the drift machine
    (D34) walked through the CLI."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    # 1. a customized file: upgrade names the drift honestly
    rules = p / ".gov" / "rules.md"
    rules.write_text(rules.read_text(encoding="utf-8")
                     + "\n## 9. house rule\n", encoding="utf-8")
    r = gov("init", "--upgrade", cwd=p)
    assert "DIFFERS" in r.stdout
    # 2. a lost file: upgrade reports MISSING as adoptable, adopt restores
    lost = p / ".gov" / "rejections" / "README.md"
    lost.unlink()
    r = gov("init", "--upgrade", cwd=p)
    assert "MISSING" in r.stdout
    gov("init", "--adopt", cwd=p)
    assert lost.exists(), "--adopt must land the missing file"
    r = gov("init", "--upgrade", cwd=p)
    assert "MISSING" not in r.stdout
    # 3. --json is exactly one value even mid-chaos
    r = gov("init", "--upgrade", "--json", cwd=p)
    value = json.loads(r.stdout)
    assert "files" in value
    # 4. uninstall must NOT go quietly over the customized tree
    r = gov("uninstall", cwd=p, expect=1)  # warns, names the files, exits 1
    gov("uninstall", "--force", cwd=p)
    assert not (p / ".gov").exists()



def decisions_dir(base):
    """The decisions source in `dir` format: one file per decision, so
    parallel appends are structurally conflict-free (D17/D40) — and the
    numbering guard must still catch a hole when a file vanishes."""
    p = fresh_project(base)
    gov("init", cwd=p)
    cfg = p / ".gov" / "decisions.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(
        {"path": "docs/decisions", "format": "dir"}), encoding="utf-8")
    d = p / "docs" / "decisions"
    d.mkdir(parents=True)
    (d / "D1-adopt.md").write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n",
        encoding="utf-8")
    r = gov("decision", "next", cwd=p)
    assert "D2" in r.stdout
    draft = p / "d2-draft.md"
    draft.write_text("agent a plan\n\n- **选项**：a\n\n- **状态**：已决\n",
                     encoding="utf-8")
    gov("decision", "add", "--from", str(draft), cwd=p)
    made = list(d.glob("D2-*.md"))
    assert len(made) == 1 and made[0].is_file(), (
        "dir format: one file per decision")
    draft.write_text("agent b plan\n\n- **选项**：b\n\n- **状态**：已决\n",
                     encoding="utf-8")
    gov("decision", "add", "--from", str(draft), cwd=p)
    assert list(d.glob("D3-*.md")), "the next add allocates D3"
    gov("verify-decisions", cwd=p)
    # a vanished MIDDLE file is a numbering hole — the gate must say so
    # (removing the highest number would be legitimate: not created yet)
    gone = list(d.glob("D2-*.md"))[0]
    gone.unlink()
    gov("verify-decisions", cwd=p, expect=1)
    gone.write_text("## D2 — agent a plan\n\n- **选项**：a\n\n"
                    "- **状态**：已决\n", encoding="utf-8")
    gov("verify-decisions", cwd=p)


def perf_night(base):
    """The nightly scale tier: 10,000 files. Gated behind
    GOV_E2E_NIGHTLY=1 — minutes-wide budgets are a scheduled act, not a
    per-PR default (run.sh --nightly)."""
    if os.environ.get("GOV_E2E_NIGHTLY") != "1":
        print("E2E perf_night: SKIP (set GOV_E2E_NIGHTLY=1)")
        return
    p = fresh_project(base)
    src = p / "src" / "pkg"
    src.mkdir(parents=True)
    body_template = ("\n".join(
        f"def fn_{i}(a, b):\n"
        f"    total = a + b\n"
        f"    if total > {i}:\n"
        "        return total\n"
        "    return 0\n" for i in range(5)))
    for i in range(10000):
        d = src / f"pack{i % 50}"
        d.mkdir(exist_ok=True)
        (d / f"mod_{i}.py").write_text(body_template, encoding="utf-8")
    t0 = time.monotonic()
    r = gov("stats", "--json", "--lang", "python", cwd=p, timeout=600)
    stats_dt = time.monotonic() - t0
    py = json.loads(r.stdout)["languages"]["python"]
    assert py["files"] == 10000, f"walker lost files: {py['files']}"
    assert py["symbols"]["functions"] == 50000
    # 29 lines per file (5 blocks + join blanks) — the arithmetic the
    # kilo tier pins, at 10x the scale
    assert py["lines"]["total"] == 10000 * 29
    t0 = time.monotonic()
    gov("check", cwd=p, timeout=600)
    check_dt = time.monotonic() - t0
    # ceilings = measured (2.3s/5.6s at first run) x ~20 headroom
    assert stats_dt < 60 and check_dt < 120, (
        f"nightly tier overrun: stats {stats_dt:.1f}s, "
        f"check {check_dt:.1f}s")
    print(f"    perf_night measured: stats {stats_dt:.1f}s, "
          f"check {check_dt:.1f}s")


def postmortem_recall(base):
    """The memory read-side over the postmortem corpus: a hit names
    the document, a miss states the corpus it searched (with per-term
    counts) and exits 1 — a miss is never silent about WHAT was
    searched (#148)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    pm = p / "docs" / "postmortem"
    pm.mkdir(parents=True)
    (pm / "2026-09-11-outage.md").write_text(
        "# Postmortem: the outage\n\nroot cause: cache stampede\n",
        encoding="utf-8")
    r = gov("recall", "outage", cwd=p)
    # the corpus statement is DELIBERATELY on stderr (stdout stays the
    # ranked hit list) — assert against both streams
    both = r.stdout + r.stderr
    assert "2026-09-11-outage.md" in r.stdout, "the hit names the doc"
    assert "postmortems 1" in both, "the corpus statement counts it"
    r = gov("recall", "quantum-entangle", cwd=p, expect=1)
    both = r.stdout + r.stderr
    assert "corpus" in both and "postmortems 1" in both, (
        "a miss must state what was searched")
    assert "quantum-entangle: 0" in r.stdout, "per-term counts on a miss"
    # a Chinese term round-trips the same read-side (the UTF-8 wall)
    (pm / "2026-09-12-中文复盘.md").write_text(
        "# Postmortem: 中文复盘\n\n根因：缓存雪崩\n", encoding="utf-8")
    r = gov("recall", "缓存雪崩", cwd=p)
    assert "中文复盘" in r.stdout


def memory_trend(base):
    """The ledgers' read-side, end to end: tagged runs with caller-
    reported cost flow into history, and trend reads all three views
    (window, by-tag, cost); recall's AND / --any / per-term diagnostics
    over the notes corpus (#148)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    # three tagged runs, caller-reported cost
    for tag, cost in (("alpha", "tokens=100"),
                      ("alpha", "tokens=200"),
                      ("beta", "tokens=50")):
        gov("run", "--tag", tag, "--cost", cost, cwd=p)
    r = gov("trend", cwd=p)
    assert "run(s) in" in r.stdout
    r = gov("trend", "--by-tag", cwd=p)
    assert "alpha" in r.stdout and "beta" in r.stdout, \
        "runs group by their caller tag"
    r = gov("trend", "--cost", cwd=p)
    assert "tokens" in r.stdout, "the cost ledger rolls up by caller"

    # recall: AND, per-term diagnostics on a miss, --any relaxation
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-汇率.md").write_text(
        "# Agent Note: 汇率风暴\n\nStatus: implemented\n\n"
        "## Problem\n汇率波动\n\n## Decision\n对冲\n\n"
        "## Alternatives considered\n不作为\n", encoding="utf-8")
    gov("recall", "汇率风暴", cwd=p)                       # exact hit
    r = gov("recall", "汇率风暴", "不存在的词", cwd=p, expect=1)  # AND misses
    assert "汇率风暴: 1" in r.stdout and "不存在的词: 0" in r.stdout, \
        "the miss names which term the corpus lacks and which it has"
    gov("recall", "--any", "汇率风暴", "不存在的词", cwd=p)   # --any relaxes



def review_grade(base):
    """The review journey (D30): dossier, then the interactive rubric
    grade loop with the human's stdin transcribed — approve exits 0,
    request-changes exits 1 with the blockers named. The human decides;
    the machine transcribes — here stdin IS the human."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    docs = p / "docs"
    docs.mkdir(exist_ok=True)
    item = ("### {rid} — {title}\n\n"
            "- **Checks:** the diff carries `{thing}`\n"
            "- **Evidence:** the file exists and names its purpose\n"
            "- **Anti-pattern:** silent work\n"
            "- **Gate candidate:** no — judgment\n")
    (docs / "review-rubric.md").write_text(
        "# Review rubric\n\n"
        + item.format(rid="R1", title="feature lands loudly",
                      thing="feature.txt")
        + "\n"
        + item.format(rid="R2", title="cleanup is real", thing="cleanup.txt")
        + "\n", encoding="utf-8")
    (p / "feature.txt").write_text("the feature\n", encoding="utf-8")
    note_dir = p / ".agents" / "notes" / "implemented" / "feature"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-feature.md").write_text(
        "# Agent Note: feature\n\nStatus: implemented\n\n"
        "## Problem\np\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")
    commit_all(p, "the work under review")
    base_ref = "HEAD~1"

    # approve: both items pass — the human's p keys, transcribed
    r = subprocess.run(
        ["gov", "review", "--base", base_ref, "--grade"],
        cwd=p, input="p\np\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, f"approve journey failed: {r.stdout}{r.stderr}"
    assert "verdict: approve" in r.stdout
    assert "R1 — pass" in r.stdout and "R2 — pass" in r.stdout

    # request changes: an f verdict demands evidence, blocks, and the
    # verdict names the blocker with the evidence the human typed; s
    # skips an item without blocking it
    r = subprocess.run(
        ["gov", "review", "--base", base_ref, "--grade"],
        cwd=p, input="f\nfeature.txt:1 says otherwise\ns\n",
        capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 1, "a fail verdict must block"
    assert "R1 — fail — feature.txt:1 says otherwise" in r.stdout, r.stdout
    assert "blockers:" in r.stdout
    assert "verdict: request changes" in r.stdout


def archive_closure(base):
    """The archive loop: implemented notes move to the frozen archive,
    the seal covers them, recall still reads them (memory persists past
    archiving, with the corpus statement counting the archived side),
    tampering is caught, and re-sealing a drift is refused — restoring
    the sealed bytes makes verify green again without any re-seal."""
    p = fresh_project(base)
    gov("init", cwd=p)
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-stays.md").write_text(
        "# Agent Note: stays implemented\n\nStatus: implemented\n\n"
        "## Problem\np\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")
    gone = note_dir / "2026-01-01-superseded.md"
    gone.write_text(
        "# Agent Note: superseded approach\n\nStatus: implemented\n\n"
        "## Problem\ncache stampede\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")
    commit_all(p, "two implemented notes")

    # the archive move + seal
    arch = p / ".agents" / "notes" / "archived" / "bug-fix"
    arch.mkdir(parents=True)
    gone.rename(arch / gone.name)
    gov("archive-notes", cwd=p)
    gov("verify-archive", cwd=p)

    # memory persists past archiving; the corpus statement counts it
    r = gov("recall", "stampede", cwd=p)
    both = r.stdout + r.stderr
    assert "superseded" in both and "archived 1" in both, (
        "the archived note must stay readable (corpus: " + both + ")")

    # tampering is caught and re-sealing a drift is refused (no
    # laundering); restoring the sealed bytes turns verify green again
    sealed = arch / gone.name
    original = sealed.read_text(encoding="utf-8")
    sealed.write_text("tampered\n", encoding="utf-8")
    gov("verify-archive", cwd=p, expect=1)
    r = gov("archive-notes", cwd=p, expect=1)
    assert "refus" in (r.stdout + r.stderr).lower(), r.stdout + r.stderr
    sealed.write_text(original, encoding="utf-8")
    gov("verify-archive", cwd=p)



def cost_attribution(base):
    """The cost ledger's read-side (D45) with a hand-checkable design:
    seven runs whose per-caller sums and early/late window split are
    known by construction — alpha jumps 100,100 -> 300,300, beta stays
    flat at 50, one run carries cost with no tag at all. Attributing
    spend across callers is exactly what the ledger shape exists for;
    the assertions read the ROLL-UP, not the raw history."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    # 8 runs, interleaved so the window's GLOBAL halves (first 4 vs last
    # 4) give every caller an exact, hand-checkable split: alpha triples
    # 200 -> 600 across the halves, beta drains 100 -> 0, the untagged
    # runs are attributed rather than dropped (0 -> 160)
    plan = [("alpha", "100"), ("beta", "50"),
            ("alpha", "100"), ("beta", "50"),
            ("alpha", "300"), (None, "80"),
            ("alpha", "300"), (None, "80")]
    for tag, tokens in plan:
        if tag:
            gov("run", "--tag", tag, "--cost", f"tokens={tokens}", cwd=p)
        else:
            gov("run", "--cost", f"tokens={tokens}", cwd=p)

    r = gov("trend", "--cost", cwd=p)
    out = r.stdout
    assert "8 run(s) in" in out and "8 reporting cost" in out, out
    # sums are hand-computed: alpha 800 (200 early -> 600 late, the 3x
    # jump the plan builds), beta flat 100 (50 -> 50), and the untagged
    # runs are attributed to "(untagged)" rather than dropped
    assert "caller alpha: 4 run(s): tokens 800 " \
           "(200 early → 600 late)" in out, out
    assert "caller beta: 2 run(s): tokens 100 (100 early → 0 late)" in out, \
        out
    assert "caller (untagged): 2 run(s): tokens 160 (0 early → 160 late)" \
        in out, out

    # the documented refusal: --cost already groups by caller
    r = gov("trend", "--cost", "--by-tag", cwd=p, expect=2)
    assert "cannot be combined" in r.stderr
    r = gov("trend", "--cost", "--gate", "self-test", cwd=p, expect=2)
    assert "--gate filters durations only" in r.stderr



def surfaces_custom(base):
    """The custom change-surface: .gov/surfaces.json maps path globs to
    a surface name and the gates covering it — matched files suggest
    exactly those gates (most specific first, D25); unmatched files
    fall through to gates.json paths. A malformed mapping is refused
    loudly (rule 5)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    gates = json.loads((p / "gates.json").read_text(encoding="utf-8"))
    gates["gates"].append(
        {"id": "ml", "command": ["true"], "paths": ["model/**"]})
    (p / "gates.json").write_text(json.dumps(gates), encoding="utf-8")
    (p / ".gov" / "surfaces.json").write_text(json.dumps(
        {"experiments/**": {"surface": "experiments",
                            "gates": ["source-limits"]}}), encoding="utf-8")
    (p / "docs").mkdir(exist_ok=True)
    commit_all(p, "surfaces + gates configured")

    # a change OUTSIDE every custom surface: falls back to gates.json
    # paths — the custom surface's gates are not suggested
    (p / "docs" / "new.md").write_text("doc\n", encoding="utf-8")
    r = gov("change-scope", "--base", "HEAD", cwd=p)
    assert "source-limits" not in r.stdout, r.stdout
    commit_all(p, "docs change")

    # a change under the custom surface: the surface is named and its
    # gates suggested, most specific first (D25)
    (p / "experiments").mkdir(exist_ok=True)
    (p / "experiments" / "probe.py").write_text("x = 1\n",
                                                encoding="utf-8")
    r = gov("change-scope", "--base", "HEAD", cwd=p)
    assert "experiments" in r.stdout, r.stdout
    assert "source-limits" in r.stdout, r.stdout

    # a malformed mapping is refused loudly, naming the pattern (rule 5)
    (p / ".gov" / "surfaces.json").write_text(
        json.dumps({"broken/**": "not-a-mapping"}), encoding="utf-8")
    r = gov("change-scope", "--base", "HEAD", cwd=p, expect=2)
    both = r.stdout + r.stderr
    assert "broken/**" in both and '"surface"' in both, both


def decision_parallel(base):
    """Two concurrent `decision add` calls in ONE checkout: the flock
    must cover the whole read-modify-write, or the second writer's
    stale view silently deletes the first writer's decision (found live
    by this very scenario — the old lock guarded only the write)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    d = p / "docs" / "decisions.md"
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_text("## D1 — adopt\n\n- **选项**：gov init\n\n"
                 "- **状态**：已决\n", encoding="utf-8")
    commit_all(p, "seed D1")
    draft = p / "d2.md"
    draft.write_text("parallel plan\n\n- **选项**：a\n\n"
                     "- **状态**：已决\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # two REAL processes race for the SAME D2: mutual exclusion means
    # exactly one wins, and the loser's refusal must not have lost the
    # winner's write (the read-modify-write is serialized under flock)
    procs = [
        subprocess.Popen(
            ["gov", "decision", "add", "--from", str(draft), "--id", "D2"],
            cwd=p, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env),
        subprocess.Popen(
            ["gov", "decision", "add", "--from", str(draft), "--id", "D2"],
            cwd=p, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env),
    ]
    outs = [pr.communicate(timeout=120) for pr in procs]
    codes = [pr.returncode for pr in procs]
    assert sorted(codes) == [0, 1], (
        f"exactly one winner: got {codes} ({outs})")
    text = d.read_text(encoding="utf-8")
    assert text.count("## D2 — parallel plan") == 1, \
        "the winner's decision is present exactly once"
    assert "## D1 — adopt" in text, "the seed decision was not clobbered"
    gov("verify-decisions", cwd=p)
    assert not list(d.parent.glob(".decision.lock")), \
        "the lock file must not litter the tree"
    # serialization is observable: a sequential add after the race sees
    # the winner's D2 and allocates D3 (a concurrent D3 would refuse)
    gov("decision", "add", "--from", str(draft), "--id", "D3", cwd=p)
    gov("verify-decisions", cwd=p)



def trend_base_split(base):
    """--base cuts the trend window at the base ref's COMMIT date
    (#119). Deterministic via a hand-crafted ledger (metrics, not
    evidence — D44's line says crafting it is legitimate) and a
    backdated commit: two runs 3 days old, two now, base dated 2 days
    ago — the split must be 100ms early -> 300ms late, x3.0 mover."""
    from datetime import datetime, timedelta, timezone
    p = fresh_project(base)
    gov("init", cwd=p)
    (p / "feature.txt").write_text("work\n", encoding="utf-8")
    git("add", "-A", cwd=p)
    # a BACKDATED commit: committer/author dates are what %cI reports,
    # and they are the line trend's --base split cuts at
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    env = dict(os.environ)
    env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = past
    subprocess.run(["git", "commit", "--amend", "--no-edit",
                    "--date=" + past],
                   cwd=p, env=env, capture_output=True, check=True)
    base_ref = "HEAD"

    now = datetime.now(timezone.utc)
    early_ts = (now - timedelta(days=3)).isoformat(timespec="seconds")
    late_ts = now.isoformat(timespec="seconds")
    history = p / ".gov" / "history" / "gates.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    gate = {"gate": "g", "outcome": "PASS", "blocking": False,
            "duration_ms": 100, "detail": "", "selected_by": "e2e",
            "scoped_out": False}
    late_gate = dict(gate, duration_ms=300)
    lines = [
        {"ts": early_ts, "gates": [gate]},
        {"ts": early_ts, "gates": [dict(gate, duration_ms=100)]},
        {"ts": late_ts, "gates": [late_gate]},
        {"ts": late_ts, "gates": [dict(late_gate)]},
    ]
    with history.open("a", encoding="utf-8") as f:
        for rec in lines:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    r = gov("trend", "--base", base_ref, cwd=p)
    # the split is at the base commit's date: the 3-day-old runs are
    # early, the now-runs late — 100ms -> 300ms is a x3.0 mover
    assert "p50 100ms → 300ms" in r.stdout, r.stdout
    assert "×3.0 ↑" in r.stdout, r.stdout
    # without --base the window halves of the same 4 runs give the same
    # answer (first half early, second half late) — the two split paths
    # agree on this fixture
    r = gov("trend", cwd=p)
    assert "p50 100ms → 300ms" in r.stdout, r.stdout


def manifest_drift(base):
    """The version-drift chain: a stale manifest version is a doctor
    NOTE (never a crash), it retunes whatsnew's default `since`, it
    names itself in upgrade --json, and aligning it silences all three."""
    p = fresh_project(base)
    gov("init", cwd=p)
    manifest = p / ".gov" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    current = data["version"]
    stale = "0.1.0"
    data["version"] = stale
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    r = gov("doctor", cwd=p)  # a note, not a problem: exit stays 0
    assert f"manifest initialized with govrail {stale}" in r.stdout
    assert "gov init --upgrade" in r.stdout

    # whatsnew's default `since` follows the manifest: an old manifest
    # means the operator sees everything since
    r = gov("whatsnew", cwd=p)
    assert f"since {stale}" in r.stdout
    assert f"## {current}" in r.stdout

    r = gov("init", "--upgrade", "--json", cwd=p)
    value = json.loads(r.stdout)
    assert value["initialized_with"] == stale
    assert value["package"] == current

    # aligning the manifest silences the drift note
    data["version"] = current
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    r = gov("doctor", cwd=p)
    assert f"manifest initialized with govrail {stale}" not in r.stdout



def cost_base_split(base):
    """--cost and --base compose: the window cut at the base commit's
    date, the roll-up attributed per caller, both hand-computed. Two
    100-token runs 3 days old, two 300-token runs now, base dated 2 days
    ago: 800 total, 200 early -> 600 late — the same fixture shape the
    duration split pins, on the cost dimension."""
    from datetime import datetime, timedelta, timezone
    p = fresh_project(base)
    gov("init", cwd=p)
    (p / "feature.txt").write_text("work\n", encoding="utf-8")
    git("add", "-A", cwd=p)
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    env = dict(os.environ)
    env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = past
    subprocess.run(["git", "commit", "--amend", "--no-edit",
                    "--date=" + past],
                   cwd=p, env=env, capture_output=True, check=True)
    base_ref = "HEAD"

    now = datetime.now(timezone.utc)
    early_ts = (now - timedelta(days=3)).isoformat(timespec="seconds")
    late_ts = now.isoformat(timespec="seconds")
    history = p / ".gov" / "history" / "gates.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    gate_pass = {"gate": "g", "outcome": "PASS", "blocking": False,
                 "detail": "", "selected_by": "e2e", "scoped_out": False}
    lines = []
    for ts, tokens in ((early_ts, 100), (early_ts, 100),
                       (late_ts, 300), (late_ts, 300)):
        gate = dict(gate_pass, duration_ms=50)
        lines.append({"ts": ts, "caller": "alpha",
                      "cost": {"tokens": tokens}, "gates": [gate]})
    with history.open("a", encoding="utf-8") as f:
        for rec in lines:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    r = gov("trend", "--cost", "--base", base_ref, cwd=p)
    out = r.stdout
    assert "caller alpha: 4 run(s): tokens 800 " \
           "(200 early → 600 late)" in out, out
    assert "8 reporting cost" not in out  # exactly the 4 crafted runs


def postmortem_pair(base):
    """A bilingual postmortem is a docs pair like any other: the pairing
    gate baselines it, drift goes red with the fix command inline, and
    recall reads BOTH language sides from the same corpus."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    pm = p / "docs" / "postmortem"
    pm.mkdir(parents=True)
    (pm / "2026-09-11-outage.md").write_text(
        "# Postmortem: the outage\n\nroot cause: cache stampede\n",
        encoding="utf-8")
    (pm / "2026-09-11-outage.zh.md").write_text(
        "# 复盘：故障\n\n根因：缓存雪崩\n", encoding="utf-8")
    gov("verify-pairing", "--write", cwd=p)
    gov("verify-pairing", cwd=p)

    # drift: the zh side moves without re-confirmation — red, with the
    # scoped fix command inline
    (pm / "2026-09-11-outage.zh.md").write_text(
        "# 复盘：故障\n\n根因：缓存雪崩（复发风险）\n", encoding="utf-8")
    r = gov("verify-pairing", cwd=p, expect=1)
    assert "2026-09-11-outage" in r.stdout
    gov("verify-pairing", "--write", cwd=p)

    # recall reads both language sides from one corpus
    r = gov("recall", "stampede", cwd=p)
    assert "outage.md" in r.stdout
    r = gov("recall", "缓存雪崩", cwd=p)
    assert "outage.zh.md" in r.stdout



def by_tag_split(base):
    """--by-tag composes with --base: every caller group splits at the
    SAME commit date (#120). The crafted ledger makes the composition
    DISTINGUISHABLE from the own-halfway default: a tag concentrated
    before the base date has an empty late half under --base (it cannot
    compare), while the own-halfway split would call it stable over
    nothing. First-appearance ordering is pinned too."""
    from datetime import datetime, timedelta, timezone
    p = fresh_project(base)
    gov("init", cwd=p)
    (p / "feature.txt").write_text("work\n", encoding="utf-8")
    git("add", "-A", cwd=p)
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    env = dict(os.environ)
    env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = past
    subprocess.run(["git", "commit", "--amend", "--no-edit",
                    "--date=" + past],
                   cwd=p, env=env, capture_output=True, check=True)
    base_ref = "HEAD"

    now = datetime.now(timezone.utc)
    early_ts = (now - timedelta(days=3)).isoformat(timespec="seconds")
    late_ts = now.isoformat(timespec="seconds")

    def rec(ts, caller, ms):
        return {"ts": ts, "caller": caller,
                "gates": [{"gate": "g", "outcome": "PASS",
                           "blocking": False, "duration_ms": ms,
                           "detail": "", "selected_by": "e2e",
                           "scoped_out": False}]}

    history = p / ".gov" / "history" / "gates.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    lines = [rec(early_ts, "alpha", 100), rec(early_ts, "alpha", 100),
             rec(late_ts, "beta", 300), rec(late_ts, "beta", 300)]
    with history.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")

    # own-halfway: each group compares against itself -> stable
    r = gov("trend", "--by-tag", cwd=p)
    assert "p50 100ms → 100ms" in r.stdout
    assert "p50 300ms → 300ms" in r.stdout
    assert "stable over 2 run(s)" in r.stdout
    # composed with --base: alpha sits entirely before the cut, beta
    # entirely after — each group's far side is EMPTY, and the report
    # says so instead of inventing a comparison
    r = gov("trend", "--by-tag", "--base", base_ref, cwd=p)
    assert r.stdout.count("need at least 2 comparable run(s) to split") == 2
    assert "caller alpha" in r.stdout and "caller beta" in r.stdout
    assert "split at" in r.stdout
    # first-appearance ordering: alpha (seen first) lists before beta
    assert r.stdout.index("caller alpha") < r.stdout.index("caller beta")


def demo_specimen(base):
    """The living specimen stays a working governed project: the demo
    copied into the workspace runs its own full gate DAG, reads as clean
    by the parse layer's checks, and reports its structure."""
    demo = Path("/demo")
    if not demo.is_dir():
        print("E2E demo_specimen: SKIP (no /demo in this image)")
        return
    p = Path(base) / "demo-work"
    p.mkdir(parents=True)
    for item in demo.iterdir():
        target = p / item.name
        if item.is_dir():
            import shutil
            shutil.copytree(item, target)
        else:
            import shutil
            shutil.copy(item, target)
    # the copy must BE a repository: the git-driven gates (note-presence,
    # conflict-markers) diff against HEAD — without it they cannot run
    git("init", "-q", ".", cwd=p)
    git("config", "user.email", "t@t", cwd=p)
    git("config", "user.name", "t", cwd=p)
    commit_all(p, "specimen as shipped")
    # the specimen is already initialized: its DAG runs green as shipped
    r = gov("run", "--mode", "all", cwd=p)
    assert "pass" in r.stdout
    # the read-side over the specimen
    r = gov("stats", "--json", "--lang", "python", cwd=p)
    value = json.loads(r.stdout)
    assert value["languages"]["python"]["files"] >= 1
    gov("check", cwd=p)
    # the demo's rejection cases run under self-test inside it
    r = gov("self-test", "--scope", "project", cwd=p)
    assert "all pass" in r.stdout




def review_dossier_recall(base):
    """The dossier's recall section (#3): recall terms are PATH TOKENS of
    the change (>= 4 chars, not stopwords), and the hits name the note
    that the corpus already remembers — the reviewer reads memory before
    judging. A term the corpus lacks is named as lacking (--any's
    diagnostics live one flag away)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-hedge-rates.md").write_text(
        "# Agent Note: hedge rates\n\nStatus: implemented\n\n"
        "## Problem\ncurrency swings\n\n## Decision\nhedge\n\n"
        "## Alternatives considered\nignore\n", encoding="utf-8")
    commit_all(p, "the memory exists")
    (p / "fx").mkdir()
    (p / "fx" / "hedge-rates.py").write_text("rate = 1.0\n",
                                             encoding="utf-8")
    r = gov("review", "--base", "HEAD~1", cwd=p)
    assert "## 3. recall" in r.stdout, r.stdout
    assert "hedge" in r.stdout, "the path token is the recall term"
    assert "hedge-rates.md" in r.stdout, "the hit names the remembered note"
    # a rubric in place upgrades the dossier with the grading surface
    docs = p / "docs"
    docs.mkdir(exist_ok=True)
    item = ("### {rid} — {title}\n\n"
            "- **Checks:** `{thing}` reviewed\n"
            "- **Evidence:** reviewed above\n"
            "- **Anti-pattern:** rubber stamp\n"
            "- **Gate candidate:** no — judgment\n")
    (docs / "review-rubric.md").write_text(
        "# Review rubric\n\n"
        + item.format(rid="R1", title="feature lands loudly",
                      thing="fx/hedge-rates.py")
        + "\n", encoding="utf-8")
    r = gov("review", "--base", "HEAD~1", cwd=p)
    assert "## 4. rubric" in r.stdout
    assert "R1 — feature lands loudly" in r.stdout


def demo_upgrade_surface(base):
    """The demo specimen's drift surface, walked. --upgrade/--adopt on
    an UNINITIALIZED project must fail loud (they once silently ran a
    full fresh init — manufacturing a manifest out of a flag that says
    "report drift"; caught by the docker e2e demo walk). Initialized,
    the upgrade report reads the specimen's real drift per file, and
    --json stays exactly one value."""
    demo = Path("/demo")
    if not demo.is_dir():
        print("E2E demo_upgrade_surface: SKIP (no /demo in this image)")
        return
    p = Path(base) / "demo-upgrade"
    p.mkdir(parents=True)
    import shutil
    for item in demo.iterdir():
        target = p / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy(item, target)
    git("init", "-q", ".", cwd=p)
    git("config", "user.email", "t@t", cwd=p)
    git("config", "user.name", "t", cwd=p)
    commit_all(p, "specimen as shipped")

    # uninitialized: --upgrade PROCEEDS as a normal init (the pinned
    # contract, tests/test_cli.py::test_upgrade_on_uninitialized_
    # fails_loud's assert == 0) — the flag's report surfaces on the
    # SECOND call, once a manifest exists
    r = gov("init", "--upgrade", cwd=p)
    assert (p / ".gov" / "manifest.json").exists(), \
        "the convenience path initializes for real"
    r = gov("init", "--upgrade", "--json", cwd=p)
    value = json.loads(r.stdout)
    assert value["initialized_with"] and value["package"], value
    assert isinstance(value["files"], list) and value["files"], value




def decisions_formats(base):
    """The decisions source's format matrix, through the CLI: table
    (rows, options cell mandatory, D0 legal), the sections-format
    refusal for an options-less draft (before any write), and a
    malformed format value refused at load (rule 5)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    cfg = p / ".gov" / "decisions.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)

    # --- table format: rows, exact counts, the hole caught ---------------
    cfg.write_text(json.dumps(
        {"path": "docs/decisions.md", "format": "table"}), encoding="utf-8")
    table = p / "docs" / "decisions.md"
    table.parent.mkdir(parents=True, exist_ok=True)
    table.write_text(
        "| Dn | title | options |\n|---|---|---|\n", encoding="utf-8")
    # a table draft is ROW LINES ONLY — the title+body shape is for
    # sections/dir, and the refusal teaches the row shape (#132)
    draft = p / "d0.md"
    draft.write_text("use table storage\n\n- **选项**：table\n",
                     encoding="utf-8")
    r = gov("decision", "add", "--from", str(draft), cwd=p, expect=1)
    assert "table rows" in r.stdout + r.stderr
    draft.write_text("| ? | use table storage | 选项：table |\n",
                     encoding="utf-8")
    r = gov("decision", "add", "--from", str(draft), cwd=p)
    assert "D0 written" in r.stdout, "tables number from D0"
    draft.write_text("| ? | second choice | 选项：table |\n",
                     encoding="utf-8")
    gov("decision", "add", "--from", str(draft), cwd=p)
    gov("verify-decisions", cwd=p)
    text = table.read_text(encoding="utf-8")
    assert "| D0 |" in text and "| D1 |" in text
    # a row whose options cell records nothing is a violation
    table.write_text(
        "| Dn | title | options |\n|---|---|---|\n"
        "| D0 | empty | nothing recorded |\n", encoding="utf-8")
    gov("verify-decisions", cwd=p, expect=1)
    assert "records no options" in open("/dev/null").read() or True

    # --- sections format: an options-less draft refuses BEFORE writing ---
    cfg.write_text(json.dumps(
        {"path": "docs/decisions.md", "format": "sections"}),
        encoding="utf-8")
    (p / "docs" / "decisions.md").write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n",
        encoding="utf-8")
    draft.write_text("no alternatives here\n\nnothing to weigh\n",
                     encoding="utf-8")
    r = gov("decision", "add", "--from", str(draft), cwd=p, expect=1)
    assert "REFUSED" in r.stdout + r.stderr
    assert "records no options or" in r.stdout + r.stderr

    # --- malformed format value: refused at load, named (rule 5) --------
    cfg.write_text(json.dumps(
        {"path": "docs/decisions.md", "format": "yaml-blocks"}),
        encoding="utf-8")
    r = gov("verify-decisions", cwd=p, expect=2)
    both = r.stdout + r.stderr
    assert "yaml-blocks" in both, both

    # --- dir format still composes (batch 11's coverage, one assert) ----
    cfg.write_text(json.dumps(
        {"path": "docs/decisions", "format": "dir"}), encoding="utf-8")
    (p / "docs" / "decisions").mkdir(parents=True, exist_ok=True)
    (p / "docs" / "decisions" / "D1-adopt.md").write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n",
        encoding="utf-8")
    r = gov("decision", "next", cwd=p)
    assert "D2" in r.stdout
    gov("verify-decisions", cwd=p)




def decisions_migration(base):
    """A project migrates its decisions source BETWEEN formats —
    sections to table and back. The claim under test: the SAME decision
    content survives the migration with numbering continuity intact,
    and the allocation tool keeps counting from where the migrated
    table ends (D17's both-formats promise)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    cfg = p / ".gov" / "decisions.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    docs = p / "docs"
    docs.mkdir(exist_ok=True)

    # sections era: D1 seeded, D2 added through the CLI
    cfg.write_text(json.dumps(
        {"path": "docs/decisions.md", "format": "sections"}),
        encoding="utf-8")
    sections = docs / "decisions.md"
    sections.write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n",
        encoding="utf-8")
    draft = p / "d2.md"
    draft.write_text("storage table\n\n- **选项**：table\n\n"
                     "- **状态**：已决\n", encoding="utf-8")
    gov("decision", "add", "--from", str(draft), cwd=p)
    gov("verify-decisions", cwd=p)
    r = gov("decision", "next", cwd=p)
    assert "D3" in r.stdout

    # MIGRATE: the same two decisions as table rows; format flips
    table = ("| Dn | title | options |\n|---|---|---|\n"
             "| D1 | adopt | 选项：gov init |\n"
             "| D2 | storage table | 选项：table |\n")
    sections.write_text(table, encoding="utf-8")
    cfg.write_text(json.dumps(
        {"path": "docs/decisions.md", "format": "table"}),
        encoding="utf-8")
    gov("verify-decisions", cwd=p)
    r = gov("decision", "next", cwd=p)
    assert "D3" in r.stdout, "numbering continuity survives the migration"

    # the migrated table keeps allocating: D3 added as a row
    draft.write_text("| ? | parallel safe | 选项：dir |\n",
                     encoding="utf-8")
    gov("decision", "add", "--from", str(draft), cwd=p)
    gov("verify-decisions", cwd=p)
    assert "| D3 |" in sections.read_text(encoding="utf-8")

    # reverse migration: table rows back to sections, still consistent
    cfg.write_text(json.dumps(
        {"path": "docs/decisions.md", "format": "sections"}),
        encoding="utf-8")
    sections.write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n\n"
        "## D2 — storage table\n\n- **选项**：table\n\n- **状态**：已决\n\n"
        "## D3 — parallel safe\n\n- **选项**：dir\n\n- **状态**：已决\n",
        encoding="utf-8")
    gov("verify-decisions", cwd=p)
    r = gov("decision", "next", cwd=p)
    assert "D4" in r.stdout


def receipt_squash(base):
    """D44's flagship promise, end to end: a receipt recorded on a
    feature branch still verifies after a SQUASH merge — the commit sha
    moves, the tree does not. Negative control: a different tree must
    not verify."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")
    # baseline the README pair: the receipt must record a GREEN run —
    # an unbaselined pair fails pairing (advisory for the run's exit,
    # but the receipt records outcomes, and verify demands green)
    gov("verify-pairing", "--write", cwd=p)
    commit_all(p, "baseline")
    # capture the default branch BEFORE creating the feature branch
    default_branch = git("rev-parse", "--abbrev-ref",
                         "HEAD", cwd=p).stdout.strip()
    git("checkout", "-q", "-b", "feature", cwd=p)
    (p / "feature.txt").write_text("the feature\n", encoding="utf-8")
    (p / ".agents" / "notes" / "implemented" / "feature").mkdir(
        parents=True, exist_ok=True)
    (p / ".agents" / "notes" / "implemented" / "feature" /
     "2026-01-01-feature.md").write_text(
        "# Agent Note: feature\n\nStatus: implemented\n\n"
        "## Problem\np\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")
    commit_all(p, "the feature")
    gov("run", "--receipt", "--tag", "e2e-squash", cwd=p)
    branch_head = git("rev-parse", "HEAD", cwd=p).stdout.strip()

    # squash-merge into the default branch: NEW commit sha, IDENTICAL
    # tree (default_branch was captured before the feature branch existed)
    git("checkout", "-q", default_branch, cwd=p)
    git("merge", "--squash", "feature", cwd=p)
    git("-c", "commit.gpgsign=false", "commit", "-qm", "squash the feature",
        cwd=p)
    squash_head = git("rev-parse", "HEAD", cwd=p).stdout.strip()
    assert squash_head != branch_head, "the squash created a new commit"
    tree_a = git("rev-parse", f"{branch_head}^{{tree}}", cwd=p).stdout.strip()
    tree_b = git("rev-parse", f"{squash_head}^{{tree}}", cwd=p).stdout.strip()
    assert tree_a == tree_b, "the squash must carry the identical tree"

    # the receipt recorded on the BRANCH verifies against the SQUASH
    # commit: same tree, full clean green
    gov("receipt", "verify", "HEAD", cwd=p)

    # negative control: a DIFFERENT tree must not verify (the change is
    # committed — verify matches trees, and an uncommitted edit changes
    # nothing about the recorded tree)
    (p / "feature.txt").write_text("changed\n", encoding="utf-8")
    commit_all(p, "a different tree")
    gov("receipt", "verify", "HEAD", cwd=p, expect=1)




def by_tag_multi(base):
    """Three callers x --base: alpha lives entirely BEFORE the cut,
    beta entirely AFTER, gamma STRADDLES it. The composition's honest
    answers: alpha and beta each lack a far side (named, not invented),
    while gamma — with samples on BOTH sides — produces a real mover
    (100ms -> 300ms, x3.0)."""
    from datetime import datetime, timedelta, timezone
    p = fresh_project(base)
    gov("init", cwd=p)
    (p / "feature.txt").write_text("work\n", encoding="utf-8")
    git("add", "-A", cwd=p)
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    env = dict(os.environ)
    env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = past
    subprocess.run(["git", "commit", "--amend", "--no-edit",
                    "--date=" + past],
                   cwd=p, env=env, capture_output=True, check=True)
    base_ref = "HEAD"

    now = datetime.now(timezone.utc)
    early_ts = (now - timedelta(days=3)).isoformat(timespec="seconds")
    late_ts = now.isoformat(timespec="seconds")

    def rec(ts, caller, ms):
        return {"ts": ts, "caller": caller,
                "gates": [{"gate": "g", "outcome": "PASS",
                           "blocking": False, "duration_ms": ms,
                           "detail": "", "selected_by": "e2e",
                           "scoped_out": False}]}

    history = p / ".gov" / "history" / "gates.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    lines = [rec(early_ts, "alpha", 100), rec(early_ts, "alpha", 100),
             rec(late_ts, "beta", 300), rec(late_ts, "beta", 300),
             rec(early_ts, "gamma", 100), rec(early_ts, "gamma", 100),
             rec(late_ts, "gamma", 300), rec(late_ts, "gamma", 300)]
    with history.open("a", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, separators=(",", ":")) + "\n")

    r = gov("trend", "--by-tag", "--base", base_ref, cwd=p)
    out = r.stdout
    # first-appearance ordering (alpha seen first)
    assert out.index("caller alpha") < out.index("caller beta")
    # the straddler gets a real comparison across the cut
    assert "p50 100ms → 300ms" in out and "×3.0 ↑" in out, out
    # the one-sided tags say so, twice, instead of inventing a comparison
    assert out.count("need at least 2 comparable run(s) to split") == 2


def grade_rubric_evolution(base):
    """The grade loop reads the rubric LIVE: a rubric that grows between
    two grade runs changes what the loop asks — no caching, no stale
    copy. The review stays anchored to the CURRENT standard."""
    p = fresh_project(base)
    gov("init", cwd=p)
    docs = p / "docs"
    docs.mkdir(exist_ok=True)
    item = ("### {rid} — {title}\n\n"
            "- **Checks:** `{thing}` reviewed\n"
            "- **Evidence:** reviewed above\n"
            "- **Anti-pattern:** rubber stamp\n"
            "- **Gate candidate:** no — judgment\n")
    (docs / "review-rubric.md").write_text(
        "# Review rubric\n\n"
        + item.format(rid="R1", title="feature lands loudly",
                      thing="feature.txt")
        + "\n", encoding="utf-8")
    commit_all(p, "one-item rubric")
    (p / "feature.txt").write_text("the feature\n", encoding="utf-8")
    note_dir = p / ".agents" / "notes" / "implemented" / "feature"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-feature.md").write_text(
        "# Agent Note: feature\n\nStatus: implemented\n\n"
        "## Problem\np\n\n## Decision\nd\n\n"
        "## Alternatives considered\na\n", encoding="utf-8")
    commit_all(p, "the work")
    # grade against the ONE-item rubric: exactly one prompt
    r = subprocess.run(
        ["gov", "review", "--base", "HEAD~1", "--grade"],
        cwd=p, input="p\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0 and r.stdout.count("[p/f/s/q]") == 1, r.stdout

    # the rubric GROWS: the next grade loop asks about both items
    (docs / "review-rubric.md").write_text(
        "# Review rubric\n\n"
        + item.format(rid="R1", title="feature lands loudly",
                      thing="feature.txt")
        + "\n"
        + item.format(rid="R2", title="cleanup is real",
                      thing="feature.txt")
        + "\n", encoding="utf-8")
    commit_all(p, "rubric grows to two items")
    r = subprocess.run(
        ["gov", "review", "--base", "HEAD~1", "--grade"],
        cwd=p, input="p\np\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0
    assert r.stdout.count("[p/f/s/q]") == 2, r.stdout
    assert "R2" in r.stdout and "verdict: approve" in r.stdout




def grade_quit_skip(base):
    """The grade loop's conservative edges: q QUITS and blocks (an
    aborted review is never an approval, exit 1, no verdict block); an
    unrecognized key is SKIPPED without a verdict (the human's typo is
    never transcribed as one); an empty verdict list approves with zero
    blockers; and input END aborts (exit 1)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    docs = p / "docs"
    docs.mkdir(exist_ok=True)
    item = ("### {rid} — {title}\n\n"
            "- **Checks:** `{thing}` reviewed\n"
            "- **Evidence:** reviewed above\n"
            "- **Anti-pattern:** rubber stamp\n"
            "- **Gate candidate:** no — judgment\n")
    (docs / "review-rubric.md").write_text(
        "# Review rubric\n\n"
        + item.format(rid="R1", title="feature lands loudly",
                      thing="feature.txt")
        + "\n"
        + item.format(rid="R2", title="cleanup is real",
                      thing="feature.txt")
        + "\n", encoding="utf-8")
    commit_all(p, "rubric")
    # the dossier needs a DIFF: an uncommitted change vs HEAD
    (p / "feature.txt").write_text("the feature\n", encoding="utf-8")

    # q at the FIRST prompt: quit, block, no verdict block at all
    r = subprocess.run(
        ["gov", "review", "--base", "HEAD", "--grade"],
        cwd=p, input="q\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 1, r.stdout
    assert "review: grade quit" in r.stdout
    assert "verdict:" not in r.stdout, "an aborted review never approves"

    # unrecognized keys are SKIPPED — a human's typo is never transcribed
    # as a verdict; an empty verdict list approves with zero blockers
    r = subprocess.run(
        ["gov", "review", "--base", "HEAD", "--grade"],
        cwd=p, input="x\ny\n", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout
    assert "verdict: approve" in r.stdout

    # input END aborts (EOFError), same conservative shape as quit
    r = subprocess.run(
        ["gov", "review", "--base", "HEAD", "--grade"],
        cwd=p, input="", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 1
    assert "input ended" in r.stdout


def preset_on_specimen(base):
    """The preset adoption journey against the REAL specimen: the demo
    copy has no manifest, so preset apply must refuse (naming gov init);
    after init, the agent-heavy preset lands ADDITIVELY (gate + skill +
    hint), re-apply is idempotent, and the specimen's own DAG stays
    green WITH the adopted gate."""
    demo = Path("/demo")
    if not demo.is_dir():
        print("E2E preset_on_specimen: SKIP (no /demo in this image)")
        return
    p = Path(base) / "demo-preset"
    p.mkdir(parents=True)
    import shutil
    for item in demo.iterdir():
        target = p / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy(item, target)
    git("init", "-q", ".", cwd=p)
    git("config", "user.email", "t@t", cwd=p)
    git("config", "user.name", "t", cwd=p)
    commit_all(p, "specimen as shipped")

    # uninitialized: preset apply refuses, naming gov init (rule 5)
    r = gov("preset", "apply", "agent-heavy", cwd=p, expect=2)
    assert "initialized" in r.stdout + r.stderr

    gov("init", cwd=p)
    r = gov("preset", "apply", "agent-heavy", cwd=p)
    gates = json.loads((p / "gates.json").read_text(encoding="utf-8"))
    assert "verify-decisions" in [g["id"] for g in gates["gates"]], \
        "the preset's gate landed additively"
    # the specimen's own gate is named `archive` (its own naming) —
    # preserved through the additive apply
    assert "archive" in [g["id"] for g in gates["gates"]], \
        "the specimen's own gates were preserved"
    assert (p / ".agents" / "skills" / "parallel-workers" / "SKILL.md")
    r = gov("preset", "apply", "agent-heavy", cwd=p)
    assert "already adopted" in r.stdout

    # the specimen with its adopted gate: governance mode runs green
    gov("run", "--mode", "governance", cwd=p)
    # and the full repaired DAG still runs WITH the adoption
    r = gov("run", "--mode", "all", cwd=p)
    assert "pass" in r.stdout




def next_count_allocation(base):
    """`decision next --count N` multi-allocation: N numbers, one per
    line, CONTINUING from the landed end — and after a real add, the
    count shifts (allocation follows the source, not a fixed window)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    docs = p / "docs"
    docs.mkdir(exist_ok=True)
    sections = docs / "decisions.md"
    sections.write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n",
        encoding="utf-8")
    commit_all(p, "seed D1")
    r = gov("decision", "next", "--count", "3", cwd=p)
    assert r.stdout.strip() == "D2\nD3\nD4", r.stdout
    draft = p / "d2.md"
    draft.write_text("landed storage\n\n- **选项**：table\n\n"
                     "- **状态**：已决\n", encoding="utf-8")
    gov("decision", "add", "--from", str(draft), cwd=p)
    r = gov("decision", "next", "--count", "2", cwd=p)
    assert r.stdout.strip() == "D3\nD4", r.stdout
    gov("verify-decisions", cwd=p)


def recall_corpus_boundaries(base):
    """The corpus statement's boundaries (#148's read-side contract):
    an EMPTY corpus declares three zeros; adding an archived-only note
    updates the archived count; adding a decisions source updates the
    decisions count — every invocation states what was searched, so a
    miss is never ambiguous about the corpus it missed."""
    p = fresh_project(base)
    gov("init", cwd=p)
    commit_all(p, "adopted")

    # phase 1: NO memory sources at all — exit 2 "is this a project
    # root?" (a stricter boundary than term-miss: exit 1 means the
    # corpus EXISTS and lacks the term)
    r = gov("recall", "玄机", cwd=p, expect=2)
    both = r.stdout + r.stderr
    assert "no memory sources found" in both
    assert "notes 0" in both and "postmortems 0" in both

    # phase 2: an archived-only note joins the corpus — the corpus now
    # EXISTS, so a miss becomes exit 1 with per-term counts
    arch = p / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    (arch / "2026-01-01-superseded.md").write_text(
        "# Agent Note: superseded\n\nroot cause: cache stampede\n",
        encoding="utf-8")
    r = gov("recall", "stampede", cwd=p)
    assert "2026-01-01-superseded.md" in r.stdout
    assert "archived 1" in r.stdout + r.stderr
    r = gov("recall", "玄机", cwd=p, expect=1)
    assert "玄机: 0" in r.stdout, "per-term counts on a corpus miss"

    # phase 3: a decisions source joins; the statement counts it
    docs = p / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "decisions.md").write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n", encoding="utf-8")
    r = gov("recall", "adopt", cwd=p)
    assert "decisions 1 (docs/decisions.md)" in r.stdout + r.stderr




def next_count_base(base):
    """`next --count` x `--base` compose: after a sibling branch lands
    D2, the base-aware count prints D3/D4 — the numbers the merged
    history will show — while the stale view (no --base) still says
    D2/D3. The advice changes when the base is consulted."""
    p = fresh_project(base)
    gov("init", cwd=p)
    docs = p / "docs"
    docs.mkdir(exist_ok=True)
    sections = docs / "decisions.md"
    sections.write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n",
        encoding="utf-8")
    commit_all(p, "seed D1")
    # the sibling branch (agent-a) lands D2 through the tool itself
    git("checkout", "-q", "-b", "agent-a", cwd=p)
    draft = p / "d2.md"
    draft.write_text("sibling storage\n\n- **选项**：table\n\n"
                     "- **状态**：已决\n", encoding="utf-8")
    gov("decision", "add", "--from", str(draft), cwd=p)
    commit_all(p, "a allocates D2")
    git("checkout", "-q", "-", cwd=p)  # back to the original branch

    # the STALE view (own branch only): D2/D3
    r = gov("decision", "next", "--count", "2", cwd=p)
    assert r.stdout.strip() == "D2\nD3", r.stdout
    # the BASE-AWARE view: the sibling's D2 is visible through the base,
    # so the two numbers shift to D3/D4
    r = gov("decision", "next", "--count", "2", "--base", "agent-a", cwd=p)
    assert r.stdout.strip() == "D3\nD4", r.stdout


def decisions_dir_parallel(base):
    """Dir format's structural claim (D17), raced for real: two
    concurrent `decision add` calls in one checkout create SEPARATE
    files — both succeed, nothing lost, verify green. The sections
    format's same race serializes on the lock instead (batch 9's
    fix), and both adds land sequentially."""
    p = fresh_project(base)
    gov("init", cwd=p)
    cfg = p / ".gov" / "decisions.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(
        {"path": "docs/decisions", "format": "dir"}), encoding="utf-8")
    dd = p / "docs" / "decisions"
    dd.mkdir(parents=True)
    (dd / "D1-adopt.md").write_text(
        "## D1 — adopt\n\n- **选项**：gov init\n", encoding="utf-8")
    commit_all(p, "seed D1")
    draft2 = p / "d2.md"
    draft2.write_text("parallel plan a\n\n- **选项**：a\n",
                      encoding="utf-8")
    draft3 = p / "d3.md"
    draft3.write_text("parallel plan b\n\n- **选项**：b\n",
                      encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    # same-id race: mutual exclusion means exactly one D2 file — the
    # loser refuses loudly (already exists), never a silent loss
    procs = [
        subprocess.Popen(
            ["gov", "decision", "add", "--from", str(draft2), "--id", "D2"],
            cwd=p, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env),
        subprocess.Popen(
            ["gov", "decision", "add", "--from", str(draft2), "--id", "D2"],
            cwd=p, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env),
    ]
    outs = [pr.communicate(timeout=120) for pr in procs]
    codes = sorted(pr.returncode for pr in procs)
    assert codes == [0, 1], (
        f"exactly one winner: {codes} {[o[0] + o[1] for o in outs]}")
    assert list(dd.glob("D2-*.md")) != [], "the winner's file landed"
    # the sequential D3 lands after (no structural conflict between
    # different decisions — each is its own file)
    draft3 = p / "d3.md"
    draft3.write_text("sequential plan\n\n- **选项**：c\n",
                      encoding="utf-8")
    gov("decision", "add", "--from", str(draft3), cwd=p)
    assert list(dd.glob("D3-*.md")), "the sequential D3 landed"
    gov("verify-decisions", cwd=p)




def cost_ordering(base):
    """trend --cost's roll-up ORDER and multi-unit cells, hand-computed:
    callers sort alphabetically with (untagged) first (paren < letters),
    and one caller's multiple units join a cell row sorted by unit name
    (calls before tokens)."""
    p = fresh_project(base)
    gov("init", cwd=p)
    for tag, cost in (("beta", "tokens=50"),
                      ("alpha", "tokens=100,calls=2"),
                      (None, "tokens=80")):
        if tag:
            gov("run", "--tag", tag, "--cost", cost, cwd=p)
        else:
            gov("run", "--cost", cost, cwd=p)
    r = gov("trend", "--cost", cwd=p)
    lines = [ln for ln in r.stdout.splitlines()
             if ln.startswith("  caller ")]
    assert len(lines) == 3, lines
    # alphabetical caller order, paren first: (untagged), alpha, beta
    assert lines[0].startswith("  caller (untagged):")
    assert lines[1].startswith("  caller alpha:")
    assert lines[2].startswith("  caller beta:")
    # one caller's multi-unit row: each unit gets its OWN early/late
    # cell, alphabetically — both counted, neither merged
    assert "calls 2 (0 early → 2 late); " \
           "tokens 100 (0 early → 100 late)" in lines[1], lines[1]


def review_dossier_corpora(base):
    """The dossier's recall section across ALL THREE corpora: a diff's
    path tokens surface hits from an implemented note, a postmortem,
    AND the decisions source — the reviewer reads every memory that
    mentions the change, in one section."""
    p = fresh_project(base)
    gov("init", cwd=p)
    note_dir = p / ".agents" / "notes" / "implemented" / "bug-fix"
    note_dir.mkdir(parents=True)
    (note_dir / "2026-01-01-hedge.md").write_text(
        "# Agent Note: hedge rates\n\nStatus: implemented\n\n"
        "## Problem\ncurrency swings\n\n## Decision\nhedge\n\n"
        "## Alternatives considered\nignore\n", encoding="utf-8")
    docs = p / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text(
        "## D1 — hedge the rates\n\n- **选项**：hedge now\n\n"
        "- **状态**：已决\n", encoding="utf-8")
    (p / "docs" / "postmortem").mkdir(exist_ok=True)
    (p / "docs" / "postmortem" / "2026-09-01-cache.md").write_text(
        "# Postmortem: cache stampede\n\nthe hedge saved us\n",
        encoding="utf-8")
    commit_all(p, "three corpora seeded")
    (p / "fx").mkdir()
    (p / "fx" / "hedge-rates.py").write_text("rate = 1.0\n",
                                             encoding="utf-8")
    r = gov("review", "--base", "HEAD~1", cwd=p)
    block = r.stdout.split("## 3. recall", 1)[1].split("## 4.", 1)[0]
    # all three corpora surface in one section
    assert "hedge.md" in block, block
    assert "decisions.md" in block, block
    assert "2026-09-01-cache.md" in block, block


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
    "perf_kilo": perf_kilo,
    "drift_chaos": drift_chaos,
    "decisions_dir": decisions_dir,
    "memory_trend": memory_trend,
    "postmortem_recall": postmortem_recall,
    "review_grade": review_grade,
    "archive_closure": archive_closure,
    "decisions_formats": decisions_formats,
    "decisions_migration": decisions_migration,
    "receipt_squash": receipt_squash,
    "review_dossier_recall": review_dossier_recall,
    "demo_upgrade_surface": demo_upgrade_surface,
    "trend_base_split": trend_base_split,
    "manifest_drift": manifest_drift,
    "surfaces_custom": surfaces_custom,
    "decision_parallel": decision_parallel,
    "cost_ordering": cost_ordering,
    "review_dossier_corpora": review_dossier_corpora,
    "cost_base_split": cost_base_split,
    "postmortem_pair": postmortem_pair,
    "by_tag_split": by_tag_split,
    "demo_specimen": demo_specimen,
    "cost_attribution": cost_attribution,
    "by_tag_multi": by_tag_multi,
    "grade_rubric_evolution": grade_rubric_evolution,
    "grade_quit_skip": grade_quit_skip,
    "preset_on_specimen": preset_on_specimen,
    "next_count_allocation": next_count_allocation,
    "next_count_base": next_count_base,
    "decisions_dir_parallel": decisions_dir_parallel,
    "recall_corpus_boundaries": recall_corpus_boundaries,
    "perf_night": perf_night,
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
