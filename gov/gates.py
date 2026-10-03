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
the diff against that git ref (unpathed gates always run), and ``--gate``
runs the named gate(s) in one traversal (#405). ``--at <ref>`` judges the
selection against the tree AS OF the ref (#406) — a detached temporary
worktree carries the run, so gate triage never needs a checkout.
``enabled: false`` parks a gate outside every run — reported
as a ``DISABLED`` line, never silently dropped — so "off" stays written down
in the config instead of deleting the definition. A gate with
``allowFailure: true`` reports its failure output tagged ``advisory``
without affecting the exit code. Blocking failures end with a summary block
naming each failed gate, its diagnostic line, and how to rerun it alone
(#419: a JSON-emitting gate is quoted by its kernel, not `{`; #404: the
wall time and the #407 environment classification ride the line). Gates a
failed dependency took down are named in a "skipped, not evaluated" block
with the reason (#420).

Two gate properties shape HOW a gate runs, not what it judges. ``exclusive:
true`` runs the gate ALONE (#403/#417): the scheduler drains the pool before
starting it and admits nothing else until it settles — a self-test whose
project cases mutate the live tree can never race a sibling's reads, and a
fresh-clone gate cannot starve a tight-budget sibling's wall clock.
``requires: ["network"]`` (the known set is closed: rule 5) classifies what
a red verdict may really mean (#407): the outcome line and the summary tag
the failure ENV-possible — the machine's connectivity, not the tree — so a
docs-only diff's red is readable without a PR-body essay.

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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any

# #124: receipts are a sibling module; gates.py also runs as a plain
# script (self-test scratch dirs), where the package context is absent.
try:
    from . import receipt as receipt_mod
    from . import anchor as anchor_mod
    from . import atomicio, gitutil, pathmatch
    from .root import anchor_to_git_root, force_utf8_stdio
    from .version import __version__
except ImportError:  # direct-script execution (python gov/gates.py)
    import receipt as receipt_mod
    import anchor as anchor_mod
    import atomicio, gitutil, pathmatch
    from root import anchor_to_git_root, force_utf8_stdio
    from version import __version__

BLOCKING_OUTCOMES = ("FAIL", "TIMEOUT", "MISSING")
OUTCOME_ORDER = ("FAIL", "TIMEOUT", "MISSING", "SKIP", "PASS")
# Recorded for enabled gates a run did NOT execute: bookkeeping, not
# verdicts (#119; consumed by trend's NON_RUN and task close's green
# judgment, #323). SKIP is deliberately absent — a dependency failed,
# so evidence is genuinely missing.
NON_RUN_OUTCOMES = ("SCOPED_OUT", "NOT_SELECTED", "NOT_RUN", "DISABLED")
# #407: the environment vocabulary a gate may declare in `requires`.
# Closed on purpose (rule 5): a typo like "netwrok" must abort, not
# silently classify nothing.
KNOWN_REQUIRES = frozenset({"network"})

def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile a path glob under the plane's one grammar (pathmatch).

    ``**`` spans directories including zero of them — ``**/x.py`` reaches
    a root-level ``x.py`` and ``a/**/b.py`` reaches ``a/b.py``, matching
    the gitignore/globstar convention users write by reflex. The old
    local translator compiled ``**`` to ``.*``, which demanded at least
    one directory between the slashes and silently scoped gates out of
    root-level files.
    """
    return pathmatch.glob_to_regex(pattern)


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
    # #257: the rule contract in one paragraph — shown on the failure
    # line, so a rejected developer sees WHAT the gate demands without
    # opening the checker's source (JSON has no comments; label is one
    # line).
    description: str = ""
    needs: list[str] = field(default_factory=list)
    timeout_ms: int | None = None
    allow_failure: bool = False
    enabled: bool = True
    paths: list[str] = field(default_factory=list)
    # #407: an environment a gate cannot judge without (known: "network").
    # A failed gate that declares one is reported ENV-classified — the
    # verdict may be this machine's connectivity, not the tree.
    requires: list[str] = field(default_factory=list)
    # #403/#417: run ALONE — the scheduler drains every running gate
    # before starting this one and starts nothing else until it settles.
    # Two field-proven races die here: a gate whose case mutates the live
    # tree never overlaps a sibling's reads, and a heavy gate (a fresh
    # clone) never starves a tight-budget sibling's wall clock.
    exclusive: bool = False
    # Git hooks this gate rides (e.g. "pre-commit"): the hook runner runs
    # the gate against the index (--staged) with the SAME advisory/
    # blocking contract the DAG honors — the hook stopped hand-wiring
    # `gate || status=1`, which ignored allowFailure entirely.
    stages: list[str] = field(default_factory=list)


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
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raise ConfigError(f"{path} not found")
    except OSError as e:
        raise ConfigError(f"{path}: {e}")
    return load_config_from(raw, path)


def load_config_from(raw: bytes, path: str) -> tuple[dict[str, list[str]], list[Gate], int, str | None]:
    """Parse config BYTES (N8: the caller may have seal-verified this
    exact buffer already — parsing must not re-read the file)."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: {e}")

    raw = _require_object(parsed, "the config root")
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
        allowed_gate = {"id", "command", "label", "description", "needs",
                        "timeoutMs", "allowFailure", "enabled", "paths",
                        "stages", "requires", "exclusive"}
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
        stages = g.get("stages", [])
        known_stages = {"pre-commit", "pre-push"}
        if not isinstance(stages, list) or not all(isinstance(s, str) for s in stages):
            raise ConfigError(f"gate '{gid}': 'stages' must be an array of strings")
        bad_stages = sorted(set(stages) - known_stages)
        if bad_stages:
            raise ConfigError(f"gate '{gid}': unknown stage(s): {', '.join(bad_stages)} "
                              f"(known: {', '.join(sorted(known_stages))})")
        description = g.get("description", "")
        if not isinstance(description, str):
            raise ConfigError(
                f"gate '{gid}': 'description' must be a string")
        requires = g.get("requires", [])
        if not isinstance(requires, list) or not all(
                isinstance(r, str) for r in requires):
            raise ConfigError(
                f"gate '{gid}': 'requires' must be an array of strings")
        bad_requires = sorted(set(requires) - KNOWN_REQUIRES)
        if bad_requires:
            raise ConfigError(
                f"gate '{gid}': unknown requires value(s): "
                f"{', '.join(bad_requires)} (known: "
                f"{', '.join(sorted(KNOWN_REQUIRES))})")
        exclusive = g.get("exclusive", False)
        if not isinstance(exclusive, bool):
            raise ConfigError(f"gate '{gid}': 'exclusive' must be a boolean")
        gates.append(
            Gate(
                id=gid,
                command=command,
                label=label,
                description=description,
                needs=list(needs),
                timeout_ms=timeout,
                allow_failure=allow_failure,
                enabled=enabled,
                paths=list(paths),
                stages=list(stages),
                requires=list(requires),
                exclusive=exclusive,
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


DEFAULT_TIMEOUT_MS = 600_000
# The ledger's per-gate detail budget. #109 keeps the *report* unclipped —
# "why did it fail" is answered by one run — but the JSONL history line
# used to embed the same full output with no ceiling at all, so one
# chatty gate grew every future `gov run` and `gov trend`. A ceiling on
# the *record* (report untouched) bounds the growth; 0 disables.
HISTORY_DETAIL_CAP = int(os.environ.get("GOV_HISTORY_DETAIL_CAP", "262144"))
HISTORY_DETAIL_LINES = 40


def detail_clip(detail: str) -> str:
    """Ledger detail: the first HISTORY_DETAIL_LINES lines plus a count —
    a 300-line pairing failure used to embed 46KB per record (the
    ledger is trend data, not a full dump; the human report keeps the
    full output)."""
    lines = detail.splitlines()
    if len(lines) <= HISTORY_DETAIL_LINES:
        return detail
    kept = "\n".join(lines[:HISTORY_DETAIL_LINES])
    return (kept + f"\n... [{len(lines) - HISTORY_DETAIL_LINES} more "
            "line(s); the run report keeps the full output]")
HISTORY_ROTATE_BYTES = 50 * 1024 * 1024

# Popen handles of gates currently running, so --fail-fast can kill the
# whole pool instead of waiting out the stragglers.
_LIVE_PROCS: set = set()


def _kill_tree(proc: Any) -> None:
    """Kill a gate's process tree, not just its direct child.

    A timeout that kills only the direct child leaves any grandchild the
    gate spawned holding the output pipes — `communicate` then blocks on
    the orphans forever and ``timeoutMs`` never actually fires. POSIX:
    the gate runs in its own session, so the group dies together;
    Windows: ``taskkill /T`` walks the tree.
    """
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _selection_label(selected_by: str, changed: list[str] | None,
                     scoped_out: list[str] | None) -> str:
    """What the summary line counted (#355).

    The same tree answers ``8 gates: 8 pass`` under ``--base HEAD~1`` and
    ``12 gates: 12 pass`` bare. Both numbers are correct and unrelated,
    and read as a contradiction because the line never says which
    mechanism picked the set.
    """
    if selected_by == "every-gate":
        return "every enabled gate"
    if selected_by.startswith("mode:"):
        return f"mode: {selected_by.split(':', 1)[1]}"
    if selected_by.startswith("default-mode:"):
        return f"default mode: {selected_by.split(':', 1)[1]}"
    if selected_by.startswith("base:"):
        base = selected_by.split(":", 1)[1]
        n = len(scoped_out or [])
        return (f"path-scoped vs {base}"
                + (f", {n} gate(s) out of scope" if n else ""))
    if selected_by == "gate":
        return "one gate, named by --gate"
    if selected_by == "gates":
        # #405: a subset traversal names more than one gate.
        return "several gates, named by --gate"
    return "all enabled gates"


def _first_line(text: str) -> str:
    """The first non-blank line, trimmed — the summary's quoting unit."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


_DIAGNOSTIC_KEYS = ("summary", "error", "message", "detail", "reason",
                    "description", "finding")
_DIAGNOSTIC_CLIP = 200


def _compact(value: Any) -> str:
    """One diagnostic-worthy line out of a JSON value (#419)."""
    if isinstance(value, str):
        text = value.strip()
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            text = str(value)
    text = " ".join(text.split())
    return text[:_DIAGNOSTIC_CLIP] + ("…" if len(text) > _DIAGNOSTIC_CLIP
                                      else "")


def _json_kernel(text: str) -> str | None:
    """The actionable kernel of a JSON-emitting gate's output (#419).

    A gate whose report is JSON used to be quoted as its first line —
    `{` — with the actual finding invisible until the gate was re-run.
    When the output parses as one JSON value, quote what a human acts
    on: a known diagnostic field, else the first scalar field, else the
    first element of the first array (a broken-edge, a finding). None
    when the text is not JSON — the caller falls back to line quoting.
    """
    candidate = text.strip()
    if not candidate or candidate[0] not in "{[":
        return None
    try:
        doc = json.loads(candidate)
    except (ValueError, RecursionError):
        return None
    if isinstance(doc, dict):
        for key in _DIAGNOSTIC_KEYS:
            value = doc.get(key)
            if isinstance(value, (str, int, float, bool)):
                return f"{key}: {_compact(value)}"
        for value in doc.values():
            # A finding-shaped payload (brokenEdges, findings, drifts)
            # leads with its LIST — the first element is the actionable
            # kernel; scalars like host/version are context, not the
            # finding (#419).
            if isinstance(value, list) and value:
                return _compact(value[0])
        for key, value in doc.items():
            if isinstance(value, (str, int, float, bool)):
                return f"{key}: {_compact(value)}"
    if isinstance(doc, list) and doc:
        return _compact(doc[0])
    return None


def _diagnostic_line(text: str) -> str:
    """The one line the failure summary quotes (#419; stderr first per D26).

    Same polarity as before — stderr wins when it said anything — but a
    JSON-emitting gate's quote is now its kernel (first broken edge /
    first finding), not the first character of its payload.
    """
    source = text if text.strip() else ""
    if not source:
        return ""
    kernel = _json_kernel(source)
    if kernel is not None:
        return kernel
    for line in source.splitlines():
        stripped = line.strip()
        # A line that is only a JSON structural character carries no
        # finding — skip it so a pretty-printed payload falls through to
        # a content line instead of quoting `{`.
        if stripped and stripped not in ("{", "}", "[", "]"):
            return stripped
    return _first_line(source)


def _run_one(gate: Gate, live: set | None = None
             ) -> tuple[Gate, str, str, bool, int, str]:
    """Run one gate; return (gate, outcome, detail, blocking_failed,
    duration_ms, summary_line).

    A passing gate's output is kept as detail too: exit 0 with something
    to say (a warning, an advisory) must stay visible — passing never
    silences a gate (D20 amends D2's "passes are silent").

    ``summary_line`` — the one line the failure summary quotes (#341).
    Gates split two ways about where their blocking diagnostic lives:
    the task gate prints per-card status lines to stdout and its problems
    to stderr, the check gate prints findings to stdout and keeps stderr
    for fatal config errors. The plane's own convention (D26) puts the
    human report on stderr, so stderr wins when it said anything and the
    gate's stdout leads otherwise — quoting the combined first line made
    the summary name whichever status line happened to print first, and
    a voided card's story is not a diagnostic."""
    exe = gate.command[0]
    started = time.monotonic()
    # Resolve once and run the resolved path: on Windows a bare name like
    # "npm" resolves to npm.cmd, which CreateProcess will not execute —
    # the run used to die with a raw FileNotFoundError there.
    resolved = shutil.which(exe)
    command = gate.command
    if resolved is None and exe == "gov" and os.environ.get("GOV_BIN"):
        # #250: the hooks resolve gov for themselves (GOV_BIN → PATH →
        # python3 -m gov) and export the result; gate commands that name
        # `gov` inherit the same resolution instead of dying MISSING in
        # environments where the entry point is not on PATH.
        command = [*os.environ["GOV_BIN"].split(), *gate.command[1:]]
        resolved = shutil.which(command[0]) or command[0]
    if resolved is None:
        return gate, "MISSING", f"command not found: {exe}", True, 0, \
            f"command not found: {exe}"
    timeout_ms = gate.timeout_ms or DEFAULT_TIMEOUT_MS
    try:
        proc = subprocess.Popen(
            [resolved, *command[1:]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # Gate output is repo tooling output, UTF-8 by convention;
            # the locale codec must not crash the run on it (#168).
            encoding="utf-8", errors="replace",
            # Own session/process group: the kill below can reach the
            # gate's whole tree (M: subprocess-tree timeout).
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
    except OSError as exc:
        # Exec-format (no shebang), permission, ... — a gate that cannot
        # start is a gate outcome (MISSING), never a runner traceback.
        return gate, "MISSING", f"cannot execute {exe}: {exc}", True, 0, \
            f"cannot execute {exe}: {exc}"
    if live is not None:
        live.add(proc)
    timed_out = False
    try:
        try:
            out, err = proc.communicate(timeout=timeout_ms / 1000)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
            try:
                out, err = proc.communicate(timeout=5)
            except (subprocess.TimeoutExpired, ValueError):
                out, err = "", ""
    finally:
        if live is not None:
            live.discard(proc)
    duration_ms = int((time.monotonic() - started) * 1000)
    output = ((out or "") + (err or "")).strip()
    if timed_out:
        # communicate() already recovered whatever the gate printed before
        # the kill — a TIMEOUT with that evidence names what was seen
        # instead of a bare "exceeded Nms". Truncated: the report side of
        # a TIMEOUT is a lead, not the full dump (the JSON record clips
        # again at HISTORY_DETAIL_CAP).
        detail = f"exceeded {timeout_ms}ms"
        if output:
            detail += " — captured output:\n" + output[:2000]
            if len(output) > 2000:
                detail += "\n... (truncated at 2000 characters)"
        return gate, "TIMEOUT", detail, True, duration_ms, \
            (_first_line(output) or f"exceeded {timeout_ms}ms")
    if proc.returncode == 0:
        return gate, "PASS", output, False, duration_ms, ""
    # #109 failure-first: a failing gate's evidence is never clipped at
    # capture time — the full output flows to the report and the JSON
    # record, so "why did it fail" is answered by one run. Passing gates
    # keep their display-side budget instead (D20 tail-3).
    return gate, "FAIL", output, True, duration_ms, \
        _diagnostic_line(err if (err or "").strip() else out)


def _changed_files(base: str) -> list[str] | None:
    """Files changed against ``base`` (tracked diff + untracked); None on error.

    The listing is gitutil's: quotepath off and NUL-split, so a non-ASCII
    path reaches the ``paths`` matchers as itself instead of git's quoted
    octal escape (which scoped path-matched gates out silently).
    """
    files, error = gitutil.changed_files(base)
    if error is not None:
        print(f"gov run: --base {base!r} failed: {error}", file=sys.stderr)
        return None
    return files


def _name_omitted(gates: list[Gate], selection: list[str], what: str,
                  json_mode: bool = False) -> None:
    """Name enabled gates a mode does not select (#355).

    "12 gates" against a 13-gate file is the question the summary could
    not answer; it is also the disagreement behind #329/#339, where a
    mode-all receipt met a reader that expected every gate. One line, and
    only when something is actually omitted.
    """
    omitted = [g.id for g in gates if g.enabled and g.id not in set(selection)]
    if omitted:
        # --json keeps stdout to exactly one JSON value (D26): the prose
        # moves to stderr, same as every other pre-run line.
        print(f"gov run: {what} omits {len(omitted)} enabled gate(s): "
              f"{', '.join(omitted)} (--every-gate runs the full matrix)",
              file=sys.stderr if json_mode else sys.stdout)


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


def _heal_evidence_tracking(last_run_dir: Path) -> None:
    """#423: tracked evidence dirties every receipt the run records — a
    habitual ``git add -A`` tracked 25 ``.log.prev`` files in the field
    and the rotation then made the adopter's ledger 4/4 ``dirty=true``.
    Untrack the directory's contents from the index and ignore it, with
    a named notice; the staged removals ride the adopter's next commit
    (the same shape #353 used for the allocator locks, one level louder:
    here the artifact is a whole directory)."""
    try:
        ls = subprocess.run(
            ["git", "ls-files", "--", last_run_dir.as_posix()],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        if ls.returncode != 0 or not ls.stdout.strip():
            return
        rm = subprocess.run(
            ["git", "rm", "-r", "--cached", "-q", "--",
             last_run_dir.as_posix()],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        if rm.returncode != 0:
            print(f"gov run: cannot untrack tracked evidence under "
                  f"{last_run_dir.as_posix()}: {(rm.stderr or '').strip()}",
                  file=sys.stderr)
            return
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        root = (Path(top.stdout.strip()) if top.returncode == 0
                and top.stdout.strip() else Path.cwd())
        try:
            from . import atomicio as _atomicio
        except ImportError:  # direct-script execution (self-test scratch)
            import atomicio as _atomicio
        _atomicio.ensure_line(root / ".gitignore",
                              last_run_dir.as_posix() + "/")
        n = len(ls.stdout.splitlines())
        print(f"gov run: healed evidence tracking — {n} file(s) under "
              f"{last_run_dir.as_posix()} were tracked (an add -A habit "
              "captures the runner's own scratch, and the rotation then "
              "dirtied every receipt this run records); untracked them "
              "from the index — commit the removal and the .gitignore "
              "line")
    except OSError as e:
        print(f"gov run: evidence-tracking heal failed: {e}",
              file=sys.stderr)


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
    config_path: str = "gates.json",
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
    summaries: dict[str, str] = {}
    blocking: dict[str, bool] = {}
    durations: dict[str, int] = {}
    skipped_set: set[str] = set()

    indegree = {g.id: len([n for n in g.needs if n in selected_ids]) for g in selected}
    dependents: dict[str, list[str]] = {g.id: [] for g in selected}
    for g in selected:
        for dep in g.needs:
            if dep in selected_ids:
                dependents[dep].append(g.id)

    # The admission queue (#403/#417): gates start ONLY through pump(), so
    # an exclusive gate can hold the whole pool — it is admitted alone and
    # nothing else is admitted until it settles. The pool's internal queue
    # therefore always stays empty; `concurrency` bounds the running set.
    from collections import deque
    ready_q: deque = deque(g for g in selected if indegree[g.id] == 0)
    running: set[str] = set()

    with ThreadPoolExecutor(max_workers=concurrency or 1) as pool:
        pending: dict[Any, Gate] = {}

        def pump() -> None:
            """Admit ready gates under the exclusive lane's contract."""
            while ready_q:
                exclusive_running = any(
                    by_id[gid].exclusive for gid in running)
                if exclusive_running:
                    return  # an exclusive gate owns the pool until it settles
                head = ready_q[0]
                if head.exclusive:
                    if running:
                        return  # it runs alone: wait for the pool to drain
                    ready_q.popleft()
                    running.add(head.id)
                    pending[pool.submit(_run_one, head, _LIVE_PROCS)] = head
                    continue
                if len(running) >= (concurrency or 1):
                    return
                ready_q.popleft()
                running.add(head.id)
                pending[pool.submit(_run_one, head, _LIVE_PROCS)] = head

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
                    # #420: the reason rides the record — a reader of the
                    # JSON (or the skipped block below) learns WHY without
                    # re-deriving the DAG.
                    reason = f"needs failed: {', '.join(failed_needs)}"
                    outcomes[child] = "SKIP"
                    details[child] = reason
                    durations[child] = 0
                    skipped_set.add(child)
                    emit(f"SKIP {child} ({reason})")
                    settle(child)
                else:
                    ready_q.append(child_gate)

        pump()

        stop = False
        while pending and not stop:
            # FIRST_COMPLETED, not as_completed: a future enqueued by
            # pump() mid-loop was never visible to the as_completed
            # iterator created from the earlier snapshot, so a finished
            # child's dependents waited for the whole current generation
            # to drain before they could start (layer-serialized instead
            # of a live DAG). wait(FIRST_COMPLETED) re-reads `pending`
            # every turn: finish one gate, settle it, its dependents are
            # admitted immediately. --fail-fast semantics are
            # unchanged (blocking failure kills the pool below).
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            batch = [(pending.pop(fut), fut) for fut in done]
            for gate, fut in batch:
                running.discard(gate.id)
                g, outcome, detail, is_blocking, duration_ms, summary = \
                    fut.result()
                outcomes[g.id] = outcome
                details[g.id] = detail
                summaries[g.id] = summary
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
                    # Future.cancel() only reaches unstarted work; a gate
                    # already mid-run used to be waited out to the end.
                    # Killing the live process trees makes every running
                    # _run_one return immediately — fail-fast is fast.
                    for proc in list(_LIVE_PROCS):
                        _kill_tree(proc)
                    pending = {}
                    break
                settle(g.id)
            if not stop:
                pump()

    # #375: one run yields all the evidence — every gate's FULL output
    # lands in .gov/last-run/<gate>.log (gitignored), so a truncated
    # report view or a scrolled terminal never forces a re-run just to
    # read a failure. #394/#396: logs are ROTATED, never deleted — the
    # generation this run replaces (a stale gate's log, or a failing
    # gate's scene about to be overwritten by a passing rerun) moves to
    # <gate>.log.prev, so a transient crash survives the diagnostic
    # rerun that used to erase it.
    last_run_dir = Path(".gov") / "last-run"

    def _rotate(gid: str) -> None:
        old = last_run_dir / f"{gid}.log"
        if old.is_file():
            old.replace(last_run_dir / f"{gid}.log.prev")

    try:
        last_run_dir.mkdir(parents=True, exist_ok=True)
        _heal_evidence_tracking(last_run_dir)
        for stale in last_run_dir.glob("*.log"):
            if stale.stem not in outcomes:
                _rotate(stale.stem)
        for gid, detail in details.items():
            if detail:
                _rotate(gid)
                (last_run_dir / f"{gid}.log").write_text(
                    detail + ("\n" if not detail.endswith("\n") else ""),
                    encoding="utf-8")
    except OSError as e:
        print(f"gov run: cannot write .gov/last-run/ evidence: {e}",
              file=sys.stderr)

    failed = [gid for gid in outcomes if blocking.get(gid, False)]
    # A failing gate's evidence prints ONCE, in the body, under an
    # outcome-specific header (#317: the old summary reprinted the tail a
    # second time — long output read double). The summary keeps only the
    # one-line pointer with the rerun command — and, since #375, the
    # path of the full captured output.
    outcome_marks = {"FAIL": "failed", "TIMEOUT": "timed out",
                     "MISSING": "command missing"}
    for gid, outcome in outcomes.items():
        if outcome not in BLOCKING_OUTCOMES or not details[gid]:
            continue
        if blocking.get(gid, False):
            emit(f"--- output of {gid} ({outcome_marks[outcome]}) ---")
        else:
            # allowFailure: report loudly, block never (advisory, D2/D13).
            emit(f"--- output of {gid} ({outcome_marks[outcome]}; "
                 "advisory; allowFailure) ---")
        emit(details[gid])

    # A pass that said something (a warning, an advisory) stays visible:
    # head 2 + tail 3 lines, exit code and PASS outcome unchanged (D20;
    # #317: the head is kept because gates like note-presence print their
    # base= judgment as the FIRST line — a tail-only cap hid the verdict's
    # evidence while announcing it was hidden).
    for gid, outcome in outcomes.items():
        if outcome != "PASS" or not details[gid]:
            continue
        lines = details[gid].splitlines()
        shown = lines[:2] + lines[-3:] if len(lines) > 5 else lines
        shown = list(dict.fromkeys(shown)) if len(lines) > 5 else shown
        omitted = len(lines) - len(shown)
        emit(f"--- output of {gid} (passed with output) ---")
        emit("\n".join(shown))
        if omitted > 0:
            emit(f"... ({omitted} earlier line(s) not shown; full output: "
                 f"{(last_run_dir / (gid + '.log')).as_posix()})")

    if failed:
        by_gate = {g.id: g for g in gates}
        emit(f"--- summary: {len(failed)} blocking failure(s) ---")
        for gid in failed:
            # #341: the quote is the gate's diagnostic line (stderr first,
            # then stdout — see _run_one), never just its first status
            # line: a voided card's story line used to stand in for the
            # real blocking cause two hundred lines down. #419: a
            # JSON-emitting gate is quoted by its kernel, not `{`.
            first = summaries.get(gid) or ""
            # #109: the failure line itself names the rerun command — the
            # reader should not have to remember the flag exists. The
            # gate's own output printed once in the body above (#317);
            # the summary stays a pointer, not a reprint. #404: the wall
            # time rides the line, so "121s here, 69s standalone" is
            # readable without a manual rerun; #407: a gate that declared
            # an environment gets that named where the verdict lands.
            gate = by_gate[gid]
            notes = []
            if gate.requires:
                notes.append(f"requires {', '.join(gate.requires)} — the "
                             "verdict may be this machine's environment, "
                             "not the tree")
            if durations.get(gid, 0) >= 1000:
                # #404: the wall time rides the line when it can matter —
                # "121s here, 69s standalone" is the starvation tell; a
                # sub-second gate's 0.0s is noise, not evidence.
                notes.append(f"ran {durations[gid] / 1000:.1f}s")
            note = f" ({'; '.join(notes)})" if notes else ""
            line = f"{gid}: {first}" if first else f"{gid}:"
            emit(f"{line}{note} (rerun: gov run --gate {gid}; full output: "
                 f"{(last_run_dir / (gid + '.log')).as_posix()})")

    # #420: the skip set is named WHERE the counts are — a summary that
    # says "5 skip" without the names or the reasons sends the reader
    # scrolling (or diffing two runs) for what the runner already knew.
    skipped = [gid for gid in outcomes if outcomes.get(gid) == "SKIP"]
    if skipped:
        emit(f"--- skipped, not evaluated: {len(skipped)} gate(s) ---")
        for gid in skipped:
            emit(f"{gid} ({details.get(gid, 'a dependency did not pass')} — "
                 "SKIP is not evidence; fix the failed need and re-run)")

    if failed:
        emit(f"evidence: {last_run_dir.as_posix()}/<gate>.log holds each "
             "failing gate's full captured output; *.log.prev is the "
             "previous generation (#394: a transient crash survives the "
             "rerun)")
    counts = {o: sum(1 for v in outcomes.values() if v == o) for o in OUTCOME_ORDER}
    parts = [f"{n} {o.lower()}" for o, n in counts.items() if n]
    # #355: the count is qualified — a bare `N gates: N pass` is right and
    # unreadable (the same tree answers 8, 9 and 12 from three entry
    # points); the bracket names the mechanism that picked the set.
    label = _selection_label(selected_by, changed, scoped_out)
    emit(
        f"{len(outcomes)} gates: " + (", ".join(parts) if parts else "none ran")
        + f"  [{label}]"
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
        try:
            rec = receipt_mod.build_receipt(records, receipt.get("tag", ""),
                                            receipt.get("selection", {}),
                                            config_path=config_path)
        except receipt_mod.ReceiptError as exc:
            # A corrupt ledger tail must not bury this run's own report:
            # name the receipt failure, keep the exit code truthful.
            emit(f"receipt: skipped — the receipts ledger is unreadable ({exc})")
        except atomicio.SymlinkRefused as exc:
            emit(f"receipt: skipped — {exc}")
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
        if (record_path.stat().st_size if record_path.exists() else 0) \
                > HISTORY_ROTATE_BYTES:
            # One-generation rotation: the ledger stays append-only per
            # run, but a ledger with no ceiling at all grows forever; the
            # previous generation survives as <name>.1 for archaeology.
            # The rename-vs-append window stays (two concurrent runs can
            # straddle a rotation — the loser's record lands in the fresh
            # file) — a deliberate, tiny race: renaming under a lock would
            # buy atomicity the ledger does not need to stay truthful.
            record_path.replace(record_path.parent / (record_path.name + ".1"))
        run_record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "gates": [
                ({**r, "detail": detail_clip(r["detail"])}
                 if HISTORY_DETAIL_CAP and len(r.get("detail", "")) > HISTORY_DETAIL_CAP
                 else r)
                for r in records
            ],
        }
        if caller:
            run_record["caller"] = caller
        if cost:
            run_record["cost"] = cost
        # N6 follow-up: history must distinguish "green under the sealed
        # constitution" from "green under --config something-else".
        run_record["config"] = config_path
        # Single os.write over O_APPEND (not a TextIOWrapper append, whose
        # 8KB buffer could split one record into interleaved fragments
        # under concurrent runs): POSIX positions each write at EOF
        # atomically, so one encoded line lands whole.
        line = json.dumps(run_record, separators=(",", ":")).encode("utf-8") \
            + b"\n"
        # N10: the history ledger refuses a symlinked path — gate output
        # is plane data and must not be couriered outside the repository.
        # Trend data, not evidence (D44): a refused append warns and the
        # run continues; nothing was written anywhere.
        try:
            # the boundary is the ledger's own checkout (structural:
            # <main>/.gov/history/gates.jsonl), not the protected path's
            # opinion of its repository — a linked directory would make
            # git's walk-up answer for the attacker (N15)
            atomicio.assert_contained(
                record_path, root=anchor_mod.ledger_root(record_path))
            fd = os.open(record_path,
                         os.O_WRONLY | os.O_CREAT | os.O_APPEND
                         | getattr(os, "O_NOFOLLOW", 0), 0o644)
            try:
                data = line
                while data:  # partial writes: each retry re-appends at EOF
                    data = data[os.write(fd, data):]
            finally:
                os.close(fd)
        except atomicio.SymlinkRefused as e:
            print(f"gov run: {e} — this run is NOT recorded",
                  file=sys.stderr)
    if rec is not None:
        target = receipt_path if receipt_path is not None \
            else receipt_mod._receipt_path()
        # #10: the chain head is re-read and the append happens under one
        # guard flock in receipt.append_receipt — building the receipt
        # earlier (pre-gates) read the same head for concurrent runs, and
        # the second record broke the chain for every later verify.
        try:
            rec = receipt_mod.append_receipt(rec, target)
        except (receipt_mod.ReceiptError, atomicio.SymlinkRefused) as exc:
            # a receipt that cannot append is not taken — named here,
            # never faked; a symlinked ledger also means nothing leaked
            emit(f"receipt: skipped — the receipts ledger refused the "
                 f"append ({exc})")
        else:
            commit = rec.get("commit") or "?"
            state = " (dirty tree — will not verify as this commit)" \
                if rec.get("dirty") else ""
            emit(f"receipt: {rec['id']} recorded against {commit}{state} "
                 f"(cite it: gov receipt verify <commit>)")
    return 1 if failed else 0


def _outcome_line(gate: Gate, outcome: str, in_scope: int | None = None) -> str:
    parts = []
    if gate.allow_failure and outcome in BLOCKING_OUTCOMES:
        parts.append("(advisory; allowFailure)")
    if gate.requires and outcome in BLOCKING_OUTCOMES:
        # #407: the environment classification lands where the verdict
        # does — a red network-bound gate reads as ENV-possible, not as
        # a tree defect, without opening gates.json.
        parts.append(f"[requires {', '.join(gate.requires)} — ENV-possible]")
    if in_scope is not None:
        # #21/D32: a scan over zero matched files must not read like a
        # scan. #317: the count is self-explaining — these are the diff's
        # files the gate's `paths` matched, not an abstract "scope".
        parts.append(f"({in_scope} file(s) in scope)" if in_scope
                     else "(0 files in scope — nothing changed matches)")
    if outcome != "PASS" and gate.description:
        # #257: say WHAT the gate demands, right where the rejection lands
        parts.insert(0, f"— {gate.description}")
    return f"{outcome} {gate.id}" + (" " + " ".join(parts) if parts else "")


def _plane_precheck(tool: str = "gov run", config_rel: str | None = None,
                    config_raw: bytes | None = None,
                    allow_unsealed_config: bool = False) -> None:
    """Out-of-band seal check, BEFORE the config is trusted (the
    reflexive gap, N1): the in-DAG `plane` gate is defined inside the
    very file it seals, so a tampered gates.json could disable that
    gate and silence its own detection. This check reads the seal and
    the config BYTES directly and needs nothing from gates.json to
    judge them — pre-push, CI, task close, and manual runs all pass
    through here, so the tamper-evidence no longer depends on any
    runner remembering to add a step. A plane config without its seal
    is drift too (N2: deleting the ledger is the attack one level up);
    a recorded config edit is accepted via the explicit
    `gov verify-plane --write` re-baseline, exactly like the gate's."""
    try:
        from . import verify_plane
    except ImportError:  # direct-script execution (self-test scratch)
        import verify_plane
    overlays = None
    if config_rel and config_raw is not None:
        # N8: the caller's buffer IS the config — the seal is judged over
        # these exact bytes and the parser reuses them, closing the
        # parse-read/seal-read TOCTOU window.
        overlays = {config_rel: config_raw}
    drift = verify_plane.violations(overlays=overlays)
    if drift:
        print(f"{tool}: REFUSED — the governance plane drifted from its "
              f"seal (checked out-of-band, before this config was trusted):",
              file=sys.stderr)
        for d in drift:
            print(f"  {d}", file=sys.stderr)
        print("  restore the files (git checkout) or accept the new state "
              "explicitly: gov verify-plane --write", file=sys.stderr)        # #259: the refusal must be self-explaining across versions — a
        # checkout initialized with an older plane (whose CI pin also
        # names that older version) hits this the day the mechanism
        # itself moves. Say which side is which instead of assuming the
        # running binary is the newest thing in the room.
        try:
            manifest_version = json.loads(
                Path(".gov", "manifest.json").read_text(encoding="utf-8")
            ).get("version")
        except (OSError, ValueError):
            manifest_version = None
        if manifest_version and manifest_version != __version__:
            print(
                f"  note: this plane was initialized with govrail "
                f"{manifest_version}; you are running {__version__} — "
                "the CI pin should match the manifest, and `gov init "
                "--upgrade` shows what changed",
                file=sys.stderr)
        raise SystemExit(1)
    # #311: a recent re-baseline must be SEEN — the reset itself is a
    # recorded ritual, but a ritual nobody hears about does not raise the
    # cost of a rogue re-seal. Announced in the run header, advisory, and
    # ONCE per record (#337: a note repeated on every run stops being a
    # note — the ledger keeps the long form, `gov verify-plane` the detail).
    verify_plane.announce_rebaselines(tool)
    # N6: --config pointing outside the sealed set opts out of everything
    # the seal just verified. In a governed repository that is a
    # recorded-decision-level change, not a flag.
    if config_rel is not None and config_rel not in (
            "gates.json",) and not allow_unsealed_config:
        from .verify_plane import _sealed_files
        governed = _sealed_files(Path.cwd()) or (Path.cwd() / ".gov" / "rules.md").is_file()
        if governed and Path(config_rel).resolve() != (Path.cwd() / "gates.json").resolve():
            print(f"{tool}: REFUSED — --config {config_rel!r} is outside the "
                  "sealed plane. A governed repository runs its sealed "
                  "gates.json; to bless another config, seal it or pass "
                  "--allow-unsealed-config (recorded in the run history).",
                  file=sys.stderr)
            raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()  # reports leave as UTF-8 on every OS (#168)
    # #13: `gov run` was the one command that skipped the root anchor —
    # gates.json, the seal precheck, and .gov/history all resolve against
    # cwd, so a subdirectory invocation read the wrong (or no) config and
    # recorded history outside the plane's ledger. Anchoring first also
    # means a relative --config resolves from the repo root, which is the
    # wanted behavior.
    anchor_to_git_root("gov run")
    parser = argparse.ArgumentParser(prog="gov run", description="Run the governance gate DAG.")
    parser.add_argument("--config", default="gates.json")
    parser.add_argument("--allow-unsealed-config", action="store_true",
                        help="run with a --config outside the sealed plane "
                             "(recorded in the run history and receipt)")
    parser.add_argument("--mode", default=None,
                        help="mode name from gates.json (overrides defaultMode)")
    parser.add_argument("--base", default=None,
                        help="select gates whose 'paths' match the diff against this git ref; "
                             "with --merge: the integration target baseline instead "
                             "(default origin/master)")
    parser.add_argument("--gate", nargs="+", default=None, metavar="GATE_ID",
                        help="run these gate(s) by id, space-separated "
                             "(#405: one DAG traversal for a subset — "
                             "`--gate closures bundle-files`; a shipped "
                             "integration already passes two)")
    parser.add_argument("--at", default=None, metavar="REF",
                        help="judge the selected gate(s) against the tree "
                             "as-of this ref (#406): a detached temporary "
                             "worktree is materialized and the run happens "
                             "inside it, so gate triage never needs a "
                             "checkout; history and receipts are not "
                             "recorded (the evidence would die with the "
                             "worktree)")
    parser.add_argument("--only-paths", default=None, metavar="GLOB,...",
                        help="judge only what these globs carry (#374): the "
                             "changed-file set is intersected with the list "
                             "and path-scoped gates select against THAT — a "
                             "multi-worker checkout scopes a run to one "
                             "worker's paths; the union is still verified at "
                             "push. The declared set is exported to the gates "
                             "as GOV_CHANGE_PATHS (root-guarded)")
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
                             "to stderr. WITHOUT --json, stdout carries the "
                             "human report (the documented polarity; errors "
                             "are always stderr)")
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
            (args.at, "--at"),
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

    # #406: --at materializes the ref's tree into a detached temporary
    # worktree and the rest of this function runs INSIDE it — config,
    # seal precheck, anchors, and the gates themselves all read the
    # judged tree, so a CI-red gate is reproduced exactly without a
    # checkout on a shared worktree. Refusals: --receipt (the receipt
    # and the evidence directory would die with the worktree — a citation
    # that cannot verify is worse than none) and a ref that is not a
    # commit. History recording is skipped for the same lifetime reason,
    # said out loud once.
    if args.at:
        if args.receipt:
            print("gov run: --at and --receipt cannot be combined — a "
                  "receipt and its evidence would die with the temporary "
                  "worktree", file=sys.stderr)
            return 2
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", f"{args.at}^{{commit}}"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        if proc.returncode != 0:
            print(f"gov run: --at {args.at!r} is not a commit git can "
                  f"resolve: {(proc.stderr or '').strip().splitlines()[-1] if (proc.stderr or '').strip() else 'unknown error'}",
                  file=sys.stderr)
            return 2
        at_sha = proc.stdout.strip()
        import atexit
        import tempfile
        wt = tempfile.mkdtemp(prefix="gov-at-")
        proc = subprocess.run(
            ["git", "worktree", "add", "--detach", wt, at_sha],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        if proc.returncode != 0:
            print(f"gov run: --at could not materialize a worktree at "
                  f"{at_sha[:12]}: {(proc.stderr or '').strip()}",
                  file=sys.stderr)
            return 2
        original_cwd = Path.cwd()

        def _remove_at_worktree() -> None:
            os.chdir(original_cwd)
            subprocess.run(
                ["git", "worktree", "remove", "--force", wt],
                capture_output=True)
            shutil.rmtree(wt, ignore_errors=True)

        atexit.register(_remove_at_worktree)
        os.chdir(wt)
        args.no_record = True
        print(f"gov run: --at {args.at} ({at_sha[:12]}) — judging a "
              "temporary worktree; history is not recorded",
              file=sys.stderr)

    # N8: ONE read of the config bytes; the seal is verified over this
    # exact buffer BEFORE parsing, so a drifted constitution refuses as
    # the plane (1) even when it is also syntactically broken, and a
    # concurrent writer cannot split "tampered bytes parsed / clean
    # bytes seal-checked".
    try:
        config_raw = Path(args.config).read_bytes()
    except FileNotFoundError:
        print(f"config error: {args.config} not found", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"config error: cannot read {args.config}: {e}", file=sys.stderr)
        return 2
    try:
        config_rel = Path(args.config).resolve().relative_to(
            Path.cwd().resolve()).as_posix()
    except ValueError:
        config_rel = Path(args.config).resolve().as_posix()
    _plane_precheck(config_rel=config_rel, config_raw=config_raw,
                    allow_unsealed_config=args.allow_unsealed_config)
    if args.allow_unsealed_config:
        # N9: the ritual's evidence must live in TRACKED storage — the
        # gitignored run history is deletable without git residue. The
        # ledger is tracked, so the append is a visible working-tree
        # change; if it cannot be recorded, the ritual is refused
        # (an unrecorded bypass is worthless — rule 5).
        try:
            from . import rituals
        except ImportError:  # direct-script execution
            import rituals
        try:
            rituals.append(config_rel=config_rel, ritual="unsealed-config")
        except OSError as e:
            print(f"gov run: REFUSED — the unsealed-config ritual could "
                  f"not be recorded in the tracked ledger: {e}",
                  file=sys.stderr)
            return 2
        print(f"gov run: ritual recorded — unsealed config "
              f"{args.config!r} executed by caller "
              f"{rituals._identity()} (see .gov/rituals.jsonl, tracked)",
              file=sys.stderr)
    try:
        modes, gates, concurrency, default_mode = load_config_from(
            config_raw, args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    explicit = [flag for flag, on in (("--gate", args.gate), ("--mode", args.mode),
                                      ("--base", args.base), ("--every-gate", args.every_gate),
                                      ("--only-paths", args.only_paths)) if on]
    if len(explicit) > 1:
        print(f"gov run: {' and '.join(explicit)} cannot be combined", file=sys.stderr)
        return 2

    selection = None
    scoped_out_ids: list[str] = []
    # #119: name the mechanism that picked the gate set, so a JSON reader
    # can tell "mode ci chose 5 gates" from "the diff scoped 3 out".
    selected_by = "all-enabled"
    if args.gate:
        # #405: a subset in ONE DAG traversal — the shipped integrations
        # already pass two ids, and N separate traversals re-pay the DAG
        # N times. Unknown and parked ids are refused by NAME (a typo in
        # the second id must not read as a green first one).
        gate_ids = list(dict.fromkeys(args.gate))
        known = {g.id for g in gates}
        unknown = [gid for gid in gate_ids if gid not in known]
        if unknown:
            print(
                f"gov run: unknown gate(s): {', '.join(unknown)} "
                f"(known: {', '.join(sorted(known)) or 'none'})",
                file=sys.stderr,
            )
            return 2
        by_id = {g.id: g for g in gates}
        parked = [gid for gid in gate_ids if not by_id[gid].enabled]
        if parked:
            # N4/D24: explicitly naming a parked gate is operator error —
            # a silent green hides it. Parking is visible; so is this.
            print(
                f"gov run: gate(s) disabled — {', '.join(parked)}: "
                "re-enable or pick another",
                file=sys.stderr,
            )
            return 2
        selection = gate_ids
        selected_by = "gate" if len(selection) == 1 else "gates"
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
        _name_omitted(gates, selection, f"mode '{args.mode}'", args.json)
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
    elif args.only_paths:
        # #374: the changed set (the auto cascade — working tree when
        # dirty, the unpushed range when clean) is intersected with the
        # declared globs, and path-scoped gates select against THAT.
        # Unpathed gates still run: they judge the repository, not a
        # file set. A declared intersection that keeps NOTHING is a
        # caller typo, not a green zero (rule 5).
        globs = [g.strip() for g in args.only_paths.split(",") if g.strip()]
        if not globs:
            print("gov run: --only-paths: empty glob list", file=sys.stderr)
            return 2
        changed_all = _changed_files("HEAD")
        if changed_all is None:
            return 2
        from .pathmatch import glob_to_regex
        kept = []
        for f in changed_all:
            parts = f.replace("\\", "/").split("/")
            for g in globs:
                rx = glob_to_regex(g)
                if rx.match(f) or ("/" not in g and rx.match(parts[-1])):
                    kept.append(f)
                    break
        if not kept:
            print(f"gov run: --only-paths {args.only_paths!r}: none of the "
                  f"{len(changed_all)} changed file(s) match — a scoped run "
                  "that would judge nothing is a typo, not a pass "
                  "(rule 5)", file=sys.stderr)
            return 2
        selection, scoped_out_ids = _select_by_paths(gates, kept)
        selected_by = f"only-paths:{len(kept)}-file(s)"
        os.environ["GOV_CHANGE_PATHS"] = ",".join(globs)
        os.environ["GOV_CHANGE_ROOT"] = str(Path.cwd().resolve())
        scope_line = (
            f"scope --only-paths: {len(kept)}/{len(changed_all)} changed "
            f"file(s) in {', '.join(globs)}; {len(selection)} gate(s) "
            "selected (unpathed gates judge the repository)"
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
        _name_omitted(gates, selection, f"the default mode '{default_mode}'", args.json)
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
                     cost=cost, config_path=args.config)


if __name__ == "__main__":
    raise SystemExit(main())
