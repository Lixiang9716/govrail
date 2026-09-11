#!/usr/bin/env python3
"""Gate runner.

Reads a gates.json (see docs/decisions.md D1/D2), runs each gate as a command
that exits non-zero on failure, and reports one outcome per gate:

    PASS    command exited 0
    FAIL    command exited non-zero
    TIMEOUT exceeded its timeoutMs
    MISSING the executable does not exist
    SKIP    a needed dependency did not pass (blocking failure, or was skipped)

Exit codes: 0 = all green; 1 = at least one blocking failure; 2 = config invalid.
Run order respects the ``needs`` DAG; ``concurrency`` caps parallel gate runs.
SKIP propagates transitively: a gate whose need was skipped is itself skipped,
never silently run and reported PASS.

Selection: ``--mode <name>`` runs that mode's gate list; otherwise the
top-level ``defaultMode`` runs (when configured); otherwise every enabled
gate. ``--base <ref>`` instead selects the gates whose ``paths`` globs match
the diff against that git ref (unpathed gates always run), and ``--gate <id>``
runs one gate. ``enabled: false`` parks a gate outside every run — reported
as a ``DISABLED`` line, never silently dropped — so "off" stays written down
in the config instead of deleting the definition. A gate with
``allowFailure: true`` reports its failure output tagged ``advisory``
without affecting the exit code. Blocking failures end with a summary block
naming each failed gate, its first output line, and how to rerun it alone.

The runtime is Python 3 plus the tree-sitter parse layer (D54).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

# #124: receipts are a sibling module; gates.py also runs as a plain
# script (self-test scratch dirs), where the package context is absent.
try:
    from . import receipt as receipt_mod
    from .root import force_utf8_stdio
except ImportError:  # direct-script execution (python gov/gates.py)
    import receipt as receipt_mod
    from root import force_utf8_stdio

BLOCKING_OUTCOMES = ("FAIL", "TIMEOUT", "MISSING")
OUTCOME_ORDER = ("FAIL", "TIMEOUT", "MISSING", "SKIP", "PASS")

_RX_CACHE: dict[str, re.Pattern[str]] = {}


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile a path glob: ``**`` spans directories, ``*``/``?`` do not."""
    rx = _RX_CACHE.get(pattern)
    if rx is not None:
        return rx
    out: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    rx = re.compile("^" + "".join(out) + "$")
    _RX_CACHE[pattern] = rx
    return rx


class ConfigError(Exception):
    """gates.json is invalid; fix the file, not the project."""


class DriftRefused(Exception):
    """Non-additive drift under ``merge_gates_by_id(on_drift="refuse")``.

    ``ids`` names the shared gate ids whose content differs — the caller
    turns them into the loud refusal (rule 5), writing nothing.
    """

    def __init__(self, ids: list[str]):
        self.ids = ids
        super().__init__(", ".join(ids))


