# 复盘 0001:必需检查弃权,而弃权即合并

## 执行摘要

PR #290 在 CI 存在红项的记录下落进了 master。必需检查——`gates` 汇总
job——从未投票:它依赖的 `lint` job 失败了,GitHub 的默认语义是"依赖失败
则跳过本 job",而分支保护把 skipped 状态的必需检查视为已满足。于是
auto-merge 在 PR 开出两分钟后就完成了合并——head 提交上明明白白挂着
`lint: failure` 和八个 `e2e-docker` 矩阵红格,却没有任何裁决去咨询它们。
三个独立缺陷叠加才酿成这次逃逸:一个失败时选择"弃权"的汇总 job、一套把
弃权当作通过的合并语义、以及一份手写的 needs 清单让部分工作流游离在裁决
之外。#294 修掉了实例(69 处 ruff 发现;lint 收编进本地 DAG),#296 修掉了
机制(`if: always()` + 对全部 job 的裁决)。持久的教训:**能跳过的必需
检查不是门——对合并者而言,弃权就是通过。**

## 时间线

证据是 PR head(`04ce396`)上的 check-run 记录,以及 `f80c2b9`(修复前的
master)上的工作流文件原样。

- 2026-09-18 20:13 UTC —— PR #290 开出(squash,auto-merge 已启用)。
- 同一次运行 —— `lint: failure`(重构带入 69 处 ruff 发现);`gates:
  skipped`,因为它的 `needs: [lint, gates-cell, governance, derive]`
  (`.github/workflows/ci.yml` 在 `f80c2b9` 时)包含了失败的 job,而当时
  还没有 `if: always()` 去覆盖默认跳过;`e2e-docker`:10 个矩阵格 8 个
  `failure`——在 needs 清单之外,任何裁决都看不见。
- 20:15 UTC —— auto-merge 把 `6fb6fba` 落上 master。必需检查的记录是
  `skipped`,保护设置视其为满足;红着的 job 从未被咨询。69 处 ruff 发现
  从此在 master 上。
- 20:36 UTC —— PR #294 开出:修净 69 处发现,并把 ruff CI job 收编为
  blocking 的 `lint` 门、配上拒绝用例——本地 pre-push DAG 从此看得见 CI
  看得见的世界(落为 `8a85f1d`,记录于 D61)。
- 2026-09-19 03:20 UTC —— PR #296 开出,这次对着机制而不是实例:`gates`
  needs 扩到全部 11 个 job,`if: always()` 让汇总在依赖失败时也必须渲染
  裁决,裁决对 `needs.*.result` 中任何 `failure`/`cancelled` 走红
  (落为 `5266655`)。
- 03:29 UTC —— #296 合并;任务卡 T-0003 以全绿 receipt 关卡(`106ede8`)。

## 根因

同一个类,三个实例:"一个执行面,从未声明自己在失败时的行为"。

1. **汇总弃权了。** `gates` job 没有声明失败行为,于是继承了 GitHub 的
   默认:依赖失败则跳过。一个为聚合失败而生的汇总,恰好在它存在的理由
   面前沉默了。
2. **弃权满足了合并者。** 分支保护要求的是"named check";一个报告
   `skipped` 的检查不是 failure,于是保护放行。这道门从红色世界有两条
   出口,而守卫只堵了响亮的那条。
3. **裁决范围靠手维护。** `needs` 只列了十个 job 中的四个;
   `e2e-docker` 的八个红格从未抵达任何裁决。成员靠人肉策展的聚合体,
   会在"新增一个 job"的那一刻开始静默撒谎——而那一刻恰恰是注意力都在
   别处的时候。

下次能认出来的普遍形式:每个聚合裁决都必须声明失败时的行为(永远渲染、
响亮失败——rule 5 应用到 CI 上),必须对被裁对象的**闭合全集**计算而不是
策展子集,并且每个 CI 专属检查都要在本地平面有个家——否则 pre-push 门与
CI 裁决的是两个不同的世界。

## 补上的护栏

- **汇总不能再弃权:** `.github/workflows/ci.yml` 的 gates job 现在带
  `if: always()`,needs 全部 11 个 job,对 `needs.*.result` 中任何
  `failure`/`cancelled` 走红,只容忍条件性跳过(PR #296;笔记
  `.agents/notes/implemented/process/2026-09-19-ci-auto-merge-gates-job.md`;
  任务卡 T-0003 以全绿 receipt 关卡)。
- **CI 专属检查有了本地的家:** `lint` 门——blocking、自吃专用、接进
  `modes.all`,配拒绝用例 `.gov/rejections/case-lint.sh`(PR #294;D61;
  笔记
  `.agents/notes/implemented/architecture/2026-09-19-code-design-contracts.md`)。
- **残余风险,已记录:** needs 数组仍是手写的(GitHub 没有全 job 通配);
  缓解在于漏加一个 job 现在是一行可见的 diff,且 `.github/workflows/ci.yml`
  中 gates job 的注释写明了常设规则——新 CI job 的发现面包含 gates 的
  needs 清单。
