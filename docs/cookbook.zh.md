# 食谱 —— 任务、命令、预期输出

[English](cookbook.md) | 中文

食谱按任务组织：症状或目标、命令、好的输出长什么样。参考手册在
README；这一层回答"现在该做什么"。

## 安装与第一天

```sh
gov init --project .            # 规则、门禁、笔记、技能落地
gov doctor                      # PATH、python、钩子、gates schema——健康？
gov run                         # pairing 以 advisory 运行直到 baseline
```

新装不该红。有文档要配对时：

```sh
gov verify pairing --write      # 全部配对建立基线（部分成功：能记的记，
                                # 不能记的报）
```

## 五分钟见到你的第一次红→绿

随包门禁守的是治理平面本身；你自己的测试命令才让平面成为「你的」。
从 `pip install` 到第一次红→绿：

```sh
gov init --project . --hooks    # 落地平面，外加 pre-push 运行器
gov gate add tests --paths 'tests/**' -- pytest -q
                                # 校验、合并，随后跑一次验证 `gov run --gate tests`
                                # ——要么 PASS，要么具名失败，绝不无声
echo 'def test_broken(): assert False' > tests/test_broken.py
gov run --gate tests            # 红：FAIL tests（1 个文件在范围内），失败输出
                                # 只内联打印一次
rm tests/test_broken.py
gov run --gate tests            # 又绿了——这一红一绿就是产品本身
gov note new --class feature --ref D0 "接入 tests 门禁"
                                # 记录接线决策（规则 2）
```

你的语言没有规则时，门禁会说出来而不是悄悄通过：`gov check` 对无规则
可查的源码打印 `SKIP(nolang: …)`（#308）。单语项目？pairing 门保持
advisory 即可——`gov init` 会在安装时把这一点说明白（#315）。

## 我想按项目类型起步

`gov init` 注入的是通用地板（D28：类型化内容不进默认模板）。**preset** 负责补上类型化的一套——某类项目需要的门、技能与 manifest 提示。先看再装：

```sh
gov preset list                 # 本包发布了哪些类型
gov preset show <name>          # 只读：每个门、mode、技能、提示
```

今天随包三个（D53）：`agent-heavy`——多 agent 并行开发（decisions 守卫、worker 协议技能、簿记豁免）；`python-lib`——Python 包仓库的 pytest 与 build 门，接入 `all` 与 `quick`；`docs-bilingual`——CHANGELOG/HIGHLIGHTS 同步守卫，面向真有这两个文件的仓（缺文件门红是正确的 fail-loud；HIGHLIGHTS 段落标题必须是 `## <版本> <描述>`——裸 `## 1.0.0` 不被识别为段落）。

然后一条命令带着 preset 起步：

```sh
gov init --preset agent-heavy   # 或：python-lib / docs-bilingual
```

```
init: initialized /path/to/project
  …
preset: applying 'agent-heavy' to /path/to/project
  gates: added 1 (in preset order): verify-decisions
  skill: created .agents/skills/parallel-workers/SKILL.md
  hint: wrote manifest 'note_presence_exempt' = [".gov/tasks/**"]
```

apply 经平面的采纳契约增量落地——同 id 的本地门保留并点名（D39），已有技能跳过（D29），manifest 里你已设的键赢（D49）——所以它也能事后补装到已初始化项目（`gov preset apply <name>`）；重复 apply 全部报 "already adopted"、零写入。preset 名写错？exit 2 会列出存在的。

## 改完文档 pairing 变红了

报错自带修复——照抄即可：

```
docs/foo.md: out of sync — re-confirm: gov verify pairing --write docs/foo
(the en side last moved in a1b2c3d, confirmed 2026-09-01T10:00:00+00:00)
```

`--write <stem>` 只重基线指名的对。括号里说明哪侧在哪个提交动的、
何时确认的——先核对翻译再确认，别反过来。