def merge_gates_by_id(
    local: dict,
    incoming: dict,
    *,
    what: str,
    on_drift: str,
    mode_membership: str = "added-only",
) -> tuple[dict, list[dict], list[str]]:
    """D39's additive merge by gate id — the one gates-merge semantics.

    Shared by ``gov init --adopt-new`` and ``gov preset apply``
    (gov/presets.py): gate id is identity, so incoming gates whose id is
    absent locally are appended in incoming order, and every local gate
    object is preserved untouched (D8). A shared id whose content differs
    is non-additive drift; ``on_drift`` picks the ruling:

    - ``"refuse"`` (--adopt-new): the shipped template moved under a
      customization — the whole merge is refused (``DriftRefused``), the
      hand-merge path stays (D27/D34);
    - ``"keep"`` (presets): the local gate IS the adopted state — it is
      kept and the difference is named in a notice.

    ``incoming``'s modes ride along; ``mode_membership`` picks how an
    EXISTING local mode absorbs them (a NEW mode is created when every
    id it names resolves inside the merged config — for --adopt-new that
    means newly added gates only (D39's "purely additive new mode"), a
    preset may also point at kept local gates):

    - ``"added-only"`` (default, --adopt-new): an existing local mode
      gains only the ids this merge newly added (D39) — a gate the local
      side already had stays wherever local membership put it;
    - ``"converge"`` (presets): a preset's mode declaration is a
      membership patch — an existing local mode gains every declared id
      that resolves in the merged gates and is not already a member,
      whether it was adopted this round or already present, so a second
      apply converges a project whose membership drifted (or never
      landed) even when every gate is already adopted. Local membership
      and its order are never touched; a declared id that resolves to no
      gate in this project is skipped and NAMED in a notice (rule 5).

    The caller's ``defaultMode`` never changes; when ``incoming``
    declares one that differs, a notice says so. ``what`` labels the
    source in the notices ("the template", "preset 'agent-heavy'").

    Returns ``(merged_config, added_gates, notices)``; refusing drift
    raises ``DriftRefused``. Validating the merged result against the
    real schema is the caller's job — never land a config the runner
    would reject.
    """
    if on_drift not in ("refuse", "keep"):
        raise ValueError(f"unknown on_drift ruling: {on_drift!r}")
    if mode_membership not in ("added-only", "converge"):
        raise ValueError(f"unknown mode_membership ruling: {mode_membership!r}")
    if on_drift == "refuse" and mode_membership == "converge":
        raise ValueError(
            "mode_membership='converge' is a preset ruling — --adopt-new "
            "never rewrites existing local mode membership (D39)")
    local_gates = local["gates"]
    local_by_id = {g["id"]: g for g in local_gates}
    incoming_gates = incoming.get("gates") or []
    incoming_by_id = {g["id"]: g for g in incoming_gates}

    conflicting = sorted(
        gid for gid, g in local_by_id.items()
        if gid in incoming_by_id and g != incoming_by_id[gid]
    )
    if conflicting and on_drift == "refuse":
        raise DriftRefused(conflicting)

    added = [g for g in incoming_gates if g["id"] not in local_by_id]
    added_ids = {g["id"] for g in added}
    notices: list[str] = []
    if on_drift == "keep":
        for gid in incoming_by_id:
            if gid not in local_by_id:
                continue
            if gid in conflicting:
                notices.append(
                    f"gate '{gid}' exists locally with different content — kept "
                    "your local version (a preset never overwrites)")
            else:
                notices.append(f"gate '{gid}' already adopted (identical)")

    merged = {k: v for k, v in local.items()}
    merged["gates"] = local_gates + added
    # Which ids a not-yet-existing mode may name at creation: --adopt-new
    # creates a mode only when it is purely additive (D39); a preset's mode
    # is a declarative membership patch and may point at kept local gates.
    resolvable = added_ids if on_drift == "refuse" \
        else added_ids | set(local_by_id)
    modes_note: list[str] = []
    local_modes = dict(merged.get("modes") or {})
    for mode, ids in (incoming.get("modes") or {}).items():
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            continue  # malformed incoming mode; schema validation will judge
        if mode in local_modes:
            existing = list(local_modes[mode])
            if mode_membership == "added-only":
                appended = [g for g in ids if g in added_ids and g not in existing]
                ghosts: list[str] = []
            else:  # converge: the declaration is a membership patch
                appended = []
                ghosts = []
                for g in ids:
                    if g in existing:
                        continue  # already a member — nothing to converge
                    (appended if g in resolvable else ghosts).append(g)
            local_modes[mode] = existing + appended
            if appended:
                modes_note.append(
                    f"mode '{mode}' += {', '.join(appended)} (from {what})")
            if ghosts:
                modes_note.append(
                    f"mode '{mode}': skipped gate id(s) that no gate in this "
                    f"project carries: {', '.join(ghosts)} — add the gate or "
                    "the id by hand")
        elif all(g in resolvable for g in ids):
            local_modes[mode] = list(ids)  # new mode, fully resolvable
            modes_note.append(f"mode '{mode}' created from {what}")
        else:
            modes_note.append(
                f"mode '{mode}' NOT adopted — it references gates outside "
                "this additive merge; add it by hand")
    if local_modes or "modes" in local:
        merged["modes"] = local_modes
    notices.extend(modes_note)
    if "defaultMode" in incoming \
            and incoming.get("defaultMode") != merged.get("defaultMode"):
        notices.append(
            f"{what} defaultMode is '{incoming.get('defaultMode')}' (yours stays "
            f"'{merged.get('defaultMode')}')")
    return merged, added, notices


@dataclass
class Gate:
    id: str
    command: list[str]
    label: str = ""
    needs: list[str] = field(default_factory=list)
    timeout_ms: int | None = None
    allow_failure: bool = False
    enabled: bool = True
    paths: list[str] = field(default_factory=list)


