# Persistence change 0001: baseline — the declared format inventory

Status: acknowledged

The baseline record of the persistence discipline (D63). It declares
the complete inventory of the plane's own persisted formats as shape
descriptors under `docs/persistence/schemas/`, each descriptor naming
its artifact, writer, readers, runtime class (tracked vs
runtime-deletable), and fields — authored from the code that writes
and reads them, not from memory. Every later change to any of these
shapes must land a successor record in this directory chaining to this
one: same `before` digest as the predecessor's `after` for each type
it touches, and the newest record's `after` must always equal the live
schema file's digest (that anchor is what makes touching a schema
without acknowledging it go red).

Classes: `compatible` — readers of the previous shape keep working.
`breaking` — older readers must refuse loudly, and `gov update` owns
the migration story; the record states it.

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

`.gov/history/` companions (`gates.jsonl`, `stats.jsonl`) ride the
`run-receipt` runtime class: deletable by design (N9), acknowledged but
never migrated.
