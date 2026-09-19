# Agent Note: CI 全绿才准 auto-merge：gates 汇总收编全部 job

Status: implemented

## Problem

#290 在 lint job 红着的状态下被 auto-merge 进了 master。根因：分支保护的必需检查只有 `gates` 汇总 job，而它 `needs: [lint, gates-cell, governance, derive]` 只覆盖四个 job——backport-shadow、windows、macos、gbk-locale、e2e-docker、nightly 全部游离在裁决之外。只要游离 job 红、覆盖内全绿，必需检查照样绿，auto-merge 照样落。"CI 完全绿才准合并"从未被机制保证过。

## Decision

`gates` 汇总 job 的 `needs` 扩到工作流全部 11 个 job（含 `changes`），加 `if: always()`，裁决步显式红于任一 `failure`/`cancelled`、容忍条件性 `skipped`（nightly 是 schedule-only；windows/macos/gbk-locale/e2e-docker/backport-shadow 在 docs-only PR 上合法跳过）。必需检查名保持 `gates`——分支保护零改动、零迁移窗口，洞在原地补上。`if: always()` 双重承重：依赖失败时本 job 仍要跑出红裁决；skip 不等于 red。

## Alternatives considered

- **新开一个 all-green 汇总 job 并把分支保护切过去**：被否——必需检查名迁移有窗口期（切早了等待一个不存在的 check，全部 PR 卡死），且 `gates` 这个名字已是本仓必需检查的既定词汇；原地扩展零迁移。
- **把游离 job 逐个加进分支保护的 required contexts**：被否——contexts 清单会随 job 增删漂移，每加一个 CI job 要记得改保护设置（人肉纪律，rule 1 要消灭的东西）；聚合裁决让清单成为 ci.yml 里的一个 needs 数组，diff 可评审。
- **容忍 skipped 是否开口子**：skipped 只发生在声明条件不适用时（schedule-only、docs-only），且每个 skip 都是工作流文件里的显式 `if:`——把 skipped 判红会让任何 docs-only PR 永远无法合并。failure/cancelled 全红，不豁免。
