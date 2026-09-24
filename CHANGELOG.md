# Changelog

## [0.49.0](https://github.com/Lixiang9716/govrail/compare/v0.48.0...v0.49.0) (2026-09-24)


### Features

* a scoped run judges one worker's paths; every run leaves full evidence ([#388](https://github.com/Lixiang9716/govrail/issues/388)) ([51ed433](https://github.com/Lixiang9716/govrail/commit/51ed433cdb014427ad4f823a4061b25e1e862335))
* surprise list answers keyword lookups over the full entry ([#382](https://github.com/Lixiang9716/govrail/issues/382)) ([5d4e78a](https://github.com/Lixiang9716/govrail/commit/5d4e78a9dfd8d2de7027bdc8a1b83453a276d5b2))


### Bug Fixes

* parse facts are single-visit and named; ArkTS joins the language set ([#387](https://github.com/Lixiang9716/govrail/issues/387)) ([93f04df](https://github.com/Lixiang9716/govrail/commit/93f04df4ba3e9f41b9fed81646121cbc8ce495fe))
* task mutating commands echo which card moved; --slug asserts it ([#378](https://github.com/Lixiang9716/govrail/issues/378)) ([#383](https://github.com/Lixiang9716/govrail/issues/383)) ([ce82159](https://github.com/Lixiang9716/govrail/commit/ce82159f9f918c9de44f9821a822b7c06eb36819))
* the new-branch push scope declares its root; self-test is immune to an ambient scope ([#371](https://github.com/Lixiang9716/govrail/issues/371)) ([#384](https://github.com/Lixiang9716/govrail/issues/384)) ([1ce6ece](https://github.com/Lixiang9716/govrail/commit/1ce6ece6ccfd8ab0e95cab251dd93342f1d1dfc8))
* update --apply re-wires the drifted hook from the template; init --hooks stops implying claude ([#380](https://github.com/Lixiang9716/govrail/issues/380)) ([56e8a0f](https://github.com/Lixiang9716/govrail/commit/56e8a0f9a95ca01a0d3f135aaf7ac092e9b2cb42))
* verify pairing --write resolves a bare stem against the include scope and names the roots it tried ([#379](https://github.com/Lixiang9716/govrail/issues/379)) ([#381](https://github.com/Lixiang9716/govrail/issues/381)) ([71d37c9](https://github.com/Lixiang9716/govrail/commit/71d37c9f3a0c1bf5160688444692a16723afb7c8))

## [0.48.0](https://github.com/Lixiang9716/govrail/compare/v0.47.1...v0.48.0) (2026-09-21)


### Features

* **agent-hooks:** capture what the platform actually sends ([#365](https://github.com/Lixiang9716/govrail/issues/365)) ([1743ace](https://github.com/Lixiang9716/govrail/commit/1743ace96217ddf47d3bf8a2e8edf5c9ba4d2f20))
* **parse:** ship every tree-sitter grammar — 41 packs, a declared factory, snippet fixtures ([#362](https://github.com/Lixiang9716/govrail/issues/362)) ([4016f6f](https://github.com/Lixiang9716/govrail/commit/4016f6f747fd211eeb628f9a27fe5508020da4ed))
* **parse:** Swift and Kotlin grammars join the parse layer; gov parse walks the pack set ([#361](https://github.com/Lixiang9716/govrail/issues/361)) ([c8042fd](https://github.com/Lixiang9716/govrail/commit/c8042fd6832e4d885b8f4dc98b304cb34bb8a31f))


### Bug Fixes

* **surface:** issue batch [#340](https://github.com/Lixiang9716/govrail/issues/340)-[#349](https://github.com/Lixiang9716/govrail/issues/349) — check-gate exclusions, truth-telling machine surfaces, recall QoL ([#350](https://github.com/Lixiang9716/govrail/issues/350)) ([026dda7](https://github.com/Lixiang9716/govrail/commit/026dda78982276c2e569eef30fc7148a6e00f388))
* **surface:** issue batch 2 — task cards got hands, notices stop repeating, runtime artifacts stay out of git status ([#359](https://github.com/Lixiang9716/govrail/issues/359)) ([96e4282](https://github.com/Lixiang9716/govrail/commit/96e42821447ef5594592e483bfa75a8c1d7cef76))
* **task:** one green predicate for receipts; bricked done cards get exits ([#329](https://github.com/Lixiang9716/govrail/issues/329)) ([aaaee7a](https://github.com/Lixiang9716/govrail/commit/aaaee7a4fcb29030fbcd43544f7971ea8de7afb5))
* **task:** the checklist is a contract again, and a lease names its card ([#360](https://github.com/Lixiang9716/govrail/issues/360)) ([8a6cd60](https://github.com/Lixiang9716/govrail/commit/8a6cd6080ae5857e614997ce5d299062e2830bcc))
* the pairing config exists from init ([#367](https://github.com/Lixiang9716/govrail/issues/367)); a stale pin can be advanced on purpose ([#368](https://github.com/Lixiang9716/govrail/issues/368)) ([#370](https://github.com/Lixiang9716/govrail/issues/370)) ([a8c4683](https://github.com/Lixiang9716/govrail/commit/a8c4683056f1ec56a75b86aee130feaf4f88b1c3))
* the push scope is what the push carries; notes can point forward; gate add can be previewed ([#369](https://github.com/Lixiang9716/govrail/issues/369)) ([52d447e](https://github.com/Lixiang9716/govrail/commit/52d447e23ac2302789c7c070970ce63ff284dec9))

## [0.47.1](https://github.com/Lixiang9716/govrail/compare/v0.47.0...v0.47.1) (2026-09-19)


### Bug Fixes

* **task:** card ids are addresses — high-water allocation, never recycled ([#327](https://github.com/Lixiang9716/govrail/issues/327)) ([261dd04](https://github.com/Lixiang9716/govrail/commit/261dd046c587bfc6c87d1c1e280879dfb825b7e6))

## [0.47.0](https://github.com/Lixiang9716/govrail/compare/v0.46.0...v0.47.0) (2026-09-19)


### Features

* **plane:** adoption-surface hardening — resolve all 14 open issues ([#308](https://github.com/Lixiang9716/govrail/issues/308)-[#319](https://github.com/Lixiang9716/govrail/issues/319), [#273](https://github.com/Lixiang9716/govrail/issues/273), [#274](https://github.com/Lixiang9716/govrail/issues/274)) ([05d6ead](https://github.com/Lixiang9716/govrail/commit/05d6ead31724f4363c2a06cf1fd82cabb28fdd39))


### Bug Fixes

* **ci:** every automated unattended re-baseline names its --reason ([42d5de5](https://github.com/Lixiang9716/govrail/commit/42d5de58c0e9ce4f3e6f3b0383dab689fcfdfa52))
* **packaging:** ship preset bundle files in the wheel — presets/*/* package-data ([06661f0](https://github.com/Lixiang9716/govrail/commit/06661f0b9d7bb889fd1ab9c8c76cd50a171a717e))
* **plane:** --confirm-unattended is authoritative over the tty probe (D66 follow-through) ([6087c0e](https://github.com/Lixiang9716/govrail/commit/6087c0e123412be0d295c6f34648cf3e69ad4f49))
* **plane:** update choreography completes, task cards get a recorded exit ([#320](https://github.com/Lixiang9716/govrail/issues/320)-[#325](https://github.com/Lixiang9716/govrail/issues/325)) ([ac6ec83](https://github.com/Lixiang9716/govrail/commit/ac6ec8355f2cc874fd010dedcc5423ee25f3d747))
* **tests:** tomli under 3.10 for the packaging pin — tomllib is 3.11+ (support floor is 3.10) ([f50f8e9](https://github.com/Lixiang9716/govrail/commit/f50f8e968af1e9a7391c653c5a32c7cea2a22d4f))

## [0.46.0](https://github.com/Lixiang9716/govrail/compare/v0.45.0...v0.46.0) (2026-09-19)


### Features

* **gates:** doc-budgets — standing prose gets character ceilings; generated-truth header completes its triple ([#304](https://github.com/Lixiang9716/govrail/issues/304)) ([4bba8cb](https://github.com/Lixiang9716/govrail/commit/4bba8cbfa468eb4ebfff829b3873dc4e946575e9))
* **hooks:** commit-boundary automation — staged autofix, staged derivation, evidence rubric R10 (D64) ([#307](https://github.com/Lixiang9716/govrail/issues/307)) ([cb02bbc](https://github.com/Lixiang9716/govrail/commit/cb02bbc789ccaa5b81b7c26e219d5cb425379b16))
* **persistence:** declared format inventory + acknowledgment chain (D63) ([#306](https://github.com/Lixiang9716/govrail/issues/306)) ([23100f9](https://github.com/Lixiang9716/govrail/commit/23100f9c5e1807b26bdc0c9d34f9bc61a6f06052))

## [0.45.0](https://github.com/Lixiang9716/govrail/compare/v0.44.0...v0.45.0) (2026-09-19)


### Features

* **surprise:** the surprise ledger — expectation vs reality, counted; the third strike escalates (rule 11) ([#302](https://github.com/Lixiang9716/govrail/issues/302)) ([9c87db3](https://github.com/Lixiang9716/govrail/commit/9c87db30b7f63da5a0410fc65bf59e7347f302cb))

## [0.44.0](https://github.com/Lixiang9716/govrail/compare/v0.43.1...v0.44.0) (2026-09-19)


### Features

* **gates:** skill-coverage — the router skill must route every shipped command ([#298](https://github.com/Lixiang9716/govrail/issues/298)) ([18c2e59](https://github.com/Lixiang9716/govrail/commit/18c2e59e18c5f86e7da553b426fe70060f0bf3f3))

## [0.43.1](https://github.com/Lixiang9716/govrail/compare/v0.43.0...v0.43.1) (2026-09-19)


### Bug Fixes

* **ci:** the gates summary now verdicts EVERY job — auto-merge only on full green ([#296](https://github.com/Lixiang9716/govrail/issues/296)) ([5266655](https://github.com/Lixiang9716/govrail/commit/5266655478014668affd5f31cf7b5cd856697908))

## [0.43.0](https://github.com/Lixiang9716/govrail/compare/v0.42.0...v0.43.0) (2026-09-18)


### Features

* agent-dev template with gates, notes, pairing, and skills ([07d84c5](https://github.com/Lixiang9716/govrail/commit/07d84c5a5148c99a20284a55c0cc23d57954cbbb))
* dual bash and pwsh governance runners, drop the Node runtime ([30c5873](https://github.com/Lixiang9716/govrail/commit/30c5873f2b33cf9831e684b9740a7677a89ed2d3))
* grow-the-plane rule, conditional-stance craft, heartbeat, and CI self-test ([19cdf90](https://github.com/Lixiang9716/govrail/commit/19cdf90f34c1084a7ab35a3730e7b6da9462a400))
* JSON output on the hot paths — run gains selected_by/scoped_out, doctor/verify-decisions/audit-notes gain --json ([#119](https://github.com/Lixiang9716/govrail/issues/119)) ([751d0ae](https://github.com/Lixiang9716/govrail/commit/751d0aed20f376aacd5add80fdbe29538355cf97))
* links gate, trim-cot-leakage and find-simplifications skills ([278b85c](https://github.com/Lixiang9716/govrail/commit/278b85cd7b316b8f74feb7be61ad3f124f94ed19))
* one-line curl installer for scaffolding verified projects ([1e77b9b](https://github.com/Lixiang9716/govrail/commit/1e77b9b3726171e18c87f6ed9b01b81005f008c5))
* optional pre-commit hook — pairing drift surfaces at commit, not push (D40) ([9a68c38](https://github.com/Lixiang9716/govrail/commit/9a68c38d114738d1b5ee6fcb5cefd2af13ec2c0d))
* paired installers, installer CI legs, and release-pinned scaffolds ([cff7d22](https://github.com/Lixiang9716/govrail/commit/cff7d220d16554197e6d260ab6090247989db799))
* pairing sidecar is self-describing — template comments, --write field echo, --explain ([#155](https://github.com/Lixiang9716/govrail/issues/155)) ([d446b2d](https://github.com/Lixiang9716/govrail/commit/d446b2db9bcbd36c995725de376d4fc66e583206)), closes [#150](https://github.com/Lixiang9716/govrail/issues/150)
* self-test classifies FAILs via clean-env replay ([#139](https://github.com/Lixiang9716/govrail/issues/139), D47) ([9bacfce](https://github.com/Lixiang9716/govrail/commit/9bacfcebcec10aa8cddeb96d07248b5b862da147))
* twin pairs confirm together via script-pairs manifest ([d4586ed](https://github.com/Lixiang9716/govrail/commit/d4586ed633bb6573cc22752394ef26d34253b4a6))
* verifiable run receipts — gov run --receipt + gov receipt verify ([#124](https://github.com/Lixiang9716/govrail/issues/124), D44) ([76bb324](https://github.com/Lixiang9716/govrail/commit/76bb32477717d1d665ecfca8131600771655eb18))
* vocabulary gate, notes discipline, and twin-probe script pairs ([#12](https://github.com/Lixiang9716/govrail/issues/12)) ([d37c101](https://github.com/Lixiang9716/govrail/commit/d37c101f2110dc0728b81bc554d69dc56410a823))


### Bug Fixes

* --write resolves bare stem and .zh.md side without crashing ([#18](https://github.com/Lixiang9716/govrail/issues/18)) ([62f9ea8](https://github.com/Lixiang9716/govrail/commit/62f9ea85dd599988b2973814d0ce377c982504de))
* audit-notes flag registry pinned to each command's real --help surface ([#102](https://github.com/Lixiang9716/govrail/issues/102)) ([d542e3f](https://github.com/Lixiang9716/govrail/commit/d542e3f278acd32c132a5fd9b830ae22cbe62a85)), closes [#101](https://github.com/Lixiang9716/govrail/issues/101)
* **cli:** hand-roll required subcommands; keep case env off stdlib shadows ([5f2ed54](https://github.com/Lixiang9716/govrail/commit/5f2ed54293303e60f367763704720781863a6501)), closes [#138](https://github.com/Lixiang9716/govrail/issues/138)
* **lint:** 69 ruff findings + lint gate-ized into the DAG (post-[#290](https://github.com/Lixiang9716/govrail/issues/290) follow-up) ([#294](https://github.com/Lixiang9716/govrail/issues/294)) ([8a85f1d](https://github.com/Lixiang9716/govrail/commit/8a85f1da1f124c510724681e51e2c80344733505))
* pin LF checkout so content-addressed gates hold on Windows ([2e2538e](https://github.com/Lixiang9716/govrail/commit/2e2538eb58d722ed96ee85e3dfcd12684b330b44))
* pwsh port must run the pwsh command variant ([20f731b](https://github.com/Lixiang9716/govrail/commit/20f731bc8e6c108f7a8207053ed35b42ac5c13cc))
* six defects found by adversarial end-to-end testing ([#15](https://github.com/Lixiang9716/govrail/issues/15)) ([388eb9c](https://github.com/Lixiang9716/govrail/commit/388eb9c9d6e2a5b6e20ed20ef0da81593400620a))
* subcommand --help/--version must be side-effect free ([#16](https://github.com/Lixiang9716/govrail/issues/16)) ([8ee84d6](https://github.com/Lixiang9716/govrail/commit/8ee84d67d11368afcfb423dc68c9a43a6eba44b0))
* twin ports are alternatives, not both-required ([#13](https://github.com/Lixiang9716/govrail/issues/13)) ([0ae0574](https://github.com/Lixiang9716/govrail/commit/0ae05741c98f0e3c631918c52c9246b93e224d65))


### Reverts

* drop the in-template installers; distribution rides template mechanics ([b8a6f71](https://github.com/Lixiang9716/govrail/commit/b8a6f71ae30eb0a3988945b25e6b074a2671cfa5))

## [0.42.0](https://github.com/Lixiang9716/govrail/compare/v0.41.0...v0.42.0) (2026-09-18)


### Features

* code design contracts — modular monolith, registry surfaces, self-hosted guardrails ([#290](https://github.com/Lixiang9716/govrail/issues/290)) ([6fb6fba](https://github.com/Lixiang9716/govrail/commit/6fb6fba89ff50f59f02669e9fa440f88b0c68d1d))

## [0.41.0](https://github.com/Lixiang9716/govrail/compare/v0.40.0...v0.41.0) (2026-09-18)


### Features

* multi-platform agent hooks — codex/copilot/gemini + dialect layer (D60) ([#288](https://github.com/Lixiang9716/govrail/issues/288)) ([0ca88e1](https://github.com/Lixiang9716/govrail/commit/0ca88e1c59218dfa584b6314a2ee66fd7ddd5f21))

## [0.40.0](https://github.com/Lixiang9716/govrail/compare/v0.39.0...v0.40.0) (2026-09-18)


### Features

* gov update (D58) + agent hooks + rule 9 + round-15 batch ([#286](https://github.com/Lixiang9716/govrail/issues/286)) ([7535b6a](https://github.com/Lixiang9716/govrail/commit/7535b6ac2acf684b46cd0d651ea670114bd82cff))

## [0.39.0](https://github.com/Lixiang9716/govrail/compare/v0.38.2...v0.39.0) (2026-09-18)


### Features

* rule 9 as a mechanical gate — open cards with unchecked items block the push ([#284](https://github.com/Lixiang9716/govrail/issues/284)) ([3c5219d](https://github.com/Lixiang9716/govrail/commit/3c5219dd9c323c295fa39387c143366bb6b9a399))

## [0.38.2](https://github.com/Lixiang9716/govrail/compare/v0.38.1...v0.38.2) (2026-09-18)


### Bug Fixes

* every remaining open item from the round-15 audit ledger ([#281](https://github.com/Lixiang9716/govrail/issues/281)) ([1f15945](https://github.com/Lixiang9716/govrail/commit/1f15945ddb590fa442dc7ae2316a4bd29ff420f8))

## [0.38.1](https://github.com/Lixiang9716/govrail/compare/v0.38.0...v0.38.1) (2026-09-18)


### Bug Fixes

* the round-15 batch — gov update and gov parse meet their own contracts ([#279](https://github.com/Lixiang9716/govrail/issues/279)) ([2e5099d](https://github.com/Lixiang9716/govrail/commit/2e5099d807611c372defee61318a22865011bc16))

## [0.38.0](https://github.com/Lixiang9716/govrail/compare/v0.37.1...v0.38.0) (2026-09-18)


### Features

* gov update — the migration choreography becomes one command (D58) ([#275](https://github.com/Lixiang9716/govrail/issues/275)) ([c35ce8b](https://github.com/Lixiang9716/govrail/commit/c35ce8ba77e9c5629ae87952f87d7bb8a85274c2))

## [0.37.1](https://github.com/Lixiang9716/govrail/compare/v0.37.0...v0.37.1) (2026-09-18)


### Bug Fixes

* gov parse names its uncovered files and declares its grammars ([#269](https://github.com/Lixiang9716/govrail/issues/269)/[#270](https://github.com/Lixiang9716/govrail/issues/270)) ([#271](https://github.com/Lixiang9716/govrail/issues/271)) ([bf58c89](https://github.com/Lixiang9716/govrail/commit/bf58c8920dfc50e1c1473bbb1a01c60061340829))

## [0.37.0](https://github.com/Lixiang9716/govrail/compare/v0.36.0...v0.37.0) (2026-09-18)


### Features

* gov parse — the parse layer as a declared primitive ([#265](https://github.com/Lixiang9716/govrail/issues/265)) ([#267](https://github.com/Lixiang9716/govrail/issues/267)) ([636258b](https://github.com/Lixiang9716/govrail/commit/636258b3439aad16ffb4a69cd97a259ff6d0bde2))

## [0.36.0](https://github.com/Lixiang9716/govrail/compare/v0.35.0...v0.36.0) (2026-09-18)


### Features

* D57 — four family hubs consolidate the command surface (32 → 22) ([#264](https://github.com/Lixiang9716/govrail/issues/264)) ([9cad635](https://github.com/Lixiang9716/govrail/commit/9cad6358e7bb761a37475fe17e477e59d3ff10b1))

## [0.35.0](https://github.com/Lixiang9716/govrail/compare/v0.34.12...v0.35.0) (2026-09-17)


### Features

* the govrail router skill — when/when-not judgment for the whole command surface, injected first ([#262](https://github.com/Lixiang9716/govrail/issues/262)) ([dd51044](https://github.com/Lixiang9716/govrail/commit/dd51044b502b2f78cf4db2c998c86c463303fd60))

## [0.34.12](https://github.com/Lixiang9716/govrail/compare/v0.34.11...v0.34.12) (2026-09-17)


### Bug Fixes

* gate failures and install friction learn to explain themselves (issue batch [#250](https://github.com/Lixiang9716/govrail/issues/250)/[#251](https://github.com/Lixiang9716/govrail/issues/251)/[#252](https://github.com/Lixiang9716/govrail/issues/252)/[#253](https://github.com/Lixiang9716/govrail/issues/253)/[#257](https://github.com/Lixiang9716/govrail/issues/257)/[#259](https://github.com/Lixiang9716/govrail/issues/259)/[#201](https://github.com/Lixiang9716/govrail/issues/201)/[#200](https://github.com/Lixiang9716/govrail/issues/200)) ([#260](https://github.com/Lixiang9716/govrail/issues/260)) ([5fb2954](https://github.com/Lixiang9716/govrail/commit/5fb2954642a76f4b3e70d35eb4ed8bd6920bd217))

## [0.34.11](https://github.com/Lixiang9716/govrail/compare/v0.34.10...v0.34.11) (2026-09-17)


### Bug Fixes

* run's output polarity becomes documented contract; the exit-code contract gets its pin (D56 revision) ([#256](https://github.com/Lixiang9716/govrail/issues/256)) ([deac507](https://github.com/Lixiang9716/govrail/commit/deac5074071a89eb7e07faebcbd8d7bb26143166))

## [0.34.10](https://github.com/Lixiang9716/govrail/compare/v0.34.9...v0.34.10) (2026-09-17)


### Bug Fixes

* the containment anchor comes from the process, never from the protected path (N15) ([#248](https://github.com/Lixiang9716/govrail/issues/248)) ([50cab4e](https://github.com/Lixiang9716/govrail/commit/50cab4e608917d4147dabee54ffb17d3f330800b))

## [0.34.9](https://github.com/Lixiang9716/govrail/compare/v0.34.8...v0.34.9) (2026-09-17)


### Bug Fixes

* containment walks the whole state path — the directory variant of the ledger escape, and AGENTS.md stops being written through ([#245](https://github.com/Lixiang9716/govrail/issues/245)) ([6913cc3](https://github.com/Lixiang9716/govrail/commit/6913cc343bb8d21064afb2f058bb50c5bb22da4e))

## [0.34.8](https://github.com/Lixiang9716/govrail/compare/v0.34.7...v0.34.8) (2026-09-17)


### Bug Fixes

* state writes refuse symlinks, attribution needs token boundaries, the torn-write sites close, machine contract written (D56) ([#243](https://github.com/Lixiang9716/govrail/issues/243)) ([7f63de1](https://github.com/Lixiang9716/govrail/commit/7f63de1567d65068869d5e82fc039f00b676d807))

## [0.34.7](https://github.com/Lixiang9716/govrail/compare/v0.34.6...v0.34.7) (2026-09-17)


### Bug Fixes

* the check gate judges the change scope, not history — plus its rule-6 rejection case ([#241](https://github.com/Lixiang9716/govrail/issues/241)) ([f6252f6](https://github.com/Lixiang9716/govrail/commit/f6252f68f2ad0f05e933172765002852ec04cc48))

## [0.34.6](https://github.com/Lixiang9716/govrail/compare/v0.34.5...v0.34.6) (2026-09-17)


### Bug Fixes

* pre-push deletion skip, hollow-note rejection, and the check gate joins the default set (D55) ([#239](https://github.com/Lixiang9716/govrail/issues/239)) ([4b4f4ed](https://github.com/Lixiang9716/govrail/commit/4b4f4ed15010ccfd03b76cb3df6230c391881859))

## [0.34.5](https://github.com/Lixiang9716/govrail/compare/v0.34.4...v0.34.5) (2026-09-17)


### Bug Fixes

* init --preview requires --adopt, and --adopt requires an initialized project ([#237](https://github.com/Lixiang9716/govrail/issues/237)) ([04671a6](https://github.com/Lixiang9716/govrail/commit/04671a615a241cfc3cdc5db482a330af7c756312))

## [0.34.4](https://github.com/Lixiang9716/govrail/compare/v0.34.3...v0.34.4) (2026-09-17)


### Bug Fixes

* init --upgrade/--preview refuse on a project with no manifest ([#235](https://github.com/Lixiang9716/govrail/issues/235)) ([83a7eb8](https://github.com/Lixiang9716/govrail/commit/83a7eb84a64e98583301b8ba0e78ce8a5ca483c8))

## [0.34.3](https://github.com/Lixiang9716/govrail/compare/v0.34.2...v0.34.3) (2026-09-17)


### Bug Fixes

* red-team round 5 — 3 HIGH + 15 MEDIUM + LOW batch ([#233](https://github.com/Lixiang9716/govrail/issues/233)) ([f2f7e40](https://github.com/Lixiang9716/govrail/commit/f2f7e40b4a4be1567c35de09145016ef50a33853))

## [0.34.2](https://github.com/Lixiang9716/govrail/compare/v0.34.1...v0.34.2) (2026-09-17)


### Bug Fixes

* the classifier probe's reproduction proof was vacuously true ([#231](https://github.com/Lixiang9716/govrail/issues/231)) ([b973706](https://github.com/Lixiang9716/govrail/commit/b9737063cc9a8a39e1581296d03987c20dd098bc))

## [0.34.1](https://github.com/Lixiang9716/govrail/compare/v0.34.0...v0.34.1) (2026-09-17)


### Bug Fixes

* red-team round 4 — TTL minted at acquisition, staged reads the record's counterpart, the unregistered case runs, and the self-test watchdog ([#229](https://github.com/Lixiang9716/govrail/issues/229)) ([db20a84](https://github.com/Lixiang9716/govrail/commit/db20a848da389f50f3ee05d575c6c08fd01d5009))

## [0.34.0](https://github.com/Lixiang9716/govrail/compare/v0.33.1...v0.34.0) (2026-09-17)


### Features

* --write announces a one-sided re-confirm — rule 7's consent moment ([#226](https://github.com/Lixiang9716/govrail/issues/226)) ([5ae192e](https://github.com/Lixiang9716/govrail/commit/5ae192e1d56ecdc6cc317ba4a5e25359593b1add))

## [0.33.1](https://github.com/Lixiang9716/govrail/compare/v0.33.0...v0.33.1) (2026-09-17)


### Bug Fixes

* ritual evidence moves to a tracked ledger (N9) ([#215](https://github.com/Lixiang9716/govrail/issues/215)) ([dc91ec4](https://github.com/Lixiang9716/govrail/commit/dc91ec4104517e95f18464c7cc1d5872e765d401))

## [0.33.0](https://github.com/Lixiang9716/govrail/compare/v0.32.0...v0.33.0) (2026-09-16)


### Features

* the README command reference is generated from gov --help ([#212](https://github.com/Lixiang9716/govrail/issues/212)) ([0f85c97](https://github.com/Lixiang9716/govrail/commit/0f85c97436b5a165fe297c60c62f942111d19769))

## [0.32.0](https://github.com/Lixiang9716/govrail/compare/v0.31.0...v0.32.0) (2026-09-16)


### Features

* gov note list --stale + release identity closure ([#210](https://github.com/Lixiang9716/govrail/issues/210)) ([b4cf504](https://github.com/Lixiang9716/govrail/commit/b4cf5047e901c645bffcd7f5dc98fe4f85e0cd48))

## [0.31.0](https://github.com/Lixiang9716/govrail/compare/v0.30.7...v0.31.0) (2026-09-16)


### Features

* rule 8 — wait on conditions, not on clocks ([#205](https://github.com/Lixiang9716/govrail/issues/205)) ([0f8d070](https://github.com/Lixiang9716/govrail/commit/0f8d070689e980b347acf9e00424f157185906b9))


### Bug Fixes

* the stale-base wording lands on master — docker scenarios pin the clarified direction; the harness prints tracebacks on scenario failure ([e043a39](https://github.com/Lixiang9716/govrail/commit/e043a39adf0213ef7f8cd5f3df735caff4eef948))

## [0.30.7](https://github.com/Lixiang9716/govrail/compare/v0.30.6...v0.30.7) (2026-09-16)


### Bug Fixes

* N6/N7/N8 — the seal's trust chain closes around --config, stripped constitutions, and single-read ordering ([#198](https://github.com/Lixiang9716/govrail/issues/198)) ([270478f](https://github.com/Lixiang9716/govrail/commit/270478f275b52a0ea3ee21091b6d761bd10883b6))
* rebuild the docker helper definition cleanly (docstring + import + call) ([#203](https://github.com/Lixiang9716/govrail/issues/203)) ([65bf351](https://github.com/Lixiang9716/govrail/commit/65bf351004b6de8bd5de0a3987fe8545da4f1e70))

## [0.30.6](https://github.com/Lixiang9716/govrail/compare/v0.30.5...v0.30.6) (2026-09-16)


### Bug Fixes

* N2 unsealed-plane drift, N3 recorded re-baseline ritual, N4 wider seal, N5 umask ([#196](https://github.com/Lixiang9716/govrail/issues/196)) ([8474cd4](https://github.com/Lixiang9716/govrail/commit/8474cd4d2a2a195eec9a5a03692bf8f308fd85ed))

## [0.30.5](https://github.com/Lixiang9716/govrail/compare/v0.30.4...v0.30.5) (2026-09-16)


### Bug Fixes

* close N2 (seal deletion = detector deletion) and harden the new modules per the 0.30.4 red-team ([5b89590](https://github.com/Lixiang9716/govrail/commit/5b89590986286d531440deeb1829c01b51d71175))

## [0.30.4](https://github.com/Lixiang9716/govrail/compare/v0.30.3...v0.30.4) (2026-09-16)


### Bug Fixes

* enforce the plane seal out-of-band + the P1/P2 floor ([#190](https://github.com/Lixiang9716/govrail/issues/190)) ([c425dda](https://github.com/Lixiang9716/govrail/commit/c425ddaba7e2e42fed221d3f1eb25359d119587c))

## [0.30.3](https://github.com/Lixiang9716/govrail/compare/v0.30.2...v0.30.3) (2026-09-15)


### Bug Fixes

* close the audited defect report — 47 findings across the plane ([#188](https://github.com/Lixiang9716/govrail/issues/188)) ([2e2fef6](https://github.com/Lixiang9716/govrail/commit/2e2fef6e0cd1730ecbd7b6dc4ae6516e5ee48e6f))

## [0.30.2](https://github.com/Lixiang9716/govrail/compare/v0.30.1...v0.30.2) (2026-09-14)


### Bug Fixes

* leases are created by atomic hard-link — a race CI caught could double-issue a lease; plus e2e batches 53-55, 8 more scenarios ([#186](https://github.com/Lixiang9716/govrail/issues/186)) ([7650a62](https://github.com/Lixiang9716/govrail/commit/7650a6230efa7e1f3fb1771d2fc881a5d4c29cb2))

## [0.30.1](https://github.com/Lixiang9716/govrail/compare/v0.30.0...v0.30.1) (2026-09-14)


### Bug Fixes

* BOM-tolerant memory plane, check --json stderr report, self-test failure dumps, non-positive window refusals — plus the docker e2e matrix, 98 scenarios (D58) ([#184](https://github.com/Lixiang9716/govrail/issues/184)) ([d847758](https://github.com/Lixiang9716/govrail/commit/d847758c23422104e79aa61b10839553b4203de3))

## [0.30.0](https://github.com/Lixiang9716/govrail/compare/v0.29.4...v0.30.0) (2026-09-11)


### Features

* encoding= checks ride the check engine — differential proof retires the regex scanner ([#182](https://github.com/Lixiang9716/govrail/issues/182)) ([d8036b5](https://github.com/Lixiang9716/govrail/commit/d8036b5661af49c06b32bac1dec402a4804141e3))
* the check engine — syntax-class rules over the parse layer (D57) ([#181](https://github.com/Lixiang9716/govrail/issues/181)) ([4b0e00f](https://github.com/Lixiang9716/govrail/commit/4b0e00f951ad596a382ffad59edbc651a835ef45))
* tree-sitter as a base dependency — the parse layer and gov stats (D54) ([#179](https://github.com/Lixiang9716/govrail/issues/179)) ([dc7e38c](https://github.com/Lixiang9716/govrail/commit/dc7e38cd7354c7724746ab003e317862840f1484))

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

## [0.22.0](https://github.com/Lixiang9716/govrail/compare/v0.21.1...v0.22.0) (2026-09-04)


### Features

* verifiable run receipts — gov run --receipt + gov receipt verify ([#124](https://github.com/Lixiang9716/govrail/issues/124)) ([6fb8d1a](https://github.com/Lixiang9716/govrail/commit/6fb8d1aa1e8ad6443e1faae9e08e2bcc07629e65))

## [0.21.1](https://github.com/Lixiang9716/govrail/compare/v0.21.0...v0.21.1) (2026-09-04)


### Bug Fixes

* decision add table-format draft shape — help and validator agree ([#132](https://github.com/Lixiang9716/govrail/issues/132)) ([7a69aa5](https://github.com/Lixiang9716/govrail/commit/7a69aa5717b48a204f9243d4fc3ac7984a08e9cf))

## [0.21.0](https://github.com/Lixiang9716/govrail/compare/v0.20.0...v0.21.0) (2026-09-04)


### Features

* gov task — task cards pin rules@hash for subagent briefs ([#125](https://github.com/Lixiang9716/govrail/issues/125)) ([bcf35bc](https://github.com/Lixiang9716/govrail/commit/bcf35bcc6983b2b14f1ae86b479ca8dfcb459608))
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
