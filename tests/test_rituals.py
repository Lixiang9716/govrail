"""The tracked ritual ledger — audit evidence in git, not deletable local storage (N9)."""
import json
from pathlib import Path


from gov import rituals

LEDGER_LINE_KEYS = {"ts", "ritual", "caller"}


def _root(tmp_path):
    (tmp_path / ".gov").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gov" / "rules.md").write_text("# rules\n", encoding="utf-8")
    (tmp_path / "gates.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_append_creates_tracked_ledger_with_full_record(tmp_path):
    rituals.append(tmp_path, ritual="unsealed-config",
                   config="evil.json", caller="agent-9")
    line = (tmp_path / ".gov" / "rituals.jsonl").read_text(
        encoding="utf-8").strip()
    entry = json.loads(line)
    assert entry["ritual"] == "unsealed-config"
    assert entry["config"] == "evil.json"
    assert entry["caller"] == "agent-9"
    assert set(LEDGER_LINE_KEYS) <= set(entry)


def test_appends_accumulate_append_only(tmp_path):
    rituals.append(tmp_path, ritual="a", caller="x")
    rituals.append(tmp_path, ritual="b", caller="y")
    lines = (tmp_path / ".gov" / "rituals.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # append-only: never rewritten, never truncated


def test_the_ledger_is_not_gitignored(tmp_path):
    """N9's whole point: the ledger must be TRACKED. The repo's
    .gitignore ignores .gov/history/ but never the ledger; this test
    fails if anyone adds a pattern that would ignore it."""
    import subprocess
    root = _root(tmp_path)
    ledger = root / ".gov" / "rituals.jsonl"
    ledger.write_text("", encoding="utf-8")
    checked = subprocess.run(
        ["git", "check-ignore", "-q", ledger.as_posix()],
        cwd=root, capture_output=True)
    # no git repo in the scratch → check-ignore can't run; emulate with
    # the repo's own .gitignore patterns instead
    patterns = (Path(__file__).resolve().parent.parent / ".gitignore"
                ).read_text(encoding="utf-8").splitlines()
    def ignored(rel):
        rel = rel.replace("\\", "/")
        for pat in patterns:
            pat = pat.strip()
            if not pat or pat.startswith("#"):
                continue
            if pat.endswith("/") and rel.startswith(pat):
                return True
            if pat == rel:
                return True
        return False
    assert not ignored(".gov/rituals.jsonl"), (
        ".gov/rituals.jsonl must never be gitignored — the tracked "
        "ledger is the N9 fix; ignoring it re-creates deletable evidence")

