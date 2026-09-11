# 治理模板 · 待决清单

核心诉求 B：让 agent 开发的质量靠机器（门禁）守住、决策靠记录（笔记）留下，且轻到能一条命令装进任何项目。

待决项按依赖顺序排列，状态分 `待定` / `已决`。

---

## D0 — gate 和 note 的分界（全局，先定）

- **问题**：一个承诺，什么时候做成 gate（机械检查），什么时候写成 note（决策理由）？重叠了怎么办？
- **选项**：
  - (a) 严格二分：能命令检查 → gate，否则 → note，二者不重叠
  - (b) 先 note 后 gate：先记决策，等能机械检查了再升级成 gate
- **倾向**：(b)，但需精确化"重叠"的含义（见下）
- **卡住什么**：门禁"该做几个"、笔记"该写多少"都以此为准
- **状态**：已决
- **决定**：note 和 gate 是两条正交的轴——note 回答"为什么有这条规则"（历史理由，人判断），gate 回答"这条规则现在为真吗"（机械检查，可重复）。同一规则可同时拥有 note（记理由）和 gate（守状态），各司其职不重叠。判别测试：①"这个承诺现在为真吗？"能用一条命令回答 → gate；②"为什么有这个承诺？"答案是历史理由 → note。生命周期：决策先以 note 诞生，后果变得可机械检查时 gate 随之诞生，note 不删（理由永不过期）。

## D1 — gates.json 的最小 schema

- **问题**：`{ id, command }` 够吗？
- **选项**：(a) 只 id+command（顺序跑）；(b) 加 needs（DAG）；(c) 加 modes（分组）
- **倾向**：(a)（后被推翻：全字段都要 + Python 单实现）
- **卡住什么**：runner 的复杂度
- **状态**：已决
- **决定**：开发者优先，**用 Python 3 单实现，删除 `{sh, pwsh}` 变体对象**。完整 schema：顶层 `{ modes, concurrency, gates[] }`；每个 gate 含 `id`（唯一非空）+ `command`（**纯 argv 数组，单态**）+ 可选 `label`/`needs`/`timeoutMs`/`allowFailure`。配置期校验重复 id、未知 needs、循环依赖，三者 fail loud。runner 与全部治理脚本用 Python 3；安装前提 = Python 3。

## D2 — "失败大声"的精确契约

- **问题**：退出码、输出格式、未知命令/缺失文件各怎么处理？
- **选项**：(a) 统一约定（非零退出 + 打印失败 gate id + 命令输出）；(b) 结构化 JSON 报告
- **倾向**：(a) 起步，JSON 后加；"未知命令/缺失文件 = 失败并报名字"必须写死
- **卡住什么**：门禁与"一串 shell 命令"的本质区别
- **状态**：已决
- **决定**：门禁五种结局 `PASS`/`FAIL`/`TIMEOUT`/`MISSING`/`SKIP`。退出码 `0`=全绿、`1`=有阻断失败、`2`=配置无效（启动前校验）。输出：每 gate 一行结局 + FAIL 附命令输出尾部 + 汇总行；通过静默（`--verbose` 全量）。默认 run-all（尊重 DAG），`--fail-fast` 可选。MISSING（命令不存在）单独点名，与 FAIL 严格区分。

## D3 — 拒绝测试的地位

- **问题**：每个门禁必带"引入违规 → 变红"的测试，还是可选？
- **选项**：(a) 核心，必带；(b) 可选，后加
- **倾向**：(a) 核心
- **卡住什么**：B 的"可信"是否成立
- **状态**：已决
- **决定**：拒绝测试是核心，但**只约束治理平面自己的门禁**（verify_notes 等）。每个治理门禁带一个拒绝用例（引入违规 → 断言变红 → 还原），由一个 meta-gate `self-test` 统一执行。项目自己的门禁（`go test` 等）不要求拒绝测试——其工具语义已保证拒绝。这是"门禁"与"空转脚本"的分水岭。
- **延伸（查结果不查过程）**：门禁失败信息必须带"规则出处"（指向 `.gov/rules.md`）。新增 `verify-note-presence` 软门禁：diff 触及代码/契约但无新增 note → **警告不阻断**。原理：不查"读没读规则"，查"做没做对"，失败信息逼 agent 去读——"不读就修不好"，比自毁行/读回执可靠（查产出、不可游戏、不引入状态变异）。

## D4 — 笔记三段 vs 五段

- **问题**：`Problem / Decision / Alternatives` 够吗，要不要 `Consequences`？
- **选项**：(a) 三段核心，Consequences 可选；(b) 五段全必填
- **倾向**：(a)
- **卡住什么**：笔记格式校验器写多严
- **状态**：已决
- **决定**：必填三段 `## Problem`（动机，独立成立）+ `## Decision`（决策，现在时）+ `## Alternatives considered`（被否方案，防重新争论）。`## Consequences` 为可选段：允许存在、不强制、不校验，等"成本"维度值钱再升格必填。校验器只认三段必填，三段缺一变红。

## D5 — 笔记生命周期最小集

- **问题**：`implemented + archived` 够吗，要不要 `proposed/rejected`？
- **选项**：(a) 只 implemented + archived；(b) 全四态
- **倾向**：(a)
- **卡住什么**：目录结构 + 归档规则
- **状态**：已决
- **决定**：最小集 = `implemented/` + `archived/`（冻结、sha256 封存、永不编辑）。`rejected/` 后加——触发条件：真的有人重新提议被否方案（事件驱动）。`proposed/` 排除——是规划工作流，非决策记忆。回退边界：`implemented` 可改，`archived` 不可改（是证据不是状态）。

## D6 — "非平凡改动"的边界

- **问题**：什么改动必须写 note？
- **选项**：(a) 宽松（改变行为/架构/跨文件契约/维护者可能重新审视的决定）；(b) 严格（机械改动也写）
- **倾向**：(a)
- **卡住什么**：规则 2 是空话还是有牙齿
- **状态**：已决
- **决定**：非平凡改动 = 改变可观察行为 / 架构结构 / 跨文件契约 / 流程工具 / 测试策略，或"维护者可能重新审视"的决定。豁免 = 纯机械/局部（错字、格式、局部重命名、注释同步）。操作化判据：一个月后的维护者看到 diff 会问"为什么"吗？会问就写 note，不问就豁免。防两端：少写丢决策，多写造疲劳。

---

## 怎么交付（③简易安装 + ④轻松适配）

## D7 — 安装载体

- **问题**：一条命令是什么形态？
- **选项**：(a) pip 包 + `init` 子命令；(b) 单文件脚本
- **倾向**：(a)
- **卡住什么**：安装/升级/卸载的体验
- **状态**：已决
- **决定**：Python CLI 包（pip/pipx 可装），含 `init` 子命令——`init` 把 gates.json 模板、笔记格式、规则注入目标项目。工具装一次、项目文件每项目注入一次。卸载 = `pipx uninstall`，天然可回退。包名待定。

## D8 — 追加不覆盖的合并语义

- **问题**：目标项目已有 AGENTS.md / gates.json 时，怎么合并？冲突怎么办？
- **选项**：待钉
- **倾向**：待钉
- **卡住什么**：适配现有项目是否真"轻松"
- **状态**：已决
- **决定**：不向 AGENTS.md 追加规则内容，改为——① 创建独立规则文件 `.gov/rules.md`；② 在 AGENTS.md 加**一行命令式引用**（幂等：已有则跳过）。规则永不与项目规则合并，语义冲突在结构上消失。选分叉 A（本地文件），不做真外部引用（依赖工具解析与联网）。结构性冲突（引用行已存在）机械报，语义冲突靠"独立文件 + 并列存在 + 提示人工"兜底，init 不仲裁。

## D9 — 幂等

- **问题**：重复 install 是否安全 no-op？
- **选项**：待钉
- **倾向**：待钉
- **卡住什么**：误操作是否造成重复
- **状态**：已决
- **决定**：幂等 = 检测"已初始化"标记（AGENTS.md 的引用行 或 `.gov/` 目录存在）→ 已存在则 no-op，打印"已初始化，版本 X"。重复 `gov init` 不产生任何变更。

## D10 — 回退契约

- **问题**：uninstall 如何精确还原 install 做的事？
- **选项**：待钉
- **倾向**：待钉
- **卡住什么**：可回退是否成立
- **状态**：已决
- **决定**：`gov uninstall` 精确反转 init——① 删 `.gov/` 目录（含 manifest + rules.md）；② 移除 AGENTS.md 里的引用行（标记可识别）；③ 按 manifest 删除 init 创建的项目文件（**仅 create-if-missing 的**，项目原有的绝不碰）。`.gov/manifest.json` 记录 init 创建了什么，uninstall 读它反转。

## D11 — 默认运行集与 gate 下线（gates.json schema 增补）

- **问题**：`gov run` 不带 `--mode` 时跑全部 gates，`modes.all` 只是可显式选择的名字而非默认集——从 modes.all 摘掉某 gate 后默认运行照旧；想下线一个 gate 只能物理删除定义，丢失配置历史与"未来重新启用"的意图。
- **选项**：(a) 魔法默认：存在名为 `all` 的 mode 即默认；(b) 顶层 `defaultMode` 显式声明；(c) per-gate `enabled: false`
- **倾向**：(b)+(c)
- **状态**：已决
- **决定**：(b)+(c) 都要。`"defaultMode": "<mode>"` 显式声明默认集（`--mode` 可覆盖；未声明且未传 `--mode` 时保持跑全部，向后兼容）；`"enabled": false` 把 gate 从一切选择中排除，运行输出打一行 `DISABLED <id>`（可见，绝不静默消失）。mode 引用 disabled gate 合法（自动过滤）——下线是一处编辑；引用**未知** gate 仍 fail loud。`defaultMode` 指向不存在的 mode = 配置错误（exit 2，带名字）。
- **被否**：(a) 隐式魔法名与"fail loud、不猜意图"冲突；(c) 单独不够——mode 集合仍无法作为默认生效；mode 引用 disabled gate 直接报错被否——那会逼用户改两处，退回"删除定义"老路。

## D12 — pairing 约定可配置 + 显式登记

- **问题**：`.zh.md` 命名与扫描范围硬编码在工具里（docs/ + README.md，排除 decisions.md 是本仓库私有事实），存量项目（如 `_CN.md` 约定）无法采用此 gate；`--write` 只能重记录已配对文件、不能声明配对，报错 `missing counterpart` 误导（用户以为是"登记"，实际什么也没发生）。
- **选项**：(a) 配置塞进 gates.json；(b) 独立 `.gov/pairing.json`；(c) 只加 `--write` 显式登记，不加配置
- **倾向**：(b)+(c)
- **状态**：已决
- **决定**：(b)+(c) 都要。`.gov/pairing.json`（全键可选，坏配置 exit 2）：`include`（glob 数组，默认 `["docs/**/*.md","README.md"]`）、`counterparts`（`{stem}` + 字面后缀的模式数组，默认 `["{stem}.zh.md"]`，后缀禁 `/` 与花括号）、`exclude`（路径数组，默认空）；本仓库对 decisions.md 的排除从代码移入本仓库自己的配置。记录文件新增 `counterpart: <文件名>` 字段钉住译文侧名字，验证优先读它，旧记录无此字段则按约定推导（向后兼容）；被记录钉住的文件名不再被当作源文档。`--write en:<path> zh:<path>` 显式登记任意命名的配对（两侧须同目录、均存在）；报错必须带"试了什么约定 + 怎么显式登记"的行动指引。
- **被否**：(a) 污染 D1 锁定的 gate schema，工具私有配置混进通用配置；(c) 单独不够——登记了约定外名字后，验证扫描发现不了该配对（登记必须能持续生效）；支持任意目录的 counterpart 被否——记录按同目录 basename 钉名字，跨目录让记录语义复杂化。

## D13 — 新装项目 advisory-first（首跑不红）

- **问题**：`gov init` 后首个 `gov run` 即红（存量文档无配对记录 → pairing 违规），第一印象是"装完就挂"，阻碍采用。
- **选项**：(a) init 探测存量文档并自动 baseline；(b) 新装 gate 先 advisory（只报告不拦截），显式确认后升级强制；(c) 保持全强制
- **倾向**：(b) + 轻量引导
- **状态**：已决
- **决定**：模板 `gates.json` 的 pairing gate 带 `allowFailure: true` 落地；runner 对 advisory 失败打标输出（结局行标 `(advisory; allowFailure)`、输出块照打——原先 allowFailure 失败不打印输出，advisory 等于看不见）；`gov init` 结束打印 next steps（跑 → `verify-pairing --write` baseline → 摘除 allowFailure 升级强制）。已 baseline 的项目（本仓库自身）直接强制。manifest 的 version 字段改记注入时的 CLI 实际版本（原硬编码 0.1.0）。
- **被否**：(a) init 内跑门禁/写 baseline 越权——init 只注入不评判，且自动写记录等于替用户确认"翻译一致"这一人类判断；(c) 即被拒的现状。

## D14 — note 存在性软门禁（兑现 D3 延伸）

