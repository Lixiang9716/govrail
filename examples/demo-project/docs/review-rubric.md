# Review rubric

English | [中文](review-rubric.zh.md)

Reviews grade against this rubric, item by item, with evidence.

### R1 — Non-trivial changes carry an honest note

- **Checks:** behavior-bearing diffs carry a note with real alternatives.
- **Evidence:** the note's Alternatives lost for stated reasons.
- **Anti-pattern:** a note that records what was done but not what it beat.
- **Gate candidate:** no — presence is gated (`gov note presence`).

### R2 — A new or changed gate proves it can reject

- **Checks:** new gates have a rejection case in `gov self-test`.
- **Evidence:** a case that introduces the violation, asserts red, restores.
- **Anti-pattern:** a gate that has only ever passed.
- **Gate candidate:** no — caught in review.
