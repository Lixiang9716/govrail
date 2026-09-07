from gov import recall


def _memory(root):
    notes = root / ".agents" / "notes" / "implemented" / "architecture"
    notes.mkdir(parents=True)
    (notes / "2026-01-01-gate-runner.md").write_text(
        "# Agent Note: the gate runner DAG\n\nStatus: implemented\n\n"
        "## Problem\nconcurrency was unbounded.\n\n"
        "## Decision\nthe runner respects the needs DAG.\n\n"
        "## Alternatives considered\na plain loop.\n"
    , encoding="utf-8")
    (notes / "2026-01-02-pairing.md").write_text(
        "# Agent Note: pairing by blob hash\n\nStatus: implemented\n\n"
        "## Problem\ndrift between languages.\n\n"
        "## Decision\nhashes pin the pair.\n\n"
        "## Alternatives considered\nmanual review.\n"
    , encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "decisions.md").write_text(
        "# log\n\n## D1 — 默认运行集\n\n- **状态**：已决\n- **决定**：defaultMode 声明默认集。\n\n"
        "## D2 — pairing 约定\n\n- **状态**：已决\n"
    , encoding="utf-8")
    pm = docs / "postmortem"
    pm.mkdir()
    (pm / "2026-01-03-outage.md").write_text("# Postmortem: the outage\n\n## Root cause\ndrift.\n", encoding="utf-8")
    (pm / "README.md").write_text("# Postmortems\ncontract only\n", encoding="utf-8")


def test_recall_ranks_title_above_body(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    assert recall.main(["pairing"]) == 0
    out = capsys.readouterr().out
    note_line = [l for l in out.splitlines() if "2026-01-02-pairing.md" in l][0]
    d_line = [l for l in out.splitlines() if "decisions.md#D2" in l][0]
    assert "matched in title" in note_line
    assert "matched in title" in d_line  # the D-heading is the entry's title
    # 'defaultMode' appears only inside D1's body → body match
    assert recall.main(["defaultMode"]) == 0
    body_out = capsys.readouterr().out
    body_line = [l for l in body_out.splitlines() if "decisions.md#D1" in l][0]
    assert "matched in body" in body_line
    assert "README" not in out  # the postmortem contract is not an entry


def test_recall_requires_all_terms(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    assert recall.main(["pairing", "quantum-nonsense"]) == 1
    assert "no match" in capsys.readouterr().out


def test_miss_prints_per_term_hit_counts(tmp_path, monkeypatch, capsys):
    """#148: a miss distinguishes 'corpus lacks the term' from 'AND failed'."""
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    assert recall.main(["pairing", "quantum-nonsense"]) == 1
    out = capsys.readouterr().out
    assert "per-term hits: pairing: 2 / quantum-nonsense: 0" in out
    assert "--any" in out  # the hint names the relaxed retry


def test_miss_without_any_hit_skips_the_any_hint(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    assert recall.main(["quantum-nonsense", "void"]) == 1
    out = capsys.readouterr().out
    assert "per-term hits: quantum-nonsense: 0 / void: 0" in out
    assert "--any" not in out


def test_corpus_statement_on_every_invocation(tmp_path, monkeypatch, capsys):
    """#148: what was searched is stated on stderr; stdout stays the hits."""
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    assert recall.main(["pairing"]) == 0
    captured = capsys.readouterr()
    assert ("corpus — notes 2 (implemented 2, archived 0), "
            "decisions 2 (docs/decisions.md), "
            "postmortems 1 (docs/postmortem/)") in captured.err
    # the ranked results still lead stdout (the skill reads the top lines)
    assert captured.out.splitlines()[0].startswith(".agents/notes/")
    # misses state the corpus too — via the same stderr line
    assert recall.main(["quantum-nonsense"]) == 1
    assert "corpus — notes 2" in capsys.readouterr().err


def test_corpus_statement_names_a_missing_decisions_source(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    notes = tmp_path / ".agents" / "notes" / "implemented" / "architecture"
    notes.mkdir(parents=True)
    (notes / "2026-01-01-solo.md").write_text("# Agent Note: solo\n\n## Problem\nx\n", encoding="utf-8")
    assert recall.main(["solo"]) == 0
    assert "decisions 0 (no source)" in capsys.readouterr().err


def test_any_ranks_partial_matches(tmp_path, monkeypatch, capsys):
    """#148: --any ranks entries by terms matched instead of refusing."""
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    terms = ["pairing", "drift", "quantum-nonsense"]
    assert recall.main(terms) == 1  # strict AND: no entry carries all three
    capsys.readouterr()
    assert recall.main(["--any", *terms]) == 0
    out = capsys.readouterr().out
    assert "matched 2/3 terms" in out  # the pairing note: title + body
    assert "matched 1/3 terms" in out  # D2 (title) and the postmortem (body)
    ranked = [l for l in out.splitlines() if "matched" in l and " — " in l]
    assert "2/3" in ranked[0]


def test_any_with_zero_matches_still_fails_loud(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    assert recall.main(["--any", "quantum-nonsense"]) == 1
    out = capsys.readouterr().out
    assert "no match" in out and "quantum-nonsense: 0" in out


def test_recall_decisions_sections_are_entries(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _memory(tmp_path)
    assert recall.main(["默认运行集"]) == 0
    out = capsys.readouterr().out
    assert "decisions.md#D1" in out and "matched in title" in out


def test_recall_no_sources_fails_loud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert recall.main(["anything"]) == 2


def test_recall_archived_notes_searchable(tmp_path, monkeypatch, capsys):
    arch = tmp_path / ".agents" / "notes" / "archived" / "process"
    arch.mkdir(parents=True)
    (arch / "2026-01-01-old.md").write_text("# Agent Note: the old way\n\n## Problem\nhistory.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert recall.main(["old way"]) == 0
    assert "archived/process/2026-01-01-old.md" in capsys.readouterr().out


def test_implemented_outranks_archived_at_equal_rank(tmp_path, monkeypatch, capsys):
    """F4: current authority lists before frozen evidence."""
    monkeypatch.chdir(tmp_path)
    for rel in ("implemented/architecture", "archived/architecture"):
        d = tmp_path / ".agents" / "notes" / rel
        d.mkdir(parents=True)
        (d / "2026-01-01-pairing.md").write_text(
            "# Agent Note: pairing\n\n## Problem\nx\n", encoding="utf-8")
    assert recall.main(["pairing"]) == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if "2026-01-01-pairing.md" in l]
    assert lines[0].startswith(".agents/notes/implemented/")