## sidecar 字段到底是什么意思？

记录的字段语义过去只活在代码里——agent 手工重盖 sidecar 时被告知
"写 HEAD"，跟门禁纠缠到一次 amend + force-push 之后才绿（#150）。
这些字段不是 HEAD：

```
pair:
  en: 6f0f…    # 源侧的 git blob hash（git hash-object）——不是文件 sha256
  zh: 5c81…    # 对侧同
counterpart: foo.zh.md
last_confirmed: 2026-09-04T19:24:25+00:00  # 该次确认的 UTC ISO-8601 时刻
en_commit: 113b230  # 确认时最后触碰该侧的提交——
zh_commit: 113b230  # 不是 HEAD，也不是确认提交；仅为上下文
```

绝不手工编辑记录：`--write` 会重新生成它，并在记录内部的注释行里
声明这些语义，写出时逐字段点名。记录全文 schema 与本项目的约定，
一条只读命令即可得：

```sh
gov verify pairing --explain
```

## 漂移在提交时抓到，而不是推送时

pre-push 拦截有效，但忙碌分支上每次对编辑都先付一次被阻塞的 push
（issue #110 的实证）。装上可选的 pre-commit 钩子——只对暂存文件跑
廉价内容门：

```sh
gov init --hooks --pre-commit   # 加装项；单用 --hooks 仍是 push 阶段
```

同样的编辑现在早一个阶段、在 `git commit` 时失败，内联同款点名修
复——照跑、重新暂存，提交直接落地，不经 push 往返：

```
docs/foo.md: out of sync — re-confirm: gov verify pairing --write docs/foo
verify_translation_pairing: 1 violation(s) in 1 staged pair(s)
```

暂存里没有配对文件？钩子保持安静。觉得 commit 钩子侵入的仓库不传
`--pre-commit` 即可——提交阶段零变化，pre-push 模型原样。

## 加一个门禁的完整闭环

1. 在 `gates.json` 定义（未知键即报错——笔误无法静默停靠）：

```json
{"id": "source-limits", "command": ["./check_limits.sh"],
 "paths": ["src/**", "eval/**"]}
```

2. 证明它能拒绝——`.gov/rejections/` 下的拒绝用例，shebang 在首行、
   gate 声明在前五行内：

```sh
#!/bin/sh
# gate: source-limits
# 造一个超限模块，断言门禁变红，还原
...
```

3. 查账本：`gov self-test --scope project` 末尾应是
   `source-limits(1)`——而不是 `NONE — rule 6`。

## rebase 把冲突标记带进了提交

症状：rebase 中途 `git add` 了仍带 `<<<<<<<` / `=======` / `>>>>>>>`
块的文件，`git rebase --continue` 一声不吭照单提交——git 分不清真
标记与被引用的标记，只能沉默。conflict-markers 门随模板 all 模式
自带，读的是变更文件的内容：

```sh
gov verify conflict-markers            # 变更文件 vs auto 基线
gov verify conflict-markers --staged   # 只查暂存区——pre-commit 轻量版
```

diff 里存在带标记文件时的预期输出（exit 1）：

```
doc.md:3: conflict marker '<<<<<<<' — resolve the merge, or append 'gov:ignore-marker' to exempt a deliberate literal
doc.md:5: conflict marker '======='
doc.md:7: conflict marker '>>>>>>>'
verify_conflict_markers: 3 marker(s) in 1 file(s) — git will not police its own conflict text; the gate does (D38)
```

逃生门：确实要写字面量（引用标记的测试夹具、讲合并的文档）时，
在该行行尾追加令牌 `gov:ignore-marker` 即可通过。孤立的裸
`=======`（Markdown H1 setext 下划线）不算标记；只有同文件存在
兄弟标记时才计数（D38）。

## 实验装置不是运行时代码

`.gov/surfaces.json`：

```json
{"eval/**": {"surface": "experiments", "gates": ["source-limits"]}}
```