def _require_object(value: Any, what: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{what} must be an object")
    return value


def _require_str_list(value: Any, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ConfigError(f"{what} must be an array of strings")
    return value


def _require_positive_int(value: Any, what: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{what} must be a positive integer")
    return value


def _command_variants(raw: Any) -> list[str]:
    """A command is a plain argv array (D1: single form, no shell variants)."""
    if isinstance(raw, list) and all(isinstance(p, str) for p in raw) and raw:
        return raw
    raise ConfigError("command must be a non-empty array of strings")


def load_config(path: str) -> tuple[dict[str, list[str]], list[Gate], int, str | None]:
    """Return (modes, gates, concurrency, default_mode).

    ``default_mode`` is None when the config declares none — callers then
    run every enabled gate (the historical default).
    """
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"{path} not found")
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: {e}")

    raw = _require_object(raw, "the config root")
    # D29: unknown keys abort loud — a typo like "enable": false silently
    # parks nothing, which is exactly the quiet back door D24 closed.
    allowed_top = {"modes", "defaultMode", "concurrency", "gates"}
    unknown_top = sorted(set(raw) - allowed_top)
    if unknown_top:
        raise ConfigError(
            f"unknown top-level key(s): {', '.join(unknown_top)} "
            f"(known: {', '.join(sorted(allowed_top))})"
        )
    gates_raw = raw.get("gates", [])
    if not isinstance(gates_raw, list):
        raise ConfigError("'gates' must be an array")
    modes_raw = raw.get("modes", {})
    if modes_raw is not None and not isinstance(modes_raw, dict):
        raise ConfigError("'modes' must be an object")
    concurrency = _require_positive_int(raw.get("concurrency"), "'concurrency'")

    gates: list[Gate] = []
    ids: set[str] = set()
    for i, g in enumerate(gates_raw):
        g = _require_object(g, f"gates[{i}]")
        allowed_gate = {"id", "command", "label", "needs", "timeoutMs",
                        "allowFailure", "enabled", "paths"}
        unknown = sorted(set(g) - allowed_gate)
        if unknown:
            known_id = g.get("id") or f"gates[{i}]"
            raise ConfigError(
                f"gate '{known_id}': unknown key(s): {', '.join(unknown)} "
                f"(known: {', '.join(sorted(allowed_gate))})"
            )
        gid = g.get("id")
        if not isinstance(gid, str) or not gid:
            raise ConfigError(f"gates[{i}] has an empty or non-string id")
        if gid in ids:
            raise ConfigError(f"duplicate gate id: {gid}")
        ids.add(gid)
        try:
            command = _command_variants(g.get("command"))
        except ConfigError as e:
            raise ConfigError(f"gate '{gid}': {e}")
        label = g.get("label", "")
        if not isinstance(label, str):
            raise ConfigError(f"gate '{gid}': 'label' must be a string")
        needs = g.get("needs", [])
        if not isinstance(needs, list) or not all(isinstance(n, str) for n in needs):
            raise ConfigError(f"gate '{gid}': 'needs' must be an array of strings")
        timeout = g.get("timeoutMs")
        if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0):
            raise ConfigError(f"gate '{gid}': 'timeoutMs' must be a positive integer")
        allow_failure = g.get("allowFailure", False)
        if not isinstance(allow_failure, bool):
            raise ConfigError(f"gate '{gid}': 'allowFailure' must be a boolean")
        enabled = g.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ConfigError(f"gate '{gid}': 'enabled' must be a boolean")
        paths = g.get("paths", [])
        if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise ConfigError(f"gate '{gid}': 'paths' must be an array of strings")
        if any(not p for p in paths):
            raise ConfigError(f"gate '{gid}': 'paths' must not contain empty strings")
        gates.append(
            Gate(
                id=gid,
                command=command,
                label=label,
                needs=list(needs),
                timeout_ms=timeout,
                allow_failure=allow_failure,
                enabled=enabled,
                paths=list(paths),
            )
        )

    # Validate needs references.
    by_id = {g.id: g for g in gates}
    for g in gates:
        for dep in g.needs:
            if dep not in by_id:
                raise ConfigError(f"gate '{g.id}' needs unknown gate '{dep}'")

    # Cycle detection via Kahn's algorithm over the needs DAG.
    indegree = {g.id: 0 for g in gates}
    dependents: dict[str, list[str]] = {g.id: [] for g in gates}
    for g in gates:
        for dep in g.needs:
            indegree[g.id] += 1
            dependents[dep].append(g.id)
    order: list[str] = []
    ready = [gid for gid, d in indegree.items() if d == 0]
    while ready:
        gid = ready.pop()
        order.append(gid)
        for child in dependents[gid]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if len(order) != len(gates):
        in_cycle = sorted(gid for gid, d in indegree.items() if d > 0)
        raise ConfigError(f"cycle among gates: {', '.join(in_cycle)}")

    modes: dict[str, list[str]] = {}
    for name, gate_list in modes_raw.items():
        gate_list = _require_str_list(gate_list, f"mode '{name}'")
        for gid in gate_list:
            if gid not in by_id:
                raise ConfigError(f"mode '{name}' references unknown gate '{gid}'")
        modes[name] = list(gate_list)

    default_mode = raw.get("defaultMode")
    if default_mode is not None:
        if not isinstance(default_mode, str) or not default_mode:
            raise ConfigError("'defaultMode' must be a non-empty string")
        if default_mode not in modes:
            known = ", ".join(modes) or "none"
            raise ConfigError(
                f"'defaultMode' references unknown mode '{default_mode}' (known: {known})"
            )

    # Reachability (D24): with modes defined, an enabled gate that belongs
    # to no mode silently never runs — a silent parking mechanism the
    # design never sanctioned. Parking is "enabled": false — the one loud
    # mechanism (a DISABLED line). Mode omission is not a parking lot.
    if modes:
        members = {gid for ids in modes.values() for gid in ids}
        unreachable = sorted(g.id for g in gates if g.enabled and g.id not in members)
        if unreachable:
            raise ConfigError(
                f"enabled gate(s) not in any mode: {', '.join(unreachable)} — "
                'park a gate with "enabled": false (the one loud mechanism); '
                "mode omission silently never runs (rules 1/6)"
            )

    return modes, gates, concurrency or 0, default_mode


def parse_cost(raw: str) -> dict[str, float]:
    """#126/D45: parse a caller-supplied cost string, ``unit=value`` pairs.

    ``tokens=1200,calls=4`` → ``{"tokens": 1200, "calls": 4}``. Units are
    free-form tokens; values must be finite non-negative numbers — govrail
    standardizes the LEDGER SHAPE, it never meters anything itself (the
    tool that ran the LLMs supplies the numbers it already tracks).
    Malformed input fails loud naming the fragment (rule 5).
    """
    cost: dict[str, float] = {}
    for fragment in raw.split(","):
        fragment = fragment.strip()
        if not fragment:
            continue
        if "=" not in fragment:
            raise ValueError(
                f"cost fragment {fragment!r} is not unit=value "
                "(e.g. tokens=1200,calls=4)"
            )
        unit, _, value = fragment.partition("=")
        unit = unit.strip()
        if not unit:
            raise ValueError(f"cost fragment {fragment!r} has an empty unit")
        try:
            number = float(value.strip())
        except ValueError:
            raise ValueError(
                f"cost fragment {fragment!r}: {value.strip()!r} is not a number"
            ) from None
        if not math.isfinite(number) or number < 0:
            raise ValueError(
                f"cost fragment {fragment!r}: value must be finite and >= 0"
            )
        cost[unit] = int(number) if number.is_integer() else number
    if not cost:
        raise ValueError(f"cost string {raw!r} carries no unit=value pair")
    return cost


def _history_path() -> Path:
    """#23/D32 — see gov/anchor.py (shared with `gov stats --record`)."""
    try:
        from .anchor import history_path
    except ImportError:  # direct-script execution (self-test scratch dirs)
        from anchor import history_path
    return history_path("gates.jsonl")


def _run_one(gate: Gate) -> tuple[Gate, str, str, bool]:
    """Run one gate; return (gate, outcome, detail, blocking_failed).

    A passing gate's output is kept as detail too: exit 0 with something
    to say (a warning, an advisory) must stay visible — passing never
    silences a gate (D20 amends D2's "passes are silent").
    """
    exe = gate.command[0]
    started = time.monotonic()
    if shutil.which(exe) is None:
        return gate, "MISSING", f"command not found: {exe}", True, 0
    try:
        proc = subprocess.run(
            gate.command,
            capture_output=True,
            text=True,
            # Gate output is repo tooling output, UTF-8 by convention;
            # the locale codec must not crash the run on it (#168).
            encoding="utf-8", errors="replace",
            timeout=gate.timeout_ms / 1000 if gate.timeout_ms else None,
        )
    except subprocess.TimeoutExpired:
        return gate, "TIMEOUT", f"exceeded {gate.timeout_ms}ms", True, gate.timeout_ms
    duration_ms = int((time.monotonic() - started) * 1000)
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode == 0:
        return gate, "PASS", output, False, duration_ms
    # #109 failure-first: a failing gate's evidence is never clipped at
    # capture time — the full output flows to the report and the JSON
    # record, so "why did it fail" is answered by one run. Passing gates
    # keep their display-side budget instead (D20 tail-3).
    return gate, "FAIL", output, True, duration_ms


def _changed_files(base: str) -> list[str] | None:
    """Files changed against ``base`` (tracked diff + untracked); None on error."""
    files: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only", base],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            print(
                f"gov run: --base {base!r} failed: {proc.stderr.strip()}",
                file=sys.stderr,
            )
            return None
        files.update(f for f in proc.stdout.splitlines() if f)
    return sorted(files)