- **问题**：规则 2 说"每个非平凡变更必须带 Agent Note"，规则 1 说可检查的承诺必须是 gate——存在性恰恰可检查（diff 触及行为面 ↔ diff 触及 notes），但 notes gate 只验格式，存在性纯靠自觉。规则与工具脱节。
- **选项**：(a) 硬门禁：非平凡 diff 无 note 即红；(b) 软门禁：警告不阻断 + 规则出处；(c) commit message 里要求 `note:` 引用
- **倾向**：(b)（D3 延伸已锁定）
- **状态**：已决
- **决定**：新增 `gov verify-note-presence`：diff（含未跟踪文件）触及行为面（非 docs/非 notes/非根级 .md）而无 `implemented/` note 变更 → **警告不阻断（exit 0）**，输出带 `.gov/rules.md` 规则 2 出处与"平凡改动可忽略"的出口；`--strict` 升级为阻断（exit 1）。默认 base=`HEAD`（工作树+暂存区——本地推送前检查的自然单位，且从仓库第一个提交起就存在；CI 显式传 ref）。git 失败 exit 2。默认进模板 `all` 模式。change-scope 输出同款提示联动。
- **被否**：(a) "是否平凡"终究是人的判断，机械硬拦必产生假阳性，逼人绕过；(c) commit message 是另一个平面（且 squash/rebase 会改写），diff+notes 文件面才是稳定证据。

## D15 — gate 级 `paths` 与 diff 选门

- **问题**：规则 1 说"按变更跑最小集合"，但工具不支持 scope→gate 映射——`gov run` 不知道哪些门与本次变更相关（单测挂了也拦文档改动），长期诱导 `--mode quick` 绕过或 `--no-verify`。change-scope 的面→门映射硬编码（还引用不存在的 `links` 门），与 gates.json 脱节。
- **选项**：(a) 不做，靠 mode 手选；(b) gate 定义加 `paths` glob 数组 + `gov run --base <ref>` 自动选门；(c) 只改 change-scope 的硬编码映射
- **倾向**：(b)
- **状态**：已决
- **决定**：gate 可选字段 `"paths": [glob]`（`**` 跨目录、`*` 不跨；匹配仓库相对全路径）。`gov run --base <ref>`：git diff（含未跟踪）→ 选 paths 命中的门 + 无 paths 的门（永远相关），打印 `scope vs <ref>: N/M ...; out of scope: ...`。`--mode`/`--base`/`--gate`（单门重跑）互斥、显式传参优先于 defaultMode。change-scope 建议改为读 gates.json 的 paths（单一事实源；无 paths 配置才退回落级映射，删除幽灵 `links`），并给出 `gov run --base` 执行提示。失败运行末尾追加摘要块：哪个门挂 + 首行输出 + `gov run --gate <id>` 重跑提示。
- **被否**：(a) 最小集合原则空转；(c) 两份映射必然漂移（`links` 幽灵即证据）；把 paths 塞进 change-scope 私有配置被否——门与它覆盖的范围属同一事实，必须住在 gate 定义里。

## D16 — init 的 hooks / CI 加装

- **问题**：治理平面的价值全在"自动执行"，但 `gov init` 不提供任何执行路径——采用者只能手写 pre-push hook 和 CI workflow。
- **选项**：(a) 不做（用户自理）；(b) `gov init --hooks` / `gov init --ci` 可选加装；(c) 默认全装
- **倾向**：(b)
- **状态**：已决
- **决定**：`--hooks` 装 `.gov/hooks/pre-push`（留档可见）并写入 `.git/hooks/pre-push`（可执行，内容即 `exec gov run`）；`.git/hooks/pre-push` 已存在且非 gov 钩子 → **加装前预检 fail loud（exit 2）**，绝不覆盖、不留半初始化状态；已存在 gov 钩子 → 幂等替换。`--ci` 仅在 `.github/workflows/gov.yml` 缺失时生成（checkout + setup-python + pip install govrail + `gov run`），已存在则不动。两者记入 manifest（created + gitHooks），`uninstall` 精确反转。非 git 仓库用 `--hooks` → exit 2。
- **被否**：(a) 与"机器守线"的立身之本矛盾；(c) 惊喜写入 `.git/` 与 `.github/` 侵犯项目主权，加装必须显式 opt-in。

## D17 — 评审量规（rubric）与元门禁

- **问题**：规则 1 说"不可检查的约定属于评审"，但评审本身没有结构——标准活在评审人脑子里：跨人（跨 agent）不一致、不可审计、作者无法在提交前自检；"评审质量"本身无从检验。
- **选项**：(a) 只写散文式评审指南；(b) 双语量规文档 + code-review skill 接线；(c) 再加 `verify-rubric` 元门禁
- **倾向**：(b)+(c)
- **状态**：已决
- **决定**：`docs/review-rubric.md`（+.zh.md+.i18n.yaml 双语三件套，规则 7）：R1–R8，每条四字段 `Checks`/`Evidence`/`Anti-pattern`/`Gate candidate`——**条目是评审态，门禁是运行态**，`Gate candidate` 显式标注毕业去向，可机械化的按事件驱动成长升级成门禁（D14 即先例）。code-review skill 按量规逐项判定（"约定第三次被手工执行 → skill"，成长表原文）。`gov verify-rubric` 只查**量规自身结构**：ID 从 R1 连续唯一、四字段齐全非空、`yes` 必须写去向、`.zh.md` 侧 ID 集合对齐（跨语言契约是 ID，措辞是译者自由）——判断本身永不伪机械化。rubric 门禁进本仓库 gates.json（paths 限定量规两文件）；**不进注入模板**。
- **被否**：(a) 无结构散文=各人各标，正是量规要消灭的；(c) 同时把模板量规注入所有项目——违背事件驱动成长：没有采用者第三次手工执行过"写量规"这件事，就不该模板化；采用者的量规内容取决于他们的规则。

## D18 — 记忆的读侧：recall 与 audit-notes

- **问题**：写侧纪律已闭环（笔记必须存在、格式必须对——"notes are the agent memory"），但读侧只有裸 grep：找一条决策要手翻三四个目录；笔记契约说 implemented 要"与已交付事实保持一致"，漂移却完全无声。
- **选项**：(a) 只靠 grep 与人工；(b) `gov recall` 结构感知检索 + `gov audit-notes` 机械新鲜度信号；(c) 嵌入/向量检索；(d) 会话级工作记忆
- **倾向**：(b)
- **状态**：已决
- **决定**：(b)。`gov recall <terms>`：跨 notes（implemented+archived）、decisions.md（每个 `## Dn` 节是一条）、postmortem 条目（README 除外）的确定性检索；全词 AND、大小写不敏感；按命中位置排序（标题 > 节标题 > 正文）；无命中 exit 1（fail loud——不许对着空结果推理）。`gov audit-notes`：只报**机械**信号——backtick 的 `gov <子命令>` 已不存在、`Dn` 引用在 decisions.md 无对应条目、带分隔符+扩展名的 backtick 路径解析失败（占位符与 glob 豁免）；archived 冻结豁免（D5）；发现即报告、exit 0——是给 archive-agent-notes 技能的证据，不是判决。两者均为工具而非门禁（不进 gates.json），随包分发给采用者。
- **被否**：(a) 读侧摩擦正是记忆"写了没人读"的直接原因；(c) 零依赖是锁定承诺，且语义检索不可审计、在此规模（几十篇）是伪需求；(d) 工作记忆属 harness/session 层——治理平面只管版本化的仓库记忆，平画分离。

## D19 — agent 技能随包分发

- **问题**：技能（recall-first 等）此前仓库本地、不随 `gov init` 注入——采用者的 agent 会话得不到"先查记忆再提案、先选最小集再跑门禁"的触发器，工具空转到货、习惯不来。D17/D18 的"事件驱动、暂不模板化"立场中，技能这一半的事件已到：维护者明确要求分发。
- **选项**：(a) 继续仓库本地；(b) 四技能作为 init 模板注入（create-if-missing，项目自有同名技能绝不覆盖，manifest 记录、uninstall 反转）；(c) 连量规一起模板化
- **倾向**：(b)
- **状态**：已决
- **决定**：(b)。技能写成**条件式**使其在有无量规的项目都成立（code-review/pre-push-checks：有 `docs/review-rubric.md` 按条目评，无量规回退到判断轴清单）——由此模板与本仓库活文件**字节相同**，并以一条 pytest 防漂移断言锁住（模板 ≠ 活文件即红）。打包经 `package-data "skills/*/SKILL.md"` 子目录 glob，构建 wheel 实证收录。量规本身**仍不模板化**（其条目一半引用本仓库特有事实，D17 立场不变；技能用条件引用消化该依赖）。
- **被否**：(a) 工具分发了、触发器不分发，等于卖了枪不配准星——采用者 agent 的第一动作仍是手工 grep；(c) 需要重写一套通用量规条目，超出本次诉求，且"评审标准"比"工具习惯"更贴项目个性，事件未到。

## D20 — 承诺语义的机械化（诚实执行轮）

