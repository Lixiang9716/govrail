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
