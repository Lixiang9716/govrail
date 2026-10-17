# Agent Note: #429-#446 — 跨 worktree 身份与预算诚实(D71)

Status: implemented

## Problem

单检出单写者假设在多 worktree 与长 DAG 下成批破产:卡 id 每检出高水位让同克隆四个 sibling 各铸同一号(#435,实测一天五个 T-0212);卡是检出内文件,另一 worktree 的守护流程得到裸"no card matches"引向重铸(#436);`task new` 无重复守卫,幂等脚本静默铸空双胞胎(#431);close 的 600s 平预算被冷缓存打穿,弃判读作十一个假红(#442);重复 `--gate` 旗标只留末值,四次验证读成一次绿(#441);surprise 台账 pre-split 旧行让 record 在追加之后 KeyError——数据落地、退出码说谎(#430/#438);传递 skip 的"needs failed: X"因果倒置(#434);摘要只有计数(#437);Windows 的 CreateProcess 无法执行 shebang 用例、裸名 bash 会落进 System32 的 WSL(#429);项目用例无单跑选择器(#445-1);作用域绿不说 CI 还会跑全矩阵(#440);只产报告的委托观察运行被规则 9 逼进无卡违规(#444)。

## Decision

身份:卡 id 铸造增 common dir 的 O_EXCL 标记(`gov-task-minted/<id>.spent`,无 TTL——id 一经铸造永久作废),sibling worktree 同克隆互斥,败者重分配;`task new` 对同题开放卡点名拒绝、--force 显式 escape;解析失败指认当前分支 + 历史 id。预算:close 默认无界(--timeout 0),超时如实说"弃判、未评、卡未动"。报告诚实:skip 原因改"blocked by red:";计数摘要带 id(封顶 5);重复 --gate 旗标拒绝并指认空格形态;surprise 查找跳过旧行并声明一行。Windows:.sh 用例经 GOV_CASE_BASH 路由(排除 System32 WSL bash),"cannot execute"失败在 nt 归 environment-suspect;`--case` 接受项目用例路径;hook 绿时声明 CI 会补跑全矩阵。规则 9 增豁免段:只产报告、只动未跟踪暂存的委托观察运行免卡。

## Alternatives considered

铸造标记的租约替代被否(TTL 过期后挡不住间隔数小时的铸造,nonce 后缀破坏 id 形态与全部引用);近似同题匹配被否(阈值武断会误伤合法重开,精确同题零误伤);close 预算按门数缩放被否(又一个魔法常数,无界+如实弃判已覆盖);skip 措辞保留"needs failed"被否(四个会话各自卡顿数秒是实测成本);Windows 用例改一律 .py 被否(用例语言是项目选择,豁免 .sh 是拒收采用方生态)。
