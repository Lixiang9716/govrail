# 贡献指南

[English](CONTRIBUTING.md) | 中文

govrail 是面向 agent 驱动开发的治理平面，并且用它自己的规则治理自己的
开发——因此贡献就意味着遵守它注入到其他项目里的同一套规则。

## 环境准备

```sh
git clone https://github.com/Lixiang9716/govrail.git
cd govrail
pip install -e .        # 以可编辑模式安装 gov CLI
```

## 运行门禁

```sh
pytest -q                 # 单元测试
gov self-test             # 拒绝用例：证明每条治理 gate 都能拒绝
gov run                   # 完整 gate DAG（notes + pairing + note-presence + self-test）
```

## 提交改动

1. 完成改动。
2. 运行 `gov run`，修掉所有红项（`gov run --base <ref>` 只跑最小充分集）。
3. 改动若非平凡，在同一个 PR 里新增或更新一篇 Agent Note
   （`.agents/notes/implemented/<class>/<date>-<topic>.md`）。笔记必须
   包含 `## Problem`、`## Decision`、`## Alternatives considered`——
   精确标准见 `.gov/rules.md` 规则 2 与 3。
4. 开 PR。CI 会运行门禁。

## AI 辅助贡献

欢迎并预期 AI 辅助开发——本仓库自身即由 agent 深度驱动。三条规则保证
这件事是诚实的：

- **必须披露。** 在 PR 描述中说明哪些部分由 agent 完成。未披露的
  agent 产出可能被直接拒绝——评审投入取决于知道代码是谁写的。
- **合并由人负责。** 开 PR 的人是记录在案的作者：能够解释每一处改动、
  回应评审、并负责回滚。
- **gate 不在乎代码是谁敲的。** agent 改动同样要通过拒绝用例、同样的
  Agent Note 格式、同样的封印重基线纪律。gate 无法评判的部分，属于
  评审工作——不是走形式。

## 等待 CI 与异步步骤

等条件，不等时钟（规则 8）：`gh pr checks --watch`、
`gh run watch <id> --exit-status`、测试里"带截止时间的条件轮询"。
指望某个状态已经发生的裸 `sleep N` 会在评审中被拒绝；唯一合法的
sleep 是为真实物理时间节拍（如租约 TTL 到期）计时。

## 笔记与规则

- 常设指令：[.gov/rules.md](.gov/rules.md)（动手前先读）。
- 已锁定的设计决策：[docs/decisions.md](docs/decisions.md)（中文）。
- 双语文档成对整体合并：[docs/i18n/README.md](docs/i18n/README.md)。
- 选择最小充分检查集：`gov change-scope --base <verified-ref>`。

## 发布

1. 发布由 release-please 依据 conventional commits 自动裁切；版本号
   以 `gov/version.py` 为唯一来源。
2. 发布标签会自动触发 PyPI 发布——工作流校验标签与包版本一致。PyPI
   索引可能滞后发布约一分钟；发布后立刻 `pip install -U` 可能拿不到
   新 wheel——先重试，再怀疑发布。
3. 发布 PR 存续期间，工作流会把缺失的 HIGHLIGHTS 小节起草到 PR 分支
   上（`gov verify-doc-sync --write`：条目逐字复制自 CHANGELOG，每个
   标题自声明为草稿，D46）——发布合并时 CHANGELOG + 版本 + HIGHLIGHTS
   一起落地，doc-sync gate 在 master 上永不红。草稿只满足配对，不满足
   文笔：合并前后把小节条目改写成面向用法的内容（HIGHLIGHTS 的真正
   载荷），在此之前标题会明确标注 "draft"。

### 发布 PR 可能需要一次点击

`chore(master): release x.y.z` PR 由 release-please 机器人创建。
GitHub 会把它的 CI 运行挂在 "action_required"（机器人 PR 的 workflow
运行需要维护者批准；该设置只存在于仓库界面）。遇到时二选一：

- 打开 PR 的检查页点击 **Approve and run**——CI 运行，`gates` 检查
  出报告，PR 正常合并；或
- 以 owner 通道合并（`gh pr merge <n> --squash --admin`）——管理员
  不受本仓库必需检查约束，这是有意为之的范围设定：每个非管理员 PR
  （无论人或 agent）仍然必须通过 `gates`。

优先第一种：它让发布 PR 的 CI 证据保持真实。