此后 eval-only 改动的 `gov change-scope` 只建议
`source-limits`——产品面零噪音。

## 评审一份 PR

```sh
gov review --base origin/main --grade
```

一条命令：档案（范围、笔记、recall、量规），然后交互打分
（`p`/`f`/`s`/`q`；`f` 追问证据），然后裁决块——逐条行、blockers、
`verdict: approve` 或 `request changes`。人裁决；机器誊写。

## recall 一无所获——是哪个词失败了？

`gov recall` 要求所有词命中同一条目，多词 miss 曾只能盲猜。现在 miss 自带诊断，且每次运行都在 stderr 陈述搜过的语料（stdout 的排序命中仍居首）：

```sh
gov recall 效用 utility 归因
```

```
recall: no match for '效用 utility 归因'
  per-term hits: 效用: 0 / utility: 2 / 归因: 0
  (strict AND — every term in one entry; retry with --any to rank partial matches)
```

`utility: 2` 说明语料认识这个词——是 AND 拖垮的；`效用: 0` 说明语料里根本没有它。照提示重试：

```sh
gov recall --any 效用 utility 归因    # 部分命中，按命中词数排序
```

严格 AND 仍是默认；`--any` 空结果依旧 exit 1。

## 写一篇笔记

```sh
gov note new --class process --ref D6 "为什么选 x"
gov note check        # 格式 + 路径 + 悬空 D 引用，pre-commit 级轻量
```

错的 class 或悬空的 D 引用在投入文字之前就被拒。没有决策表时
D 引用明示"未核对"——绝不静默跳过。

## 决策表

`gov decision verify` 守卫编号（唯一、连续）、备选（每条 D 记录
打败了什么）、并报告孤儿（无笔记引用——信息性）。上下文可能过期
的决策带 `review-by: 2027-01-01`；过期打 review-due 提示。

## 并行分支都要"下一个 D 号"

```sh
gov decision next --base origin/master   # 合并后历史会显示的号
gov decision add --from draft.md --against origin/master  # --against = --base
gov decision verify --base origin/master
```

