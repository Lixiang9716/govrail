# Agent Note: the parse layer ships every tree-sitter grammar — 39 packs, a declared factory, and the footprint stated out loud

Status: implemented

Related: D54, issues #335, #342, #351

## Problem

"Language-agnostic" was true of the governance machinery and only half
true of the code-facts layer: ten grammars shipped, so an adopter whose
tree is Kotlin or Swift — or PHP, Ruby, C#, Lua, Elixir, Scala, Zig,
Dart, Haskell, Julia, PowerShell, Objective-C, OCaml, Nix, Solidity,
TLA+, Fortran, Ada, CUDA, Groovy, Bash — got either a silent skip or a
language-blind fallback counter. The shape repeated every time: a size
gate declares limits for the whole repo, the parse layer cannot read a
language, and the limits quietly do not apply there. Two adopters filed
that as #335 (Swift) and #342 (Kotlin); the general form is "the plane
covers the languages it happened to ship yesterday".

## Decision

- **The parse layer now ships 39 packs**, i.e. every tree-sitter grammar
  whose wheels cover the platform matrix the project itself verifies:
  linux glibc x86_64/aarch64, macOS x86_64/arm64, Windows amd64. That is
  the previous ten plus twenty-nine: ada, bash, c-sharp, css, cuda, dart,
  elixir, embedded-template, fortran, groovy, haskell, hcl, html, json,
  julia, lua, make, markdown, nix, objc, ocaml, php, powershell, ruby,
  scala, solidity, sql, svelte, tlaplus, toml, yaml, zig (thirty-two
  packages total, one per language; `gov stats` names the set).
- **Excluded, with the reason**: `perl` (no macOS x86_64 wheel),
  `dockerfile` (2 of 7 platforms), `cmake` and `graphql` (1 of 7), plus
  `solidity` and `tlaplus` — whose wheels INSTALL on Windows but cannot
  be loaded there. The cause is a shape, not bad luck: a grammar whose
  factory returns a raw POINTER int works on Linux and macOS and dies on
  Windows, where the binding's `c_ulong` is 32-bit and a 64-bit pointer
  overflows (`OverflowError: Python int too large to convert to C
  unsigned long`). Every shipped grammar returns a PyCapsule, and a
  local test now asserts exactly that — the class is caught before CI
  instead of one grammar per CI round. Each is one `pip` gap
  away from joining — the packs are ~10 lines each — and naming them
  here is what keeps the omission a decision instead of an oversight. The one covered platform gap that remains is Kotlin's
  musl-aarch64 wheel (source build there), stated in the previous note.
- **Packs declare their factory when the binding does not ship
  `language()`**: php ships only `language_php`/`language_php_only` and
  ocaml only `language_ocaml`/`_interface`/`_type`. A new optional
  `factory` pack key names it; the guess-the-name chain stayed as the
  fallback for the dialects that do ship `language`.
- **Axes are what the language HAS, not what the schema wants**: a
  stylesheet has nesting and strings and no functions; bash has no
  classes; markdown has neither comments nor strings in its grammar, so
  its pack carries globs and exclusions and nothing else — a line-facts
  pack, declared as such in `LINE_FACTS_ONLY` with its reason rather
  than silently exempted. Nothing in the plane reads a zero as
  "missing"; the `rule` echo on every stats row says which kinds were
  counted.
- **Every pack is proven against its language as WRITTEN**: a 39-entry
  fixture table parses one tiny valid snippet per language and asserts
  zero ERROR/missing nodes plus at least one span from the pack's own
  `functions` kinds. That catches the failure the load-time kind check
  cannot: a kind that EXISTS but that ordinary code never produces
  (OCaml's `let f x = …` is a `value_definition`, not a `function` —
  found this way, not by review).
- **The footprint is stated, not discovered later**: 42 grammar
  dependencies install to about 96 MB (largest: ocaml 13, cuda 7.2,
  julia 6.8, fortran 6.7, c-sharp 6.1, objc 5.5, tlaplus 5.2, haskell
  4.3). That is a real cost against the "light" posture, and it is the
  maintainer's to spend: the eight heaviest are ~55 MB of it if a trim
  is ever wanted, and removing a language is one dependency line plus
  one pack file. `gov stats` on this repository with 39 packs runs in
  ~1.1 s.
- README (both sides) states thirty-nine grammars and the
  packs-vs-rules axis; the docker e2e scenario pins the shipped set by
  NAME (a vanished pack and a silently-arrived one are both
  regressions).

## Alternatives considered

- **Ship only languages adopters asked for** — rejected as a policy:
  "we shipped what was asked" is exactly how the ten-grammar gap grew;
  the language list should follow the parse layer's capability, not the
  order in which issues arrived.
- **Keep the biggest grammars optional (`govrail[langs-heavy]`)** —
  rejected: D54 already refused optional parse dependencies (a fail-loud
  path on every parse feature, a second install step), and an extra
  would make the shipped language set differ between installs, which is
  worse for a governance tool than a bigger install.
- **Patch the packs by pattern-selecting kinds from each grammar's kind
  table alone** — rejected after doing it as a DRAFT: names like
  `function` exist in several grammars where they are not what a size
  gate means (OCaml), and `case`/`if` are statement kinds in some
  grammars and expressions in others. The table was generated, then
  every axis was reviewed against a snippet; the snippet now lives in
  the test so the review cannot rot.
- **Skip markup and data formats (css, html, json, yaml, toml, make,
  markdown, sql, embedded templates, svelte)** — considered, because
  they add no function spans: kept anyway, since `gov stats`/`gov parse`
  line facts are what a repo-wide size gate reads for them, and their
  absence would recreate the same silent skip one format over. Their
  axes are honest zeros, and the ones with no axes at all are declared
  line-facts-only.
- **Vendor the grammars or build them at install time** — rejected:
  that trades maintained wheels for a build pipeline the project does
  not have and breaks the abi3 story D54 rests on.
