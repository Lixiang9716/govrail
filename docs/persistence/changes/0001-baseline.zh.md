# 持久化变更 0001:基线——已声明的格式清单

状态:已确认

持久化纪律(D63)的基线记录。它声明了平面自身持久化格式的完整清单,
以形状描述符的形式落在 `docs/persistence/schemas/`——每个描述符点名其
产物、写入者、读者、运行时类别(tracked 与 runtime-deletable)与字段——
从读写这些格式的代码出发撰写,不凭记忆。此后任何对这些形状的变更,
都必须在本目录落一条后继记录并链接到本条:对它触及的每个类型,
`before` 摘要等于前继的 `after`;最新记录的 `after` 必须等于活体
schema 文件的摘要(正是这个锚点让不确认就改 schema 的行为变红)。

类别:`compatible`——旧形状的读取者继续工作。
`breaking`——旧读取者必须响亮拒绝,迁移由 `gov update` 负责,记录中写明。

```json
{
  "record": "0001",
  "date": "2026-09-19",
  "class": "baseline",
  "changes": {
    "gates-config": {
      "before": null,
      "after": "b8717065d4f97df5d19e8e6748d060583bc2d9065b9c37a845476b38df52a8b3"
    },
    "manifest": {
      "before": null,
      "after": "eb11f516168235f19f34dd8b44a7ae70b6ac11ac87dbaad3bb00d44a10398b80"
    },
    "note-file": {
      "before": null,
      "after": "1cb198226f0f63db1ae3473037a72c43bae6f9ecf9aa5da927f1948b098b821e"
    },
    "pairing-config": {
      "before": null,
      "after": "0ea383ff140271fd878621a76efe9e621ccf308d9d49b9791b268d2d83c63229"
    },
    "pairing-record": {
      "before": null,
      "after": "b9a7e9376a49ce324e242b026ea46f6a25e2b79d1c105a394d386999033776d0"
    },
    "plane-seal": {
      "before": null,
      "after": "b3d9f914ef172611d0b089d9a818be59056030b016d009e632aba18a1f7f5ccd"
    },
    "rituals-ledger": {
      "before": null,
      "after": "aa2906b7cc87fd38c438ba81c0b09a2d3aa26dd78f05f3408eae49bcf398a869"
    },
    "run-receipt": {
      "before": null,
      "after": "97c461387c3799ffb15c5780ce6c9106ebbdf451b39dd820a95f416d50342a9a"
    },
    "surprises-ledger": {
      "before": null,
      "after": "45fb10506456cb6c4aecef381d7bcb77dca193b6a9a39932017e1e8b11480552"
    },
    "task-card": {
      "before": null,
      "after": "e481fcf313e5e5248dc4f7e4606e6dcb1b90efa49035259dc08a76863077e4fc"
    }
  }
}
```

`.gov/history/` 的同伴(`gates.jsonl`、`stats.jsonl`)归入 `run-receipt`
的运行时类别:设计上可删(N9),确认在案但永不迁移。