两个 worktree 从同一基线各算"下一个空闲号"都会拿到 D39；`--base`
并入基线分支已落地的号，门禁运行时点名冲突（`D39: number
collision … 用 gov decision next --base 重编号）而不是让重复行
悄悄合并。单文件格式的追加是原子的（临时文件+替换），但跨
worktree 合并仍是文本冲突——配置 `.gov/decisions.json`
`{"path": ".gov/decisions", "format": "dir"}`（一决策一文件）后
追加即新增文件：并行分支合并零冲突。

陈旧的基线会被点名，而不只是被吸收（#147）：本地表缺少 ref 上已有
的行时，`next` 与 `add` 都会警告——`your base is 2 rows behind
'origin/master' (missing D2, D3) — rebase before numbering`——软警告，
绝不阻断；你拿到的仍是合并后历史会显示的号。`--against` 是 `--base`
的别名，不是第二套语义。

## 多分支并行，合并前如何预演并集

```sh
gov run --merge feat-a feat-b feat-c --base origin/master
```

**症状**：每个 agent 分支在自己的树上全部门禁绿过，合并却坏了——
文本冲突 git 能拦，语义冲突（各自绿、并集红：两条分支往
`gates.json` 加了同一个门 id，或两处改动合在一起才坏）在落地后、
树已经出货时才现形。

**命令**：预演按给定顺序把各分支合并进建于 `--base`（集成基线；
缺省 `origin/master`，缺省不存在会点名并要求显式旗标）之上的
分离 scratch worktree。每合并一条分支，就在该步的并集树上跑门禁
——按本步引入的 diff 选最小充分集。

**预期输出**（全绿）：每步一行摘要——`merge: step 2/3: 'feat-b'
-> tree 9a1b2c3d4e5f; gates: 4 ran, 4 pass`——然后 `merge: union of
3 branch(es) is green`，exit 0。**文本冲突时**：exit 1，输出
`merge: branch 2 (feat-b) conflicts with already-merged set (feat-a)`
加冲突文件列表，且 scratch worktree **保留现场**（打印路径）供检查；
门禁红同样点名失败分支、已合并集合、失败门与首行输出。修好再跑。
带 `--receipt` 时最末步为并集树录 D44 回执——落地后（含 squash
merge）`gov receipt verify <commit>` 证明落地的树就是绿过的那棵。

## 多个 agent 共写一个文件，如何不互踩

```sh
gov lease acquire reports/summary.md --agent w1 --ttl 600  # exit 0 = 拿到租约
gov lease acquire reports/summary.md --agent w2            # exit 3，点名持有者
gov lease release reports/summary.md --agent w1            # 只有持有者能释放
```

**症状**：几个并行 agent 写同一个文件，互相覆盖——变成"谁最后写谁
赢"。worker 之间互相盲态，需要工具来说"等"还是"走"。

**命令**：写之前先拿租约。租约是 git common dir 下的一个小 JSON 文件
（覆盖同 clone 的全部 worktree），由 `--ttl` 封顶、绝不永久阻塞，且
**只管活性**：它防止重复劳动，不承载正确性。资源被占时 exit 3——这
就是"阻塞还是继续"的时刻：`--wait 30` 以 1s 间隔轮询（直到租约过期
或被释放），或者先去干别的。

**预期输出**：赢家打印
`acquire: 'reports/summary.md' leased by 'w1' until 2026-09-05T…`；
输家在 stderr 得到
`acquire: REFUSED — 'reports/summary.md' is held by 'w1' until …`，
退出码 3——同 holder 重复 acquire 也是 3，锁不可重入。非持有者的
release 会被点名冒充者并 exit 2。`gov lease list` 列出当前租约（纯诊断）。
持有者崩溃时，租约在 `--ttl` 后过期，下一个 acquire 懒接管——此后
可能双持。这正是锁不承担正确性的原因：落地的内容仍由你的门禁与评审
裁决，master 的正确性锚在 push CAS。

## 两个 worker 领同一张卡会怎样

**症状**：两个并行 worker 都读到卡片 T-0001 是 open，于是都开始干活
——卡片格式本身拦不住这种重复劳动（卡片是 rules 钉住 + 回执，D43；
认领簿记不能写进卡片）。

**命令**：开工前先认领：

```sh
gov task claim T-0001 --agent w1 --ttl 20m   # exit 0 = 这张卡归你了
gov task claim T-0001 --agent w2             # exit 3，点名持有者
gov task list                                # [claimed by w1 until …]
gov task release T-0001 --agent w1           # 干完了：放手
```

**预期输出**：赢家的 stderr 打
`task: T-0001 claimed by 'w1' until 2026-09-05T…`；输家得到
`acquire: REFUSED — 'task/T-0001' is held by 'w1' until …`、exit 3——
这就是"等还是先走开"的时刻（`--wait 20m` 以 1s 轮询；等待时长至少要
给到持有者剩余 TTL，否则只会在自己的期限上以 exit 3 收场——见
parallel-workers 技能的 TTL 一节）。过期租约由下一个认领者懒接管；对
已关闭的卡 claim 是 exit 2 而非 busy——等是等不开的。认领状态只住在
git common dir 下的租约文件里：`gov task list --json` 把它暴露为
`claim` 字段（过期视为 null），卡片 JSON 本身一字不动；卡片落地时
`gov task close` 顺路清掉持有者自己的租约。

## 模板演进了——先看，再采纳

```sh
gov doctor                    # 还会点名你从未采用的 shipped 门
gov init --upgrade            # 逐文件 diff；绝不写入
gov init --adopt all          # 只落地缺失的模板文件
gov init --adopt-new gates.json  # 把新 shipped 门增量合入定制版
                                 # gates.json（按 gate id）
