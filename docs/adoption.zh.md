# 把平面采用进项目

[English](adoption.md) | 中文

平面用"一个动作一条命令"的方式采用。规则在 [.gov/rules.md](../.gov/rules.md)；已锁定的决策在 [decisions.md](decisions.md)。

## 安装与移除

```sh
gov init --project <path>       # 注入门禁、笔记、规则、引用行
gov init --project <path> --hooks --ci  # 同时安装执行路径
gov uninstall --project <path>  # 精确反转；只删 init 创建的东西
```

`init` 幂等（重复运行是 no-op）且非侵入：创建 `.gov/rules.md`，仅在缺失时添加 `gates.json` 和笔记 README，向 AGENTS.md 追加一行引用，绝不覆盖项目自己的文件。

`--hooks` 写入 pre-push 钩子（`.gov/hooks/pre-push`，接入 `.git/hooks/pre-push`），推送离开本机前跑 `gov run`；外来的 pre-push 绝不覆盖——加装在任何变更之前预检、fail loud。`--ci` 仅在文件不存在时生成 `.github/workflows/gov.yml`（跑 `gov run`）。两者都记入 manifest，`uninstall` 精确反转。

## 第一天循环

```sh
gov run                  # 默认模式的门禁 DAG；pairing 以 advisory 报告
gov self-test            # 证明每个治理门禁都能拒绝违规
gov run --base HEAD~1    # 只跑 paths 命中本次 diff 的门
gov change-scope --base HEAD~1   # 改了什么、哪些门覆盖它
```

新装项目的 pairing 门禁是 advisory（`allowFailure: true`）：报告哪些存量文档还没有基线，但不拦截。准备强制配对时，先记录存量配对，再从 `gates.json` 的 pairing 门禁摘除 `allowFailure`：

```sh
gov verify pairing --write       # 为全部配对建立基线（写 .i18n.yaml 记录）
```

译文命名不同的项目（如 `foo_CN.md`）在 `.gov/pairing.json` 里配置约定，或用
`gov verify pairing --write en:<path> zh:<path>` 逐个登记。

触及行为面却没有 Agent Note 的改动会被 `gov note presence` 警告（带规则出处）；补上笔记，或等团队准备好后加 `--strict` 让它拦截。日常簿记永不警告——任务卡回执（`.gov/tasks/**`）默认豁免；仓库还可在 `.gov/manifest.json` 里用 `"note_presence_exempt": ["docs/**", …]` 申报更多豁免面，advisory 只在确实期望 note 的范围外触发。

然后做一次真实改动，记为 Agent Note，再重跑门禁。
