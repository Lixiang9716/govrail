# Agent Note: Swift and Kotlin grammars join the parse layer — grammar first, rules only when they can be honest

Status: implemented

Related: D54, issues #335, #342, #351

## Problem

The parse layer shipped eight grammars (c, cpp, go, java, javascript,
python, rust, typescript) and nothing for Swift or Kotlin, so two
languages adopters actually write were structurally invisible:

- An adopter's `code-size` gate declares `file<=500 / func<=50 /
  indent<=5` for its whole tree, but `.swift` files were skipped with
  `no shipped grammar matches` — the limits were enforced on paper and
  nowhere else (#335). Kotlin got the gate's language-blind fallback
  instead, which counts every code line's indentation and so flags
  idiomatic closure chains at depths no brace-logic language reaches
  (#342). Both reports came from the same repository.
- `gov parse` — the primitive a size gate declares its limits against —
  could not see either language, because it walked the RULES-bearing
  language set (the shipped `gov/checks/<lang>.json` files) rather than
  the installed packs. `gov stats` walked the packs; the two commands
  disagreed about what "supported" means, and the disagreement was
  invisible until a language had a grammar and no rules.

## Decision

- `tree-sitter-swift` and `tree-sitter-kotlin` join the base
  dependencies, and `gov/langs/swift.json` + `gov/langs/kotlin.json`
  join the packs. Every node kind a pack names is validated against the
  grammar's kind table at load (D54's rule), so a wrong kind refuses to
  load rather than zeroing a metric silently. The Swift pack counts
  closures as function bodies and `if/for/while/repeat/switch/do/guard`
  as nesting; the Kotlin pack counts `when`/`try` expressions, which are
  that grammar's control flow.
- **No check rules ship for either language.** The Swift grammar parses
  the language well, but `tree-sitter-kotlin` mis-parses `object` and
  `interface` declarations (verified: an `object Single { … }` block
  lands in an ERROR node), so a shipped `parse-errors` rule would
  manufacture red on correct Kotlin — the ArkTS lesson (#343) applied
  before the mistake instead of after. Grammar first, rules only when
  they can be honest; the check gate keeps naming `.swift`/`.kt` as
  `SKIP(nolang: …)` (a declared skip, not silence).
- **`gov parse` walks every installed pack**, the same set `gov stats`
  walks — not the rules-bearing set. Parsing structure facts and judging
  syntax rules are two axes, and a size gate needs the first one exactly
  where the second does not exist yet. `--lang` still narrows it; the
  help text names the pack set it actually walks.
- README (both sides) states ten grammars and the axis distinction;
  known-answer fixtures land for both languages (hand-counted depths and
  spans: `if→for→while` = 3, a lone `if` = 1), plus a pack-integrity
  walk that loads every installed pack so a shipped pack cannot rot
  between releases.

Wheel availability was verified before any code, per D54's bar:
`tree-sitter-swift` 0.7.3 ships abi3 wheels for every target in the
matrix (macOS both, manylinux both, musllinux both, Windows both);
`tree-sitter-kotlin` 1.1.0 covers all of those EXCEPT musllinux
aarch64, where pip falls back to the sdist and needs a Rust toolchain.
That gap is documented here rather than hidden: Alpine on ARM is the one
platform where the Kotlin half of the pack set costs a build step, and
the plane's own CI (linux glibc/musl x86_64, macOS, Windows) is
unaffected.

## Alternatives considered

- **Swift only, Kotlin later** — rejected: the wheel gap is one target
  (musl-aarch64) and the alternative is leaving Kotlin on the
  language-blind counter that #342 is about; a documented caveat on an
  exotic target beats a language structurally out of the contract.
- **Ship check rules too (parse-errors at least)** — rejected on
  evidence: the Kotlin grammar's `object`/`interface` gap would fail
  correct code, and a gate that goes red on correct code is the one
  failure mode adopters cannot argue with.
- **Keep `gov parse` scoped to rules-bearing languages and add a rule
  file per new language just to unlock it** — rejected: it inverts the
  dependency (rules exist to judge; packs exist to read), and it would
  have forced the Kotlin parse-errors rule this decision just refused.
- **Wait for a Kotlin grammar version with the musl-aarch64 wheel** —
  rejected as the gate for shipping: it would hold Swift (fully covered)
  hostage to Kotlin's one gap; the caveat is stated instead.
- **Vendor the grammars' C sources into the wheel** — rejected: it
  trades a maintained dependency for a build pipeline the project does
  not have, and it breaks the abi3 story D54 rests on.
