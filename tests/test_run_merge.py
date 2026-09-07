"""Acceptance tests for ``gov run --merge`` — the preflight of parallel-branch
unions (D51).

Each branch of a parallel batch passes every gate on its own tree, but the
UNION is never tested before the merge; text conflicts git catches, semantic
collisions (each branch green, the merge red) nobody catches. These tests pin
the shipped semantics: per-step D15 selection in a detached scratch worktree,
named refusals (hostile environment, missing base, D33 wall 1), the kept
scene on conflict, byte-identical host worktrees, and the D44 receipt for the
union tree — which must verify across a landing that moves the commit sha but
not the content (tree sha match).

Fixture style mirrors tests/test_decision.py's two-worktree acceptance tests
and tests/test_host_integrity.py's fingerprint discipline.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRUB = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
# Portable gate command (#168): the Unix coreutils true/false and sh do
# not exist on Windows — "a command that exits 0" must not depend on PATH.
PASS = [sys.executable, "-c", "pass"]
PASS_JSON = json.dumps(PASS)


def _env(**extra):
    env = dict(_SCRUB)
    env["PYTHONPATH"] = str(REPO)  # run THIS checkout's gov, not the wheel
    env.update(extra)
    return env


def _git(root, *argv, check=True):
    return subprocess.run(["git", *argv], cwd=root, check=check,
                          capture_output=True, text=True, env=_env(), encoding="utf-8", errors="replace")


def _gov(root, *argv, env=None):
    return subprocess.run([sys.executable, "-m", "gov", "run", *argv],
                          cwd=root, capture_output=True, text=True,
                          env=env if env is not None else _env(), encoding="utf-8", errors="replace")


def _fingerprint(repo):
    """(config, refs, status, HEAD) — the host must be byte-identical."""
    config = hashlib.sha256((repo / ".git" / "config").read_bytes()).hexdigest()
    refs = subprocess.run(["git", "show-ref"], cwd=repo, capture_output=True,
                          text=True, env=_env(), encoding="utf-8", errors="replace").stdout
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                            capture_output=True, text=True,
                            env=_env(), encoding="utf-8", errors="replace").stdout
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True, env=_env(), encoding="utf-8", errors="replace").stdout
    return config, hashlib.sha256(refs.encode()).hexdigest(), status, head


def _host(tmp_path):
    """A committed fixture repo: one trivially green gate, three-line file."""
    root = tmp_path / "host"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main", ".")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    # the ledger convention (D28/D29): history is local and gitignored —
    # preflight runs record into the HOST checkout's .gov/history (D32).
    (root / ".gitignore").write_text(".gov/history/\n", encoding="utf-8")
    (root / "gates.json").write_text(
        json.dumps({"gates": [{"id": "ok", "command": PASS}]}),
        encoding="utf-8")
    (root / "f.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


def _branch(root, name, edit):
    _git(root, "checkout", "-q", "-b", name)
    edit(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", name)
    _git(root, "checkout", "-q", "main")


def _scene_path(output):
    for line in output.splitlines():
        if "kept for inspection: " in line:
            return Path(line.split("kept for inspection: ", 1)[1].strip())
    return None


def _cleanup_scene(root, scene):
    """The scene is kept BY DESIGN; the test tidies it after asserting."""
    if scene is not None and scene.is_dir():
        subprocess.run(["git", "-C", str(root), "worktree", "remove",
                        "--force", str(scene)], capture_output=True)
        shutil.rmtree(scene, ignore_errors=True)
        subprocess.run(["git", "-C", str(root), "worktree", "prune"],
                       capture_output=True)


# --- a: each branch green, union green, host untouched ----------------------


def test_merge_green_union_leaves_host_byte_identical(tmp_path):
    root = _host(tmp_path)
    # a fetched origin/master exists → the DEFAULT base is usable
    _git(root, "update-ref", "refs/remotes/origin/master", "HEAD")
    _branch(root, "a", lambda r: (r / "a.txt").write_text("a\n",
                                                          encoding="utf-8"))
    _branch(root, "b", lambda r: (r / "b.txt").write_text("b\n",
                                                          encoding="utf-8"))
    before = _fingerprint(root)
    worktrees_before = _git(root, "worktree", "list").stdout
    scratch_before = set(Path(tempfile.gettempdir()).glob("gov-merge-*"))
    result = _gov(root, "--merge", "a", "b")  # no --base: default resolves
    assert result.returncode == 0, result.stdout + result.stderr
    assert "union of 2 branch(es) is green" in result.stdout
    assert "scratch worktree removed" in result.stdout
    # the host worktree is byte-identical: status clean, no new files,
    # HEAD/refs/config untouched (the merge commits live only in the
    # scratch's detached HEAD)
    assert _fingerprint(root) == before
    assert _git(root, "worktree", "list").stdout == worktrees_before
    # and no gov-merge scratch is left behind in the temp area
    leftovers = {p for p in Path(tempfile.gettempdir()).glob("gov-merge-*")
                 if p.is_dir()} - scratch_before
    assert not leftovers, leftovers


# --- b: semantic collision — each branch green, the union red ---------------


def _semantic_fixture(tmp_path):
    """Two branches that edit gates.json at opposite ends: A inserts
    ``drill-dup`` after the opening bracket, B appends the same id before
    the closing bracket. The hunks are separated by filler gates, so the
    text merges cleanly — and the loader then rejects the duplicate id."""
    root = _host(tmp_path)
    base = (
        '{"gates": [\n'
        '  {"id": "filler-1", "command": ' + PASS_JSON + '},\n'
        '  {"id": "filler-2", "command": ' + PASS_JSON + '},\n'
        '  {"id": "filler-3", "command": ' + PASS_JSON + '},\n'
        '  {"id": "base-ok", "command": ' + PASS_JSON + '}\n'
        ']}\n'
    )
    (root / "gates.json").write_text(base, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fillers")

    def front(r):
        cfg = (r / "gates.json").read_text(encoding="utf-8")
        (r / "gates.json").write_text(cfg.replace(
            '{"gates": [\n',
            '{"gates": [\n  {"id": "drill-dup", "command": '
            + PASS_JSON + '},\n',
            1), encoding="utf-8")

    def back(r):
        cfg = (r / "gates.json").read_text(encoding="utf-8")
        (r / "gates.json").write_text(cfg.replace(
            '  {"id": "base-ok", "command": ' + PASS_JSON + '}\n]}\n',
            '  {"id": "base-ok", "command": ' + PASS_JSON + '},\n'
            '  {"id": "drill-dup", "command": ' + PASS_JSON + '}\n'
            ']}\n', 1), encoding="utf-8")

    _branch(root, "a", front)
    _branch(root, "b", back)
    return root


def test_merge_catches_semantic_collision_each_branch_green(tmp_path):
    root = _semantic_fixture(tmp_path)
    # each branch alone passes every gate (rule 6: prove the premise first)
    for br in ("a", "b"):
        _git(root, "checkout", "-q", br)
        alone = _gov(root, "--every-gate")
        assert alone.returncode == 0, (
            f"branch {br} must be green alone: {alone.stdout + alone.stderr}")
    _git(root, "checkout", "-q", "main")
    # and the text merge is CLEAN (this is the collision git cannot see)
    _git(root, "checkout", "-q", "--detach")
    text = _git(root, "merge", "--no-ff", "--no-edit", "a")
    assert text.returncode == 0, text.stderr
    text = _git(root, "merge", "--no-ff", "--no-edit", "b")
    assert text.returncode == 0, (
        f"the fixture must merge cleanly as text: {text.stderr}")
    merged = (root / "gates.json").read_text(encoding="utf-8")
    assert merged.count('"drill-dup"') == 2  # the duplicate is IN the union
    _git(root, "checkout", "-q", "main")
    _git(root, "reset", "-q", "--hard")

    result = _gov(root, "--merge", "a", "b", "--base", "main")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "branch 2 (b) FAILED the gates on the union tree" in result.stdout
    assert "already-merged set (a)" in result.stdout
    # the union is red for a SEMANTIC reason, not a text conflict
    assert "duplicate gate id: drill-dup" in result.stderr
    assert "conflicts with already-merged set" not in result.stdout
    scene = _scene_path(result.stdout)
    assert scene is not None and scene.is_dir(), "the scene must be kept"
    _cleanup_scene(root, scene)


# --- c: text conflict — named, scene kept -----------------------------------


def test_merge_names_text_conflict_and_keeps_scene(tmp_path):
    root = _host(tmp_path)
    _branch(root, "a", lambda r: (r / "f.txt").write_text(
        "A1\ntwo\nthree\n", encoding="utf-8"))
    _branch(root, "b", lambda r: (r / "f.txt").write_text(
        "B1\ntwo\nthree\n", encoding="utf-8"))
    result = _gov(root, "--merge", "a", "b", "--base", "main")
    assert result.returncode == 1, result.stdout + result.stderr
    assert ("branch 2 (b) conflicts with already-merged set (a)"
            in result.stdout)
    assert "f.txt" in result.stdout  # the conflicted file is named
    scene = _scene_path(result.stdout)
    assert scene is not None and scene.is_dir(), "the scene must be kept"
    on_disk = (scene / "f.txt").read_text(encoding="utf-8")
    assert "<<<<<<<" in on_disk  # the live conflict, inspectable
    _cleanup_scene(root, scene)


# --- d: hostile environment — refuse loud, host untouched -------------------


def test_merge_refuses_hostile_git_dir(tmp_path):
    root = _host(tmp_path)
    _branch(root, "a", lambda r: (r / "a.txt").write_text("a\n",
                                                          encoding="utf-8"))
    other = tmp_path / "elsewhere"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main", ".")
    before = _fingerprint(root)
    hostile = _env(GIT_DIR=str(other / ".git"))
    result = _gov(root, "--merge", "a", "--base", "main", env=hostile)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "REFUSING" in result.stderr and "GIT_DIR" in result.stderr
    # nothing ran: no worktree, no merge, host byte-identical
    assert _fingerprint(root) == before
    assert len(_git(root, "worktree", "list").stdout.strip().splitlines()) == 1


# --- e: base discipline — a missing ref is a named demand -------------------


def test_merge_missing_base_demands_explicit_ref(tmp_path):
    root = _host(tmp_path)  # no origin/master exists here
    _branch(root, "a", lambda r: (r / "a.txt").write_text("a\n",
                                                          encoding="utf-8"))
    result = _gov(root, "--merge", "a")  # no --base, default cannot resolve
    assert result.returncode == 2, result.stdout + result.stderr
    assert "origin/master" in result.stderr
    assert "--base" in result.stderr  # it demands the explicit ref
    assert _scene_path(result.stdout) is None  # nothing ran
    result = _gov(root, "--merge", "a", "--base", "no-such-ref")
    assert result.returncode == 2 and "no-such-ref" in result.stderr
    result = _gov(root, "--merge", "ghost", "--base", "main")
    assert result.returncode == 2 and "'ghost'" in result.stderr


# --- receipt: D44 evidence for the union tree -------------------------------


def test_merge_receipt_scopes_steps_but_full_matrix_last(tmp_path):
    """Steps select the minimal sufficient set (D15); with --receipt the
    LAST step upgrades to every enabled gate — a scoped selection could
    never verify as full evidence (D44)."""
    root = _host(tmp_path)
    (root / "gates.json").write_text(json.dumps({"gates": [
        {"id": "ok", "command": PASS},
        {"id": "docs", "command": PASS, "paths": ["docs/**"]},
    ]}), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "docs gate")
    _branch(root, "a", lambda r: (r / "a.txt").write_text("a\n",
                                                          encoding="utf-8"))
    _branch(root, "b", lambda r: (r / "b.txt").write_text("b\n",
                                                          encoding="utf-8"))

    plain = _gov(root, "--merge", "a", "b", "--base", "main", "--no-record")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    # step reports stream on the caller's stderr; the orchestrator's own
    # lines go to stdout
    both = plain.stdout + plain.stderr
    assert "PASS docs" not in both  # never in step scope
    assert "out of scope: docs" in both

    receipted = _gov(root, "--merge", "a", "b", "--base", "main",
                     "--receipt", "--no-record")
    assert receipted.returncode == 0, receipted.stdout + receipted.stderr
    both = receipted.stdout + receipted.stderr
    assert "PASS docs" in both  # the last step ran everything
    assert "full matrix" in receipted.stdout
    assert "receipt: r-" in receipted.stderr


def test_merge_receipt_verifies_landed_union_by_tree(tmp_path):
    """The spec's landing story: the receipt binds the union TREE sha, so a
    landing that reproduces the content (same order, same files — a squash
    merge moves the commit sha, not the tree) verifies."""
    root = _host(tmp_path)
    _branch(root, "a", lambda r: (r / "a.txt").write_text("a\n",
                                                          encoding="utf-8"))
    _branch(root, "b", lambda r: (r / "b.txt").write_text("b\n",
                                                          encoding="utf-8"))
    result = _gov(root, "--merge", "a", "b", "--base", "main",
                  "--receipt", "--no-record")
    assert result.returncode == 0, result.stdout + result.stderr
    # land the union for real: same order, same content, NEW commit shas
    _git(root, "checkout", "-q", "-b", "landed")
    _git(root, "merge", "--no-ff", "--no-edit", "a")
    _git(root, "merge", "--no-ff", "--no-edit", "b")
    landed = _git(root, "rev-parse", "HEAD").stdout.strip()
    verify = subprocess.run(
        [sys.executable, "-m", "gov", "receipt", "verify", landed],
        cwd=root, capture_output=True, text=True, env=_env(), encoding="utf-8", errors="replace")
    assert verify.returncode == 0, (
        f"the landed union must verify by tree sha: {verify.stderr}")
    assert "all PASS" in verify.stdout


# --- surface discipline ------------------------------------------------------


def test_merge_rejects_runner_selection_flags(tmp_path):
    root = _host(tmp_path)
    for flag in ("--json", "--fail-fast", "--every-gate"):
        result = _gov(root, "--merge", "a", flag, "--base", "main")
        assert result.returncode == 2, flag
        assert "--merge" in result.stderr and flag in result.stderr
    result = _gov(root, "--merge", "a", "--gate", "ok", "--base", "main")
    assert result.returncode == 2 and "--gate" in result.stderr
    # and the hostile-combination check fires before any worktree exists
    assert len(_git(root, "worktree", "list").stdout.strip().splitlines()) == 1


def test_merge_never_combines_with_mode(tmp_path):
    root = _host(tmp_path)
    result = _gov(root, "--merge", "a", "--mode", "quick")
    assert result.returncode == 2 and "--mode" in result.stderr
