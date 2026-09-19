# 持久化

[English](README.md) | 中文

平面自己会写盘的每一种格式——封印、台账、任务卡、回执、清单——都是采用者跨版本依赖的用户数据。本目录是防止这些形状被静默更改的确认链:形状可以变,但必须带着一条记录,说明兼容性影响,并链接到它之前的那条。

## 组成

- `schemas/<type>.schema.json` —— 每种持久化格式的**当前**声明形状:产物、写入者、读者、运行时类别(`tracked` / `runtime-deletable`)与字段。从读写该格式的代码出发撰写。
- `changes/NNNN-<topic>.md`(中文配对)—— 每次变更一条确认记录,恰含一个 fenced JSON 块:记录号、日期、类别(`baseline` / `compatible` / `breaking`)、它触及类型的逐类型 `before`/`after` 摘要。含 `TODO` 的未完成草稿验证不过。
- `catalog.json` —— 由 `scripts/check_persistence.py --update` **生成**,禁止手改。把每个类型映射到活体 schema 摘要与最新记录。

## 规则

- 某类型的第一条记录是它的 `baseline`(`before: null`);此后每条后继对其触及的每个类型,`before` 等于前继的 `after`——线性链,无分叉。
- 某类型最新记录的 `after` 必须等于活体 schema 文件的摘要:**不落记录就改 schema 会变红**,记录声称的摘要与文件不符同样变红。
- 类别:`compatible` 旧读取者继续工作;`breaking` 旧读取者必须响亮拒绝,迁移由 `gov update` 负责,记录中写明。
- `runtime-deletable` 格式(`.gov/history/`,N9)确认在案但永不迁移——读取者对不认识的形状仍要响亮失败。
- 验证诚实证明的边界:链在树内自洽,且锚定到已声明的形状。**代码**是否符合 schema,靠评审与测试,不靠这门——与 DSH 对其验证器的声明同一极限。

门是 `persistence`(blocking,自吃专用)。与格式变更同一个 PR 落记录——没有记录的 schema 变更走不出这台机器。