def _select_by_paths(
    gates: list[Gate], changed: list[str]
) -> tuple[list[str], list[str]]:
    """Gates whose paths match the diff (unpathed gates always run)."""
    selected: list[str] = []
    out: list[str] = []
    for g in gates:
        if not g.enabled:
            continue
        if not g.paths or any(
            _glob_regex(p).match(f) for p in g.paths for f in changed
        ):
            selected.append(g.id)
        else:
            out.append(g.id)
    return selected, out


def run_gates(
    gates: list[Gate],
    selection: list[str] | None,
    concurrency: int,
    fail_fast: bool,
    json_mode: bool = False,
    record_path: Path | None = None,
    changed: list[str] | None = None,
    selected_by: str = "all-enabled",
    scoped_out: list[str] | None = None,
    caller: str | None = None,
    receipt: dict | None = None,
    receipt_path: Path | None = None,
    cost: dict[str, float] | None = None,
) -> int:
    """Run the selected gates (every enabled gate when selection is None).

    In ``json_mode`` the human-readable report goes to stderr and stdout
    carries exactly one JSON array — one object per gate, in config order:
    ``{gate, outcome, blocking, duration_ms, detail, selected_by,
    scoped_out}`` (D25; #119 adds the last two). Disabled gates appear
    with outcome ``DISABLED``; enabled gates the selection mechanism did
    not pick appear as ``NOT_SELECTED``, and gates excluded by ``--base``
    path scoping as ``SCOPED_OUT`` — one invocation answers the whole
    gate-set question, not just what ran.

    ``receipt`` (from ``--receipt``, issue #124/D44) appends a
    hash-chained receipt of this run — per-gate outcomes bound to the
    tree's commit and tree sha, tagged with the run's caller (#120) — to
    ``receipts.jsonl`` next to the gates history.
    """

    def emit(text: str) -> None:
        if json_mode:
            print(text, file=sys.stderr, flush=True)
        else:
            print(text, flush=True)

    for g in gates:
        if not g.enabled:
            emit(f"DISABLED {g.id}")
    active = [g for g in gates if g.enabled]
    if selection is None:
        selected = active
    else:
        by_id = {g.id: g for g in gates}
        selected = [by_id[gid] for gid in selection if by_id[gid].enabled]
    selected_ids = {g.id for g in selected}
    by_id = {g.id: g for g in selected}

    outcomes: dict[str, str] = {}
    details: dict[str, str] = {}
    blocking: dict[str, bool] = {}
    durations: dict[str, int] = {}
    skipped_set: set[str] = set()

    indegree = {g.id: len([n for n in g.needs if n in selected_ids]) for g in selected}
    dependents: dict[str, list[str]] = {g.id: [] for g in selected}
    for g in selected:
        for dep in g.needs:
            if dep in selected_ids:
                dependents[dep].append(g.id)

    ready = [g for g in selected if indegree[g.id] == 0]

    with ThreadPoolExecutor(max_workers=concurrency or 1) as pool:
        pending: dict[Any, Gate] = {}

        def enqueue(gate: Gate) -> None:
            pending[pool.submit(_run_one, gate)] = gate

        def settle(gid: str) -> None:
            """Propagate a settled gate to its dependents; SKIP transitively."""
            for child in dependents[gid]:
                indegree[child] -= 1
                if indegree[child] != 0:
                    continue
                child_gate = by_id[child]
                failed_needs = [
                    n
                    for n in child_gate.needs
                    if n in selected_ids and (blocking.get(n, False) or n in skipped_set)
                ]
                if failed_needs:
                    outcomes[child] = "SKIP"
                    durations[child] = 0
                    skipped_set.add(child)
                    emit(
                        f"SKIP {child} (needs failed: {', '.join(failed_needs)})"
                    )
                    settle(child)
                else:
                    enqueue(child_gate)

        for g in ready:
            enqueue(g)

        stop = False
        while pending and not stop:
            for fut in list(as_completed(pending)):
                gate = pending.pop(fut)
                g, outcome, detail, is_blocking, duration_ms = fut.result()
                outcomes[g.id] = outcome
                details[g.id] = detail
                durations[g.id] = duration_ms
                blocking[g.id] = is_blocking and not g.allow_failure
                scope_n = None
                if changed is not None and g.paths:
                    scope_n = sum(1 for f in changed
                                  if any(_glob_regex(pt).match(f) for pt in g.paths))
                emit(_outcome_line(g, outcome, scope_n))
                if fail_fast and blocking[g.id]:
                    stop = True
                    for other in pending:
                        other.cancel()
                    pending = {}
                    break
                settle(g.id)

    failed = [gid for gid in outcomes if blocking.get(gid, False)]
    for gid, outcome in outcomes.items():
        if outcome not in BLOCKING_OUTCOMES or not details[gid]:
            continue
        if blocking.get(gid, False):
            emit(f"--- output of {gid} ---")
        else:
            # allowFailure: report loudly, block never (advisory, D2/D13).
            emit(f"--- output of {gid} (advisory; allowFailure) ---")
        emit(details[gid])

    # A pass that said something (a warning, an advisory) stays visible:
    # last 3 lines, exit code and PASS outcome unchanged (D20).
    for gid, outcome in outcomes.items():
        if outcome != "PASS" or not details[gid]:
            continue
        lines = details[gid].splitlines()
        shown = lines[-3:]
        omitted = len(lines) - len(shown)
        emit(f"--- output of {gid} (passed with output) ---")
        emit("\n".join(shown))
        if omitted > 0:
            emit(f"... ({omitted} earlier line(s) not shown)")

    if failed:
        emit(f"--- summary: {len(failed)} blocking failure(s) ---")
        for gid in failed:
            first = details[gid].strip().splitlines()[0] if details[gid].strip() else ""
            # #109: the failure line itself names the rerun command — the
            # reader should not have to remember the flag exists.
            line = f"{gid}: {first}" if first else f"{gid}:"
            emit(f"{line} (rerun: gov run --gate {gid})")

    counts = {o: sum(1 for v in outcomes.values() if v == o) for o in OUTCOME_ORDER}
    parts = [f"{n} {o.lower()}" for o, n in counts.items() if n]
    emit(
        f"{len(outcomes)} gates: " + (", ".join(parts) if parts else "none ran")
    )

    scoped_out_ids = set(scoped_out or [])
    records = []
    for g in gates:
        if not g.enabled:
            records.append(
                {"gate": g.id, "outcome": "DISABLED", "blocking": False,
                 "duration_ms": 0, "detail": "",
                 "selected_by": selected_by, "scoped_out": False}
            )
        elif g.id in outcomes:
            records.append(
                {"gate": g.id, "outcome": outcomes[g.id],
                 "blocking": blocking.get(g.id, False),
                 "duration_ms": durations.get(g.id, 0),
                 "detail": details.get(g.id, ""),
                 "selected_by": selected_by, "scoped_out": False}
            )
        elif g.id in scoped_out_ids:
            # #119: the gate exists, is enabled, and the diff did not touch
            # its paths — an agent reading the record must see it was
            # scoped out, not silently absent.
            records.append(
                {"gate": g.id, "outcome": "SCOPED_OUT", "blocking": False,
                 "duration_ms": 0, "detail": "",
                 "selected_by": selected_by, "scoped_out": True}
            )
        elif g.id in selected_ids:
            # Selected but never settled — a --fail-fast run cancelled it.
            records.append(
                {"gate": g.id, "outcome": "NOT_RUN", "blocking": False,
                 "duration_ms": 0, "detail": "",
                 "selected_by": selected_by, "scoped_out": False}
            )
        else:
            records.append(
                {"gate": g.id, "outcome": "NOT_SELECTED", "blocking": False,
                 "duration_ms": 0, "detail": "",
                 "selected_by": selected_by, "scoped_out": False}
            )
    if json_mode:
        print(json.dumps(records, indent=2))
    rec = None
    if receipt is not None:
        # #124/D44: the receipt records what actually happened — failures
        # included; only verification decides what counts as evidence.
        # Tree state is measured BEFORE any ledger write: a tracked
        # .gov/history must not dirty the very receipt that describes it.
        rec = receipt_mod.build_receipt(records, receipt.get("tag", ""),
                                        receipt.get("selection", {}))
    if record_path is not None:
        # D28/D29: append-only history — one line per run, the plane's
        # own philosophy. Recording is the default (the file is local
        # and gitignored); --no-record opts out.
        # #120/D42: a caller tag (--tag / GOV_CALLER) rides along as
        # caller-supplied free text; absent = anonymous, exactly the
        # pre-#120 record shape.
        # #126/D45: an optional cost ledger (--cost / $GOV_COST) rides the
        # same run line — also absent-unless-supplied, so unreported runs
        # keep the pre-#126 record shape.
        record_path.parent.mkdir(parents=True, exist_ok=True)
        run_record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "gates": records,
        }
        if caller:
            run_record["caller"] = caller
        if cost:
            run_record["cost"] = cost
        with record_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(run_record, separators=(",", ":")) + "\n")
    if rec is not None:
        target = receipt_path if receipt_path is not None \
            else receipt_mod._receipt_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":"),
                               ensure_ascii=False) + "\n")
        commit = rec.get("commit") or "?"
        state = " (dirty tree — will not verify as this commit)" if rec.get("dirty") else ""
        emit(f"receipt: {rec['id']} recorded against {commit}{state} "
             f"(cite it: gov receipt verify <commit>)")
    return 1 if failed else 0


