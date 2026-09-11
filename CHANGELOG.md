# Changelog

## [0.29.4](https://github.com/Lixiang9716/govrail/compare/v0.29.3...v0.29.4) (2026-09-11)


### Bug Fixes

* self-test's undeclared-case warning prints the remedy inline ([#167](https://github.com/Lixiang9716/govrail/issues/167)) ([#177](https://github.com/Lixiang9716/govrail/issues/177)) ([5464adb](https://github.com/Lixiang9716/govrail/commit/5464adb23cff475b9bcb51c3fde39052188e7d93))

## [0.29.3](https://github.com/Lixiang9716/govrail/compare/v0.29.2...v0.29.3) (2026-09-07)


### Bug Fixes

* pytest suite joins the windows CI job — portable fixtures, named skips ([#168](https://github.com/Lixiang9716/govrail/issues/168) follow-up) ([0216de1](https://github.com/Lixiang9716/govrail/commit/0216de194266710e2b98caf03d0003e0b418ed41))

## [0.29.2](https://github.com/Lixiang9716/govrail/compare/v0.29.1...v0.29.2) (2026-09-07)


### Bug Fixes

* pin UTF-8 on self-test's own spawns; thread crashes fail loud ([#172](https://github.com/Lixiang9716/govrail/issues/172)) ([#173](https://github.com/Lixiang9716/govrail/issues/173)) ([a82386a](https://github.com/Lixiang9716/govrail/commit/a82386ae884ddac2891835538fbe24790503af96))

## [0.29.1](https://github.com/Lixiang9716/govrail/compare/v0.29.0...v0.29.1) (2026-09-07)


### Bug Fixes

* Windows portability — guarded fcntl, portable self-test fixtures, UTF-8 git decode ([#168](https://github.com/Lixiang9716/govrail/issues/168)) ([c49630a](https://github.com/Lixiang9716/govrail/commit/c49630aaa23c781ad4d84d6ad83bb8acfb3039f7))

## [0.29.0](https://github.com/Lixiang9716/govrail/compare/v0.28.0...v0.29.0) (2026-09-05)


### Features

* task claims — lease semantics for parallel workers ([#165](https://github.com/Lixiang9716/govrail/issues/165)) ([4c60837](https://github.com/Lixiang9716/govrail/commit/4c60837e43173b7e5ec429b57eabca93eb355769))

## [0.28.0](https://github.com/Lixiang9716/govrail/compare/v0.27.0...v0.28.0) (2026-09-05)


### Features

* presets — python-lib and docs-bilingual bundles ([#164](https://github.com/Lixiang9716/govrail/issues/164)) ([71dd341](https://github.com/Lixiang9716/govrail/commit/71dd341421e48c09b30915e885c93beea6be546a))
* presets — typed adoption bundles (machinery + agent-heavy) ([#162](https://github.com/Lixiang9716/govrail/issues/162)) ([757c92b](https://github.com/Lixiang9716/govrail/commit/757c92b087b7dedd7c1986e9a596da8ae9fb6dcf))

## [0.27.0](https://github.com/Lixiang9716/govrail/compare/v0.26.0...v0.27.0) (2026-09-05)


### Features

* acquire/release — lease locks for oblivious parallel agents ([#160](https://github.com/Lixiang9716/govrail/issues/160)) ([d584def](https://github.com/Lixiang9716/govrail/commit/d584def9e5febe5c776d4235dd8f1c4f2601d6fd))
* run --merge — preflight the union of parallel branches before landing ([#158](https://github.com/Lixiang9716/govrail/issues/158)) ([59abc76](https://github.com/Lixiang9716/govrail/commit/59abc766ae44878667b713556e922abcac8ae2b1))

## [0.26.0](https://github.com/Lixiang9716/govrail/compare/v0.25.0...v0.26.0) (2026-09-04)


### Features

* decision --against alias with stale-base warning; doctor names unadopted shipped gates ([#147](https://github.com/Lixiang9716/govrail/issues/147)) ([#151](https://github.com/Lixiang9716/govrail/issues/151)) ([3488119](https://github.com/Lixiang9716/govrail/commit/34881196657fc5915da1d36568debf041e6f43f4))
* note-presence exemptions — task receipts by default, manifest note_presence_exempt ([#154](https://github.com/Lixiang9716/govrail/issues/154)) ([72c9d28](https://github.com/Lixiang9716/govrail/commit/72c9d28f5d3c29add8e650937bff8c5e119866ee))
* pairing sidecar is self-describing — template comments, --write field echo, --explain ([#155](https://github.com/Lixiang9716/govrail/issues/155)) ([d446b2d](https://github.com/Lixiang9716/govrail/commit/d446b2db9bcbd36c995725de376d4fc66e583206)), closes [#150](https://github.com/Lixiang9716/govrail/issues/150)
* recall misses are diagnosable — corpus statement, per-term counts, --any ([#148](https://github.com/Lixiang9716/govrail/issues/148)) ([#153](https://github.com/Lixiang9716/govrail/issues/153)) ([113b230](https://github.com/Lixiang9716/govrail/commit/113b230896089dfd4be1c612dee186fc1fc81780))

## [0.25.0](https://github.com/Lixiang9716/govrail/compare/v0.24.1...v0.25.0) (2026-09-04)


### Features

* self-test classifies FAILs via clean-env replay ([#139](https://github.com/Lixiang9716/govrail/issues/139)) ([e1a561a](https://github.com/Lixiang9716/govrail/commit/e1a561a3b141917435a629cc03971b1eb236d087))

## [0.24.1](https://github.com/Lixiang9716/govrail/compare/v0.24.0...v0.24.1) (2026-09-04)


### Bug Fixes

* **cli:** hand-roll required subcommands; keep case env off stdlib shadows ([5f2ed54](https://github.com/Lixiang9716/govrail/commit/5f2ed54293303e60f367763704720781863a6501)), closes [#138](https://github.com/Lixiang9716/govrail/issues/138)
* **cli:** hand-roll required subcommands; keep case env off stdlib shadows ([#138](https://github.com/Lixiang9716/govrail/issues/138)) ([6f4b7ea](https://github.com/Lixiang9716/govrail/commit/6f4b7ea42365f91bfc6c940b84d78f211bb398b8))

## [0.24.0](https://github.com/Lixiang9716/govrail/compare/v0.23.0...v0.24.0) (2026-09-04)


### Features

* release flow drafts HIGHLIGHTS sections — verify-doc-sync --write (D45) ([d5ec91a](https://github.com/Lixiang9716/govrail/commit/d5ec91a55970e10de49cbe85c9b9e6e7d4358de0))

## [0.23.0](https://github.com/Lixiang9716/govrail/compare/v0.22.0...v0.23.0) (2026-09-04)


### Features

* caller-reported cost ledger in .gov/history — gov run --cost/GOV_COST, gov trend --cost (D44, [#126](https://github.com/Lixiang9716/govrail/issues/126)) ([b3e8696](https://github.com/Lixiang9716/govrail/commit/b3e869627919e5d95ee3cfb877541bdffaa03bbf))
* caller-reported cost ledger in .gov/history — gov run --cost/GOV_COST, gov trend --cost (D45, [#126](https://github.com/Lixiang9716/govrail/issues/126)) ([f71aabd](https://github.com/Lixiang9716/govrail/commit/f71aabd7977e2d8c6eabd36e3b95dc86f6b8434c))

## [0.22.0](https://github.com/Lixiang9716/govrail/compare/v0.21.1...v0.22.0) (2026-09-04)


### Features

* verifiable run receipts — gov run --receipt + gov receipt verify ([#124](https://github.com/Lixiang9716/govrail/issues/124)) ([6fb8d1a](https://github.com/Lixiang9716/govrail/commit/6fb8d1aa1e8ad6443e1faae9e08e2bcc07629e65))

## [0.21.1](https://github.com/Lixiang9716/govrail/compare/v0.21.0...v0.21.1) (2026-09-04)


### Bug Fixes

* decision add table-format draft shape — help and validator agree ([#132](https://github.com/Lixiang9716/govrail/issues/132)) ([7a69aa5](https://github.com/Lixiang9716/govrail/commit/7a69aa5717b48a204f9243d4fc3ac7984a08e9cf))
* decision add table-format draft shape — help and validator agree ([#132](https://github.com/Lixiang9716/govrail/issues/132)) ([2d68ac4](https://github.com/Lixiang9716/govrail/commit/2d68ac432cad90288e70709c35d21bf12c0d6168))

## [0.21.0](https://github.com/Lixiang9716/govrail/compare/v0.20.0...v0.21.0) (2026-09-04)


### Features

* gov task — task cards pin rules@hash for subagent briefs ([#125](https://github.com/Lixiang9716/govrail/issues/125)) ([bcf35bc](https://github.com/Lixiang9716/govrail/commit/bcf35bcc6983b2b14f1ae86b479ca8dfcb459608))
* gov task — task cards pin rules@hash for subagent briefs ([#125](https://github.com/Lixiang9716/govrail/issues/125)) ([5635baf](https://github.com/Lixiang9716/govrail/commit/5635bafbd0fed362d3ead6fc2136af51f68ee366))
* JSON output on the agent hot paths (gov run / audit-notes / verify-decisions / doctor) ([82e6603](https://github.com/Lixiang9716/govrail/commit/82e66032b1bb4daca710eec1e1b903edf269b66e))

## [0.20.0](https://github.com/Lixiang9716/govrail/compare/v0.19.0...v0.20.0) (2026-09-04)


### Features

* caller tagging in .gov/history — gov run --tag / GOV_CALLER, gov trend --by-tag (D42, [#120](https://github.com/Lixiang9716/govrail/issues/120)) ([#127](https://github.com/Lixiang9716/govrail/issues/127)) ([862bcaf](https://github.com/Lixiang9716/govrail/commit/862bcaf327a759e313e552864e55941f0daa91b1))

## [0.19.0](https://github.com/Lixiang9716/govrail/compare/v0.18.0...v0.19.0) (2026-09-04)


### Features

* gov -C &lt;path&gt; targets another worktree without cd ([#121](https://github.com/Lixiang9716/govrail/issues/121)) ([6f8a79e](https://github.com/Lixiang9716/govrail/commit/6f8a79ebfec2b845e4fefc5b85f29bc7491098c2))

## [0.18.0](https://github.com/Lixiang9716/govrail/compare/v0.17.0...v0.18.0) (2026-09-04)


### Features

* optional pre-commit hook — pairing drift surfaces at commit, not push (D41) ([#114](https://github.com/Lixiang9716/govrail/issues/114)) ([9a68c38](https://github.com/Lixiang9716/govrail/commit/9a68c38d114738d1b5ee6fcb5cefd2af13ec2c0d))

## [0.17.0](https://github.com/Lixiang9716/govrail/compare/v0.16.0...v0.17.0) (2026-09-04)


### Features

* decision-row tooling for parallel branches — next/add/--base/dir format ([#107](https://github.com/Lixiang9716/govrail/issues/107)) ([fd41fd9](https://github.com/Lixiang9716/govrail/commit/fd41fd90fe437db2348128a800ec846cf6bf8040))
* decision-row tooling for parallel branches — next/add/--base/dir format ([#107](https://github.com/Lixiang9716/govrail/issues/107)) ([6622f6f](https://github.com/Lixiang9716/govrail/commit/6622f6fed6b7cbf3be01a6ebbaa4986c5cc50b7f))

## [0.16.0](https://github.com/Lixiang9716/govrail/compare/v0.15.1...v0.16.0) (2026-09-04)


### Features

* gov init --adopt-new gates.json — additive adoption of new shipped gates (D39) ([965542f](https://github.com/Lixiang9716/govrail/commit/965542f5eb4982e90a640299788ff68c5391e9a3))

## [0.15.1](https://github.com/Lixiang9716/govrail/compare/v0.15.0...v0.15.1) (2026-09-04)


### Bug Fixes

* failure-first gate output — failed evidence is never clipped, failure line names the rerun command ([#109](https://github.com/Lixiang9716/govrail/issues/109)) ([964f7fa](https://github.com/Lixiang9716/govrail/commit/964f7fa82fcff41b1f1dfd2e20608c3cf9734809))
* failure-first gate output — failed evidence never clipped, failure line names the rerun command ([316fc9e](https://github.com/Lixiang9716/govrail/commit/316fc9e90c1dd92cd74b613f093a2553050cd252))

## [0.15.0](https://github.com/Lixiang9716/govrail/compare/v0.14.1...v0.15.0) (2026-09-04)


### Features

* conflict-marker gate — git's blind spot becomes a content gate (D38) ([#105](https://github.com/Lixiang9716/govrail/issues/105)) ([699bb2f](https://github.com/Lixiang9716/govrail/commit/699bb2f2af2bd136bab08939da9ba52255026dd0))

## [0.14.1](https://github.com/Lixiang9716/govrail/compare/v0.14.0...v0.14.1) (2026-09-03)


### Bug Fixes

* audit-notes flag registry pinned to each command's real --help surface ([#102](https://github.com/Lixiang9716/govrail/issues/102)) ([d542e3f](https://github.com/Lixiang9716/govrail/commit/d542e3f278acd32c132a5fd9b830ae22cbe62a85)), closes [#101](https://github.com/Lixiang9716/govrail/issues/101)

## [0.14.0](https://github.com/Lixiang9716/govrail/compare/v0.13.2...v0.14.0) (2026-09-03)


### Features

* CHANGELOG ↔ HIGHLIGHTS pairing — version-following made mechanical (D37) ([#97](https://github.com/Lixiang9716/govrail/issues/97)) ([240d39b](https://github.com/Lixiang9716/govrail/commit/240d39b019d84a65fb7642c992a9ff3e88d2b458))

## [0.13.2](https://github.com/Lixiang9716/govrail/compare/v0.13.1...v0.13.2) (2026-09-03)


### Bug Fixes

* gov whatsnew states the installed wheel and maps version lag ([#92](https://github.com/Lixiang9716/govrail/issues/92) residual) ([#95](https://github.com/Lixiang9716/govrail/issues/95)) ([a98fdc0](https://github.com/Lixiang9716/govrail/commit/a98fdc00b1feff352e05a83d6bcd92f69105240a))

## [0.13.1](https://github.com/Lixiang9716/govrail/compare/v0.13.0...v0.13.1) (2026-09-03)


### Bug Fixes

* bare adopt-preview cross-references the drift inventory; version-alignment guard (D35) ([#90](https://github.com/Lixiang9716/govrail/issues/90)) ([a37c03b](https://github.com/Lixiang9716/govrail/commit/a37c03b6ae94664c7adac0ba643a7c7731b8ec2a))

## [0.13.0](https://github.com/Lixiang9716/govrail/compare/v0.12.2...v0.13.0) (2026-09-03)


### Features

* adoption provenance, adopt preview and disclosure, external D-references (D34) ([#88](https://github.com/Lixiang9716/govrail/issues/88)) ([d3fbf26](https://github.com/Lixiang9716/govrail/commit/d3fbf263897ce494f9f8172e8dc15312e8763a2d))

## [0.12.2](https://github.com/Lixiang9716/govrail/compare/v0.12.1...v0.12.2) (2026-09-03)


### Bug Fixes

* host integrity — three walls around the self-test's scratch fixtures ([#86](https://github.com/Lixiang9716/govrail/issues/86)) ([9e7d45b](https://github.com/Lixiang9716/govrail/commit/9e7d45b2bc2e66f89fbebaf98dd1c75c06eec299))

## [0.12.1](https://github.com/Lixiang9716/govrail/compare/v0.12.0...v0.12.1) (2026-09-03)


### Bug Fixes

* worktrees, hook context, blast radius, and the vacuous-green family ([#15](https://github.com/Lixiang9716/govrail/issues/15)-[#23](https://github.com/Lixiang9716/govrail/issues/23)) ([#83](https://github.com/Lixiang9716/govrail/issues/83)) ([282a98c](https://github.com/Lixiang9716/govrail/commit/282a98cfb1214821cd0034a57d25194fb42978fb))

## [0.12.0](https://github.com/Lixiang9716/govrail/compare/v0.11.0...v0.12.0) (2026-09-02)


### Features

* the usability round — living specimen, cookbook, whatsnew, reports that point ahead (D31) ([#81](https://github.com/Lixiang9716/govrail/issues/81)) ([a291386](https://github.com/Lixiang9716/govrail/commit/a2913861fb3b22a5a48daedb469b420aa265eade))

## [0.11.0](https://github.com/Lixiang9716/govrail/compare/v0.10.1...v0.11.0) (2026-09-02)


### Features

* wishes round IV — grade mode, pairing round-trip, decision half-life, coverage ledger, dry checks, per-gate trends (D30) ([#79](https://github.com/Lixiang9716/govrail/issues/79)) ([7b124da](https://github.com/Lixiang9716/govrail/commit/7b124daeb71633a9a2597db448c2d0c4a5c6ff26))

## [0.10.1](https://github.com/Lixiang9716/govrail/compare/v0.10.0...v0.10.1) (2026-09-02)


### Bug Fixes

* gov note new says when a D-ref is left unchecked (rule 5) ([#77](https://github.com/Lixiang9716/govrail/issues/77)) ([6eeef2d](https://github.com/Lixiang9716/govrail/commit/6eeef2d0c0c0d0987d7bd40eb95f60b38c305dd2))

## [0.10.0](https://github.com/Lixiang9716/govrail/compare/v0.9.0...v0.10.0) (2026-09-02)


### Features

* wishes round III — adopt, doctor, note scaffolding, evidence prefetch, strict schema, default recording (D29) ([#75](https://github.com/Lixiang9716/govrail/issues/75)) ([f6b21fb](https://github.com/Lixiang9716/govrail/commit/f6b21fb1e6221b8b19a2e99b832fec7af79ddc09))

## [0.9.0](https://github.com/Lixiang9716/govrail/compare/v0.8.0...v0.9.0) (2026-09-01)


### Features

* wishes 9-14 — decision guard, review dossier, skill drift, trends, noise, orphans (D28) ([#73](https://github.com/Lixiang9716/govrail/issues/73)) ([f0d7231](https://github.com/Lixiang9716/govrail/commit/f0d7231f8ad36eb86702045fcb0f0e900d557d83))

## [0.8.0](https://github.com/Lixiang9716/govrail/compare/v0.7.1...v0.8.0) (2026-09-01)


### Features

* gov init --upgrade — seeing template drift, never writing it (D27) ([#71](https://github.com/Lixiang9716/govrail/issues/71)) ([1c35ebe](https://github.com/Lixiang9716/govrail/commit/1c35ebe4f23ef957a533f153b4f8255bf624fe03))

## [0.7.1](https://github.com/Lixiang9716/govrail/compare/v0.7.0...v0.7.1) (2026-09-01)


### Bug Fixes

* rejection-case budget and the --json purity contract (D26) ([#69](https://github.com/Lixiang9716/govrail/issues/69)) ([c3ad756](https://github.com/Lixiang9716/govrail/commit/c3ad756fa5641951110e55d2ae02dc6cd27755c6))

## [0.7.0](https://github.com/Lixiang9716/govrail/compare/v0.6.6...v0.7.0) (2026-09-01)


### Features

* the adopter wishes — local rejection cases, --json, parallel self-test, surface mapping (D25) ([#67](https://github.com/Lixiang9716/govrail/issues/67)) ([a0aada4](https://github.com/Lixiang9716/govrail/commit/a0aada4c9a6f2372eb40fc68029240045ebb8e32))

## [0.6.6](https://github.com/Lixiang9716/govrail/compare/v0.6.5...v0.6.6) (2026-09-01)


### Bug Fixes

* gate reachability — one parking mechanism, and it is loud (D24) ([#65](https://github.com/Lixiang9716/govrail/issues/65)) ([014b624](https://github.com/Lixiang9716/govrail/commit/014b624345563c5eb2cb50d0c3a71ba2de2c993c))

## [0.6.5](https://github.com/Lixiang9716/govrail/compare/v0.6.4...v0.6.5) (2026-09-01)


### Bug Fixes

* the seal gets a detector, re-sealing cannot launder, uninstall is two-step (D23) ([#63](https://github.com/Lixiang9716/govrail/issues/63)) ([be77464](https://github.com/Lixiang9716/govrail/commit/be77464288c4ae45b64300ef6aa8f22adb2caa0a))

## [0.6.4](https://github.com/Lixiang9716/govrail/compare/v0.6.3...v0.6.4) (2026-09-01)


### Bug Fixes

* retrofittable add-ons, customizations named before deletion, Status closed (D22) ([#61](https://github.com/Lixiang9716/govrail/issues/61)) ([a6ab82f](https://github.com/Lixiang9716/govrail/commit/a6ab82fc62e5b462d880c4e23062f1611368f8f3))

## [0.6.3](https://github.com/Lixiang9716/govrail/compare/v0.6.2...v0.6.3) (2026-09-01)


### Bug Fixes

* the executor honesty round — auto base, root anchoring, partial baselines (D21) ([#59](https://github.com/Lixiang9716/govrail/issues/59)) ([5634b4c](https://github.com/Lixiang9716/govrail/commit/5634b4c60876c029b3b0db3c5a5bb234936d29d4))

## [0.6.2](https://github.com/Lixiang9716/govrail/compare/v0.6.1...v0.6.2) (2026-09-01)


### Bug Fixes

* audit-notes summary tells the truth; truncation marker reads in order ([#57](https://github.com/Lixiang9716/govrail/issues/57)) ([844bb88](https://github.com/Lixiang9716/govrail/commit/844bb888b08f16a1472265782b29ac9b7a4b3ff8))

## [0.6.1](https://github.com/Lixiang9716/govrail/compare/v0.6.0...v0.6.1) (2026-09-01)


### Bug Fixes

* the honesty round — enforce what was already promised (D20) ([#55](https://github.com/Lixiang9716/govrail/issues/55)) ([e7c2261](https://github.com/Lixiang9716/govrail/commit/e7c22610f9703c716ea8c67419cf7371890b6a5f))

## [0.6.0](https://github.com/Lixiang9716/govrail/compare/v0.5.0...v0.6.0) (2026-09-01)


### Features

* the agent skills ship with the plane (gov init injects them) ([#53](https://github.com/Lixiang9716/govrail/issues/53)) ([efd2988](https://github.com/Lixiang9716/govrail/commit/efd2988fe4b5f6c983356173d5daf2b03ad7550e))

## [0.5.0](https://github.com/Lixiang9716/govrail/compare/v0.4.0...v0.5.0) (2026-09-01)


### Features

* the memory read side — gov recall and gov audit-notes ([#50](https://github.com/Lixiang9716/govrail/issues/50)) ([bc5fc79](https://github.com/Lixiang9716/govrail/commit/bc5fc7947111f563de20d0bf04c2dbe6cf65473c))

## [0.4.0](https://github.com/Lixiang9716/govrail/compare/v0.3.0...v0.4.0) (2026-09-01)


### Features

* review rubric — judgment gets a structure and a meta-gate ([#48](https://github.com/Lixiang9716/govrail/issues/48)) ([5daaba0](https://github.com/Lixiang9716/govrail/commit/5daaba0307072e53795c4d40863f8c54c4f658a3))

## [0.3.0](https://github.com/Lixiang9716/govrail/compare/v0.2.0...v0.3.0) (2026-08-28)


### Features

* enforceable governance — scoped runs, note-presence, pairing conventions, hooks/CI ([#45](https://github.com/Lixiang9716/govrail/issues/45)) ([f4e9da9](https://github.com/Lixiang9716/govrail/commit/f4e9da911159af78bcb74a6ab0d72687b9cafd7a))

## [0.2.0](https://github.com/Lixiang9716/govrail/compare/v0.1.2...v0.2.0) (2026-08-23)


### Features

* self-hosted star history (daily GitHub Actions + SVG chart) ([#43](https://github.com/Lixiang9716/govrail/issues/43)) ([1049d9a](https://github.com/Lixiang9716/govrail/commit/1049d9ada8e255f40f067d73c6d13c64c14d2ada))

## [0.1.2](https://github.com/Lixiang9716/govrail/compare/v0.1.1...v0.1.2) (2026-08-23)


### Bug Fixes

* publish to PyPI inside the release workflow ([#33](https://github.com/Lixiang9716/govrail/issues/33)) ([55af7f1](https://github.com/Lixiang9716/govrail/commit/55af7f16e154b9a86f2cf68b4e709e8302b7b1c4))

## [0.1.1](https://github.com/Lixiang9716/govrail/compare/v0.1.0...v0.1.1) (2026-08-23)


### Bug Fixes

* drop unused detail parameter from gate outcome line ([#28](https://github.com/Lixiang9716/govrail/issues/28)) ([3dfa3ac](https://github.com/Lixiang9716/govrail/commit/3dfa3ac78aa127a995f2480a1738dea999cd211a))
* source package version from gov/version.py for release-please ([#31](https://github.com/Lixiang9716/govrail/issues/31)) ([067b56b](https://github.com/Lixiang9716/govrail/commit/067b56b03953c5922cd4779a8d185dc99517881c))


### Documentation

* add LICENSE, demo project, and README value/quickstart ([#23](https://github.com/Lixiang9716/govrail/issues/23)) ([74962da](https://github.com/Lixiang9716/govrail/commit/74962da042e332054cd8d12abaffaddca620f76d))


### Continuous Integration

* auto-generate changelog and release notes from conventional commits ([#25](https://github.com/Lixiang9716/govrail/issues/25)) ([4b1a062](https://github.com/Lixiang9716/govrail/commit/4b1a06277f9e6958322ca6c5d44a1ddc07e763ae))
* migrate to release-please for automated version + changelog ([#27](https://github.com/Lixiang9716/govrail/issues/27)) ([8700d3d](https://github.com/Lixiang9716/govrail/commit/8700d3d95023fc289252464a9d1fff3bdd80481f))
* verify release tag matches package version before publish ([#22](https://github.com/Lixiang9716/govrail/issues/22)) ([d6b5db2](https://github.com/Lixiang9716/govrail/commit/d6b5db29b2183e749bb2aa4e10fe228c49b7db2b))
