# Bilingual pairing contract

English | [中文](README.zh.md)

Both languages carry equal authority; either may be written first. A pair is
three sibling files: the source `foo.md`, a counterpart translation (named
`foo.zh.md` by convention), and the record `foo.i18n.yaml`.

## The sidecar

The sidecar records the git blob hash of each side at its last
confirmed-consistent state, and pins the counterpart's name:

```yaml
pair:
  en: <sha>
  zh: <sha>
counterpart: foo.zh.md
```

After editing either side, re-confirm in the same change:

```sh
gov verify pairing --write docs/example.md
```

The gate fails when a recorded hash no longer matches its file — a one-sided
edit is never silent.

## Conventions are configuration

Naming conventions live in `.gov/pairing.json` (all keys optional):

```json
{
  "include": [
    "docs/**/*.md",
    "README.md"
  ],
  "counterparts": [
    "{stem}.zh.md"
  ],
  "exclude": [
    "docs/decisions.md",
    "docs/postmortem/README.md"
  ]
}
```

A project that names translations `foo_CN.md` sets
`"counterparts": ["{stem}_CN.md"]`. A one-off pair that follows no convention
is registered explicitly — the record's `counterpart` field pins the name:

```sh
gov verify pairing --write en:docs/foo.md zh:docs/foo_CN.md
```

## Honest limits

A green gate means the pair was confirmed consistent at these exact contents —
not that the translation is good. Quality belongs to review.
