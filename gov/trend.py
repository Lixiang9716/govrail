#!/usr/bin/env python3
"""Gate duration trends from .gov/history/ (D28, wish 12).

``gov run --record`` appends one JSON line per run to
``.gov/history/gates.jsonl`` — append-only, the plane's own philosophy.
This command reads it back: per gate, the p50 of the earlier half of the
window vs the later half, so a duration regression is a sentence, not a
memory ("tests p50 1.2s → 2.6s (×2.2)"). Runs stay stateless unless
``--record`` is asked for; the history file is outside every gates.json
validation scope by construction.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:  # package context (`gov ...`)
    from .root import anchor_to_git_root
except ImportError:  # direct script execution
    from root import anchor_to_git_root

HISTORY = Path(".gov/history/gates.jsonl")


def _p50(values: list[int]) -> float:
    vs = sorted(values)
    if not vs:
        return 0.0
    mid = len(vs) // 2
    return float(vs[mid]) if len(vs) % 2 else (vs[mid - 1] + vs[mid]) / 2


def _fmt(ms: float) -> str:
    return f"{ms / 1000:.1f}s" if ms >= 1000 else f"{ms:.0f}ms"


def _fmt_cost(v: float) -> str:
    return f"{int(v):,}" if float(v).is_integer() and abs(v) < 1e15 else f"{v:,.1f}"


def _split_by_base(runs: list[dict], base: str) -> tuple[list[dict], list[dict]] | None:
    """Partition runs at --base's commit date; None = unresolvable ref."""
    import subprocess as _sp
    proc = _sp.run(["git", "show", "-s", "--format=%cI", base],
                   capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not proc.stdout.strip():
        print(f"trend: cannot resolve {base!r}: {proc.stderr.strip()}",
              file=sys.stderr)
        return None
    from datetime import datetime as _dt

    split_at = _dt.fromisoformat(proc.stdout.strip())

    def _ts(run):
        try:
            return _dt.fromisoformat(run.get("ts", ""))
        except ValueError:
            return None

    early = [r for r in runs if _ts(r) and _ts(r) <= split_at]
    late = [r for r in runs if _ts(r) and _ts(r) > split_at]
    return early, late


# #119: records may carry non-run outcomes (SCOPED_OUT, NOT_SELECTED,
# NOT_RUN, DISABLED) — a gate the diff did not touch must not drag a
# 0ms p50 down.
NON_RUN = {"SCOPED_OUT", "NOT_SELECTED", "NOT_RUN", "DISABLED"}


def _report(early_runs: list[dict], late_runs: list[dict], indent: str, args) -> None:
    """Print the per-gate p50 early→late comparison for one run window.

    Early/late are already partitioned (halfway by default, --base's
    commit date when asked); runs without a parseable ts sit outside a
    --base split, exactly as before #120.
    """
    durations: dict[str, list[int]] = {}
    for run in early_runs + late_runs:
        for rec in run.get("gates", []):
            gid = rec.get("gate")
            if gid is None or rec.get("outcome") in NON_RUN:
                continue
            durations.setdefault(gid, []).append(int(rec.get("duration_ms", 0)))

    def _window(gid: str, group: list[dict]) -> list[int]:
        return [int(rec.get("duration_ms", 0))
                for run in group for rec in run.get("gates", [])
                if rec.get("gate") == gid and rec.get("outcome") not in NON_RUN]

    movers, stable = [], []
    for gid in sorted(durations):
        if args.gate and gid != args.gate:
            continue
        early, late = _window(gid, early_runs), _window(gid, late_runs)
        if not early or not late:
            continue
        e, l = _p50(early), _p50(late)
        ratio = (l / e) if e else float("inf")
        line = f"{indent}  {gid:<16} p50 {_fmt(e)} → {_fmt(l)}"
        if ratio >= 1.5:
            movers.append(f"{line} (×{ratio:.1f} ↑)")
        elif ratio <= 0.67:
            movers.append(f"{line} (×{ratio:.1f} ↓)")
        else:
            stable.append(f"{line} — stable over {len(durations[gid])} run(s)")
    for m in movers:
        print(m)
    for s in stable:
        print(s)
    if movers:
        print(f"{indent}  (a mover compares window halves — it is a question to "
              "investigate, not a verdict; --gate <id> focuses one gate)")
    else:
        print(f"{indent}  no duration movers in this window")


def _cost_report(early: list[dict], late: list[dict], window: int) -> int:
    """#126/D45: per-caller roll-up of run-level ``cost`` over the window.

    A malformed cost field is named on stderr and skipped, never silently
    summed (rule 5); a non-numeric unit value is named too. Zero reporting
    prints the opt-in pointer — a window with no cost reported must not
    read like a roll-up of zero.
    """
    per: dict[str, dict] = {}

    def _add(runs: list[dict], when: str) -> None:
        for i, run in enumerate(runs):
            if "cost" not in run:
                continue
            tag = str(run.get("caller") or "(untagged)")
            cost = run["cost"]
            if not isinstance(cost, dict) or not cost:
                print(f"trend: skipping malformed cost field in a history "
                      f"line (expected a unit=value object)", file=sys.stderr)
                continue
            entry = per.setdefault(tag, {"runs": 0, "early": {}, "late": {}})
            entry["runs"] += 1
            bucket = entry[when]
            for unit, value in cost.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    print(f"trend: skipping non-numeric {unit!r} in a "
                          f"history line", file=sys.stderr)
                    continue
                bucket[unit] = bucket.get(unit, 0.0) + float(value)

    _add(early, "early")
    _add(late, "late")

    print(f"trend --cost: {window} run(s) in {HISTORY}, "
          f"{sum(e['runs'] for e in per.values())} reporting cost")
    for tag in sorted(per):
        entry = per[tag]
        units = sorted(set(entry["early"]) | set(entry["late"]))
        cells = []
        for unit in units:
            e, l = entry["early"].get(unit, 0.0), entry["late"].get(unit, 0.0)
            cells.append(f"{unit} {_fmt_cost(e + l)} "
                         f"({_fmt_cost(e)} early → {_fmt_cost(l)} late)")
        print(f"  caller {tag}: {entry['runs']} run(s): " + "; ".join(cells))
    if not per:
        print("  no cost reported in this window — tools opt in per run "
              "(gov run --cost tokens=…,calls=… or $GOV_COST)")
    return 0


def main(argv: list[str] | None = None) -> int:
    anchor_to_git_root("trend")
    parser = argparse.ArgumentParser(
        prog="gov trend",
        description="Gate duration trends from .gov/history/gates.jsonl.",
    )
    parser.add_argument("--last", type=int, default=20,
                        help="how many recorded runs to consider (default: 20)")
    parser.add_argument("--gate", default=None,
                        help="show a single gate only")
    parser.add_argument("--base", default=None,
                        help="git ref: split early/late at its commit date "
                             "(default: the window's halfway point)")
    parser.add_argument("--by-tag", action="store_true",
                        help="split runs by their caller tag (--tag/GOV_CALLER "
                             "on gov run) — multi-agent attribution; untagged "
                             "runs group under (untagged) (#120)")
    parser.add_argument("--cost", action="store_true",
                        help="roll up caller-reported cost (gov run --cost / "
                             "$GOV_COST, #126) per caller tag instead of "
                             "duration movers — govrail standardizes the "
                             "ledger shape; the numbers stay caller-supplied")
    args = parser.parse_args(argv)

    if args.by_tag and args.cost:
        print("trend: --by-tag and --cost cannot be combined — --cost "
              "already groups by caller tag", file=sys.stderr)
        return 2
    if args.cost and args.gate:
        print("trend: --cost reports run-level cost (it belongs to the run, "
              "not a single gate); --gate filters durations only",
              file=sys.stderr)
        return 2

    if not HISTORY.is_file():
        print("trend: no history yet — never recorded; runs record by "
              "default now, so this appears after your next gov run")
        return 0
    runs = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"trend: skipping a malformed history line", file=sys.stderr)
    runs = runs[-args.last:]

    halves: tuple[list[dict], list[dict]] | None = None
    if args.base and not args.by_tag:
        halves = _split_by_base(runs, args.base)
        if halves is None:
            return 2
        print(f"  split at {args.base}")

    if args.by_tag:
        # #120/D42: group by caller tag, order of first appearance; a run
        # without a tag is (untagged) and behaves exactly as before. The
        # early/late split happens inside each group (its own halfway, or
        # --base's date) — a tag concentrated in time still compares.
        def _tag(run) -> str:
            return str(run.get("caller") or "(untagged)")

        order: list[str] = []
        for run in runs:
            if _tag(run) not in order:
                order.append(_tag(run))
        tagged = [t for t in order if t != "(untagged)"]
        print(f"trend: {len(runs)} run(s) in {HISTORY}, by caller tag")
        if args.base:
            # resolve/validate once; each group splits at the same date
            if _split_by_base(runs, args.base) is None:
                return 2
            print(f"  split at {args.base}")
        if not tagged:
            print("  no run carries a caller tag — start one with "
                  "`gov run --tag <name>` or GOV_CALLER=<name>")
            return 0
        for tag in tagged + ["(untagged)"] if "(untagged)" in order else tagged:
            group = [r for r in runs if _tag(r) == tag]
            print(f"  caller {tag}: {len(group)} run(s)")
            if len(group) < 2:
                print("    need at least 2 comparable run(s) to split")
                continue
            if args.base:
                g_halves = _split_by_base(group, args.base)
                if g_halves is None:
                    return 2
            else:
                half = len(group) // 2
                g_halves = (group[:half], group[half:])
            if not g_halves[0] or not g_halves[1]:
                print("    need at least 2 comparable run(s) to split")
                continue
            _report(g_halves[0], g_halves[1], "  ", args)
        return 0

    if args.cost:
        # #126/D45: roll up run-level cost fields per caller tag over the
        # window (D42's tag is the grouping key — same vocabulary, no
        # second attribution scheme). Cost-bearing but untagged runs group
        # under (untagged); runs without a cost field do not appear here.
        # halves is already the base split (or None → the halfway split).
        if halves is None:
            half = len(runs) // 2
            halves = (runs[:half], runs[half:])
        return _cost_report(halves[0], halves[1], len(runs))

    half = len(runs) // 2
    halves = halves or (runs[:half], runs[half:])

    if len(runs) < 2:
        print(f"trend: {len(runs)} run(s) recorded (history exists) — "
              "need at least 2 to compare")
        return 0

    print(f"trend: {len(runs)} run(s) in {HISTORY}")
    _report(halves[0], halves[1], "", args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
