# Agent Note: machine surfaces tell the truth: check --json self-identifies, the failure summary quotes the diagnostic, pairing/task stamps say what they mean

Status: implemented

Related: D25, D26, D20

## Problem

Four surfaces described reality worse than the code behind them behaves.

- `gov check --json` (#349) carried findings but not the verdict or the
  judged set's identity: a consumer could not see WHY a scope was what
  it was (the cascade's reason the text prints), whether the run
  blocked (only derivable by recomputing from counts), or WHICH files
  the scope contained (only the count) — so two invocations on
  different cascade states look identical in JSON while judging
  different trees, which is how the "JSON contradicts the text report"
  report actually happened: the blocking run and the JSON run resolved
  different scopes, and nothing in the JSON said so.
- The runner's failure summary (#341) quoted the first line of the
  gate's combined stdout+stderr. A gate whose per-item status lines
  print to stdout (task: `voided T-0001 <story>`) and whose blocking
  diagnostic goes to stderr got its story quoted as the failure; the
  real cause sat hundreds of lines up in truncated output.
- `gov verify pairing --write` (#345a) printed `en_commit: untracked`
  to stdout but wrote a bare empty scalar into the record — a value
  that read like corruption and grepped for nothing, though the record's
  own NOTE text already promised the stamp reads 'untracked'.
- `gov task void`/`close` (#345b) mutated a tracked card and said so,
  but never said the mutation was uncommitted — in the
  void-before-push ritual the pushed tree carried a stale card until an
  unprompted follow-up commit.

## Decision

- `gov check --json` gains `base_why` (the cascade's reason, or
  "explicit --base"; null on a whole-tree sweep), `scope_files` (the
  sorted judged set, capped at 500 with an explicit
  `scope_files_truncated` flag — named, never silently clipped),
  `excluded` (the exclusion ledger), and `ok` — the exit-code verdict
  stated in the payload. A pinned test holds the real contract the
  issue asked for: within one invocation the text findings and the JSON
  files array derive from the same run and cannot contradict.
- `_run_one` keeps the streams apart and returns a summary line:
  stderr's first non-blank line, falling back to stdout's (D26 put the
  human report on stderr; gates that predate it print findings to
  stdout with a silent stderr on failure, so the fallback quotes the
  finding). The failure summary quotes that line — TIMEOUT falls back
  to its captured output's lead. `detail` stays the combined streams,
  so the D25 JSON record shape is unchanged for consumers.
- The pairing record writes `untracked` for a side with no commit, and
  its header comment says so.
- `task void`/`close` append `task: card mutation is uncommitted —
  commit it before pushing so the pushed tree carries the exit` when
  `git status --porcelain` names the card; quiet when git reports it
  clean (e.g. ignored) or outside a repository.

## Alternatives considered

- **A phrase-mode flag on recall-style "keep the query literal"**
  grounds — not this note. For #349 the alternative was declaring the
  JSON correct and closing as works-as-intended: rejected, because the
  reporter's mechanism (two runs, two scopes, indistinguishable JSON)
  is real even though a same-run contradiction is not; a surface that
  cannot say what it judged invites exactly the false contradiction
  report.
- **Quoting the LAST line of combined output** — rejected: `gov check`
  ends on the scope line, which names no finding; stream-aware beats
  position-guessing.
- **A `problem:` prefix convention gates must adopt** — rejected for
  now: it asks every gate (including adopter-wired ones) to change
  output for the runner's benefit; stderr-first needs zero gate changes
  and matches the convention half the gates already follow. A gate that
  prints noise to stderr AND its failure to stdout would misquote —
  none of the shipped gates does, and the fallback covers the reverse.
- **Machine marker instead of the literal `untracked`** (e.g. `null`) —
  rejected: the record is hand-readable YAML whose stdout already says
  `untracked`; one spelling everywhere is the point.
- **Printing the reminder unconditionally** — rejected: a constant line
  is noise the second time it is wrong; the porcelain probe makes it
  evidence.
