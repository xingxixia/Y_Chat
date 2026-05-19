# Unified Multimodal Memory Architecture

This document is the source of truth for `test atri`'s memory design.

The memory system uses one continuous multimodal memory architecture. Text,
vision, audio, events, pet state, and project context all enter the same memory
system. Scene, source, and modality are metadata, weights, and retrieval hints;
they are not isolation boundaries.

The detailed event-to-reasoning chain, model output schema, permission-gated
actions, and reasoning audit rules are documented in
`REASONING_ARCHITECTURE.md`.

## Summary

The memory system follows the principle of unified memory. It must not split
memory by scene or mode in a way that causes the pet to forget recent context
when the UI, task, modality, or state changes.

The system is always in reasoning mode. There is no path where the AI directly
responds without thinking. Every input, observation, event, and state change
passes through:

```text
build context -> reason -> form conclusions -> act/reply -> write short-term memory -> consolidate in background
```

The difference is reasoning depth, not whether reasoning happens. Reasoning
depth is selected automatically.

The first implementation goal is not perfect multimodal recognition. The goal
is to build the memory operating system correctly: short-term continuity,
long-term consolidation, deep knowledge, entity identity, visual/audio abstract
features, raw backup, automatic writing, undo/review, background consolidation,
and audit.

## Core Rules

### Do Not Split Memory By Scene

- There must not be isolated "chat memory", "vision memory", or "project
  memory" that makes the system forget when the scene changes.
- Normal conversation, state changes, window changes, task changes, and modality
  changes must keep recent memory, core long-term memory, and relevant entity
  memory continuously available.
- Scene only changes retrieval weight. Examples: `source=screen`,
  `source=voice`, `source=chat`, `source=project`.

### Deep Knowledge Uses A Slow Path

- Ordinary replies must not scan the whole deep knowledge store every time.
- Deep knowledge is maintained through background consolidation: summaries,
  indexes, and stable long-term structures.
- Deep retrieval is used only when the answer needs historical material, project
  detail, explicit memory lookup, or complex reasoning beyond the hot memory
  set.

### Always Reason

- Every event enters a reasoning loop.
- There is no non-reasoning mode.
- Reasoning depth is automatic:
  - lightweight: ordinary continuity and simple replies
  - standard: tasks, decisions, memory writes, and event interpretation
  - deep: consolidation, conflicts, long-range planning, and deep retrieval

### Reasoning Trace Is Low Weight And Short-Lived

- The reasoning process exists to produce conclusions.
- Full reasoning trace is temporary, low-weight scratch data.
- Default scratch TTL: 5 minutes.
- The full trace is summarized and deleted quickly.
- Do not store the full reasoning stream as long-term memory.
- Only conclusions, state changes, stable facts, preferences, entity relations,
  and reusable task state may enter short-term or long-term memory.

### Automatic Writing Must Be Undoable

- Ordinary operation automatically writes conclusions to short-term memory.
- Long-term writes, entity confirmations, conflict merges, and important
  consolidations may auto-write when they meet the high-confidence thresholds
  defined in `REASONING_ARCHITECTURE.md`.
- Writes below threshold, ambiguous writes, and failed/conflicting
  consolidations enter the review/undo queue.
- The user does not need to confirm every write before it happens.
- Debug Memory must make automatic memory visible, undoable, deletable,
  mergeable, and down-rankable.

## Memory Layers

### Reasoning Scratch

Temporary storage for the current reasoning process.

Contents:

- current reasoning trace
- candidate conclusions
- temporary assumptions
- candidate memory writes
- candidate actions

Rules:

- TTL defaults to 5 minutes.
- Used only to produce conclusions and memory candidates.
- Deleted after summarization or expiry.
- Not used as a long-term source of truth.

### Working Memory

The hot working set for the current interaction.

Contents:

- current conversation
- current task
- current pet state
- recent events
- current command
- recent relevant entity observations

Rules:

- Always high-priority.
- Size is not fixed by time alone.
- Kept according to context-window budget and number of active conclusions.
- Stores what is still needed, not every raw process detail.

### Short-Term Memory

Recent conclusions that need continuity across scenes and state changes.

Contents:

- recent user requirements
- recent decisions
- current task progress
- current project state
- recent entity state
- recent observed facts

Rules:

- Automatically receives conclusions after each conversation, event, or
  observation.
- Cross-scene and cross-modality.
- Not cut by fixed "hours/days" alone.
- Retention heat depends on context budget, importance, repetition, active task,
  and entity relevance.
- Consolidation starts when the user rests, leaves for a long time, context
  pressure rises, a fixed interval triggers, or the system is idle.

### Long-Term Core Memory

Stable, frequently useful memory.

Contents:

- explicit user preferences
- project design principles
- long-term behavior constraints
- permission boundaries
- stable identity relationships
- repeatedly used instructions

Rules:

- A summary is available to ordinary reasoning.
- It should stay compact.
- It should be editable and auditable.

