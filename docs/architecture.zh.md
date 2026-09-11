# 治理架构

[English](architecture.md) | 中文

模板分离两个平面。**治理平面**——门禁、笔记、配对、范围——是 Python 3 实现的、语言无关的机制，只作用于 git、Markdown 和 JSON。**产品平面**是你的任意语言代码，仅通过 `gates.json` 里的命令槽接入。

## 门禁 DAG

`gov run --mode <name>` 读取 `gates.json` 并运行一个模式。一个门禁 = 一个"非零退出即失败"的命令数组；`needs` 构成 DAG（门禁在所有依赖通过后才启动，依赖阻塞失败时标 `SKIP`），`concurrency` 限制并行度。启动任何子进程前先校验整个配置：重复 id、未知 needs、循环都会带名字 abort（退出码 2）。

不带 `--mode` 时，若配置了顶层 `defaultMode` 则运行它（注入模板自带 `"defaultMode": "all"`）——改 mode 就是改默认运行集。`enabled: false` 把门禁停在一切运行之外，输出一行 `DISABLED`，"下线"留在配置里而不是删除定义。

门禁用 `paths` glob（`**` 跨目录）声明自己覆盖的范围：`gov run --base <ref>` 按 diff 选中 paths 命中的门（无 paths 的门永远相关）并报告哪些门出了范围——最小充分集出自同一事实源，`gov change-scope` 的建议也读同一份 `paths`。`gov run --gate <id>` 单门重跑。

模板还自带一个查内容而非只看退出码的门：`gov verify-conflict-markers`（issue #104/D38）读变更文件的工作区内容，发现行首的 git 冲突标记即以 `file:line` 点名失败——git 拒绝自查的那种 rebase 失败模式由门禁接管；确实要写字面量的行追加令牌 `gov:ignore-marker` 即豁免，孤立的裸 `=======`（Markdown 标题下划线）不算标记。

### 落地前预演并集（run --merge）

并行 agent 分支各自通过全部门禁，但"并集"直到合并发生才被测到：文本冲突 git 能拦，语义冲突（各自绿、合并红）无人拦。`gov run --merge <branch>… [--base <ref>]`（D51）在建于集成基线（`--base`，缺省 `origin/master`）上的分离 scratch worktree 里预演合并：各分支按命令行顺序逐条 `--no-ff` 合并，每合并一条就在该步的并集树上跑门禁——按本步引入的 diff 选门（D15 的最小充分集；上一步的树 sha 是 diff 基线）。文本冲突或门禁红即点名中止——分支、已合并集合、冲突文件或失败门——并**保留现场** scratch worktree 供检查；全绿则清理并打印各步摘要。退出码仍是 D2 的词汇。宿主安全是 D33 的三墙，且因本命令会变更状态而升级：敌对的仓库解析变量在任何操作之前大声拒绝，git 操作一律 `-C` 钉住，scratch 必须把 toplevel 解析到自身，验收测试钉住宿主工作树字节不变。带 `--receipt` 时最末步升级为全矩阵并为并集树录 D44 回执——落地时复现同样内容的提交（squash merge 换 commit sha 不换 tree）随后经 `gov receipt verify` 可验。D51 推迟的层按各自判据到来、绝非静默：租约锁在下节随"≥2 真并行 worker"判据触发而落地（D52）；队列与调度函数仍按判据推迟。

### worker 自己的租约锁（acquire/release/locks）

预演协调的是落地前的分支；分支内部的 worker 之间也可能要协调共享资源——几个互相盲态的 agent 共写一个文件。`gov acquire <resource> [--agent ID] [--ttl S] [--wait S]` 取一份租约：在 git common dir（D32#9 的先例）下以 O_CREAT|O_EXCL 原子创建一个小 JSON 文件，同 clone 的全部 worktree 天然共享；`gov release --agent ID` 做持有者校验（不匹配即 exit 2 点名实际持有者——租约绝不代他人释放）；`gov locks` 只读列出。资源被占是 exit 3——D2 词汇的 additive 扩展，0/1/2 语义不变（D52）。过期租约在 flock 守护的临界区内懒接管——这是 flock 的合法形态（仅单命令时长）：评审 P0 的结论仍然成立，flock 属于持有进程、进程退出即失锁，任何长持物都绝不建在它上面。分层才是重点：租约是**活性层**（避免重复劳动；`--ttl` 封顶，绝不永久阻塞），刻意不承载正确性——holder 挂起超过 TTL 就可能双持，正确性仍锚在它本来就在的地方（master 的 push CAS、文档的交付 rebase）。`gov locks` 永不参与准入决策：JSON 只是诊断层。

