# govrail

[English](README.md) | 中文

[![CI](https://github.com/Lixiang9716/govrail/actions/workflows/ci.yml/badge.svg)](https://github.com/Lixiang9716/govrail/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/govrail.svg)](https://pypi.org/project/govrail/)
[![Python](https://img.shields.io/pypi/pyversions/govrail.svg)](https://pypi.org/project/govrail/)
[![GitHub Repo stars](https://img.shields.io/github/stars/Lixiang9716/govrail)](https://github.com/Lixiang9716/govrail/stargazers)

一个语言无关的、面向 agent 驱动开发的治理平面：让 coding agent 快速并行工作，同时由机器——而非人的警惕——守住质量线。运行时是 Python 3（>= 3.10）加上为代码统计层提供解析的 tree-sitter——全部由 `pip install govrail` 安装，无需其他工具。

平面提供两个机制：**门禁**（任何能被命令检查的承诺都变成机械检查）和**笔记**（每个非平凡改动记录决策、被打败的方案与后果）。双语配对让对外展示文档保持同步。

## 它改变了什么

| 没有 govrail | 有 govrail |
|---|---|
| Agent 靠"自觉"守规则，没人强制 | 每个可检查的承诺都变成会大声失败的门禁 |
| "为什么这么做"被遗忘或反复争论 | 每个决策都有一条带"被否方案"的笔记 |
| 采用工具意味着重构或引入新运行时 | 一条命令、零重构：`gov init` |

看一个被治理的项目长什么样：[examples/demo-project](examples/demo-project)——
演练每个功能的活标本（量规、拒绝用例、表面映射、决策表）。
任务导向食谱：[docs/cookbook.md](docs/cookbook.zh.md)。

## 安装

```sh
pip install govrail        # 或：uv tool install govrail / pipx install govrail
```

国内镜像同步滞后时，wheel 可能暂缺而 `pip index versions` 已能看到新版本
（JSON API 先于 simple index 更新）；此时改用官方源安装：
`pip install govrail --index-url https://pypi.org/simple`。

这把 `gov` CLI 放到你的 PATH 上（Python + tree-sitter，仅此而已）。每个动作一个子命令：

```sh
gov init --project <path>      # 把平面注入现有项目
gov init --project <path> --upgrade  # 查看模板漂移（只 diff，绝不写入）
gov init --project <path> --adopt all  # 落地缺失的模板文件（绝不覆盖已有）
gov init --project <path> --adopt-new gates.json  # 把新 shipped 门增量合入定制版 gates.json
gov preset list                # 随包 preset（D53）：agent-heavy、python-lib、
                               #  docs-bilingual——按项目类型的采纳补丁包
gov preset show python-lib     # 只读：preset 将落地的一切
gov preset apply docs-bilingual --project <path>  # 落地其门 + 技能 + manifest 提示，
                               #  增量且幂等（绝不覆盖已有）
gov init --project <path> --preset agent-heavy  # init 后立即 apply，一条命令起步
gov doctor                     # 环境自检（PATH、python、解析层、钩子、schema、未采用的门）
gov doctor --json             # 机器可读：{status, checks, problems}
gov note new --class process --ref D6 "标题"  # 笔记脚手架（预校验）
gov init --project <path> --hooks --ci  # 同时安装 pre-push 钩子与 CI
gov uninstall --project <path> # 精确反转
gov run                        # 跑默认模式（defaultMode）的门禁 DAG
gov run --base HEAD~1          # 只跑 paths 命中本次 diff 的门
gov run --merge a b --base origin/master  # 预演并行分支的并集：在 scratch worktree
                               #  逐条合并、每步树上跑门；冲突或红步保留现场（D51）
gov run --gate pairing         # 单门重跑
gov self-test                  # 拒绝用例：工具自带 + 你的（.gov/rejections/）
gov run --json                 # 机器可读：[{gate, outcome, duration_ms, detail,
                               #  selected_by, scoped_out, ...}] —— 含被路径排除的整张门禁集
gov verify-pairing --write     # 编辑一侧后重新确认双语配对
                               #   （写出时逐字段点名；记录的注释声明字段语义——#150）
gov verify-pairing --write en:docs/a.md zh:docs/a_CN.md  # 登记任意命名的配对
gov verify-pairing --explain   # 记录 schema 与约定，只读
gov verify-note-presence       # 非平凡 diff 未带 Agent Note 时警告
                               #   （任务回执默认豁免；manifest 的 note_presence_exempt 申报更多）
gov verify-rubric              # 检查评审量规的结构
gov verify-decisions           # 守卫决策表（编号、被否段、孤儿）
gov verify-decisions --base <ref> # 另查并行分支的编号冲突
gov verify-decisions --json    # 机器可读：{violations, orphans, overdue, ...}
gov decision next --base <ref>    # 下一个空闲 D 号（感知分支；基线陈旧时警告）
gov decision add --from FILE      # 原子追加决策行（写前校验；--against = --base）
gov verify-conflict-markers    # 变更文件携带 git 冲突标记时失败
gov review --base <ref> --grade  # 评审档案 + 交互式量规打分
gov trend                      # --record 历史的门禁耗时趋势
gov receipt verify <commit>    # 这棵树上录过完整全绿运行吗？（#124）
gov recall <terms>             # 检索笔记、决策、postmortem（--any 放宽 AND）
gov audit-notes                # implemented 笔记的新鲜度信号
gov audit-notes --json          # 机器可读：{findings: [{file, signal}], ...}
gov change-scope --base <ref>  # 最小充分集（.gov/surfaces.json 可映射路径）
gov task new "标题" --check "验收项"  # 任务卡：一行 rules@<hash> 钉住子代理简报
gov task check                 # 规则采纳后点名过期卡片
gov task claim T-0001 --agent w1 --ttl 20m  # 把开着的卡租给一个 worker（两人不能同领；
                                            #  busy → exit 3 点名持有者）
gov task release T-0001 --agent w1          # 释放自己持有的卡片租约
gov task close T-0001          # 跑门禁，全绿运行即完成回执
gov task list --json           # 卡片数组 [{id, title, status, rules, claim}]——claim 读自
                               #  租约文件，过期视为未认领
gov acquire reports/summary.md --agent w1  # 租约占用共享资源（busy → exit 3；
                                           #  --wait S 轮询，--ttl S 封顶；
                                           #  成功与 busy 都播报锁根路径）
gov release reports/summary.md --agent w1  # 释放自己持有的租约（绝不代他人释放）
gov locks                      # 列出当前租约（纯诊断）
```

`init` 非侵入且幂等：创建 `.gov/rules.md`，仅在缺失时添加 `gates.json`、笔记 README 与 agent 技能（recall-first、pre-push-checks、code-review、archive-agent-notes），向 AGENTS.md 追加一行引用，绝不覆盖项目自己的文件——包括它自己的技能。`--hooks`/`--ci` 可**事后补装**（已初始化项目 `gov init --hooks` 只装该加装，定制原样不动）；`--hooks --pre-commit` 额外安装可选的 pre-commit 钩子——只对暂存文件跑廉价内容门（配对 sidecar 新鲜度、冲突标记），配对漂移在 `git commit` 即被拦截并内联点名修复命令，而非晚一个阶段到 push 才现形（#110）。`uninstall` 精确反转一切；文件与模板有差异时点名并列出，需 `--force` 才继续（真两步）。新装首跑不红：pairing 门禁以 advisory 落地，`gov verify-pairing --write` 为存量文档建立基线后，摘除 `allowFailure` 即升级为强制。`enabled: false` 让门禁下线而不删除定义。

## 内部内容

- `gov/` — Python 包：`gates`（`gates.json` 上的 DAG 运行器）、`verify_notes`（三段必填）、`verify_translation_pairing`（git blob 哈希）、`verify_note_presence`、`verify_rubric`、`recall`（记忆检索）、`audit_notes`（新鲜度信号）、`change_scope`、`self_test`、`archive_notes`。
- `gov/templates/` — `gov init` 注入项目所用的规则、默认 `gates.json`、笔记格式与 agent 技能。
- `.gov/rules.md` — 规则的唯一事实源。
- `.agents/notes/` — 决策记录格式与生命周期。
- `.agents/skills/` — 让 agent 优先走到工具前的触发器：
  `recall-first`（先查记忆再提案）、`pre-push-checks`（最小充分集）、
  `code-review`（量规评审）、`archive-agent-notes`。
- `docs/review-rubric.md` — PR 如何被评审：门禁查不了的标准，逐条判定。

## 出处

机制蒸馏自 DeepSeek Harness 仓库，其"门禁高于散文"公理塑造了本模板。保留：治理平面。留给你：产品平面。已锁定的设计决策见 [docs/decisions.md](docs/decisions.md)。

## Star 历史

![Star History Chart](https://api.star-history.com/svg?repos=Lixiang9716/govrail&type=Date)
