# Earnings RAG Chat System

Spec-driven implementation plan for the Earnings Report RAG Chat System, generated from `PRD.md` and `system-design.md`. This folder is the source of truth for implementation — each phase file is self-contained and independently testable.

## Contents

- **`overview.md`** — goal, scope, non-goals, and a one-line summary of each phase.
- **`implementation-order.md`** — the phase dependency order and why it's ordered
  that way (including where Phases 3 and 4 can run in parallel). Read this before
  starting implementation.
- **`phase1-ingestion-pipeline.md`** … **`phase5-chat-ui.md`** — one file per
  phase, in implementation order. Each contains the phase's objective, what
  "independently testable" means for it, and its vertical-slice tasks with
  acceptance criteria.

## How to use this folder

1. Read `overview.md` for context, then `implementation-order.md` for the
   sequence.
2. Open `phase1-ingestion-pipeline.md` and implement its tasks in the order
   listed.
3. Verify the phase against its "Independently testable when" section before
   moving on.
4. Repeat for each subsequent phase file, in order (Phases 3 and 4 may be
   done in either order, or in parallel — see `implementation-order.md`).
   Do not skip ahead — later phases assume earlier phases are done and
   verified.

## Provenance

- PRD: `PRD.md`
- System design: `system-design.md` (backed by `decision-log.md` and `docs/adr/ADR-001` through `ADR-008`)
- Generated: 2026-09-17
