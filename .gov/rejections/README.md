# Project rejection cases

Rule 6: a gate that never fails is a vacuous script. Every project-defined
gate in `gates.json` ships a rejection case proving it can go red — and
this directory is where that proof runs.

## The contract

- Every **executable** file under this directory runs as part of
  `gov self-test`, with the repository root as the working directory.
- **Exit 0** = the rejection proof holds (your gate went red when it
  should have). **Non-zero** = the self-test fails, naming the file.
- One case per file, any executable language (`case-*.sh`, `case-*.py`, …).
- Files named `README*` are skipped.
- **Declaring its gate**: a `# gate: <id>` comment within the first five
  lines maps the case to the gate it proves — `id` being a gate id from
  `gates.json`. A line inside a module docstring counts (the ledger
  scans the first five lines of text, not the comment layer); keep the
  shebang on line 1. A case that runs without a declaration is named,
  with this same fix printed inline (#167).
- **Budget**: each case gets 10 seconds — a rejection proof is small by
  nature. A case that overruns is failed as `(timed out after 10s)`; a
  runaway case must not hold a CI job hostage. If your proof vehicle is
  an artifact that is expensive to produce (a linked binary, a fetched
  fixture), do not build it in the case — check for its presence and
  **skip loudly** when absent (`echo "SKIP — build/cli absent on this
  runner; the gate builds and proves on demand" >&2; exit 0`), and let
  the gate itself perform the build inside its own `--timeout`. A
  recognized `SKIP` marker on the case's first output line is surfaced
  as its own report line.

## This directory is part of the constitution

Adding or changing any file here is a **plane change**: the whole
directory is sealed, so the next `gov run` refuses until the plane is
re-sealed (`gov verify-plane --write`, which needs an interactive
terminal, or `--confirm-unattended --reason <authority>` from an agent
or CI). Write the case, run it once by hand to see it hold, then
re-seal — in that order, so the seal never blesses an unproven case.

## Notes

- The report counts `tools` (govrail's built-ins) and `project` (yours)
  separately: `gov self-test --scope project` runs only yours.
- Keep cases in git — and note that `gov uninstall` removes `.gov/`
  entirely, so anything you want to survive an uninstall/reinstall cycle
  belongs in the repository history, which git already gives you.