- **问题**：外部对抗测试暴露十项"文档承诺 ≠ 工具强制"：① archive-notes 在任何新项目裸崩（写 manifest 前 `archived/` 不存在，init 也不建），零笔记还封空 manifest；② runner 丢弃 exit-0 门禁的输出——advisory 警告在 DAG 里蒸发，用户只看到绿灯；③ 空 rubric（0 条目）空过，违反规则 6；④ 笔记三段顺序 README 说了但未强制；⑤ class 封闭集未强制（implemented/misc/ 照过）；⑥ `.agents/notes/drafts/` 被 verify-notes 静默忽略却被 recall 检索——两工具对"什么是笔记"意见不一，且违反规则 5；⑦ archive-notes 不解析参数；⑧ init 的 next-steps 指引在无配对文档的项目必然 exit 2；⑨ decisions.md 格式不符时 audit-notes 零提示地全量误报 Dn 引用；⑩ 根级 .md 一律 trivial，文档驱动仓库的 DESIGN.md（唯一事实源）逃逸 note 检查。
- **选项**：逐项小修 vs 引入新机制（WARN 第六结局、笔记路径配置化等）
- **倾向**：逐项小修，不加新机制
- **状态**：已决
- **决定**：① archive-notes：写前 `mkdir(parents=True)`、零笔记报 "nothing to seal"（不写空 seal）、argparse 强制（未知参数 exit 2）、非 governed 目录 exit 2。② runner（**修订 D2 的"通过静默"**）：exit 0 且有输出的门禁，PASS 结局与退出码不变，输出末尾 ≤3 行以 `(passed with output)` 块展示——"通过且无输出才静默，绿灯不吞警告"。③ verify-rubric：0 条目 = vacuous pass，拒绝。④ verify-notes：三段行级匹配且按承诺顺序强制（乱序报错）；`implemented/<class>/<file>.md` 双段路径强制、class 限 D5 封闭集；`.agents/notes/` 下未知生命周期目录 fail loud。⑤ recall 同步只检索 implemented/ + archived/——笔记的定义在两工具间唯一。⑥ verify-note-presence：根级展示文档（README*/CHANGELOG*/CHANGES*/CONTRIBUTING*）仍 trivial，**其余根级 .md（DESIGN.md、ARCHITECTURE.md 等）视为行为面**；docs/ 子树仍 trivial（配对门禁的领地）。⑦ init next-steps 做**只读存在性探测**（README.md / docs/*.md）选择指引文案——不是 D13 否决的自动 baseline：不评判、不写入，只挑建议。⑧ audit-notes：decisions.md 存在但解析出 0 条 `## Dn —` → stderr 警告格式不符、D-ref 置为 unchecked，不再全量误报。
- **被否**：WARN 第六结局——改 D2 锁定的五结局契约，展示输出尾部已达到目的；根级 .md 全部判非平凡——README/CHANGELOG 纯展示改动会刷屏警告，advisory 也怕"狼来了"；生命周期目录可配置——D5 已锁定最小集，事件未到。

## D21 — 执行器诚实轮：auto base、根锚定、部分 baseline、排序

- **问题**：① note-presence 默认 `--base HEAD`（工作树），但两个 shipped 执行器看到的都是**干净树**——push 钩子在工作树干净后运行、CI checkout 后工作树干净 → diff 恒空 → 门禁在真正的执行点上结构性失明（实测：无笔记提交推送，钩子全绿放行）。② 子目录调用时 verify-notes/verify-pairing 报 "0 notes ok / 0 pairs ok" 静默空过（路径 cwd 相对），而 recall/audit/archive/run 都会 fail loud——同一"受治理根"判断五命令两套标准。③ 裸 `--write` 遇到一个未配对文件即整体拒绝，好配对的基线也写不成。④ recall 同分排序按路径字母序，archived/ 恰在 implemented/ 前——当前权威排在冻结证据后面。
- **选项**：① 钩子从 stdin ref 区间算 base + CI 显式传 ref；或工具端 auto base 级联。② 各工具自加根校验；或共享 git 根锚定。③ 维持全有或全无；或部分成功。④ 忽略；或排序加生命周期优先级
- **倾向**：工具端统一解决
- **状态**：已决
- **决定**：① note-presence 默认 base 改为 **auto 级联**：脏树→HEAD（审查工作树）；干净→`upstream...HEAD`（审查未推送提交）；无 upstream→HEAD~1；单提交→空树（一切都是变更）。所选 base 及理由打印在输出首行。CI 模板与本仓库 ci.yml 加 `fetch-depth: 0`（浅克隆会让级联跌到"全仓库"）。钩子保持 `exec gov run`——auto 使其天然正确。显式 `--base` 永远可钉死。② 新增 `gov/root.py::anchor_to_git_root`：在 git 工作树内即 chdir 到根并**在 stderr 宣告**，五个笔记/配对工具（verify-notes、verify-pairing、recall、audit-notes、archive-notes）统一接入；非 git 目录保持原样（缺失标记自然 fail loud）。③ 裸 `--write`（含点名形式）改**部分成功**：能记的记、不能记的逐条报、末行 `wrote N, left M unpairable`、exit 1（点名不存在的路径仍是 exit 2——那是笔误不是配对状态）。④ recall 排序键加生命周期优先级：同分时 implemented/ 先于 archived/，再按路径。
- **被否**：① 钩子解析 stdin ref 区间——每个执行器各自算 base 必然再漂移；级联一次做对，钩子保持零逻辑。② 各工具自加校验——五份实现两套标准正是本缺陷的成因。③ 维持全有或全无——一个坏文件挟持所有好配对，正是"整体拒绝"在 F3 里的形态。

## D22 — 加装可补、定制不静默重置、Status 值域封闭

- **问题**：① `gov init --hooks` 对已初始化项目只报 "already initialized"——没有任何事后补装钩子的入口；唯一路径 uninstall→init --hooks 会把 `.gov/rules.md` 的定制规则与 `gates.json` 的定制标签**静默重置**为模板默认（笔记因非 init 创建而幸存）。② `Status:` 值域无校验——`Status: banana` 照过 verify-notes；生命周期实际由目录位置编码，字段成了装饰（README 未承诺封闭值域，不算违约，但按诚实标准要么校验要么明说）。
- **选项**：① 加装支持增量；或 uninstall/init 检测定制并警告/保留。② Status 封闭 {implemented, archived}；或文档声明任意文本
- **状态**：已决
- **决定**：① **双管齐下**：`--hooks`/`--ci` 在已初始化项目走**增量路径**（只做预检 + 装所请求的加装 + 合并更新 manifest；rules/gates/notes/skills/引用行一律不碰——补装钩子永不重置定制）；uninstall 保持 D10 精确反转，但删除前把**与模板有字节差异**的文件点名警告（rules.md + created 里能映射回模板的条目），定制不再静默消失。② Status 封闭为**恰一值** `implemented`（archived 笔记按归档程序本就保留 `Status: implemented` + `Archived:` 行；生命周期=目录，字段无第二状态可表达），README（仓库+模板双份）明文"值恰为 implemented，生命周期是目录不是字段"。
- **被否**：① 定制文件在 uninstall 时保留——破坏 D10 的精确反转契约；只警告不保留。② 允许 {implemented, archived} 两值——archived/ 不经 verify-notes 检查，给了第二值等于给字段塞进目录已有的职责，重新引入双事实源。

## D23 — 封条有读者、重封不洗白、uninstall 真两步

- **问题**：① uninstall 的定制警告文案说 "copy out ... then re-run"，暗示首跑已中止——实际同一运行内警告后直接删除（照提示等 re-run 再备份的用户已丢数据）。② 归档封条承诺 "any later edit is detectable"，但 manifest 只有写者没有读者：篡改归档笔记后 verify-notes（D5 跳过）/audit-notes（豁免）/recall（照常索引）无一发现；更糟的是重跑 archive-notes 按篡改后内容重算哈希重新封条——违规被永久洗白。
- **选项**：① 警告后 return 1 真两步（--force 继续）；或只改文案为"即将删除"。② 新增 verify-archive 检测器 + 重封前验旧封条；或并入 verify-notes；或维持现状加文档声明
- **状态**：已决
- **决定**：① **真两步**：检测到定制文件 → 警告 + `return 1`，**本次不删任何东西**；`gov uninstall --force` 为显式同意（仍点名删除的定制文件）。无定制时单步直删不变。② **封条闭环**：新增 `gov verify-archive` 门禁——每个归档文件对封条验 sha256、封条条目对文件双向缺失检查；未封（有文件无 manifest）也是违规。`archive-notes` 重封前**先验旧封条**：漂移 → exit 1 拒绝并列名（"restore or --rebaseline"）；`--rebaseline` 为显式同意并大声打印 RE-BASELINED 了哪些。门禁以 paths 限定 `.agents/notes/archived/**` 进本仓库与注入模板（篡改即触发）。归档技能同步：程序加"封后用 verify-archive 确认"，Never 加"不许对被篡改文件重封"。
- **被否**：① 只改文案——空头支票换成如实告示仍是单步数据丢失；两步多一次确认是 uninstall 低频操作付得起的价格。② 检测并入 verify-notes——封条是完整性不是格式，混关注点；独立门禁可被 paths 精确触发。重封无条件允许（迁移便利）——便利通道就是洗白通道，必须显式且大声。

## D24 — 门禁可达性：唯一且响的停靠机制（radiant #5 审计）

- **问题**：① 模板把 self-test 只放进 governance mode，而 defaultMode=all 不含它，注入的 CI 与 pre-push 钩子都裸跑 `gov run`——每个新 init 项目的治理自检从第一天起没有任何自动执行路径（radiant 实证：26 个拒绝用例从未在自动路径上跑过，人工审计才发现；补进 all 后 CI 10s→17s）。② 结构性根因：gates.json 存在两种停靠机制——`enabled: false`（响的：DISABLED 行）与 mode 省略（哑的：不执行也不报告，完全不可见）；后者从未被承认为停靠手段，模板自己却在用。这是 vacuous pass 的镜像：never runs 的 gate 连失败的资格都没有。③ N4：`--gate <被停门禁>` 静默 exit 0。
- **选项**：模板补 self-test 即可；或同时封死哑停靠；或引入 --every-gate
- **状态**：已决
- **决定**：三层全做。**可达性校验（fail loud）**：modes 非空时，已启用门禁不属于任何 mode → ConfigError 点名（"park with enabled:false — the one loud mechanism"）；停靠只有一条路且必响。存量项目不受影响（governance mode 里的门禁属于"某 mode"）。**模板修复**：modes.all 加入 self-test（governance mode 保留为单跑自检的快捷方式）——部分翻案 0.3.0 的"self-test 不进项目默认运行"：模板 CI 装的是**未钉版本**的 govrail，self-test 是采用者侧的工具冒烟测试，7 秒换消费者级回归检测，且规则 1"CI owns the full matrix"自洽。**--every-gate**：无视 modes/defaultMode 跑全部已启用门禁，给"full matrix"一个显式落点。**N4**：`--gate` 点名被停门禁 → exit 2（显式请求停用物是操作错误，静默绿会掩盖它）。附带：note-presence 在零提交仓库不再因无 HEAD 而 exit 2（未跟踪清单即全部变更，守住 D13 首跑不红）。
- **被否**：只修模板不封哑停靠——下一个配置还会悄悄长出 never-runs 门禁；允许"未引用 mode 的门禁"合法存在——可达性判据必须落在"属于某 mode"而非"属于 defaultMode"（否则 governance 快捷方式非法）；CI 跑两条命令（run && run --mode governance）——比一行模板改动静态多、语义少。

## D25 — 采用者愿望轮：本地拒绝用例、--json、并行分域、表面映射

- **问题**：radiant 四愿望，按价值排序：① 规则 6 要求每个治理门禁自带拒绝用例，但 self-test 只跑 govrail 自带用例——采用者给自定义门禁写的拒绝证明没有机械接线入口（"没有执行路径的承诺不存在"的自我应用）；② gate 结果只有人读行文本，机械消费（趋势、耗时回归、报告聚合）只能解析 stdout；③ self-test 进默认集后用例串行线性累积，全矩阵税会诱惑采用者把它再挪出去（G2 复发）；④ 表面分类硬编码，eval/ 这类实验装置全归 "code"，monorepo 更甚。
- **选项**：逐项采纳 vs 部分缓做
- **状态**：已决
- **决定**：四项全做。① **`.gov/rejections/` 约定**：目录下每个可执行文件是一个拒绝用例（cwd=仓库根，exit 0=拒绝证明成立；README* 跳过；不可执行点名报错）；self-test 递归执行，报告 `tools N + project M` 分开计数；`--scope tools|project` 分域；gov init 注入约定 README。② **`gov run --json`**：stdout 恰一个 JSON 数组 `[{gate, outcome, blocking, duration_ms, detail}]`（config 顺序，DISABLED 以第六种记录值出场），人读报告转 stderr，退出码不变，与一切选择器正交。③ **self-test 并行**（4 workers，输出仍按 CASES 顺序+路径序确定；全部失败一并报告而非只报第一个）。④ **`.gov/surfaces.json`**：`{"<glob>": {"surface": 名, "gates": [id...]}}`，命中者优先于内置分类、其 gates 取代回退建议（全命中时只建议配置门禁），坏配置 exit 2；无配置行为不变。
- **被否**：① 拒绝用例塞 pytest——另一个运行时、另一份报告，规则 6 的证明散落两处；② JSON 里带汇总对象——数组即记录，聚合是消费者的事（jq 一行）；分号分隔/流式行 JSON——`| jq` 直接消费要求恰一个 JSON 值；③ 用例分域替代并行——分域解决"跑哪些"，并行解决"跑多久"，全矩阵税是后者；④ 表面分类改成全配置——无配置的默认行为是新人第一印象，硬编码默认+可选覆盖才是渐进采用。

## D26 — 拒绝用例预算与 --json 纯度契约

- **问题**：① 项目拒绝用例的超时预算是 120s——一个失控用例（sleep 300）能把进了默认模式与 CI 的 self-test 拖住两分钟才失败，与门禁超时属同一家族（运行器必须有预算）。② `--json` 存在一处泄漏：`--base` 的 `scope vs` 行打到 stdout，机器消费端在 JSON 前读到人读行。
- **状态**：已决
- **决定**：① 每个拒绝用例预算 **10s**（`REJECTION_TIMEOUT_S`），超时 = FAIL 并点名 `(timed out after 10s)`，运行继续；约定写入 rejections README（拒绝证明天然是小用例）。② **--json 契约：stdout 恰一个 JSON 值**——一切人读输出（含 `scope vs` 行）走 stderr；以参数化测试锁住每个选择器路径。③ `duration_ms` 已在 0.7.0 交付（愿望 7 无需改动）。
- **被否**：预算可配置——10s 固定值 + 文档说明足够，配置项是为极端 case 服务的复杂度；用例超时缩到 3s——git init 类用例在慢 CI 上会假红。

## D27 — 模板演化的升级路径：看见，绝不代写

- **问题**：`gov init` 对已初始化项目拒绝，增量入口只有 --hooks/--ci；模板在演进（rules.md 规则、gates.json 门禁、rejections README、技能），存量采用者没有任何机械途径看到"模板变了什么、我的定制如何合并"——只能读 changelog 手工 diff（radiant 的 rules.md 已含项目规则 8，下次模板更新即手工 diff 冒险）。
- **选项**：--upgrade 自动合并/覆盖；--upgrade 只读报告；维持现状靠 changelog
- **状态**：已决
- **决定**：**`gov init --upgrade` 只做"看见"**：读 manifest 记录的 init 版本与当前包版本对（时代上下文），对每个注入文件（rules.md + notes README + rejections README + 技能 + created 里的 gates.json/gov.yml）做"现模板 vs 本地"逐文件统一 diff；缺失文件（新版模板新增、旧 init 没建过）标 MISSING-safe-to-add；全部一致时提示 safe to refresh。**绝不写入任何文件**；采纳仍是人的动作（定制文件遵循 D23 两步哲学）。差异归因诚实：init 版本=当前版本 → "customized locally"；更旧 → "customized locally and/or template evolved"（无法区分就明说无法区分）。
- **被否**：自动合并/覆盖——模板与定制三方合并是数据丢失机器，D23 刚为 uninstall 修过同类；只报"版本不同"不报文件 diff——版本号不携带哪些文件变了，等于让人继续手工 diff。

## D28 — 愿望轮 II：决策守卫、评审档案、技能防漂移、时延趋势、降噪、孤儿记录

- **问题**：六愿望。① decisions.md 是治理脊柱却是纯散文——D 编号唯一/连续、被否段在座、孤儿决策零校验（复现：重复 D9、跳号、删被否行——无工具报错）。② 评审者冷启动要手工串联 4 个命令装配材料。③ 技能文本里的 `gov` 命令/旗标引用无人校验，命令改名时面向 agent 的说明书静默过期（agent 是最照本宣科的用户）。④ `--json` 的 duration_ms 每次即弃，耗时回归只能靠人眼记忆。⑤ 长会话大量未跟踪文件让 note-presence advisory 刷屏。⑥ 双侧删除后的孤儿 .i18n.yaml 永不清点。
- **状态**：已决
- **决定**：① **`gov verify-decisions`**（verify-rubric 模式的下一个对象）：编号唯一且从 D0/D1 起连续；每条含 选项/被否/Alternatives（规则 3 精神跨文档适用）；孤儿（无笔记引用）信息性不违规。自仓库 D0–D27 首跑全绿即首位用户；进本仓库 gates.json（paths 限定 decisions.md），不进模板（内容因项目而异，同 D17 立场）。② **`gov review --base <ref>`** 四段档案：变更面（change-scope 数据）/范围内笔记（note-presence 数据）/变更关键词 recall 前五/量规条目（无量规优雅降三段）；坏 ref exit 2；code-review 技能（双份）改从档案开工。③ **audit-notes 扩技能**：`.agents/skills/**/*.md` 的反引号 `gov` 命令与旗标对照 CLI 注册表 + 旗标表（-h/--help/-v/--version 通用豁免；表覆盖全部命令）。④ **`gov run --record`** 追加一行 JSON 到 `.gov/history/gates.jsonl`（ISO 时间戳+records；append-only；**opt-in，运行默认仍无状态**）+ **`gov trend`**（窗口对半，逐门 p50 变化比，≥1.5×/≤0.67× 报为 movers）；history 不进任何 gates 校验范围，本仓库 gitignore 之。⑤ note-presence **`--staged`**（只看 index，干净即静默）+ 超五条折叠 `…and N more`；否决 ignore_untracked 配置旋钮（D26 同理）。⑥ verify-pairing 增 **dangling record** 检查（记录在、双侧皆缺 → 点名"删除或重建后 --write"）。
- **被否**：① 孤儿决策算违规——决策可以先于引用它的笔记存在，信息性是对的强度；③ 旗标注册表从 argparse 运行时反推——解析器在 main() 里运行时构建，反推的成本高于静态表+用例钉住；④ 默认记录——违背运行无状态，--record 是显式同意；⑤ 折叠阈值可配——5 条固定值足够。

## D29 — 愿望轮 III：采纳落地、环境自检、笔记前置、证据预取、严格 schema、默认记录

- **问题**：六项。① --upgrade 只报告，纯新增文件（如 rejections README）仍要手抄 site-packages。② 无环境自检：gov 不在 PATH、Python 版本错配、hook 不可执行都靠撞。③ 笔记三段式/D 引用/路径有效性都要提交后才查（笔误晚一个审计才被抓）。④ review 档案只组装不预取证据，打分仍要人工翻代码。⑤ gates.json 无 schema 校验——`"enable": false` 这类笔误静默不停靠（恰是 D24 封死的哑停靠后门）。⑥ trend opt-in 且缺席时"从未记录"与"无波动"不分。
- **状态**：已决
- **决定**：① **`gov init --adopt [file…|all]`**：只落地本地缺失的模板文件（绝不覆盖已有；钩子模板落 .gov/hooks 并 chmod +x），记入 manifest；升级报告的 MISSING 行改标 `adoptable: gov init --adopt <rel>`；修改类 diff 维持 D23 两步。② **`gov doctor`**（规则 5 风格，问题点名、exit 1）：gov 可达性、Python ≥3.9、两份 pre-push 可执行性、gates.json 严格 schema、decisions 表可解析。钩子模板解析链改为 **GOV_BIN → PATH 上的 gov → python3 -m gov**（pipx 隔离环境仍走 PATH）。③ **`gov note new --class <c> --ref <D> "标题"`**：合法路径脚手架（class 对照封闭集、D 引用对照 decisions 表，写之前就拒）；**`gov note check`**：格式+路径+悬空 D 引用，轻量到可挂 pre-commit。④ review 第 4 段为每个量规条目附**证据候选**：Checks 字段中的反引号锚点在变更文件里内联匹配（±4 行摘录、每条目至多 2 处），明示"是待核对的线索不是结论"。⑤ **load_config 严格键**：顶层与 gate 级未知键即 ConfigError 点名（`enable` 退场）。⑥ **记录默认开启**（本地文件、已 gitignore、append-only——翻转 D28 的 opt-in 子项），`--no-record` 退出；trend 区分"从未记录"与"历史存在但不足两轮"。
- **被否**：① adopt 顺带修改类文件——那是两步哲学的领地；② doctor 自动修——点名不代修，修复动作必须过人手；③ note new 自动填充内容——骨架+预校验止步，代写决策即代撒谎；⑤ 未知键警告不阻断——静默跳过的温和变体仍是静默跳过；⑥ 维持 opt-in——"本地遥测默认关"换来的只是没人打开它。

## D30 — 愿望轮 IV：评审工作台、配对往返、决策半衰期、覆盖账本、试跑、单门趋势

- **问题**：① 证据预取解决了"找证据"，裁决仍要人工誊写成 skill 契约格式。② 配对修复三步往返（变红→回想命令→全量 --write），且漂移时看不出谁先动的。③ 决策无半衰期——"D3 的上下文可能过期了"无人提示。④ 规则 6 的覆盖无人记账——13 个门禁是否都有拒绝用例纯靠自觉（evalkit-tests 差点漏掉）。⑤ gates.json 改错命令要等下次普通改动才爆（MISSING 才现形）。⑥ trend 缺单门视图与基准切分；upgrade 报告机器不可读。
- **状态**：已决
- **决定**：① **`gov review --grade`**：档案后逐条交互收 `Rn [p/f/s/q]`（f 追问 evidence），末尾生成 skill 输出契约的裁决块（逐条行 + blockers + 显式 verdict；fail → exit 1）。**人裁决、机器誊写**。② 配对：out-of-sync 报错**内联修复命令** `gov verify-pairing --write <stem>`（--write 本就支持点名对）；sidecar 增 `last_confirmed`（ISO 时刻）与 `en_commit`/`zh_commit`（双侧最后修改提交），漂移报错带"哪侧在哪个提交动的、何时确认的"。③ 决策可选 **`review-by:`** 字段（ISO 日期）：过期 → 提示行（信息性，同孤儿）；不可解析日期 → 违规。④ self-test 末尾输出**覆盖账本**：项目用例以 `# gate: <id>` 声明归属（首五行内，shebang 保持首行），报告 `gate(n)` 矩阵，无用例门禁点名 "NONE — rule 6"，幽灵 gate 名也点名；信息性不失败；坏 shebang 用例被点名而非炸穿。⑤ doctor 对每个 gate 命令做**可执行解析检查**（which 失败 → problem，把"配置能跑"与"配置是对的"分开）。⑥ trend **`--gate <id>`** 单门过滤 + **`--base <ref>`** 以该提交时间切早晚窗（变更前后对比）；`init --upgrade --json` 输出恰一个 JSON 值（status: matches/differs/missing/absent-add-on + adoptable）。
- **被否**：① --grade 自动打分——裁决主体必须是人/评审 agent，机器只管格式；② 过期 review-by 算违规——过期是"该重读"不是"错了"，与孤儿同级；④ 覆盖缺口算失败——覆盖率爬坡期会逼人删门禁而不是补用例。

