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
gov run                   # 完整 gate DAG（本仓库自己的 gates.json）
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

## 保持 README 命令参考与实际一致

README.md 中的命令区块（`gov:commands` 标记之间）由 `gov --help` 生成——
描述的唯一真相源是 `gov/cli.py`。改动任何 CLI 面后运行
`scripts/update_readme_commands.py`；区块过期、文档引用了不存在的
`gov ...` 命令/旗标、或某命令的 help 行漏列真实子命令，CI 都会变红
（tests/test_docs_cli_consistency.py）。不要手改该区块。

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
3. 发布 PR 存续期间，工作流会起草缺失的 HIGHLIGHTS 小节
   （`gov verify-doc-sync --write`：条目逐字复制自 CHANGELOG，每个
   标题自声明为草稿，D46）并把它 amend 进 release 提交本身——分支头
   是一个完整提交（CHANGELOG + 版本 + HIGHLIGHTS 同在），任何 CI 运行
   都不可能捕获到半成品 SHA；起草 job 还会自动取消被取代的待批 run，
   唯一可批准的就是完整那份。草稿只满足配对，不满足文笔：合并前后把
   小节条目改写成面向用法的内容（HIGHLIGHTS 的真正载荷），在此之前
   标题会明确标注 "draft"。

### 发布链路端到端自动

配置 `RELEASE_PAT` secret（见下方一次性设置）后，一次 release 级合并到
master 的整条链路无人值守：release-please 以用户身份开 PR（其 CI 立即
运行——不再有 action_required 挂起），起草 job 把 HIGHLIGHTS 草稿
amend 进 release 提交、取消被取代的 run、武装 auto-merge；必需检查
全绿后 GitHub 自动 squash 合并，合并推送触发 release job（打 tag +
GitHub Release + 发 PyPI）。红 PR 永不自动合并——链路在证据面前停下，
而不是在希望面前。

**一次性设置**（仓库 owner）：创建 fine-grained PAT，范围仅本仓库，权限
Contents: read/write 与 Pull requests: read/write，存为 `RELEASE_PAT`
secret。在它就位前，workflow 回退到默认 token：PR 的 CI 挂在
action_required，批准起草 amend 之后创建的那次运行（过期的旧 run 会被
自动取消）是仅剩的人工动作。owner 通道（`gh pr merge <n> --squash
--admin`）仍然可用；优先保留真实 CI 证据。
