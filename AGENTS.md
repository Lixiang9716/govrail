# AGENTS.md — standing orders

<!-- gov:rules --> Read .gov/rules.md and follow it before starting work. Start from the `govrail` skill — it routes every command to the right moment (and names the moves that are never OK).

This repository **is** the governance plane (govrail): it ships the
gates, notes, and rules that `gov init` injects into other projects. The locked
design decisions are in [docs/decisions.md](docs/decisions.md); the machinery is
described in [docs/architecture.md](docs/architecture.md).

Run `gov self-test` to prove every governance gate can reject, and
`gov run --mode all` for the full gate DAG.