每个门禁落到五种结局之一——`PASS` / `FAIL` / `TIMEOUT` / `MISSING`（可执行文件不存在）/ `SKIP`——`allowFailure: true` 让该门禁的失败仅作 advisory：结局行与输出带 `advisory` 标记照常报告，退出码保持 0。通过但有输出的门禁以 `(passed with output)` 块保留其末尾几行——"有话说的通过"绝不被静默（D20）。退出码 0 = 全绿，1 = 有阻塞失败；阻塞失败末尾追加摘要块：哪个门挂了 + 首行输出 + 单门重跑命令。

一次运行还能留下可机检的证据，而不只是一行账：`gov run --receipt` 把本次运行的哈希链回执追加到 `.gov/history/receipts.jsonl`（issue #124/D44）——逐门结局绑到树的 commit **与** tree sha，带上运行的 caller 标签（`--tag`/`$GOV_CALLER`，D42），并链到上一条回执。改、删、重排历史都会让后续所有链接断裂：`gov receipt verify <commit>` 重走链条，以 exit 0 或点名失败回答"这棵树上是否录得一次**完整**（覆盖全部 enabled 门）、**干净**（无 tracked 文件偏离 commit）、**全绿**（每门 PASS）的运行"——squash merge 换 commit sha 不换 tree，也照常命中。PR 正文引用的单条回执经 `gov receipt verify <commit> --record '<json>'` 自校验成立，"reviewer 重跑过门禁"这类散文从此可以换成机器可查的 id。链条刻意无密钥——证明一致性与绑定，不证明作者身份；真签名是后续工作。

## 知识平面

- **Agent Notes** 承载决策（`implemented/` 然后冻结的 `archived/`）。`gov verify-notes` 强制三段必填：`## Problem`、`## Decision`、`## Alternatives considered`（`## Consequences` 可选）。`gov verify-note-presence` 检查规则 2 可观察的那一半——diff 触及行为面而无 note 变更时警告（带规则出处）；`--strict` 升级为拦截。日常簿记永不警告：任务卡回执（`.gov/tasks/**`）默认豁免，仓库还可在 `.gov/manifest.json` 里用 `"note_presence_exempt": [glob]` 申报更多豁免面（与门 paths 同款 glob 语义）——advisory 只在仓库声明"确实期望 note"的范围外触发（#149）。其 base 是 auto：脏树审查工作树，干净树审查领先 upstream 的提交（无 upstream 则最后一个提交）——push 钩子与 CI 永远看到干净树，因此审查的是被推送的工作而非空 diff。记忆的读侧：`gov recall <terms>` 跨笔记、决策、postmortem 检索（按命中位置排序）。每次运行都在 stderr 陈述搜过的语料（按类计数），miss 时打印逐词命中计数——"某个词拖垮了 AND"与"语料里根本没有这个词"从此可分辨（#148）；`--any` 对部分命中做排序返回而不是拒绝——严格 AND 仍是默认。`gov audit-notes` 报机械新鲜度信号——世界已不再满足的引用——作为归档技能判断的证据。
- **双语配对** 承载对外展示文档：源 `foo.md` + 译文侧 + `foo.i18n.yaml` 记录，用 git blob 哈希钉死两侧（并钉住译文侧文件名）。命名约定是 `.gov/pairing.json` 里的配置（`include`、`counterparts`、`exclude`）；不符合任何约定的配对用 `gov verify-pairing --write en:<path> zh:<path>` 显式登记。单边编辑失败。
- **`gov self-test`** 为每个治理门禁跑一个拒绝用例——证明每个门禁都能拦住所声称的违规，所以没有空转脚本。它是工具自身的回归，进模板默认运行（`governance` 模式保留为单跑自检的快捷方式）：模板 CI 装的是未钉版本的 govrail，工具自身的冒烟测试因此在采用者侧运行。每个已启用门禁必须属于某个 mode——停靠只有 `"enabled": false` 这一条响的机制（DISABLED 行）；`gov run --every-gate` 是显式全矩阵。每个 FAIL 都会被分类（#139/D47）：用例在最小干净环境（仅包副本、清空宿主 `PYTHON*`；编译依赖 tree-sitter 在两侧都从本解释器的 site-packages 解析，D54）重放一次，FAIL 行据此标注 `environment-suspect`（重放通过）或 `tool-defect`（重放仍红）——分类只是诊断，绝不改判；`--case NAME` 可按名单单跑一个用例。
- **任务卡** 承载子代理交接（`gov task`，#125/D43）：`gov task new "标题" --check "验收项"` 写出 `.gov/tasks/T-0001-*.json`，以内容哈希钉住当前规则集（`.gov/rules.md` + `gates.json`），任务简报只需一行 `obey rules@<hash>` 而不复述纪律。`gov task check`（门禁，paths 限定 `.gov/tasks/**`）在治理采纳后点名过期卡片，并复核已完成卡片的回执；`gov task close T-0001` 跑门禁 DAG，把全绿运行记为卡片的完成回执。
- **评审量规** 承载门禁查不了的判断标准：[review-rubric.md](review-rubric.zh.md) 对 PR 逐条带证据判定；每条的 `Gate candidate` 字段写明承诺可机械化后是否毕业成门禁。`gov verify-rubric` 检查量规自身的结构——永不检查判断本身。

