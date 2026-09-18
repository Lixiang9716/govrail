# preset: docs-bilingual

For bilingual documentation repositories where release-facing docs move in
pairs: the CHANGELOG is updated (by release tooling or by hand) and the
usage-oriented HIGHLIGHTS file must follow, version numbers read from the
CHANGELOG — never guessed (D37). Applying lands one gate,
`doc-sync` (`gov verify doc-sync`), scoped to `CHANGELOG.md` +
`HIGHLIGHTS.md`, registered in the `all` mode. Premise, stated plainly:
the repository must really carry the two files — `CHANGELOG.md` at the
root and the HIGHLIGHTS file where `verify-doc-sync` reads it
(`gov/HIGHLIGHTS.md`, the layout this plane's own repository uses) — and
the HIGHLIGHTS section headings must read `## <version> <description>`:
the version followed by a space and text (D37's parser recognizes
exactly that shape; a bare `## 1.0.0` heading is not a section, and the
gate reports the version as missing). A
repository without them sees a red gate naming the missing file: that is
correct fail-loud (rule 5), the premise of the type — move the file or
drop the preset, never silence the gate.

## Apply

```sh
gov preset show docs-bilingual     # read-only: exactly what lands
gov preset apply docs-bilingual    # into an initialized project
gov init --preset docs-bilingual   # one command for a new project
```

Apply is idempotent: on an already-adopted repository every item reports
"already adopted" and nothing is written.
