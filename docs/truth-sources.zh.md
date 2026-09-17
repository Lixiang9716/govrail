# 真相源登记

[English](truth-sources.md) | 中文

本仓库的每个事实都有**唯一**的权威归属——其余一切都是副本（由机械方式保持
同步）或链接。本登记表列出每个真相源、它的副本、以及钉住这层关系的测试：
没有钉的行就是会撒谎的行。哪一类文字归哪个文档层管辖，见
[tiers.md](tiers.md)——本登记表不重复那张表，而是把它扩展到代码常量、
台账与封印。

## 代码常量类

| # | 真相源 | 管辖 | 副本 | 钉住它的测试 |
|---|---|---|---|---|
| 1 | `gov/version.py` `__version__` | 包版本 | pyproject 动态读取；发布 tag 与它校验 | release 工作流的 tag 校验 |
| 2 | `gov/cli.py` `_COMMANDS` | 命令表面与一行描述 | README 的生成命令区块（`gov:commands` 标记） | `tests/test_docs_cli_consistency.py` |
| 3 | `gov/audit_notes.py` `FLAGS` | 每个命令的旗标表面 | `gov <cmd> --help` 输出 | `tests/test_flag_registry.py` |
| 4 | `gov/verify_translation_pairing.py` `DEFAULT_CONFIG` | 配对默认值（include、counterparts、exclude） | `docs/i18n/README.md` 的示例 JSON | `tests/test_truth_sources.py` |
| 5 | `gov/note.py` `CLASSES` + `gov/verify_notes.py` `LIFECYCLES` | 笔记分类学（闭合集） | notes README 中的枚举 | `tests/test_truth_sources.py` |
| 6 | `gov/doctor.py` `HAND_SHIPPED_GATES` ∪ `gov/templates/gates.json` | shipped gate 全集 | doctor 的 gate 采纳检查读取两者 | `tests/test_truth_sources.py` |

## 文件权威类

| # | 真相源 | 管辖 | 副本 | 钉住它的测试 |
|---|---|---|---|---|
| 7 | `.gov/rules.md` | 宪法（8 条规则） | `gov/templates/rules.md`、demo 标本副本 | `tests/test_template_sync.py` |
| 8 | `gov/templates/gates.json` | 采纳者 gate DAG 基底 | demo 的 gates（基底 + 其类型化特有项）；仓库根的 `gates.json` 是 **dogfood 实例**而非基底 | `tests/test_template_sync.py` |
| 9 | `gov/templates/gov.yml` | 采纳者 CI 形态 | `gov init --ci` 渲染它（钉版本） | `tests/test_template_sync.py` |
| 10 | `.gov/pairing.json` + 各 `*.i18n.yaml` | 双语配对真相（每侧 git blob hash） | — | `gov verify-pairing`（pairing gate） |
| 11 | `.gov/plane-seal.json` | 平面自身配置的 sha256 封印 | — | `gov verify-plane`（DAG 内与带外） |
| 12 | `.gov/rituals.jsonl` | append-only 仪式台账（tracked） | — | 首次仪式创建；`tests/test_rituals.py` |
| 13 | `docs/decisions.md` | 决策日志与 D 号分配 | `.gov/decisions.json` 可覆写路径/格式（本仓库未实例化 = 默认） | `gov verify-decisions`、`gov decision next` |
| 14 | `CHANGELOG.md` ↔ `gov/HIGHLIGHTS.md` | 已发布版本配对 | HIGHLIGHTS 小节由 CHANGELOG 起草 | `gov verify-doc-sync`（doc-sync gate） |
| 15 | `.agents/skills/*/SKILL.md` | 随包 skills | `gov/templates/skills/`、demo 副本、agent-heavy preset 的 `parallel-workers` 副本 | `tests/test_template_sync.py` |
| 16 | `.gov/rejections/case-*.sh` | 拒绝用例（规则 6） | demo 副本（另加 demo 自有 gate 的自有用例） | `tests/test_template_sync.py` |

## 不是文件的锚

| # | 真相源 | 管辖 | 钉住方式 |
|---|---|---|---|
| 17 | git 历史 | 采纳记录：历史中存在过的封印永远无法静默变成"从未采用"（N7）；仪式台账与配对的过往状态在历史中存续 | 结构性——改写历史超出任何工作区工具的威胁模型 |

## 明确不是真相源

- `.gov/history/` —— 运行时台账，设计上 gitignore；仪式台账存在的理由
  正是这片存储可删（N9）。
- `.release-please-manifest.json` —— 由 release-please 自行同步，人不编辑。
- README 快速开始的注释 —— 人工策展的判断，非生成物；其引用的命令仍被
  `tests/test_docs_cli_consistency.py` 对 CLI 表面做解析校验。
- 仓库根的 `gates.json` —— dogfood 实例（它带着 D4 已从采纳者 DAG 退役的
  `self-test`）；面向采纳者的真相是模板，见第 8 行。

新增真相源？登记表自身的规则：**一行必须点名它的钉**——同一个变更里
写好测试，否则那一行记录的是意图，不是事实。