## D31 — 果用性轮：样例、食谱、whatsnew、报告内指路

- **问题**：能力不是瓶颈，可发现性是——实证：至少三个已发布功能被当作新愿望重新提出（--json 的 duration_ms、--write 点名对、note new 无表提示）。更新后采用者的全部信息是 CHANGELOG 一行 + README 一行；demo-project 只演示平面约三成（无 rejections/surfaces/rubric/decisions）；无任务导向文档；报告有答案但部分缺"下一步"。
- **状态**：已决
- **决定**：四件全做。① **活样例**：demo-project 扩为全功能标本（rubric 双语对、带 review-by 的决策表、`# gate:` 声明的拒绝用例、surfaces.json、带 Related: D 的笔记、gates.json 含 rubric/decisions/source-limits 门），采用者可 `diff -r` 对表。② **食谱**（`docs/cookbook.md` 双语对）：任务导向（"pairing 变红了""加门禁闭环""读 mover""长会话降噪"），收纳本 session 真实撞墙场景，每篇 症状→命令→预期输出。③ **`gov whatsnew [--since]`**：随包分发策划版 `gov/HIGHLIGHTS.md`（用法导向，按 minor 版组织，非 commit 流水），默认 since=manifest 的 init 版本；`init --upgrade` 检测到包新于 manifest 时提示该命令——更新与发现之间的桥。④ **报告内指路铺满**：覆盖账本 NONE 行附用例文件格式；trend mover 附解读句（"是要调查的问题，不是结论"）。
- **被否**：whatsnew 直接读 CHANGELOG——commit 流水不是用法说明，策划版要维护但每一行都在回答"怎么用"；食谱进包分发——repo 文档足够，包保持轻；样例进 CI 跑全绿——样例住在我们仓库内会被根锚定到主仓库，独立验证留给采用者的拷贝。

## D32 — 对抗审计轮 III：worktree、钩子语境、爆炸半径、空洞绿灯家族

- **问题**：九项（#15–#23）。① doctor 用 `os.path.isdir(".git")` 判仓库——linked worktree 的 .git 是文件，钩子检查静默丢失还报 sound。② 裸 `verify-pairing --write` 重写所有 sidecar——绿对获得从未发生的确认（时间戳/提交字段），污染无关 diff。③ 决策平面在 docs/decisions.md 之外静默空转——表在 DESIGN.md 的项目得到 vacuous 绿（规则 6 违约穿绿灯）。④ 覆盖账本与刚 PASS 的用例自相矛盾——无 `# gate:` 声明的旧用例跑过却仍被提示"write one"。⑤ doctor 无视 manifest 版本漂移（0.12.0 vs 记录的 0.6.5，环境自检一字不提）。⑥ pre-push 钩子语境下 self-test 稳定失败而手动全绿——GIT_DIR/GIT_WORK_TREE 泄漏使根锚定把临时仓库解析到宿主仓库（本地已复现：泄漏环境下 pairing 案例锚定到 govrail 主仓库）。⑦ 范围排除的门禁输出与真扫描绿灯一模一样（"0 file(s) within limits"）。⑧ 钩子恒跑全量 defaultMode，无视 push 区间——docs-only push 也跑全套 pytest，并发 push 互相压垮。⑨ .gov/history 按 worktree 碎片化，主仓库只见零头。
- **状态**：已决
- **决定**：① doctor 以 `git rev-parse --git-common-dir` 定钩子目录（worktree 与主仓一致）。② 裸 `--write` 只重基线**当前失步**的对（全绿时明示 no-op；强制绿对走点名形式）。③ **决策源可配置**：新共享加载器 `gov/decisions.py`（`.gov/decisions.json` {path, format: sections|table}；表格格式解析 `| Dn | … |` 行、表头备选列覆盖全行检查）；verify-decisions / audit-notes / recall 三消费方统一走它；**无源且有笔记引用 D → REFUSED exit 1**（不再 vacuous 绿）；无源且无引用 → 良性。④ 账本区分"未执行"（提示 write one）与"已执行未声明"（点名文件与缺失的 `# gate:` 行；永不提示写已跑过的用例）。⑤ doctor 比对 manifest 与包版本，漂移打 note 并指 upgrade/whatsnew。⑥ **self-test 进程入口剥除 GIT_***（工具按 cwd 解析仓库是 D21 的设计，继承环境只会误导；影响仓库解析的变量被清洗时大声声明）；钩子模板同样 unset 后再 exec。⑦ 路径门禁结局行附 `n in change scope`（0 时明示"nothing changed matches"，与扫描输出可分辨）。⑧ 钩子模板读 push stdin 取 remote sha 作 `--base`（docs-only push 只跑选中门并点名排除项；新分支无 remote → 全量）。⑨ history 写入 **git common dir 的父目录**（= 主 checkout 的 .gov/history；worktree 运行入主账本）。
- **被否**：⑥ 逐 subprocess 补丁式清洗——入口一次剥离覆盖进程内用例与其全部子进程；⑧ 钩子跑全量+缓存——规则 1 说 CI 拥有全矩阵，钩子拥有最小充分集；③ 无源一律拒绝——破坏首跑不红（D13），引用存在才是危险信号。

## D33 — 宿主完整性：scratch 夹具的三墙

- **问题**：#24——self-test 的 scratch 夹具两次反噬宿主仓库：① 0.12.0 钩子语境并发运行，泄漏的 GIT_DIR/GIT_INDEX_FILE 使 scratch 的 git 命令解析到宿主仓库，三个 worktree 分支各留孤儿 "init" 提交并随 push 出货；② 0.12.1（环境清洗已生效）worktree 自测窗口内主仓库 .git/config 被改写为 core.bare=true + user t/t——机制未钉死，意味着单点修复不可信。
- **状态**：已决
- **决定**：纵深防御三墙（任何一墙独立成立即安全）：**墙 1（夹具环境）**——`_git_repo` 的每条 git 命令以剥离 GIT_* 且注入 `GIT_CEILING_DIRECTORIES=<scratch父>` 的环境运行，泄漏的解析变量进不了夹具；**墙 2（toplevel 守卫）**——init 后、任何 config/add/commit 前，断言 `git rev-parse --show-toplevel` 恰为 scratch 本身，不匹配即大声中止（"refusing to configure or commit into it"），宁可测试红也不碰别人的仓库；**墙 3（全局天花板）**——self-test 入口在清洗环境后统一设 `GIT_CEILING_DIRECTORIES=<tempdir>`，进程内用例直呼 git 也无法向上走出临时区。验收测试固化：从 linked worktree 内跑全量 self-test（含敌对 GIT_DIR/GIT_INDEX_FILE 泄漏变体），宿主 config/refs/status/HEAD 字节级不变；守卫负向用例钉住"逃逸即中止"。
- **被否**：仅靠入口清洗（0.12.1 的事故证明它不够——机制未钉死时单墙不可信）；夹具改用 libgit2/纯 Python 实现——引入依赖且重写 33 个用例的收益不抵风险；禁用 worktree 场景——采用者的真实环境正是 worktree。

## D34 — 溯源三向判定、采纳预览与申报、外部 D 引用