### Deep Knowledge Memory

Large or detailed knowledge that should not be loaded every turn.

Contents:

- project history
- large documents
- historical logs
- complex experiences
- detailed technical facts
- long-term knowledge indexes

Rules:

- Not loaded into ordinary replies by default.
- Maintained through background summaries and indexes.
- Used by explicit lookup, project/history questions, complex reasoning, or
  consolidation jobs.

### Entity Identity Memory

Stable identity layer for "same person", "same object", "same sound source",
"same project", "same file", "same device", "same place", or "same window".

Rules:

- Entities are not isolated scene memory.
- Entities have short-term and long-term lifecycle state.
- A new observation starts as temporary.
- Similar repeated observations become candidate entities.
- User confirmation or high-confidence clustering can promote an entity to
  long-term.
- Relevant current entities are hot memory; irrelevant entities stay cold until
  retrieved.
- Visual and audio identity cannot rely on text descriptions.

Lifecycle:

- `temporary`: one or a few observations, not stable
- `candidate`: repeated similarity or initial match
- `confirmed`: user-confirmed or high-confidence stable identity
- `archived`: hidden or no longer active

### Raw Backup

Original materials used for review, debugging, and re-extraction.

Contents:

- full conversation logs
- screenshots
- image crops
- audio clips
- misc source material

Rules:

- Raw backup is not the main memory body.
- It exists for review, correction, and re-extracting features.
- It uses rolling retention.
- Default max size: 20 GB.
- Default max age: 30 days.
- If either size or age limit is exceeded, old backup material is cleaned.

Directories:

```text
runtime/memory_blobs/text/
runtime/memory_blobs/vision/
runtime/memory_blobs/audio/
runtime/memory_blobs/misc/
```

### Audit And Review

Every automatic memory mutation must be traceable.

Contents:

- source event
- source modality
- reasoning summary
- write reason
- confidence
- importance
- before/after data
- undo state

Rules:

- Automatic writes are allowed.
- Important long-term writes and entity changes must be undoable. High-
  confidence writes may happen automatically, but they still need audit and
  rollback support.
- Deletion is soft-delete first; audit remains.

## Modality Rules

### Text

Text memory may include:

- raw conversation backup
- semantic embedding
- extracted conclusions
- facts
- preferences
- task state
- project decisions

Rules:

- Normal text enters short-term conclusions first.
- Stable facts and preferences may consolidate into long-term core.
- Large text material belongs in deep knowledge.

### Vision

Vision memory must not degrade into text-only description.

Vision memory must store non-text abstract features such as:

- image embedding
- perceptual hash
- local features
- color features
- shape features
- texture features
- object-region features
- observation cluster metadata

Rules:

- Text description is only auxiliary explanation.
- It is not the visual identity body.
- Screenshots and crops belong to raw backup.
- Visual entities are built through repeated observation clustering and
  confirmation.

Concrete first storage plan:

- Full screenshots are raw backup files under
  `runtime/memory_blobs/vision/screenshots/`.
- Object/person/window crops are raw backup files under
  `runtime/memory_blobs/vision/crops/`.
- Each visual observation stores source, screenshot path, optional crop path,
  bounding box, timestamp, source event, visible context, and pet state.
- Feature records store references to abstract visual features such as
  embedding refs, perceptual hashes, color histograms, shape signatures, local
  feature summaries, and texture summaries.
- Entity records store stable object/person/window identity candidates and
  visual prototypes built from repeated observations.
- The prompt-facing context uses summaries, confidence, recent observations,
  and feature references. It does not place high-dimensional raw vectors in the
  prompt.

### Audio

Audio memory must not degrade into transcript-only text.

Audio memory must store non-text abstract features such as:

- audio embedding
- voiceprint/timbre features
- pitch/rhythm/spectrum summaries
- sound-source clustering metadata

Rules:

- Transcript is auxiliary.
- Raw audio clips belong to raw backup.
- Sound sources may become entities.

Concrete first storage plan:

- Raw clips are backup files under `runtime/memory_blobs/audio/clips/`.
- Each audio observation stores source, clip path, timestamp, duration,
  transcript if available, source event, and current context.
- Feature records store references to audio embeddings, voiceprint/timbre
  features, pitch/rhythm/spectrum summaries, and sound-source cluster metadata.
- Entity records may represent a person voice, recurring device sound, software
  sound, room/environment sound, or other stable sound source.
- The transcript is useful for content memory, but it is not the identity body.

### State And Events

Events are evidence, not automatically long-term truth.

Rules:

- `runtime/events.jsonl` is event history, not the long-term memory store.
- Background consolidation extracts conclusions from events.
- Pet state, commands, errors, permissions, and project events can all become
  observations.

### Project And Files

Project memory must remain permission-gated.

Rules:

- Do not read file contents by default.
- Read only authorized roots.
- Current project task state belongs in working/short-term memory.
- Large project knowledge belongs in deep knowledge memory.

## Reasoning Loop

