#!/usr/bin/env python3
"""Preflight the union of parallel branches before landing (``gov run --merge``).

Parallel agent branches each pass every gate on their own tree, but the
UNION is never tested until the merge happens — text conflicts git catches,
semantic collisions (each branch green, the merge red) nobody catches.
This module rehearses the merge before it matters: a detached scratch
worktree is created from the integration baseline (``--base``, default
``origin/master``), each named branch is merged in command-line order with
``git merge --no-ff --no-edit``, and after every merge the gate DAG runs on
that step's union tree — the minimal sufficient set per D15, selected by
the diff the step itself introduced (the previous step's tree sha, recorded
after its gates ran, is the diff baseline; the first step diffs against the
baseline commit). The last step's tree IS the full union, so every gate
examines merged content; with ``--receipt`` the last step additionally
records D44 evidence: it upgrades to the full matrix (every enabled gate —
a scoped receipt would never verify as full evidence) and the receipt binds
to the union tree sha, so a landing that reproduces this content (a squash
merge moves the commit sha, not the tree) verifies via
``gov receipt verify``.

Outcomes (D2 vocabulary, no new codes): exit 0 — every step green; exit 1 —
a text conflict or a red step, named with the branch, the already-merged
set, and (for a red step) the failed gates' key output lines — the scratch
worktree is KEPT and its path printed for inspection; exit 2 — invalid
configuration or ref (including a hostile environment), named before
anything runs.

Host safety is D33's three walls, applied to a command that MUTATES
repository state (it creates worktrees and makes merge commits):

1. the caller's environment is checked BEFORE anything runs: any
   repository-resolving variable (GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE,
   GIT_OBJECT_DIRECTORY, GIT_ALTERNATE_OBJECT_DIRECTORIES,
   GIT_QUARANTINE_PATH) aborts loudly (exit 2, variables named) instead of
   silently re-pointing the preflight at another domain; every git command
   and gate subprocess runs with all GIT_* stripped;
2. every git operation is pinned with ``-C`` to the caller's repository
   root (resolved once from cwd) or to the scratch worktree itself, and the
   scratch must resolve ``--show-toplevel`` to itself before anything is
   merged into it — an escape aborts loud, never configures;
3. the acceptance tests pin the guarantee: before/after a preflight the
   host worktree is byte-identical (status clean, HEAD and refs unchanged).

The preflight itself creates no lock files and unlinks none: its work is
git commands and read-only gate executions (D40's ``.decision.lock`` unlink
race is a known defect this feature deliberately does not import). History
and receipt ledgers keep their D32 anchoring: a scratch run records into the
main checkout's ``.gov/history`` — the runs really happened, so they land in
the ledger, gitignored by convention.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Variables that re-point git at ANOTHER repository (or corrupt this one's
# view of it). A preflight resolves branch names and creates worktrees in
# the repository it is invoked on; with one of these set, "the repository"
# is ambiguous — so the ambiguity is refused, not guessed (rule 5, D33
# wall 1 upgraded from "scrub and announce" to "refuse", because this
# command mutates state rather than observing it).
HOSTILE_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
)

DEFAULT_BASE = "origin/master"
_GATES_SCRIPT = Path(__file__).resolve().parent / "gates.py"


def _scrubbed_env(extra: dict | None = None) -> dict:
    """Environment for every git call and gate subprocess (D33 wall 1).

    All GIT_* variables are stripped so repository resolution happens by
    cwd/``-C`` alone, exactly like the tools do when run by hand (#20/D32).
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    if extra:
        env.update(extra)
    return env


def _git(root: Path, *argv: str) -> subprocess.CompletedProcess:
    """One git command, pinned to ``root`` with -C and the scrubbed env."""
    return subprocess.run(
        ["git", "-C", str(root), *argv],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",  # git speaks UTF-8, not the locale codec (#168)
        env=_scrubbed_env(),
    )


def _rev_exists(root: Path, ref: str) -> bool:
    return _git(root, "rev-parse", "--verify", "--quiet",
                ref + "^{commit}").returncode == 0


def _step_argv(scratch: Path, config: str, diff_base: str, last: bool,
               receipt: bool, tag: str | None, cost: str | None,
               no_record: bool) -> list[str]:
    """The gates invocation for one step, run with cwd = the scratch worktree.

    ``--base <diff_base>`` is the previous step's tree sha (or the baseline
    commit for the first step), so the D15 selection sees exactly the diff
    this step introduced. The step runs with ``--json``: stdout carries
    exactly one JSON array for the orchestrator to summarize; the human
    report streams on stderr, live, as gates run (D26's contract, reused —
    nothing is buffered away from the operator).
    """
    argv = [sys.executable, str(_GATES_SCRIPT), "--config", config,
            "--json"]
    if last and receipt:
        # D44: a receipt is only evidence when the selection covered every
        # enabled gate — so the union's step upgrades to the full matrix
        # (no --base: the diff scope is deliberately the whole tree).
        argv += ["--every-gate", "--receipt"]
    else:
        # ``--base <diff_base>`` is the previous step's tree sha (or the
        # baseline commit for the first step), so the D15 selection sees
        # exactly the diff this step introduced.
        argv += ["--base", diff_base]
    if tag:
        argv += ["--tag", tag]
    if cost:
        argv += ["--cost", cost]
    if no_record:
        argv += ["--no-record"]
    return argv


def _summarize(records: list[dict]) -> tuple[list[str], int, int, list[str]]:
    """(failed gate ids, executed, passes, out-of-scope ids) from a step."""
    failed = [r["gate"] for r in records
              if r.get("blocking") or r.get("outcome")
              in ("FAIL", "TIMEOUT", "MISSING")]
    # Only records that actually executed count as "ran": SCOPED_OUT,
    # NOT_SELECTED, DISABLED, and NOT_RUN are statements about the gate
    # set, not executions.
    executed = [r for r in records if r.get("outcome")
                in ("PASS", "FAIL", "TIMEOUT", "MISSING", "SKIP")]
    passes = sum(1 for r in executed if r.get("outcome") == "PASS")
    scoped = [r["gate"] for r in records if r.get("scoped_out")]
    return failed, len(executed), passes, scoped


def _remove_worktree(root: Path, scratch: Path) -> None:
    _git(root, "worktree", "remove", "--force", str(scratch))
    shutil.rmtree(scratch, ignore_errors=True)
    _git(root, "worktree", "prune")


def run_merge(branches: list[str], base: str | None = None,
              config: str = "gates.json", receipt: bool = False,
              tag: str | None = None, cost: str | None = None,
              no_record: bool = False) -> int:
    if not branches or any(not b.strip() for b in branches):
        print("gov run --merge: empty branch name", file=sys.stderr, flush=True)
        return 2

    # Wall 1, first: refuse a hostile domain BEFORE anything runs. A silent
    # scrub would quietly re-point the preflight at the cwd repository while
    # the caller's shell meant another one — for a state-mutating command
    # that switch is a decision, and decisions are not made silently.
    leaked = [v for v in HOSTILE_VARS if os.environ.get(v)]
    if leaked:
        print(
            "gov run --merge: REFUSING to run — the environment carries "
            f"repository-resolving variable(s): {', '.join(leaked)}. A merge "
            "preflight resolves branches and creates worktrees in the "
            "repository it is invoked on; unset the variable(s) and re-run "
            "there (D33 wall 1: fail loud, never switch domain silently).",
            file=sys.stderr, flush=True)
        return 2
    env = _scrubbed_env()

    # The caller's repository, resolved by git from cwd (D21) — then pinned:
    # every later git call targets this root or the scratch with -C.
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    if proc.returncode != 0:
        print(f"gov run --merge: not a git repository: {proc.stderr.strip()}",
              file=sys.stderr, flush=True)
        return 2
    root = Path(proc.stdout.strip()).resolve()

    # Rule 5: an explicit --base that resolves is intent; a missing DEFAULT
    # is a named demand for one, never a guess.
    default_base = not base
    base = base or DEFAULT_BASE
    if not _rev_exists(root, base):
        if default_base:
            print(f"gov run --merge: default base '{DEFAULT_BASE}' does not "
                  "exist in this repository — pass an explicit --base <ref> "
                  "(the integration target baseline, e.g. origin/master)",
                  file=sys.stderr, flush=True)
        else:
            print(f"gov run --merge: base '{base}' does not exist in this "
                  "repository", file=sys.stderr, flush=True)
        return 2
    base_sha = _git(root, "rev-parse", "--verify",
                    base + "^{commit}").stdout.strip()

    for br in branches:
        if not _rev_exists(root, br):
            print(f"gov run --merge: branch '{br}' does not exist in this "
                  "repository", file=sys.stderr, flush=True)
            return 2

    if cost:
        # Validate before any mutation (rule 5): a malformed cost string
        # must not leave a worktree behind to be cleaned up.
        try:
            from gov.gates import parse_cost
        except ImportError:  # direct-script execution (self-test scratch)
            from gates import parse_cost
        try:
            parse_cost(cost)
        except ValueError as e:
            print(f"gov run --merge: --cost: {e}", file=sys.stderr, flush=True)
            return 2

    tmp = Path(tempfile.mkdtemp(prefix="gov-merge-"))
    print(f"merge: preflighting the union of {len(branches)} branch(es) onto "
          f"base '{base}' ({base_sha[:12]}) — scratch worktree {tmp}", flush=True)
    added = _git(root, "worktree", "add", "--detach", str(tmp), base_sha)
    if added.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"gov run --merge: could not create the scratch worktree: "
              f"{(added.stderr or added.stdout).strip()}", file=sys.stderr, flush=True)
        return 2

    # Wall 2 (the toplevel guard, #24/D33): before anything is merged into
    # the scratch, it must resolve to ITSELF. If git resolves anywhere else,
    # abort loud rather than merge into someone else's checkout.
    top = _git(tmp, "rev-parse", "--show-toplevel")
    resolved = Path(top.stdout.strip()).resolve() if top.returncode == 0 else None
    if resolved != tmp.resolve():
        _remove_worktree(root, tmp)
        print(f"gov run --merge: scratch worktree escaped — git in {tmp} "
              f"resolves to {resolved or '<no repository>'}; refusing to "
              "merge into it (D33 wall 2)", file=sys.stderr, flush=True)
        return 2

    merged: list[str] = []
    steps: list[tuple[str, str, str]] = []  # (branch, tree sha, summary tail)
    prev = base_sha
    for k, br in enumerate(branches, start=1):
        names = ", ".join(merged) if merged else "<base>"
        print(f"merge: step {k}/{len(branches)}: merging '{br}' "
              f"(already-merged set: {names})", flush=True)
        m = _git(tmp, "merge", "--no-ff", "--no-edit", br)
        if m.returncode != 0:
            conflicted = [
                f for f in _git(tmp, "diff", "--name-only",
                                "--diff-filter=U").stdout.splitlines() if f
            ]
            if (m.stdout or m.stderr).strip():
                print((m.stdout + m.stderr).strip(), flush=True)
            if conflicted:
                print(f"merge: branch {k} ({br}) conflicts with "
                      f"already-merged set ({names})", flush=True)
                print("merge: conflicted file(s):", flush=True)
                for f in conflicted:
                    print(f"  {f}", flush=True)
            else:
                print(f"merge: branch {k} ({br}) could not be merged "
                      f"(already-merged set: {names})", flush=True)
            print(f"merge: the union cannot land as ordered — stopping "
                  f"before any further branch", flush=True)
            print(f"merge: scratch worktree kept for inspection: {tmp}", flush=True)
            return 1

        head = _git(tmp, "rev-parse", "HEAD").stdout.strip()
        last = k == len(branches)
        argv = _step_argv(tmp, config, prev, last, receipt, tag, cost,
                          no_record)
        step_env = _scrubbed_env(
            {"GIT_CEILING_DIRECTORIES": str(tmp.parent)})  # wall 3 hardening
        # stderr streams live (the human report must not be buffered away);
        # stdout is the one JSON value the orchestrator summarizes (D26).
        step = subprocess.run(argv, cwd=tmp, env=step_env,
                              stdout=subprocess.PIPE, text=True,
                              encoding="utf-8", errors="replace")
        records: list[dict] = []
        if step.stdout and step.stdout.strip():
            import json
            try:
                records = json.loads(step.stdout)
            except json.JSONDecodeError:
                records = []
        failed, ran, passes, scoped = _summarize(records)
        if step.returncode != 0:
            print(f"merge: branch {k} ({br}) FAILED the gates on the union "
                  f"tree — already-merged set ({names})", flush=True)
            if failed:
                for r in records:
                    if r["gate"] in failed:
                        first = (r.get("detail") or "").strip().splitlines()
                        line = first[0] if first else "(no output)"
                        print(f"merge:   failed gate '{r['gate']}': {line}",
                              flush=True)
            else:
                print("merge:   (the step run exited "
                      f"{step.returncode} before reporting gates — its "
                      "error is printed above)", flush=True)
            print(f"merge: the union of these branches is not landable — "
                  f"fix the collision and re-run", flush=True)
            print(f"merge: scratch worktree kept for inspection: {tmp}",
                  flush=True)
            return 1
        tail = ""
        if last and receipt:
            tail = " (full matrix — receipt recorded for the union tree)"
        print(f"merge: step {k}/{len(branches)}: '{br}' -> tree {head[:12]}; "
              f"gates: {ran} ran, {passes} pass"
              + (f"; out of scope: {', '.join(scoped)}" if scoped else "")
              + tail, flush=True)
        merged.append(br)
        steps.append((br, head, f"{ran} gate(s) ran, {passes} pass"))
        prev = head

    final = steps[-1][1]
    print(f"merge: union of {len(branches)} branch(es) is green — "
          f"final tree {final[:12]} ({final})", flush=True)
    for i, (br, sha, tail) in enumerate(steps, start=1):
        print(f"merge:   step {i}: merged '{br}' -> {sha[:12]}; {tail}", flush=True)
    if receipt:
        print("merge: the receipt for the union tree is in this repository's "
              ".gov/history/receipts.jsonl — after landing, cite it: "
              "gov receipt verify <landed-commit> (verification matches the "
              "tree sha, so a squash merge of this content verifies)", flush=True)
    _remove_worktree(root, tmp)
    print(f"merge: scratch worktree removed ({tmp})", flush=True)
    return 0