- **问题**：① drift 报告把一切差异标成 "customized locally and/or template evolved"——采纳者真正要问的是"上游动没动、要不要重新采纳"，只好手工 diff shipped 模板与 origin/main。② `--adopt <file>` 无法单文件预览。③ adopt 顺手改 manifest 不吭声。④ 跨项目 D 命名空间缺失：radiant 引用 govrail:D24 被判本地悬空/孤儿，无合法外部引用语法。
- **状态**：已决
- **决定**：① **采纳溯源**：init/adopt 在 manifest 记录每个实际落地模板文件的 sha256（`templates` 字段；项目自有文件不记——没有采纳就没有重采纳）；`--upgrade` 对差异文件做三向判定：local==记录 → **UPSTREAM MOVED**（你的副本自采纳后未动，`--adopt <rel>` 可安全取新模板）/ local≠记录且≠当前 → **BOTH MOVED**（你的定制与上游演化并存，手工合并）/ 无记录（旧 manifest）→ 维持含糊措辞并注明"no adoption hash recorded"；`--upgrade --json` 输出 `era` + `adoptable`。**未定制副本的安全重采纳**：`--adopt` 对"存在但与采纳哈希逐字节相等"的文件允许替换（那不是项目的内容，是旧模板的残影——替换零丢失），定制文件仍永不覆盖。② `--adopt <file> --preview`：缺失文件展示将落地内容、已有文件展示替换 diff，零写入、manifest 不动。③ adopt 修改 manifest 时显式申报（"manifest updated — N adopted, M re-adopted; template hashes recorded"）。④ **`govrail:D<n>` 为唯一合法外部引用命名空间**：audit-notes 的悬空检查、verify-decisions 的孤儿计算、note check 的校验统一**剥离**外部引用后再提取本地 D（govrail:D24 ≠ 本地 D24，既不误报悬空、也不掩盖本地孤儿）；`note new --ref govrail:D24` 接受为外部引用（记录、不本地校验、明示）。
- **被否**：任意前缀外部命名空间（`foo:D1`）——为拼写错误开静默后门，只认 govrail:（唯一已知的外部决策表）；升级时自动重采纳全部 UPSTREAM MOVED——批量替换跨多个文件时应有人看一眼 preview；manifest 记录模板全文哈希以外的内容（如时间戳）——判定只需字节身份。

## D35 — 小修轮：裸预览自解释、版本对齐防再犯、索引滞后记档

- **问题**：① 裸 `--adopt --preview` 只打横幅——可采纳/已漂移的清单明明在 `--upgrade` 里，预览入口不自解释。② HIGHLIGHTS 段落标题预写 0.12.3、轮子实发 0.13.0（同类二犯：手预测版本 vs release-please 裁决），`whatsnew --since 0.12.2` 读起来像差一版；pip 首跑因索引未同步漏装 0.13.0（同因不同症）。
- **状态**：已决
- **决定**：① 裸预览打印漂移清单摘要（`adoptable: N missing, M drifted`）并跨引 `--upgrade`（逐文件 diff）与 `--adopt <file> --preview`（单文件）。② HIGHLIGHTS 标题对齐轮子版本；**tag 覆盖守卫测试**：每个 ≥0.12.0 的已发布 tag 必须有对应 HIGHLIGHTS 段落，版本错位即红——从"事后对齐"变"机械防再犯"。③ CONTRIBUTING 发布节记档 PyPI 索引滞后约一分钟、首跑可能漏装、重试再疑。
- **被否**：whatsnew 运行时给错位段落加注——那是给错位打补丁而不是消灭错位；守卫测试覆盖 0.12.0 之前的 tag——HIGHLIGHTS 诞生于 0.12.0，之前的段落不存在是事实不是缺陷。

## D36 — whatsnew 的显式版本映射（#92 的 wheel 滞后残余）

- **问题**：#94 以 docs 提交补 0.13.1 HIGHLIGHTS 段，release-please 不为 docs 发轮——0.13.1 wheel 里最新段落仍是 0.13.0，`gov --version` 与 whatsnew 头在 **wheel 层**依旧错位（现场开场检查抓到）。结构性根因：段落在发布后补写，只能随下一个轮子出货；"每个轮子与最新段落一致"要求 docs-only 轮子或强制造段，或接受错位。
- **状态**：已决
- **决定**：采纳 #92 验收的第二分支为默认行为——whatsnew 头部恒显式打印安装的轮子版本；当轮子没有自己的段落（docs-only 发布，或段落滞后一拍）时打印映射注记（"wheel X has no dedicated highlights section … newest above is what this wheel carries"）。仓库层守卫（tag↔段落一致）不变：段落迟早补齐，轮子层的身份由运行时明示。
- **被否**：为 docs-only 变更强制发轮子——空轮子换一致性；每个发布强制造段——噪音段落稀释 whatsnew 信噪比。

## D37 — CHANGELOG ↔ HIGHLIGHTS 配对：版本跟随的机械守卫

- **问题**：HIGHLIGHTS 版本号三轮错位的根因是手工猜测 release-please 的裁决。用户指出：双语配对的核心逻辑（"一侧更新→另一侧必须跟上→gate 强制"）可以直接应用于 CHANGELOG ↔ HIGHLIGHTS——CHANGELOG 由 release-please 自动更新，HIGHLIGHTS 必须跟着更新且版本号从 CHANGELOG 里读（永不猜测）。
- **状态**：已决
- **决定**：新增 **`gov verify-doc-sync`** 门禁：解析 CHANGELOG 的 `## [X.Y.Z]` 版本段与 HIGHLIGHTS 的 `## X.Y.Z` 段，≥0.12.0 的每个版本必须配对；CHANGELOG 有 HIGHLIGHTS 无 → "copy the version FROM CHANGELOG"；HIGHLIGHTS 有 CHANGELOG 无（提前猜测）→ "shipped before its release"。进本仓库 gates.json（paths 限定两文件）。工作流：release-please 更新 CHANGELOG → gate 红 → 在 release PR 里补 HIGHLIGHTS（版本号照抄 CHANGELOG）→ 合并出货——同双语配对的"一侧变了另一侧必须重确认"。tag 覆盖守卫测试保留（belt and suspenders：gate 在 release PR 拦截，test 在后续 push 兜底）。
- **被否**：删 HIGHLIGHTS 读 CHANGELOG——CHANGELOG 条目是 commit 一行摘要，不是用法说明；cookbook 覆盖用法但不按版本组织，"这次更新了什么怎么用"需要按版本的段落；自动同步标题——内容仍需人写，只同步标题不解决内容缺失。

## D38 — 冲突标记门：git 不肯管的 `<<<<<<<` 由门禁管（issue #104）

- **问题**：rebase 中途把仍含冲突标记的文件 `git add`，`git rebase --continue` 照单全收——两个中间提交带着 `<<<<<<< HEAD / ======= / >>>>>>>` 入库。标准门禁集（notes/pairing/tests/source-limits）无一检查文件内容；docs-only diff 连测试门都不会红。git 自己拒绝管这件事：它无法区分字符串字面量里的标记与真冲突，所以只能沉默。
- **状态**：已决
- **决定**：新增 **`gov verify-conflict-markers`** 内容门并进模板 gates.json 的 all 模式（无 paths——标记可能落在任何文件类型）：对基线（auto 级联，同 note-presence 的 F1/D21）变更文件集读工作区内容逐行扫描；行首 `<<<<<<<`、`>>>>>>>`、`|||||||`（diff3 base）为主证据直接报错；裸 `=======` 仅同文件存在主证据时报（Markdown setext 下划线安全，#104 的"sibling marker"规则）；命中输出 `file:line` 并点名逃生门；行内含 `gov:ignore-marker` 令牌即豁免（字符串字面量的文档化逃生门）；二进制（NUL 字节）与已删除路径跳过；git 失败 exit 2。自带 tools 族拒绝用例 + `.gov/rejections/` 项目用例 + demo 标本真实用例。
- **被否**：只扫 diff 新增行——内容级扫描对"触碰过的文件"严格更强（早前提交带入的标记也在现内容里）且实现更廉；容忍字符串字面量（按语言解析）——grep 级承诺不接受按语言分叉的解析器，逃生令牌一行解决；交给各语言 linter——语言绑定，治理平面语言无关，且 docs-only diff 无 linter 可跑；裸 `=======` 无兄弟证据也报——Markdown H1 下划线立刻假阳性，一门禁的第一次误报就是它的信誉破产。

## D39 — gates.json 的增量采纳：新 shipped 门按 id 落地，非增量漂移大声拒绝（issue #108）

- **问题**：`gov init --upgrade` 对定制 gates.json 只能给 DIFFERS + 手工 diff——radiant 采纳 0.15.0 的 conflict-markers 门时只能开 site-packages 模板手抄、手改 modes/gates、肉眼校验，没有任何机制证明本地定制未被破坏、新块与 shipped 语义一致。D34 的 `--adopt` 帮不上：定制文件永不覆盖（by design）。
- **状态**：已决
- **决定**：**`gov init --adopt-new gates.json`**（增量采纳，笔记 [2026-09-04-adopt-new-gates-merge.md](../.agents/notes/implemented/feature/2026-09-04-adopt-new-gates-merge.md)）：以 gate id 为身份——shipped 有而本地无的门按模板顺序追加并逐一点名；本地每个 gate 对象原样保留；已有 mode 只追加新采纳的 id（纯新增的模板 mode 可整体创建；引用合并外门的 mode 打 notice 不采纳）；`defaultMode` 保持本地并在模板不一致时提示。落地前用真实 schema 加载器（`gates.load_config`）验证合并结果——runner 会拒的合并不落地。非增量漂移（同名门内容不同 / 结构损坏 / 目标不是 gates.json）exit 2 大声拒绝、零写入，维持 D27/D34 的手工路径。manifest 刻意不动：gates.json 仍是定制文件，记录哈希等于伪造"这就是模板字节"的溯源。
- **被否**：泛化到任意模板文件的自动合并——rules.md/README 是散文，没有可合并的条目身份，只有 gates.json 有机械 id 键（其他目标直接拒绝）；并入 `--adopt`——其契约是字节级（整文件、哈希证明），混入条目级 JSON 语义会让一个旗标承载两种证明故事；合并后记录溯源哈希——哈希将不再表示"模板字节"，破坏 D34 三向判定的前提；本地 disabled 的同名 shipped 门静默跳过或静默重启用——都不点名等于沉默改行为，按非增量漂移拒绝并由操作者裁决。

## D40 — 并行分支的决策行工具：编号分配与原子追加（issue #107）

- **问题**：radiant 的 M2 批次（8 个 PR、9 条决策行 D30–D38、多个并行 worktree）暴露两件事：①"下一个空闲 D 号"靠人从各自基线手算——两个平行分支各算一次必然同号，只能靠人工预分区（告诉一个 subagent"你拿 D31/D32"、另一个"你拿 D33"）避撞，无任何机械检查；②决策表是单个 markdown 文件，并行追加必生文本冲突，D31/D32 rebase 到已含 D33 的分支要手工解冲突并重排序号。工具层面无人回答"分支视角的下一号"与"合并后会是什么号"。
- **状态**：已决
- **决定**：① **`gov decision next [--count N] [--base REF]`**：从配置的决策源（.gov/decisions.json，共享加载器）算下一个空闲号；`--base` 并入 REF 上已落地的号——先分叉、兄弟先合并的分支不再重复分配（给出的是"合并后历史会显示的号"）。② **`gov decision add --from FILE [--id Dn] [--base REF] [--dry-run]`**：原子追加（临时文件 + os.replace，flock 防同检出并发），写前校验——重复号、跳号（破坏连续性）、缺 选项/被否 段一律拒绝并点名。③ **`dir` 格式**（.gov/decisions.json format:"dir"，一决策一文件 Dn-slug.md）：追加=新增文件，并行分支同基线各自追加结构性零冲突；加载器/verify-decisions/audit-notes/recall 统一支持。④ **`gov verify-decisions --base REF`**：分叉点两边都新增的号 = 点名冲突（合并后即重复行，拒绝并给 `decision next --base` 修复指引）；仅为预分区留的空档（号在 REF 侧存在）保持信息性。⑤ 自带 tools 族拒绝用例（--base 碰撞变红）+ 双 worktree 验收测试（同基线两 worktree 各自 add：dir 格式合并零文本冲突、同号成为点名的门禁失败，绝不静默）。
- **被否**：文件锁跨 worktree——锁不住独立检出，跨分支分配是 --base 的职责不是锁的；自动迁移既有单文件表到 dir 格式——单向大改写，采用者按需配置即可；冲突时自动改号——改号等于替人做决策且会静默改变笔记里的 D 引用，大声点名才是正解；预分区空档算违规——预分区正是并行开发的合法工作流，合并前信息性提示足够。
## D41 — 可选 pre-commit 钩子:配对漂移提前到提交时(issue #110)