## 采用：gov init / uninstall

`gov init` 把平面注入项目：复制 `.gov/rules.md`（规则的唯一事实源），仅在缺失时创建 `gates.json`、笔记 README 与 agent 技能（recall-first、pre-push-checks、code-review、archive-agent-notes）——项目自己的技能绝不被覆盖——向 AGENTS.md 追加一行引用，并把创建了什么记进 `.gov/manifest.json`。`gov uninstall` 读取该 manifest 精确反转 init——只删 init 创建的东西，绝不碰项目自己的文件。两者都幂等。

执行路径是显式选装：`gov init --hooks` 装 pre-push 钩子跑门禁 DAG（外来的 pre-push 绝不覆盖——加装在任何变更之前预检、fail loud），`gov init --ci` 仅在文件不存在时生成 `.github/workflows/gov.yml` 跑 `gov run`。两者都记入 manifest，`uninstall` 精确反转。

可选的 pre-commit 钩子（`gov init --hooks --pre-commit`，#110）只对暂存文件跑廉价内容门——`verify-pairing --staged`（被暂存 `.md`/`.zh.md` 对的 sidecar 新鲜度；暂存源侧、对侧或 sidecar 记录任一即算触及该对）与 `verify-conflict-markers --staged`——配对漂移因此在 `git commit` 即现形并内联点名修复命令，比 pre-push 拦截早一个阶段。觉得 commit 钩子侵入的仓库留在 pre-push 模型（不加 flag，提交阶段零变化）；完整门禁 DAG 绝不在 commit 时跑——commit 必须快，规则 1 把最小充分集交给 push。单用 `--pre-commit` fail loud（它随 `--hooks` 一起装）；外来的 pre-commit 绝不覆盖。

新装项目首跑不红：pairing 门禁以 advisory 落地（`allowFailure: true`），报告哪些文档待 baseline；`gov verify-pairing --write` 记录存量配对后，摘除 `allowFailure` 即升级为强制。`init` 会打印这些 next steps。

### preset：类型化采用（D53）

注入的模板刻意是通用的一套——类型化内容因项目而异，不进默认集（D28）。**preset** 是"我的项目类型需要一套成套起步配置"的答案：随包发布在 `gov/templates/presets/<name>/` 的声明式补丁包，承载已有采纳契约的三类内容——门片段、agent 技能、manifest 提示。`gov preset list` 列出随包 preset；`gov preset show <name>` 只读打印将落地的一切；`gov preset apply <name>` 落地到已初始化项目（`gov init --preset <name>` 把两步合成新项目的一条命令）。

apply 不引入任何新合并语义——复用平面的既有契约，且绝不覆盖本地状态：门片段按 id 增量合并（D39 的机器，与 `--adopt-new` 共享同一实现；同 id 的本地门即已采纳状态——保留并点名，而 `--adopt-new` 对非增量漂移是拒绝）；技能逐字节复制、仅缺失时落地（D29）；manifest 提示只写缺失键（D49——本地值永远赢，notice 明说）。apply 幂等：重复运行全部报 "already adopted"、零写入。bundle schema 严格（规则 5）：未知键、坏类型、过不了真实 `gates.json` schema 的门、mode 引用 preset 与 shipped 模板之外的门，一律 exit 2 点名 preset 与键。

与 D28 的调和是精确的：默认模板仍是通用地板（preset 绝不进默认 init）——D28 回答"每个项目都得到什么"，preset 回答"这个项目类型额外需要什么"，经旗标显式采用。首个内置 preset `agent-heavy` 打包 D51/D52 并发演练验证过的多 agent 并行工作流：`verify-decisions` 门注册进 `governance` mode（可达，D24）、`parallel-workers` worker 协议技能（lease → 验证 → 预演 → 盲态协调；同一文件也住在本仓库自己的 `.agents/skills/`，字节一致钉住）、以及 `note_presence_exempt: [".gov/tasks/**"]`（#149：任务回执是簿记）。

## 平面成长

治理平面是地板，不是天花板。成长是事件驱动的，不是灵感驱动的：

| 触发 | 落点 |
|---|---|
| 缺陷类别上线且重发现成本高 | `docs/postmortem/` 条目；其护栏蒸馏成门禁 |
| 某约定第三次被手工执行 | 一个技能，其 description 即触发条件 |
| 某散文承诺变得可机械检查 | `gates.json` 里一个新门禁 + 拒绝测试 |
| 一个非平凡决策被做出 | 同一改动里一条 Agent Note |