gov whatsnew                  # 自你的 init 版本以来新增了什么
```

修改类文件仍归你手工合并（两步哲学）；纯新增一条命令落地；定制版
gates.json 可增量吸收新 shipped 门——本地门原样保留，同名冲突大声
拒绝（D39）；`--upgrade --json` 让 agent 程序化决策。

不在 gates.json 里的门永远不会运行，而此前没有任何东西提示你采用
它——`gov doctor` 会点名当前 govrail 版本已发布、而你的 gates.json
缺少的门（#147）：模板门指向 `--adopt-new`；paths 因项目而异的工具
（`verify-decisions`、`verify-rubric`、`verify-doc-sync`）会点名要
手工接入 mode 的命令。这是 note 不是失败——采用是刻意的选择。

## 编排多个 worktree 而不 cd

```sh
gov -C ../wt-x run --base master   # 门禁跑在 wt-x 那棵树，不是当前树
gov -C ../wt-x doctor
```

`-C <path>`（或 `--path`，置于子命令之前；可像 git 一样链式）在派发
前按值切换目录，输出头部点名解析出的 work-tree 根——跑错树一眼可
见，而不只是"合法"。路径不存在则大声失败（#121）。自带 `--path`
的子命令（verify-decisions、verify-rubric）不受影响：它们的
`--path` 指文件，且写在命令之后。

## 读 trend 的 mover

运行默认记录（`.gov/history/`，已 gitignore）。`gov trend` 按窗口
对半比较每门 p50；mover（`×1.8 ↑`）是要调查的问题，不是结论：

```sh
gov trend --gate tests --base v1.2.0   # 该版本前后对比
```

## 多 agent 一个仓库——这些运行是谁的？

给运行打 `--tag`（或导出 `GOV_CALLER`；旗标优先），标签以调用方
自由文本落入 `.gov/history/gates.jsonl`。`gov trend --by-tag` 按
caller 切分窗口——每个标签的 mover 与稳定门各自报告，未打标的
运行归入 `(untagged)`，不打标则记录形状与从前完全一致（#120）：

```sh
gov run --tag subagent-3        # 或：GOV_CALLER=subagent-3 gov run
gov trend --by-tag              # 按 caller 的前后半窗口 p50 对比
```

## 这个里程碑的 LLM 花费是多少？

govrail 自己不计量任何东西——但驱动 agent 的工具通常已在数
token/调用次数。用同一个标准形状把数字交给同一行运行记录
（#126/D45），再按 caller 滚动合计：

```sh
GOV_CALLER=bridge-agent GOV_COST="tokens=1200,calls=4" gov run
gov run --tag adjudicator --cost tokens=300.5,calls=1   # 旗标优先于 env
gov trend --cost   # 按 caller：各单位的总量与早→晚窗拆分
```

未打标但上报了成本的运行归入 `(untagged)`；未带
`--cost`/`$GOV_COST` 的运行行为与从前完全一致；畸形值大声失败并
点名片段。

## 长会话被未跟踪文件警告淹没

```sh
gov note presence --staged     # 只看 index；干净即静默
```

超五条折叠（`…and N more`）。

## note-presence 对日常簿记狼来了

现在不该了：任务卡回执（`.gov/tasks/**`）默认豁免（#149）。若本仓库还有别的例行面，在 `.gov/manifest.json` 里申报——advisory 只在确实期望 note 的范围外触发：

```json
{ "note_presence_exempt": ["docs/**", "tools/**"] }
```

警告触发时会自述缺的是哪一种——"diff 里完全没有 note 文件"——且每次运行都会打印生效中的豁免面。

## 环境感觉不对劲

```sh
gov doctor
```

规则 5 风格点名问题：gov 不在 PATH、钩子不可执行、门禁命令解析
不到、schema 笔误、决策表解析失败。