- **问题**:radiant 两次实证同一往返:编辑双语对 → commit → push,pre-push 钩子以配对漂移拦截并内联修复命令 → 跑点名的 `--write` → amend → 再 push。检查本身有效,但反馈晚了一个阶段——忙碌分支上每一次对编辑都先换一次被阻塞的 push。
- **状态**:已决
- **决定**:`gov init --hooks --pre-commit` 额外安装**可选** pre-commit 钩子(单用 `--pre-commit` fail loud;外来 pre-commit 绝不覆盖,同 pre-push 规则;已初始化项目可事后补装),只跑暂存区上的廉价内容门:**`gov verify-pairing --staged`**(新)——仅检查 git index 触及的对(源侧、对侧、`.i18n.yaml` sidecar 任一被暂存即算触及),失步报错内联点名 `gov verify-pairing --write <pair>`;以及 `gov verify-conflict-markers --staged`(0.15.0 已有)。无对文件暂存时静默通过;完整门禁 DAG 仍归 pre-push(规则 1:push 拥有最小充分集,commit 必须快)。未加 flag 的仓库提交阶段行为零变化;doctor 视 pre-commit 为可选(缺席是选择不是问题,在场则查双副本可执行);两钩子都记入 manifest `gitHooks`,`uninstall` 精确反转;钩子模板连跑两门故不 `exec`,同样剥除 GIT_* 环境(#20/D32⑥)。拒绝证明:tools 族 self-test 用例 + `.gov/rejections/case-pre-commit-hook.sh`(`# gate: pairing`) + demo 标本用例。
- **被否**:默认安装——issue 明确 opt-in,觉得 commit 钩子侵入的仓库留在 pre-push 模型;pre-commit 跑完整 DAG——commit 必须快,全矩阵归 push/CI;新起子命令而非 `--staged` 模式——与 conflict-markers 的既有 `--staged` 形态一致,避免第二套 CLI 词汇。

## D42 — 历史记录的 caller 标签：多 agent 归因（issue #120）

- **问题**：多 agent 仓库（radiant 的 M2/M3：6+ 个 subagent 会话加一个 supervisor，全在并行 worktree 跑门）共用同一份 `.gov/history/gates.jsonl`，而其中每条记录都是匿名的——`gov trend` 能回答"tests 变慢了吗"，回答不了"哪个 caller 的运行总在 pairing 上翻车？""subagent 运行的时长是否系统性不同？"。归因问题在平面已收集的数据里无解。
- **状态**：已决
- **决定**：门运行接受**可选 caller 标签**：`gov run --tag <name>`，`$GOV_CALLER` 兜底（旗标优先；纯空白视为缺席）。标签以调用方自由文本记入 gates.jsonl 的 `caller` 键——privacy-light by design：不取 git 身份、不取主机名，只有 caller 自己敲的字。缺席 = 无 `caller` 键：记录形状与 #120 之前逐字节一致，未打标运行与既有读者行为不变。**`gov trend --by-tag`** 按标签分组（首现顺序；未打标归 `(untagged)`）并在**每组内部**做前后半 p50 对比——对半切分按组计算，时间上集中的标签仍可对比；`--base` 让所有组切在同一提交日期。旗标注册表（audit_notes）同步移动，由 test_flag_registry.py 钉住（#101 的教训）。
- **被否**：从 git config 推导 caller——worktree 共享一个身份，所有 subagent 会话同标签，归因无用且错得沉默；自动记录主机名/PID——未经同意的归因，issue 明确要 caller 自供文本；按 caller 拆多个历史文件——碎裂 D28/D29 选定的单一 append-only 台账，跨 caller 的 `--last` 窗口失义；强制打标——改变所有既有用户今天的体验，验收标准就是"缺席 = 今天"。
## D43 — 任务卡：子代理简报用 rules@hash 钉住规则集，不再逐字复述(issue #125)

- **问题**：orchestrator 给子代理的任务简报手工复述仓库治理纪律(显式路径暂存、禁 `git add -A`、门禁清单、决策行格式、双语对规则)，每份 ~15 行样板：重复、漂移(一次治理采纳后旧模板静默过时——0.15.0 新增的 conflict-markers 门、决策行工具落地，同会话前后简报已不一致)、不可验证(orchestrator 用散文断言"规则被遵守")。
- **状态**：已决
- **决定**：新增 `gov task` 任务卡子命令(new/check/close/list)。`gov task new "标题" --check 验收项` 写 `.gov/tasks/T-<4位>-<slug>.json`：以内容哈希钉住当前规则集(`.gov/rules.md` + `gates.json`，note 约定内嵌于 rules.md)，哈希 = 排序的 `路径:sha256` 串再 sha256，展示 12 位前缀；简报只带一行 `obey rules@<hash>`；`--rules <前缀>` 要求当前哈希匹配否则 fail loud(防 orchestrator 拿着旧 pin)。`gov task check` 重算哈希：开卡过期(STALE)即点名退出 1——作为门禁进 gates.json，paths 限定 `.gov/tasks/**`(规则 1 的最小充分集：卡片不变则门不出场)；done 卡复核回执(全 PASS 且与卡片 pin 同哈希)。`gov task close T-0001` 现场跑门禁 DAG(`gov run --json`)，全绿才写回执(ts/mode/rules/gates 结局)并置 done；红跑拒绝、卡片不动(运行已进 `.gov/history/gates.jsonl`)；对过期 pin 的卡片拒绝 close(须先按采纳后规则重新简报)。拒绝证明：tools 族两用例(采纳后 STALE 变红、回执非全绿变红)。
- **被否**：规则集哈希纳入 note 约定的独立文件——本仓库约定就住在 rules.md 里，第二事实源必然漂移；check 进默认 all 模式但不带 paths——无卡片的项目每次全跑一个必然空转的检查，违背最小充分集；红跑也置 done 留红回执——"done 却红"说谎，卡片只在全绿时闭合，红跑证据由 history 承载；回执链接 history 行而不内嵌结局——history 本地且可裁剪，回执必须自带可复核证据(check 重验结局本身，不信任散文)。

## D44 — 可验证运行回执:"agent 验证过"从自述变成可机检(issue #124)

- **问题**:agent 起草的 PR 越来越多带着手写的验证段——"reviewer 重跑了门禁:7/7"。这是自述不是证据:gates.jsonl(D28)里确实有运行记录,但既不绑 commit、不绑 tree、也不记调用方,下游读者(人或 agent)无法区分"门禁在这棵树上真的绿过"与"作者声称绿过",只能全部重跑。验证不可证伪,正在成为治理平面的信任瓶颈。
- **状态**:已决
- **决定**:**`gov run --receipt`**(笔记 [2026-09-04-verifiable-run-receipts.md](../.agents/notes/implemented/feature/2026-09-04-verifiable-run-receipts.md)):把本次运行追加为一条防篡改回执到 `.gov/history/receipts.jsonl`——`{v, id, ts, commit, tree, dirty, tag, selection, gates[], prev, hash}`,`hash` 为除自身外全部字段的规范化 JSON(sorted keys、紧凑分隔符)的 sha256,`prev` 链到上一条回执的 `hash`(首条 `GENESIS`)——改、删、重排任何历史行都会让后续所有链接断裂,`gov receipt verify` exit 2 点名行号,绝不静默放过(规则 5/6)。**`gov receipt verify <commit>`** 机械回答 issue 的问题:"这棵树上是否录得一次完整、干净、全绿的运行?"——exit 0 打印回执 id,PR 正文引用 id 取代散文。**完整**=selection 覆盖全部 enabled 门(显式 mode 恰好点名全部门也算;`--gate`/`--base` 的收窄运行按 #119 的 `selected_by` 词汇照实记录并拒绝充当完整证据,tools 族用例证明);**干净**=运行时无 tracked 文件偏离 commit(untracked 的账本不弄脏回执;树状态在写账本**之前**测量,tracked 的历史文件不会弄脏描述它自己的回执);**全绿**=每门 PASS,advisory 失败也算不绿。回执同时绑 commit 的 **tree sha**:squash merge 落地后 commit sha 已换而内容未变,验证按 tree 命中——"这棵树"的字面义。回执的 `tag` 就是运行的 caller(`--tag`/`$GOV_CALLER`,D42 的词汇——不设第二个打标旗标)。单独引用的一条回执(贴进 PR 正文,`--record '<json>'`)自校验成立——hash 覆盖其自身内容。回执由 flag 触发,不带 `--receipt` 的运行行为零变化;失败运行照实记录(回执是运行的自白,是否算证据由 verify 裁决)。链条刻意无密钥(issue 自己的定价):证明内部一致与绑定,不证明作者身份——真签名是后续工作。拒绝证明:tools 族 self-test 两用例(伪造记录 → exit 2 "hash mismatch";单门运行 → exit 1 "partial run")+ tests/test_receipt.py。
- **被否**:直接给回执上签名(GPG/cosign/HMAC)——缓办:issue 明确把"无密钥管理的 sha256 链"定价为当下可得的防篡改,跨 agent 身份的密钥分发本身是另一个治理问题,为它扣住今天就能机检的版本,只会让散文再当一个版本的证据;复用 gates.jsonl 加字段——该账本是趋势数据源(D28)、被 gitignore、由 `gov trend` 消费,叠加绑定语义会让"一行记录是什么"随读者分叉,独立 receipts 文件把"跑了什么"(指标)与"这次运行为什么作证"(证据)分开;只绑 commit sha——squash merge/rebase 会换 commit sha 而保内容,合并后的树无法对预合并回执机检,tree sha 才是"这棵树"的落点;为回执另设 `--receipt=<tag>` 打标旗标——D42 刚落定 `--tag`/`GOV_CALLER` 单一 caller 词汇,第二套打标旗标正是 D41 否掉过的词汇分叉;约定门检查 PR 散文措辞——规则 1:命令能查的进命令,散文正是被替代物不是被延伸物。

## D45 — 治理史的成本维度：调用方记账的标准账本形状（issue #126，建在 D42 的 caller 载体上）

- **问题**：多 agent 仓库在治理面观测到的运行里烧共享计量资源（LLM token/调用次数），但 `.gov/history` 只记时长与 caller（D42）——"这个里程碑的 LLM 花费按 workstream、按 agent 各是多少"从治理记录里答不出来；每个仓库自造记账（radiant 把 bridge/adjudication 预算记在自己的 keyspace，`gov trend` 看不见），成本归因没有共同语言。
- **状态**：已决
- **决定**：govrail **只标准化账本形状，绝不去计量**（数字仍归跑工具的一方）：① `gov run --cost unit=value,…`（env 回退 `$GOV_COST`；单位自由 token、值须有限非负数；旗标优先于 env）作为**可选**运行级字段写入 gates.jsonl 的运行行，与 D42 的 `caller` 同行共存——未提供时运行行与既有形状逐字节一致，未上报的运行行为零变化；坏输入在任何门跑起来之前 exit 2 点名片段（规则 5）。② `gov trend --cost` 取代时长 mover 视图，按 caller 分组滚动合计每个单位（窗口总量 + 早/晚窗拆分，--base 同一提交时刻切分）；无 cost 的运行不出现；历史行里的畸形 cost 字段 stderr 点名跳过、绝不静默求和；无任何上报时打印指路而非"合计为零"；与 `--by-tag` 互斥（--cost 本就按 caller 分组），与 `--gate` 互斥（成本属于运行不属于单个门），皆 exit 2 点名。③ 拒绝证明：`--cost tokens=lots`、裸 `calls` exit 2 点名；trend 对非对象 cost 字段点名跳过（tests/test_gates.py、tests/test_trend.py）。
- **被否**：govrail 自己计量（包一层计时/计数代理）——计量归工具，治理面只收数，否则每个新资源类型都要改本仓库；固定单位枚举（tokens/calls 硬编码）——单位集随工具演化，自由 token + 数值校验已够滚动合计，新单位零代码；per-gate 成本字段——成本是"这次运行里谁调的 LLM"的属性，不是单个门的属性，运行行才是它的层；把成本并入 D42 的 `--by-tag` 视图——时长 p50 与成本合计是两种量纲，混排会互相挤压版面与语义，分旗标各自聚焦。
## D46 — release 流程自动起草 HIGHLIGHTS 小节:doc-sync 的红不再靠人追(issue #125 后续)

- **问题**：D37 的分工是 release-please 自动写 CHANGELOG、人写 HIGHLIGHTS 的用法小节,但"补小节"没有任何机制托底——0.19.0 到 0.22.0 连续四个版本,每次 release PR 合并后 master 的 doc-sync 都红,靠 agent/人事后手补:红是设计内的(门禁工作正常),但红本身成了发布流程的常规步骤,等于门禁的失败被常态化。
- **状态**：已决
- **决定**：① **`gov verify-doc-sync --write`**(复用 verify-pairing 的 `--write` 形态,避免第二套 CLI 词汇):对每个缺小节的已发布版本,从 CHANGELOG 逐字起草小节——bullet 原文(剥离尾部出处链接组、反转义 HTML 实体)、标题自声明 `(draft: copied from CHANGELOG, rewrite for usage)`、按新到旧插在首个现有小节之前;写完重跑门禁自身检查返回其退出码(验证世界,不自证)。0.12.0 以下豁免与门禁同一 FLOOR。② **release-please workflow 增加 `highlights` job**(`release_created != 'true'` 时跑,即 release PR 还开着):checkout release 分支、`--write`、有 diff 才以 bot 身份推回 PR 分支——release 合并因此一次落地 CHANGELOG+版本号+HIGHLIGHTS 三件套,master 永远看不到 doc-sync 的红;合并时的 push release_created 为 true,job 跳过(小节必须已在合并树里)。GITHUB_TOKEN 的 push 不触发 workflow,天然无循环。单元测试 5 例(起草+门禁转绿、幂等、缺 HIGHLIGHTS fail loud、FLOOR 豁免、已覆盖不碰)。
- **被否**：release-please config 附带模板(extra-files/generic updater)——release-please 只会做版本串替换,没有"追加 markdown 小节"的钩子,配置层做不到;起草用法散文——机械化不了的判断,硬生成就是编造,逐字拷贝+自声明 draft 把"版本配对"(门禁守的)与"用法重写"(人的)分开;直接推 master——绕过 PR 的 CI 证据链,且 GITHUB_TOKEN push 不触发 CI,master 会出现无 CI 运行的提交;推 PR 分支但加 `[skip ci]`——release PR 的 gates 运行应覆盖最终树,跳过等于证据缺口( bot PR 的 CI 反正要人批,runbook 已有)。

## D47 — self-test 失败分类：干净环境重放裁决 tool-defect 与 environment-suspect（issue #139）

- **问题**:adopters 的宿主环境会以 self-test 无法察觉的方式破坏特定工具路径(#138:site-packages 里一个 argparse 1.4.0 backport,被用例自设的 `PYTHONPATH` 提到 stdlib 之前,`gov task` 在该机上全灭,self-test 如实红了两例)。红是**对的**——规则 6 不许跳过;错的诊断成本全压在操作者身上:要从 argparse 内部的 TypeError 一路 traced 到"是 govrail 缺陷还是本机环境"才算完。一个红着的 self-test 若不能区分"工具坏了"与"环境坏了",采用方每撞一次都要重走一遍这条 trace。
- **状态**:已决
- **决定**:self-test 对**每个 tools 族 FAIL 自动做一次干净环境重放**(笔记 [2026-09-04-self-test-failure-classification.md](../.agents/notes/implemented/feature/2026-09-04-self-test-failure-classification.md)):把运行中的包复制进全新临时目录(包 stdlib-only,复制即完备环境),重放子进程的 `PYTHONPATH` 只指向这份副本、宿主的全部 `PYTHON*` 变量清空、user-site 关闭——stdlib 必然先于任何 site-packages 解析,#138 的遮蔽机制在此无从发生。重放 **PASS → environment-suspect**(同一用例在去 site 层的最小环境通过:查本机 site-packages 遮蔽/`PYTHON*`);重放仍 **FAIL → tool-defect**(最小环境也红,traceback 就是缺陷证据)。FAIL 行的证据行同时改为引用嵌入输出的**末行**——真正的致命异常(如那条 TypeError)直接落在 FAIL 行上,不再让操作者从 "Traceback (most recent call last):" 读起。project 族用例是任意脚本、可能合法依赖宿主环境,自动重放证明不了任何事——只给"手工在最小环境复现"的提示行。重放跑不起来(超时、exit 2)如实报 **unclassified**,绝不猜。分类是诊断不是放行:**classified FAIL 照旧让整个 self-test 红**,exit code 语义零变化。重放的构件即 `gov self-test --case NAME`(按名单跑一个用例)——分类器与操作者共用同一条诊断通路。
- **被否**:环境可疑的 FAIL 直接转绿/skip——规则 6 的反面,红的证据价值高于分类的舒适,分类只加标签不改裁决;把"干净环境"定为 `python -S`/`-I` 裸解释器——site 层关掉后 `-m gov` 找不到包、`PYTHONPATH` 指向已安装包时又把污染目录原样带回,无法同时满足"可导入"与"去遮蔽",临时目录副本是唯一同时成立的机制;只打印提示"请检查环境"不做重放——那还是让操作者手工 trace,issue 要的是裁决自动化;对 project 族也自动重放——任意脚本在剥掉宿主环境后失败的原因千千万,一个必然红的重放只会制造噪音,证明责任留在脚本作者;FAIL 行保留首行("Traceback (most recent call last):")——那行对任何人类读者都是零信息,与 #109 确立的 failure-first(证据永不裁剪)同旨:失败行必须自己携带"为什么"。

## D48 — 陈旧基线点名与未采用门的发现（issue #147，接 D40）

- **问题**：radiant 的 7 个并行分支从 `main@6df5211` 切出，另一会话同期把 D39–D42 合上 origin/main——各分支从本地表编号起步：3 个 PR 被判 superseded、4 个中途改号、2 轮 force-push rebase。两件既有机制都没接住：① `decision next/add` 的 `--base`（D40）已在，但不传旗标时读的仍只是本地表，且并入后对"本地表落后 ref 几行"只字不提——盲编号正是碰撞的铸造点；② `verify-decisions --base` 能点名冲突，但该门在项目的 gates.json 里不存在（项目配置早于该门发布，没有任何机制提示采用）——唯一能命名碰撞的检查从未运行。
- **选项**：(a) `--against` 做成第二旗标语义；(b) `--against` 作为 `--base` 的别名 + 陈旧基线软警告；(c) 不传旗标时自动探测 ref（upstream/origin HEAD）并入；(d) doctor 点名未采用门 vs `--adopt-new` 顺带报告；(e) 把未采用门定为 doctor problem
- **状态**：已决
- **决定**：(b)+(d)。① `decision next/add` 增 `--against REF`：与 `--base` 同 dest 的别名（issue 点名的表面与既有词汇是同一语义，不开第二含义），有 ref 时计算 `ref − local`，非空即软警告 `your base is N rows behind '<ref>' (missing …) — rebase before numbering`——走 stderr，`next` 的 stdout 恰为编号列表不污染；② 同一感知进 `add`，软警告绝不阻断，union 分配的行照写；③ `gov doctor` 新增 gate-adoption 检查（note 永不 problem）：清点当前 govrail 版本发布的门——模板门（采用路径 `gov init --adopt-new gates.json`，D39）与 paths 因项目而异的手工门（verify-decisions/verify-rubric/verify-doc-sync，点名要接的命令）——按 gate id 或命令 token 对照项目 gates.json，缺失即点名；`enabled: false` 停用计为已采用（响的停靠是显式选择，D24）；旗标注册表同步 `--against`。
- **被否**：(a) 两旗标两处声明已是词汇分叉，别名把成本压到零；(c) 自动探测属"猜意图"（D11 立场），ref 缺失/离线时的静默分支比显式 flag 的缺席更难解释——警告与并入都只挂在显式 ref 上；(e) 采用是刻意的（D17/D28：平面是地板，成长事件驱动），缺失不是故障，且 defined-but-unmoded 已由 D24 的可达性校验大声拦截；把 verify-decisions 塞进注入模板——D28 已裁决不进（内容因项目而异），doctor 点名 + 手工接入正是不违该裁决的发现层。

## D49 — note-presence 的降噪：任务回执默认豁免 + manifest 申报豁免面（issue #149）

- **问题**：radiant 一周内两次假阳性：① 关任务卡写入 `.gov/tasks/T-*.json`（机器生成、rules 哈希钉住的回执，D43）被 note-presence 点名"改了非平凡文件却没有笔记"；② 每个 docs-sync PR（决策表行 + README 对重确认，无代码）同样被警告——feature PR 里笔记早已存在，sync PR 只是落地其载体。advisory-only 的定级是对的（D14），但当两种最常见的 agent 日常流程——关任务、落地 docs-sync——**永远**触发警告，agent 会学会"警告即噪音"并停止阅读，包括它真正指向遗漏的时候。
- **选项**：(a) 只把 `.gov/tasks/**` 回执判为簿记；(b) (a) + 仓库可申报豁免面（manifest 键 `note_presence_exempt`）；(c) 警告升级为 per-path 笔记归属检查
- **状态**：已决
- **决定**：(b)，外加警告自述语义。① `.gov/tasks/**` 进 trivial 前缀——任务系统本就产出防篡气回执（D43），回执是簿记不是决策，关任务默认不再触发。② `.gov/manifest.json` 新增可选键 `"note_presence_exempt": [glob, …]`（D15 glob 语义：`**` 跨目录、`*` 不跨，匹配仓库相对路径）——advisory 只在仓库声明"确实期望 note"的范围外触发；manifest 或键缺席 = 仅内建默认（manifest 是 init 的记录且可选，其未知键与本门无关——与现有 manifest 读取方一致）；manifest 存在但解析失败或键形不对 → exit 2 点名文件与键（规则 5，与 surfaces.json/decisions.json 的坏配置同风格）；活动豁免打印在输出里可见。③ 警告加一行自述：本警告意为"diff 里完全没有 note 文件"，而非"有 note 但不覆盖这些路径"——后者不可能出现（diff 存在任一 note 文件即通过，per-path 归属不可机械判定）。change-scope 的提醒与 review 档案改用同一判定函数，两处表面永不分歧（change-scope 对根级 .md 的旧判定借此对齐 D20）。advisory-only 语义不变：这是降噪，不是把检查变严。
- **被否**：(c) per-path 归属——笔记与路径之间没有机械可查的映射，真做只能把"有 note 的 diff"也变成警告（变严，正是本次要反的面）或假装检查；只做 (a)——docs-sync 类假阳性原样保留，且各仓库的簿记面不同，没有申报面就只能等下一个 issue 改工具；豁免键放 `.gov/pairing.json` 或新开 `.gov/note-presence.json`——为每扇门开一个私有配置文件是配置面碎片化，manifest 已是"本仓库对治理平面的声明"所在（D10/D34 词汇）。

## D50 — sidecar 自描述：模板注释、--write 字段回显、--explain（issue #150）

- **问题**：radiant 的编排 agent 双侧编辑 README 对后手工重盖 sidecar，按"记录提交"的自然理解写入 `en_commit`/`zh_commit = HEAD`——而门禁写入的是**最后触碰各侧文件的提交**（旧得多的哈希），错位以一次 amend + force-push 收场；且 sidecar 字段语义（哈希是 git blob hash 非 sha256、en/zh_commit 是 last-touched 非 HEAD、last_confirmed 是 ISO-8601）只存在于代码里，可发现性为零。门禁报错指向 `--write` 的部分完全按设计工作，缺的是语义的可读陈述。
- **选项**：(a) 只在生成的 sidecar 模板加注释行；(b) `--write` 写出时逐字段回显；(c) `--explain` 只读打印 schema 与约定；(d) `--write --dry-run`
- **状态**：已决
- **决定**：(a)+(b)+(c) 三处落点（笔记 [2026-09-05-pairing-sidecar-self-describing.md](../.agents/notes/implemented/feature/2026-09-05-pairing-sidecar-self-describing.md)）。① `_register` 生成的每份 `.i18n.yaml` 带注释行声明语义：pair.en/zh 是 `git hash-object` 的 blob hash 非 sha256；en_commit/zh_commit 是确认时刻**最后触碰该侧**的提交（非 HEAD、非确认提交，仅为上下文——门禁只比 en/zh 哈希）；last_confirmed 是 UTC ISO-8601（`datetime.isoformat()`）。注释是合法 YAML 且行式 `_parse_record` 本就跳过 `#` 行；注释住在 sidecar 文件里，不触碰其钉住的两侧，哈希零影响。② `--write`（显式 en:/zh: 登记、点名对、裸扫失步对三形态一致）打印记录路径、en/zh 哈希（"git blob hashes, not file sha256"）、en/zh_commit 值（"last commit that touched each side — not HEAD"；无提交记 `untracked`）与 last_confirmed——回显值与记录携带值同源，自查永不打架。③ `--explain` 打印 schema、本项目配置的约定（include glob、counterpart 模式，读 `.gov/pairing.json`）、当前在册对数、字段语义与命令面；严格只读（配置加载仍 exit 2 一致，不作任何评判——未登记的对照旧未登记）。旗标进 audit-notes 的 FLAGS 注册表（#101 的 test_flag_registry 钉法：argparse help 与表同步移动）。README 与 cookbook（双语对，重确认）记录语义与新旗标。
- **被否**：(d) `--dry-run`——issue 标题的候选，但 `--write` 幂等且现已自报字段，dry-run 为文档缺口引入第二种运行模态；真要预览批量基线，应朝那时的真实愿望设计。就地改写存量 sidecar 加注释——无谓扰动：记录在下一次正当重确认时自然获得注释，绿对保有其已挣得的确认（D32）；门禁从不读注释。行式解析器换 YAML 库——零依赖立场（D18/D25）不变，真解析器反而会拒绝或重写行式读取器正确忽略的注释。漂移报错教全套语义——D30 的报错已点名哪侧哪个提交动的、何时确认的，缺口在失败前的可发现性与对 `--write` 产物的信任，不在失败文案。

## D51 — 落地前并集预演：run --merge 与分阶段集成者模型

- **问题**：使用者用多个并行 agent 分支处理工作，各分支各自通过全部门禁，但"并集"从未被测过——合并时互相踩踏：文本冲突 git 能拦，语义冲突（各自绿、合并红）无人拦，暴露点被推迟到合并落地之后。四份独立评审（并发正确性、调度状态机、治理一致性、务实怀疑论）收敛出的最小机器是"落地前预演"；其余层（锁、租约、调度函数）按判据推迟，不在本次范围。
- **选项**：(a) `run --merge` 现在建——它是唯一覆盖"并集落地前绿过"这一承诺的机器（任何单分支门禁都测不到并集），且对串行批次同样有用（每步预演即每次落地前检查）；(b) 锁/租约层推迟——判据：出现 ≥2 个真并行 worker 或批次积压时再建，今天没有它们要防的争用；(c) schedule 纯函数最后——等政策真的长出分支（谁的批次先落、跳过谁）才有可编码的语义。
- **状态**：已决
- **决定**：**`gov run --merge <branch> [<branch>…] [--base <ref>]`**（笔记 [2026-09-05-run-merge-preflight.md](../.agents/notes/implemented/feature/2026-09-05-run-merge-preflight.md)）：在临时 scratch worktree（`git worktree add --detach <tempdir> <base>`，`--base` 为集成目标基线，缺省 `origin/master`，不存在则 exit 2 点名并要求显式旗标）中按命令行顺序逐条 `git merge --no-ff --no-edit`；**每合并一条分支，就在该并集树上跑一次门禁**——门集用 D15 的最小充分集，按"本步合并引入的 diff"选门（`--base` 指向上一步记录的树 sha），最后一步的树即全并集。文本冲突：exit 1 点名 `branch k (<名字>) conflicts with already-merged set (<名字…>)` 与冲突文件，保留现场 scratch worktree 并打印路径；门禁红：exit 1 点名失败分支、已合并集合、失败门名与关键输出行，同样保留现场；全绿：exit 0，清理 scratch，打印各步摘要。退出码遵守 D2，不新增。宿主安全落实 D33 三墙：敌对仓库解析变量（GIT_DIR 等）在跑任何东西之前大声拒绝（exit 2 点名变量）而非静默换域——本命令会变更仓库状态，歧义必须拒绝；一切 git 操作显式 `-C` 钉住仓库根或 scratch；scratch 合并前必须把 `--show-toplevel` 解析到自身（toplevel 守卫）；验收测试钉住"运行前后宿主工作树字节不变"。scratch 内不创建/unlink 任何锁文件（decision.py 的 `.decision.lock` unlink 竞态是已知缺陷，不模仿）。`--merge` 与 `--receipt` 可组合：最末步（全并集）升级为全矩阵运行并录 D44 回执——按步收窄的 selection 永远验不成"完整证据"，回执绑 tree sha，落地（含 squash）后 `gov receipt verify` 按 tree 命中可验。旗标注册表同步 `--merge`（test_flag_registry 钉法）。
- **被否**：中心化 merge queue 服务——外部服务依赖违背零依赖立场；常驻 supervisor 编排——协调状态不可版本化，治理平面只管仓库里的事实；flock+TTL+reaper 混合锁——评审 P0：reaper 无法代放其他进程持有的 flock，TTL 到期 unlink 后重建制造双持；sequence CRDT——依赖与规模双双错配，几张表用不上分布式合并；"最旧 PR 无限重试"的队头阻塞策略——一个永不绿的头阻塞整个队列。**supersede 边界**：D40 被否段"文件锁锁不住独立检出"仍然为真——本裁决只涉及同一 clone 内 worktree 的预演机制，跨分支编号正确性仍归 `--base`（D40 不变，不被本行翻案）。

## D52 — 租约锁原语：acquire/release/locks 与 exit 3 词汇扩展

- **问题**：多 worker 盲态并行的真实场景已落地——使用者确认多个 agent 互相不知情地并行工作，靠"工具阻塞/继续"协调共享资源（如共写一个文件）的写入次序。D51 把锁/租约层按判据推迟（"真有 ≥2 并行 worker 需要共享资源协调"），该判据现已触发，本行即其兑现。四份独立评审对锁层的修正结论必须全部吸收：P0 指出 flock(2) 属于持有进程、进程退出即失锁——长持锁绝不能建在 flock 上；TTL/reaper 与 flock 混用被否（reaper 无法代放他进程的 flock，unlink 后重建制造双持）。
- **选项**：
  - (a) **租约类文件锁**（本行采纳）：锁文件 `<git-common-dir>/gov-locks/<resource>.json`，`gov acquire` 以 O_CREAT|O_EXCL 原子创建；过期租约懒接管，接管临界区用 flock 守护 `<resource>.guard`（flock 的合法形态：仅单命令时长，与被否的"长持 flock"不冲突）；新鲜 O_EXCL 创建路径不需要守护、绝不 unlink 新鲜锁；`gov release` 持有者校验删除（不匹配 exit 2 点名实际持有者，绝不代放）；`gov locks` 只读诊断列表，不参与任何准入决策。
  - (b) **exit 3 additive 扩展 D2**：busy/等待超时需要被调用方分支，塞进 1（门禁失败）或 2（配置错误）都会污染既有语义；新增 3 仅由 acquire/release/locks 使用，0/1/2 语义逐字不变。
  - (c) **锁放 .git 共享域**（D32#9 先例）：`--git-common-dir` 解析（resolve()，主 worktree 返回相对 `.git`），同 clone 全部 worktree 天然共享；入口对 GIT_DIR 等六个仓库解析变量拒绝（exit 2 点名，D51 对改状态命令的拒绝强度）；common-dir 解析失败一律 exit 2，禁止 cwd 级静默降级。
  - (d) **判据触发**：引用 D51 的推迟判据与分阶段承诺；锁是活性层（fail-open），正确性锚在 push CAS（master）与交付 rebase（文档），holder 挂起超 TTL 的双持由上层校验兜底。
- **状态**：已决
- **决定**：(a)+(b)+(c)+(d)。`gov acquire <resource> [--agent ID] [--ttl S] [--wait S]`（busy 立即 exit 3 点名 holder/expires_at，--wait 秒内 1s 轮询、超时 exit 3；锁不可重入，同 holder 重复 acquire 也 exit 3）；`gov release <resource> --agent ID`（不匹配 exit 2）；`gov locks`（空锁输出空表）；holder 缺省取 GOV_CALLER（D42 词汇）再取 getuser。旗标注册表同步（test_flag_registry 钉法）。接管竞态由双进程同时起跑的验收测试钉住：恰一成功、败者 exit 3。supersede 边界：D40 被否段"文件锁锁不住独立检出"仍真——本锁只覆盖同 clone 的 worktree，跨 clone/跨机正确性仍锚 CAS，D40 不被翻案。
- **被否**：flock 长持——评审 P0：flock 属于持有进程，`gov acquire` 作为独立进程无法跨时长持有，进程退出即失锁；flock+TTL+reaper 混合——评审 P0：reaper 无法代放他进程的 flock，TTL 到期 unlink 后重建制造双持；无 TTL 裸锁——僵尸锁永锁，crashed holder 永久阻塞资源；阻塞直到永远——无界等待把协调变成死锁的另一种拼写，--wait 有界轮询替代；锁参与正确性——fail-open 姿态：正确性永不依赖锁，锁只管活性避免重复劳动，否则锁缺陷即正确性缺陷。

## D53 — preset：按项目类型的声明式补丁包

- **问题**：`gov init` 注入的模板是一套通用门（D28：类型化内容因项目而异，不进默认模板）——采用者想要按项目类型的成套起步配置（几个门 + 相关技能 + manifest 提示）只能手写 `gates.json` 并逐个抄技能；三类内容各自都有成熟的"增量落地、绝不覆盖定制"机器（D39 门合并 / D29 字节采纳 / D49 只写缺失键），但没有任何把三者打包随包分发的载体。
- **选项**：(a) 把类型化门直接进默认模板；(b) preset 远程源/注册表（可下载第三方 preset）；(c) apply 覆盖已有定制（"preset 说了算"）；(d) 交互式向导（逐项询问采用哪些）；(e) 通用"merge 语义注册表"（工具暴露可插拔合并器接口）；(f) **preset = 随包发布的、按项目类型组织的声明式补丁包**，复用既有采纳机器增量落地
- **状态**：已决
- **决定**：(f)。**格式**：`gov/templates/presets/<name>/preset.json`，顶层键闭集 {name, description, gates, modes, skills, hints}，name/description 必填；未知键、坏类型、mode 引用 (模板 gates ∪ 片段 gates) 之外的门 → exit 2 点名 preset 与键（规则 5）；gates 数组里的门对象必须过 gates.json 的真实 schema 校验（`gates.load_config`，与 D39 同一校验器）。**机器**：`gov preset list|show|apply`——apply 复用 D39 的 adopt-new 合并逻辑（提取为共享的 `gates.merge_gates_by_id`，--adopt-new 行为不变）：同 id 已存在 → 原样保留本地并点名，新 id 按声明顺序追加并逐一点名；mode 只追加新采纳 id、引用合并外门的 mode 打 notice；落地前用真实 schema 校验合并结果。技能逐字节复制、已存在跳过点名（D29 契约）；hints 只写 manifest 缺失键、已有键保持本地值并打 notice（D49 契约）；apply 幂等——已采用的仓库重复 apply 全部 "already adopted" notice、exit 0、零写入；未初始化项目 apply → exit 2 点名要求先 init（写死，绝不 improvisation 半个项目）。**`gov init --preset <name>`** = init 后立即 apply，一条命令完成新项目按类型起步；与 --upgrade/--adopt/--adopt-new 互斥（exit 2），未知 preset 名在任何写入之前先拒。**与 D28 的调和**：模板默认仍是通用门（D28 不变），类型化内容经显式 `--preset` 采用，preset 绝不进默认 init——D28 回答"默认该装什么"，preset 回答"我的项目类型还需要什么"。**首发 agent-heavy**（多 agent 并行开发场景，D51/D52 并发演练验证的工作流）：verify-decisions 门（paths 限 docs/decisions.md）注册进 governance mode（D24 可达性）、parallel-workers 技能（lease → 验证 → 预演 → 盲态协调四步协议，源文件同时放本仓库 .agents/skills/ 并加 D19 式字节一致测试，dogfood）、`note_presence_exempt: [".gov/tasks/**"]`（#149 的教训：任务回执是簿记）；内容另有 preset 目录 README 与 `gov preset show` 的可读呈现。python-lib、docs-bilingual 按同一矩阵跟进（分阶段承诺）。旗标注册表同步 `--preset`（init）与 `--project`（preset apply），test_flag_registry 钉住。
- **被否**：(a) 违背 D28——通用门是地板，类型化门进默认集让每个项目为用不上的门付税，且退回"下线靠删定义"的老路；(b) 外部下载源违背零依赖立场，且供应链上 preset 落地的是门 command（argv 数组）——任意远程 preset 即任意命令执行面，随包内置、随代码评审走；(c) apply 覆盖已有定制即 D8/D39 的反面——补丁包的全部意义就是"落在你已有的东西之上"，覆盖一条就毁掉整个契约；(d) agent 是头号用户，非交互旗标胜——向导在 CI 与脚本里不可用，逐项询问把一条命令变十次往返；(e) YAGNI——今天只有一种合并语义（D39 的 id 身份增量），为假想的第二种语义造注册表是复杂度期货，事件到了再建。

## D54 — 解析层：tree-sitter 作为基础依赖，gov stats 出结构事实

- **问题**：平面对代码的全部认知来自文件名与 diff——`paths` 匹配、conflict-marker 扫描、note-presence 的"行为面"判断都是文本层的。采用者的常见诉求（复杂度趋势、结构指标、语法类静态检查）没有任何承载：要么引入第二套工具链（违背单实现），要么永远不做。同时"语言无关"这个声明从未被非 Python 实例检验过。真正的问题是：**能不能给平面一个语法认知层，而不把判决交给一个近似前端？**
- **选项**：(a) 自写各语言 parser；(b) 只消费各工具链的机器可读诊断（vet/clippy 输出）；(c) **tree-sitter 作为基础依赖：语法层是它的本职，指标与检查消费同一棵树**；(d) 全部留 LSP/编译器，平面不做语法
- **状态**：已决
- **决定**：(c)。**依赖**：`tree-sitter` 核心 + 8 个官方语法包（python/go/java/rust/javascript/typescript/c/cpp）进基础 dependencies——"解析项目中的所有代码文件"开箱即用；语法包是 abi3（一个轮子覆盖 CPython 3.10+，glibc/musl、mac、Windows 双架构，7 个目标平台逐一核实过 wheel）。**版本地板随之上移**：requires-python 3.9 → 3.10（tree-sitter 0.26 的地板；3.9 已 EOL）；`OS Independent` 分类器下线，改按平台出轮子——C 扩展使纯轮子声明不再诚实，这句声明 0.29.1 刚修诚实过一次，不再让它重新变假。**D1 的收窄**：单实现（纯 Python 3 代码）不变；"安装前提 = Python 3"削为"Python 3.10 + 随包声明的解析绑定"；零依赖立场就此终结——D18/D25/D29/D53 被否段引用的零依赖是历史记录，不回改。**语言包是数据**（`gov/langs/*.json`：globs/exclude/nesting/functions/classes/comment/string + 语法包名），引擎零语言名；**节点名加载时对照语法的 kind 表校验**，未知 kind 拒载点名（rule 5）——拼错的节点名会让指标静默归零，这是本决策开发期间真实抓到过三次的 bug 类（java 的 `switch`/`for_statement`/`_multiline_string_literal`）。**文件集诚实**：默认排除 VCS/venv/build/dist/缓存目录，语言包可扩展不可收缩；解析失败（ERROR 节点）计数并点名文件，绝不静默跳过。**能力边界（本决策最重要的一条）**：只在"语法答案就是答案"的地方用——格式、结构、禁用构造、命名、模式；**需要类型或流的一律不做**（未定义符号、类型不匹配、调用图），因为近似前端的漏报是静默的，比误报危险得多；要编译级判断，语言自己的编译器才是权威（且已是门禁）。**第一个消费者 `gov stats`**：行数族（口径回显：多行字符串算代码——docstring 是字符串不是注释）、符号族、嵌套深度族（p50/p95/max + 离群；深度=函数体内块层数，从零起算），`--record` 入 `.gov/history/stats.jsonl`（与 gates 账本同锚定 D32；**指标不是证据**——stats 账本永不参与任何校验，D44 的分界）。**指标的可信度机制**：每个指标配一份手算得出答案的夹具（原型第一版深度计错、报出看似合理的 0——数字类 bug 的假绿比门禁的假绿更隐蔽）。doctor 增 parser 检查（依赖可导入 + 语法版本）；MIN_PYTHON 与 requires-python 同步。诚实化同批：README 双语对、"stdlib only" 措辞、D47 干净重放的"包副本即完备环境"前提（依赖类失败的误标边界写明）。**后续（未做，事件到了再建）**：检查引擎（捕获查询 + 差集表达否定 + `gov:ignore-check` 抑制计数入趋势）、subprocess/文本 I/O 缺 encoding 的疤组织检查（差分证明替换正则实现）。
- **被否**：(a) 自写 parser——N 语言 × 一套实现且必然漂移成假绿（语法接受编译器拒绝的东西），方向最大的风险恰是它最诱人的地方；(b) 只消费诊断——语义检查的正确答案（vet/clippy/ruff 的 JSON 输出确是语言中立层，值得消费），但它给不了结构指标与复杂度趋势，两者互补而非互斥；(d) 不做语法层——复杂度维护的诉求真实存在，平面不承载它就会在平面外野蛮生长，恰好绕过全部治理机器；**OS Independent 保留**——C 扩展下纯轮子声明是"声明宽于能力"（空洞绿灯的打包版），0.29.1 的修复不做两遍；**类型/流检查**——近似前端漏报静默，rule 6 能证它误报能红、证不了它不漏；**LOC/深度阈值门禁**——数字一旦拦人就开始被优化（Goodhart），指标进趋势、离群清单，不进判决。
