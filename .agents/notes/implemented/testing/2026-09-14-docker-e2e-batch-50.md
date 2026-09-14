# Agent Note: docker e2e batch 50 — the memory plane decodes BOMs away instead of failing titles

Status: implemented

Related: the docker matrix + batches 1-49 notes (same series), #172's
class (text authored on one OS read on another), D5 (the note
contract the BOM used to trip)

## Problem

A Windows editor saving a note adds a UTF-8 BOM; the file's first
line is then `\ufeff# Agent Note: …`, and verify-notes failed it with
"missing title heading (first line must start with '# ')" — a
violation whose cause is INVISIBLE in any editor (the BOM does not
render). The same BOM silenced the decisions loader's first D-row and
recall's title parse. The bytes are a legal UTF-8 encoding artifact,
not content; failing the note contract on them is a false red
exactly where cross-OS teams live.

## Decision

The memory plane's text readers — verify_notes, recall, audit_notes,
decisions (source, dir files, and the json config), decision drafts —
decode with `utf-8-sig`: a leading BOM is stripped by the decoder,
BOM-less files are byte-identical to before. One unit test pins a
BOM-prefixed note passing verify-notes; the e2e scenario pins the
whole plane — a BOM+CRLF note passes verify-notes AND its title is
recallable ("matched in title"), and a BOM'd decisions.md yields a
verified D-row with `decision next` allocating D2 past it.

## Alternatives considered

- **Name the BOM in the failure instead of tolerating it** — the
  author cannot see or easily remove an invisible byte from a
  specific editor's save path; decoding is not semantics, and
  utf-8-sig is the standard library's own answer.
- **Strip BOMs at write time too** — the plane does not rewrite
  adopter prose; the read-side decode is the whole contract.

## Verification

Host: memory_plane_bom PASS; pytest 481 passed / 2 skipped (one
new), self-test 62 all pass, `gov run --mode all` 10 gates pass.
Docker: all eight inner-suite cells at 95/95, cross×3 PASS.
