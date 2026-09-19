# preset: python-lib

For Python package repositories: a library or application packaged with a
`pyproject.toml`, where "it works" means the test suite passes and the
distribution still builds. Applying lands two gates through the plane's
existing adoption machinery, additively and never overwriting local state:
`pytest` (`python -m pytest -q`) and `build` (`python -m build`), both
scoped to `**/*.py` + `pyproject.toml`; `pytest` also joins the `quick`
mode, both join `all` — an existing local mode gains the declared ids it
lacks, its order untouched (D39's append, converged: membership lands
even when the gates arrived in an earlier round). Prerequisites: an
initialized project (`gov init`)
whose environment has `pytest` and the `build` package installed
(`pip install build`); a red `build` gate with the package missing is
correct fail-loud, not a preset defect.

## Apply

```sh
gov preset show python-lib         # read-only: exactly what lands
gov preset apply python-lib        # into an initialized project
gov init --preset python-lib       # one command for a new project
```

Applying also lands `.gov/note-presence.json` with
`require: ["**/*.py"]` (#310): the note-presence gate switches from
"any note in the diff" to strict attribution — every changed Python
file must be named by an implemented note. Delete the file to go back
to the advisory default; an existing file is never overwritten.

Apply is idempotent: on an already-adopted repository every item reports
"already adopted" and nothing is written.
