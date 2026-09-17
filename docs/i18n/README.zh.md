# 双语配对契约

[English](README.md) | 中文

两种语言具有同等权威；任何一种都可以先写。一个配对是三个同级文件：源 `foo.md`、译文侧（约定命名为 `foo.zh.md`）、记录 `foo.i18n.yaml`。

## Sidecar

sidecar 记录两侧在上次确认一致状态下的 git blob 哈希，并钉住译文侧的文件名：

```yaml
pair:
  en: <sha>
  zh: <sha>
counterpart: foo.zh.md
```

编辑任意一侧后，在同一改动中重新确认：

```sh
gov verify-pairing --write docs/example.md
```

当记录的哈希不再匹配文件时门禁变红——单侧编辑永远不会静默。

## 约定即配置

命名约定放在 `.gov/pairing.json`（所有键可选）：

```json
{
  "include": ["docs/**/*.md", "README.md"],
  "counterparts": ["{stem}.zh.md"],
  "exclude": ["docs/decisions.md", "docs/postmortem/README.md"]
}
```

译文命名为 `foo_CN.md` 的项目设 `"counterparts": ["{stem}_CN.md"]`。不符合任何约定的一次性配对显式登记——记录里的 `counterpart` 字段钉住名字：

```sh
gov verify-pairing --write en:docs/foo.md zh:docs/foo_CN.md
```

## 诚实的边界

绿灯意味着配对在这些内容上被确认过一致——不代表翻译质量好。质量属于评审。