def _outcome_line(gate: Gate, outcome: str, in_scope: int | None = None) -> str:
    parts = []
    if gate.allow_failure and outcome in BLOCKING_OUTCOMES:
        parts.append("(advisory; allowFailure)")
    if in_scope is not None:
        # #21/D32: a scan over zero matched files must not read like a scan.
        parts.append(f"{in_scope} in change scope" if in_scope
                     else "0 in change scope — nothing changed matches")
    return f"{outcome} {gate.id}" + (" " + " ".join(parts) if parts else "")


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()  # reports leave as UTF-8 on every OS (#168)
    parser = argparse.ArgumentParser(prog="gov run", description="Run the governance gate DAG.")
    parser.add_argument("--config", default="gates.json")
    parser.add_argument("--mode", default=None,
                        help="mode name from gates.json (overrides defaultMode)")
    parser.add_argument("--base", default=None,
                        help="select gates whose 'paths' match the diff against this git ref; "
                             "with --merge: the integration target baseline instead "
                             "(default origin/master)")
    parser.add_argument("--gate", default=None, help="run a single gate by id")
    parser.add_argument("--every-gate", action="store_true",
                        help="run every enabled gate — the full matrix, ignoring "
                             "modes and defaultMode (CI owns this)")
    parser.add_argument("--tag", default=None,
                        help="caller tag recorded into .gov/history/gates.jsonl "
                             "for multi-agent attribution (gov trend --by-tag "
                             "splits on it); falls back to $GOV_CALLER; "
                             "absent = anonymous, as before (#120)")
    parser.add_argument("--cost", default=None,
                        help="optional resource cost recorded into the run's "
                             "history line as free-form unit=value pairs, "
                             "e.g. --cost tokens=1200,calls=4 (falls back to "
                             "$GOV_COST) — caller-supplied ledger for "
                             "`gov trend --cost`; govrail meters nothing "
                             "itself (#126)")
    parser.add_argument("--no-record", action="store_true",
                        help="do not append this run to .gov/history/gates.jsonl "
                             "(recording is the default; see gov trend)")
    parser.add_argument("--merge", nargs="+", metavar="BRANCH", default=None,
                        help="preflight the union of parallel branches: each branch is "
                             "merged --no-ff into a detached scratch worktree built on "
                             "--base (integration baseline, default origin/master), and "
                             "the gates run after every merge on that step's tree, "
                             "selected by the diff the step introduced (D15); a text "
                             "conflict or a red step aborts named, keeping the scene; "
                             "with --receipt the last step records D44 evidence for "
                             "the union tree")
    parser.add_argument("--receipt", action="store_true",
                        help="append a tamper-evident receipt of this run to "
                             ".gov/history/receipts.jsonl, bound to the tree's "
                             "commit and tree sha (issue #124/D44); the caller "
                             "tag rides along from --tag/$GOV_CALLER (#120); "
                             "cite it with 'gov receipt verify <commit>'")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable: stdout is exactly one JSON array "
                             "of {gate, outcome, blocking, duration_ms, detail, "
                             "selected_by, scoped_out}; the human report moves "
                             "to stderr")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.merge is not None:
        # Delegation, before this process loads any gates.json of its own:
        # a preflight runs the MERGED tree's config inside the scratch
        # worktree, not the caller's checkout (merge.py owns the semantics;
        # the D33 walls live there).
        try:
            from . import merge as merge_mod
        except ImportError:  # direct-script execution (self-test scratch)
            import merge as merge_mod
        conflicts = [name for flag, name in (
            (args.mode, "--mode"), (args.gate, "--gate"),
            (args.every_gate, "--every-gate"), (args.json, "--json"),
            (args.fail_fast, "--fail-fast"), (args.verbose, "--verbose"),
        ) if flag]
        if conflicts:
            print(f"gov run: --merge and {', '.join(conflicts)} cannot be "
                  "combined — each step runs its own scoped selection, and "
                  "its human report streams live", file=sys.stderr)
            return 2
        caller = (args.tag if args.tag is not None
                  else os.environ.get("GOV_CALLER"))
        caller = caller.strip() if caller else None
        return merge_mod.run_merge(
            args.merge, base=args.base, config=args.config,
            receipt=args.receipt, tag=caller, cost=args.cost,
            no_record=args.no_record)

    try:
        modes, gates, concurrency, default_mode = load_config(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    explicit = [flag for flag, on in (("--gate", args.gate), ("--mode", args.mode),
                                      ("--base", args.base), ("--every-gate", args.every_gate)) if on]
    if len(explicit) > 1:
        print(f"gov run: {' and '.join(explicit)} cannot be combined", file=sys.stderr)
        return 2

    selection = None
    scoped_out_ids: list[str] = []
    # #119: name the mechanism that picked the gate set, so a JSON reader
    # can tell "mode ci chose 5 gates" from "the diff scoped 3 out".
    selected_by = "all-enabled"
    if args.gate:
        known = {g.id for g in gates}
        if args.gate not in known:
            print(
                f"gov run: unknown gate '{args.gate}' (known: {', '.join(sorted(known)) or 'none'})",
                file=sys.stderr,
            )
            return 2
        by_id = {g.id: g for g in gates}
        if not by_id[args.gate].enabled:
            # N4/D24: explicitly naming a parked gate is operator error —
            # a silent green hides it. Parking is visible; so is this.
            print(
                f"gov run: gate '{args.gate}' is disabled — re-enable it or "
                "pick another",
                file=sys.stderr,
            )
            return 2
        selection = [args.gate]
        selected_by = "gate"
    elif args.mode:
        if args.mode not in modes:
            print(
                f"config error: unknown mode '{args.mode}' "
                f"(known: {', '.join(modes) or 'none'})",
                file=sys.stderr,
            )
            return 2
        selection = modes[args.mode]
        selected_by = f"mode:{args.mode}"
    elif args.base:
        changed = _changed_files(args.base)
        if changed is None:
            return 2
        selection, scoped_out_ids = _select_by_paths(gates, changed)
        selected_by = f"base:{args.base}"
        scope_line = (
            f"scope vs {args.base}: {len(selection)}/{len([g for g in gates if g.enabled])} "
            f"gate(s) selected" + (f"; out of scope: {', '.join(scoped_out_ids)}" if scoped_out_ids else "")
        )
        if args.json:  # stdout carries exactly one JSON value (D26)
            print(scope_line, file=sys.stderr, flush=True)
        else:
            print(scope_line, flush=True)
    elif args.every_gate:
        selection = None  # every enabled gate — the explicit full matrix
        selected_by = "every-gate"
    elif default_mode:
        selection = modes[default_mode]
        selected_by = f"default-mode:{default_mode}"
    elif not gates:
        print("no gates configured", file=sys.stderr)
        return 0

    changed = None
    if any(g.paths for g in gates):
        # #21/D32: annotate path-scoped gates with how many changed files
        # they cover; best-effort (git missing -> no annotation).
        probe = _changed_files(args.base) if args.base else _changed_files("HEAD")
        if probe is not None:
            changed = probe

    # #120: --tag wins over $GOV_CALLER; whitespace-only means absent.
    caller = (args.tag if args.tag is not None
              else os.environ.get("GOV_CALLER"))
    caller = caller.strip() if caller else ""

    receipt_info = None
    if args.receipt:
        # What "full" means on a receipt (#124/D44): the selection covered
        # every enabled gate — an explicit mode counts when it names them
        # all; a narrowed run records how it was narrowed (selected_by,
        # #119's vocabulary — no second naming scheme) and never verifies
        # as full evidence. The tag is the run's caller (#120), not a
        # second tagging flag.
        enabled_ids = {g.id for g in gates if g.enabled}
        ran_ids = {gid for gid in (selection or [])} if selection is not None \
            else enabled_ids
        if ran_ids == enabled_ids:
            sel = {"kind": "all", "value": selected_by}
        else:
            sel = {"kind": selected_by, "value": None}
        receipt_info = {"tag": caller or "", "selection": sel}

    # #126/D45: --cost wins over $GOV_COST; malformed input fails loud
    # (rule 5) naming the offending fragment, before any gate runs.
    cost_raw = (args.cost if args.cost is not None
                else os.environ.get("GOV_COST"))
    cost = None
    if cost_raw:
        try:
            cost = parse_cost(cost_raw)
        except ValueError as e:
            print(f"gov run: --cost: {e}", file=sys.stderr)
            return 2
    return run_gates(gates, selection, concurrency, args.fail_fast,
                     json_mode=args.json,
                     record_path=None if args.no_record
                     else _history_path(), changed=changed,
                     selected_by=selected_by, scoped_out=scoped_out_ids,
                     caller=caller or None,
                     receipt=receipt_info,
                     receipt_path=receipt_mod._receipt_path(),
                     cost=cost)


if __name__ == "__main__":
    raise SystemExit(main())
