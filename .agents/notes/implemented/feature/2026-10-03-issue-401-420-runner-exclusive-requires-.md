# Agent Note: issue 批次 #401-#420 — runner 新面(exclusive/requires/--at/物化)

Status: implemented

## Problem

调度与评判面各有一批采用方实测痛点(#402/#403/#405/#406/#407/#412/#414/#417/#420):既有分支推送评判的是开发者的偶然工作树——并行工作流的未提交文件能把红带到它不在场的 push 上(#402);self-test 的改树用例与读树兄弟门在并发 DAG 里竞速,两次 CI 红出在字节相同的绿树上(#403);重门(全新 clone)饿死紧墙钟预算的兄弟门(#417);依赖网络的门在网络抖动时把 docs-only diff 判红,红色无法自证"不是这个 diff 的"(#407);`--gate` 只收一个 id,已发布的集成脚本传两个即死(#405);复现 CI 单门红需要 checkout——共享 worktree 上曾把另一会话的提交搬走(#406);DAG 边(needs)是 schema 合法字段却只能手改被密封的 gates.json(#412);code-size 全树或nothing,并行 worker 无法只判自己的文件(#414)。

## Decision

调度器增 `exclusive` 门属性(先排空运行池再独占接纳,落定前零准入;ready 队列只经 pump() 准入,有限 DAG 无饿死)——改树门与重门各得其所,本仓库 self-test 门已标;gates.json 增 `requires: ["network"]`(封闭词表,未知值配置即拒),失败的结局行与摘要打 ENV-possible 标签,仍是阻塞失败;pre-push 钩子把 pushed sha 物化成临时 worktree 在其中跑路径限定 DAG(#363 新分支路径同迁,红时证据拷回主检出,物化失败回退旧路径并声明;多 range/full-matrix 路径维持原位——单 worktree 装不下多 ref 的诚实评判);`gov run --at <ref>` 用同一物化机制服务单门复现,拒绝与 --receipt 组合(证据随 worktree 死亡),history 不落并声明;`--gate` 收多 id 一次遍历,未知/停用按名拒绝;`gov gate add` 增 `--needs`(可重复,经 runner 同款 loader 校验,环与悬空点名)与 `--exclusive`;`scripts/check_size_limits.py` 增可重复 `--only`(literal/glob,无斜杠匹配 basename,零命中按 typo 拒绝 exit 2)。rules.md 规则 6 增一句:改树的用例必须串行(exclusive 或等价物)。

## Alternatives considered

#403 的 worktree 快照方案被否:用例引用的未提交脚本/产物不在快照里,创作回路(写用例→红→改)被静默降级——证据面收窄无声,违规则 5;#402 的 GOV_SCOPE_TREE=committed 方案被否:语义对但每个读树的门都要各自改造,面太大;#407 的 ENV-FAIL 非阻塞车道被否:证据缺失不冒充绿(SKIP 教训同理),分类是诊断不是放行;#404 的 timeoutRetries 被否:重试掩盖调度致红的真相,命名+时长+重跑命令是诚实的救济;#417 的 weight 分级调度被否:exclusive 已覆盖"重门不该与紧预算门并发"的实际形态,权重系统是第二套词汇。