Every input and event follows this pipeline:

1. Receive event.
2. Build context:
   - working memory
   - recent short-term memory
   - compact long-term core summary
   - relevant current entities
   - no default deep knowledge scan
3. Reason with automatic depth selection.
4. Produce conclusions, replies, action candidates, and memory candidates.
5. Act or reply through the event system.
6. Write conclusions to short-term memory.
7. Auto-write high-confidence memory candidates; queue lower-confidence,
   ambiguous, or failed candidates for review.
8. Consolidate in the background when triggered.

The full orchestrator, provider interface, JSON schema, action permission rules,
and failure-recovery policy are defined in `REASONING_ARCHITECTURE.md`.

## Consolidation Policy

Triggers:

- user says they will rest, leave, sleep, shower, shut down, or continue later
- long inactivity
- fixed interval
- system idle
- short-term memory exceeds count or size thresholds
- context budget approaches limit

Actions:

- summarize short-term memory
- merge duplicates
- promote important conclusions to long-term core
- move detailed material into deep knowledge
- update entity state
- down-rank stale or low-confidence memory
- mark conflicts instead of overwriting silently
- clean expired reasoning scratch
- clean raw backup over retention limits
- write audit entries

## Storage Design

Main database:

```text
runtime/test_atri.sqlite3
```

Future tables:

- `memory_records`: generic memory records
- `memory_observations`: individual text/vision/audio/event observations
- `memory_entities`: stable entities
- `memory_features`: multimodal abstract features
- `memory_links`: relationships between memories/entities
- `memory_review_queue`: undo/review queue
- `memory_audit_log`: mutation audit log
- `raw_backups`: raw material index

Existing manual memory notes remain a temporary debug surface. They should later
migrate to `memory_records` with `kind=manual_note`.

## API Plan

Future endpoints:

```text
GET /memory/status
GET /memory/records
GET /memory/entities
GET /memory/entities/{id}
GET /memory/review
POST /memory/observe
POST /memory/consolidate
POST /memory/review/{id}/undo
POST /memory/entities/{id}/merge
DELETE /memory/records/{id}
```

Existing compatibility endpoints remain until migration:

```text
GET /memory
POST /memory
DELETE /memory/{item_id}
```

## Event Plan

Future memory events:

- `memory.observation.created`
- `memory.scratch.created`
- `memory.scratch.summarized`
- `memory.record.created`
- `memory.record.updated`
- `memory.record.deleted`
- `memory.entity.created`
- `memory.entity.matched`
- `memory.entity.merged`
- `memory.review.queued`
- `memory.consolidation.started`
- `memory.consolidation.completed`
- `memory.backup.created`
- `memory.error`

## Config Plan

Future config shape:

```yaml
memory:
  enabled: true
  auto_write_short_term: true
  reasoning:
    always_on: true
    depth: auto
    scratch_ttl_minutes: 5
  consolidation:
    enabled: true
    idle_enabled: true
    interval_minutes: 30
    trigger_on_context_pressure: true
    trigger_on_user_rest: true
  backup:
    enabled: true
    max_bytes: 21474836480
    max_days: 30
  retrieval:
    always_include_recent: true
    always_include_core: true
    always_include_relevant_entities: true
    deep_knowledge_default: false

permissions:
  memory.write: true
  memory.auto_write: true
  memory.raw_backup: true
  memory.consolidate: true
```

Vision and audio capture remain controlled by their own permissions, such as
`screen.observe` and `voice.listen`.

## Debug UI Plan

Debug Memory should become a fixed-height large panel with tabs, not a long page
that grows forever.

Future tabs:

- Overview
- Working
- Short-Term
- Core Long-Term
- Deep Knowledge
- Entities
- Features
- Review Queue
- Raw Backups
- Audit
- Consolidation

Required controls:

- search
- fold/collapse
- delete
- undo
- merge
- down-rank
- trigger consolidation
- inspect audit

## Implementation Order

1. Keep this architecture document as the design source of truth.
2. Update memory docs and status references.
3. Keep current manual note implementation unchanged until the schema migration
   begins.
4. Add schema migration for the future memory tables.
5. Migrate manual notes to `memory_records(kind=manual_note)`.
6. Implement short-term automatic writes from existing event/command flow.
7. Implement reasoning scratch with 5-minute TTL.
8. Implement review queue and undo.
9. Implement consolidation entry points.
10. Implement Debug Memory tabs.
11. Add vision features as abstract features, not text-only descriptions.
12. Add audio features as abstract features, not transcript-only descriptions.
13. Decide the concrete local/API embedding engines later.

## Current Status

The architecture is accepted as the memory direction. Implementation is still
pending. The always-on reasoning chain and full reasoning implementation route
are now documented in `REASONING_ARCHITECTURE.md`; memory integration should
follow that document for run ids, write candidates, permissions, schema repair,
and audit. Visual-system details, voice-system details, and embedding/vector
retrieval remain separate follow-up design topics.
