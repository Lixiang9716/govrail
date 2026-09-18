# Agent Note: 代码设计契约立规：模块化单体 + 注册表单一来源 + 自吃守护门

Status: implemented

## Problem

代码评审（含外部审查 N12/N14 的结构性发现模式）在 0.41 的树上点名了三处可维护性侵蚀，每处都已从"风格问题"长成"漂移事故的温床"：

1. **cli.py 是杂物抽屉。** 1600 行里约 1100 行是 init/uninstall/adopt/upgrade 领域机制；`gov update` 跨模块伸手拿私有函数 `cli._upgrade_files`，audit-notes 读 `cli._COMMANDS`——模块边界在说谎，而 D56 的退出码契约、D57 的别名集都以这份内部符号为母名单，漂移全靠人肉纪律（rule 9）兜底。
2. **self_test.py 是 2329 行的单一高扰动文件。** 每加一个门 = 定义案例函数 + 手工往 `CASES` 列表登记，两处 bookkeeping 缺一即漏；列表处的合并冲突随门数量单调增长。
3. **体量与分层没有门。** #265 预留的原语（`gov parse`/`gov stats` 事实 + 限额声明）躺在命令面上，而本仓库自己的 gates.json 没有消费它——"不许长出下一个巨石"只是评审愿望，违反 rule 1（gates over prose）。

另一个隐蔽事实：此前的依赖图扫描与本次新写的检查器先后漏掉/抓到 `from . import x` 形态的惰性导入环（note↔verify_notes、rituals↔verify_plane）——环真实存在，靠函数级延迟导入存活；这是本代码库既有的解耦手段，但没有成文，也没有被任何机制看见。

## Decision

设计姿态已锁入 D61；五条契约成文于 docs/architecture.md 新节 "Code design contracts"（en/zh 同步）。三步落地：

1. **注册表单一来源**：`gov/commands.py` 持有命令面板（`COMMANDS`/`DEPRECATED_ALIASES`/help-version 契约/`COMMAND_FLAGS`），`--help`、audit-notes 已知命令集、退出码契约测试四方同读一份；init/uninstall 机制整体迁入 `gov/plane.py`，三个跨模块消费者升公共名 `upgrade_files`/`adopt_missing`/`adopt_new_gates`（update 消费；tests 对 `_add_ons` 的白盒引用除外，产品代码不再有跨模块私有 import）；cli.py 瘦身为纯分发器（1625→352 行）。
2. **self_test 包化**：`gov/self_test/` 按平面族分模块（notes/gates/knowledge/surface/evidence，最大 466 行），共享夹具入 `_harness.py`；案例经 `@case` 装饰器在导入时注册——定义即登记，手工 `CASES` 列表废除。对 tests/ 的历史符号面（`main`、`CASES`、`_git_repo`、`_run_tool_case`、probes）保持 re-export。watchdog 子进程的 PYTHONPATH 随包化修正到 checkout 根。
3. **自吃门**：`import-layers` 与 `size-limits`（advisory 先行，P0-3 惯例）；评审轮的 CI lint 失败（69 处 ruff 发现骑在机械改线上，本地 pre-push DAG 看不见它）把第三个门顶上桌：CI 的 `ruff check .` job 收编为 `lint` 门（block——自吃树无采用者首跑问题；rule 6 拒绝案例齐）。原两个门的门禁化叙事：
`import-layers`（叶不导 gov 模块、仅声明入口可达 cli、导入期图无环；函数级惰性边方向照查、环豁免，且计入门汇总行保持可见——43 条；层图是数据：`scripts/import-layers.json`）与 `size-limits`（声明限额 + 逐文件计数，默认 1600 行，`scripts/size-limits.json`）。各自带 `.gov/rejections/` 拒绝案例（rule 6），D2 退出码词汇。翻转 blocking 留作单独的可见决定。

评审rubric 增 R9（单体保持模块化），en/zh 同步。create-if-missing 的模板与 shipped 门零改动——这两个门是 govrail 自吃的，不进采用者模板。

## Alternatives considered

- **cli.py 维持现状**（router skill 已解决"发现"成本）：被否——解决的是发现，不是同一词汇四家人工同步（D56 修订二的事故会按命令数量复发）；跨模块私有 import 已经是边界说谎的证据。
- **给命令面上抽象框架 / argparse 统一子命令**：被否——D57 已定四 hub taxonomy，分发器是 if 链 + hub dict，可读且被退出码契约测试钉住；引入框架是对"门是外部命令"这一产品形态的重复实现。插件框架/entry-points 同理：D53 选了数据包扩展，安装期插件破坏单次 pip install 模型。
- **Gate 抽象基类 / DI 容器 / 内部事件总线**：被否——`Gate` 是记录不是行为（多态住在 `gates.json` 命令槽）；1.6 万行规模函数参数即注入；状态层的追加式哈希链台账已是事件溯源，代码层再造一份是重复收费。
- **self_test 只加装饰器不拆文件**：被否——装饰器只消灭双 bookkeeping，不消灭单一高扰动文件的合并冲突；2329 行的文件本身即审阅障碍。全量物理平移的风险用"pytest 720 + self-test 56+12 全绿 + 历史符号面 re-export"兜住，过程中真实抓出三类纯机械搬移必漏项（watchdog 的 PYTHONPATH 父目录层级、`-m gov.self_test` 需 `__main__.py`、adopts 案例直跑旧文件路径）。
- **环处理为"extract 公共叶、现在修死"**：部分采纳、部分推迟——`PLACEHOLDERS`/`_identity` 类常量下沉是正确方向，但本轮两个环全是惰性边（初始化无害、方向单一），先以"方向照查 + 环豁免 + 计数可见"立约，修环留在 `import-layers` 翻 blocking 的同一决定里做（届时它不再是 advisory）。
- **两门直接 blocking**：被否——P0-3 的第一跑不变红是平面自己的安装纪律；先 advisory 攒运行证据，翻 blocking 是有消费者署名的独立变更（D56 同款极性逻辑）。
