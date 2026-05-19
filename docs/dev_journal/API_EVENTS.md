# API and Events

## Backend HTTP

Initial endpoint:

```text
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "app": "test_atri"
}
```

Internal event endpoint:

```text
POST /events/internal
```

Request body is one event envelope. Response body:

```json
{
  "events": []
}
```

Current thin-slice behavior: `user.command.submitted` routes through Reasoning
R1's deterministic fallback executor. The backend emits reasoning trace events,
state events, and a safe fallback `pet.bubble.show` response. Real model calls,
formal long-term memory writes, and action execution remain disabled.

Model provider status endpoint:

```text
GET /model/provider/status
```

Returns whether the configured model provider is enabled, configured, and which
provider/model names are selected. This endpoint does not call a model.

Future model provider config endpoints:

```text
GET /model/provider/config
POST /model/provider/config
POST /model/provider/enable
```

Rules:

- `GET /model/provider/config` returns provider names, selected provider,
  enabled flags, model names, base URLs, and masked key state only.
- API keys must never be returned in clear text.
- `POST /model/provider/config` may update provider selection, model/base URL,
  and API key values after secondary confirmation.
- `POST /model/provider/enable` may change `llm.enabled` and
  `permissions.model.call` after secondary confirmation.
- Provider config writes must create audit records.
- Debug may switch provider and input keys, but real model calls remain disabled
  until both config and permission gates are enabled.
- DeepSeek is the first real provider route. OpenAI-compatible is an
  interface/config/status placeholder until a later provider stage.
- API keys are stored locally in `runtime/config.yaml`, shown masked in Debug,
  and must not be written in clear text to logs, Debug responses, or audit.

Permission status endpoint:

```text
GET /permissions/status
```

Returns configured permissions and enabled/disabled lists. This endpoint is
read-only and must not toggle capabilities.

Log status endpoint:

```text
GET /logs/status
```

Returns log file names, byte sizes, and short tail excerpts from `runtime/logs`.
This endpoint is read-only and must not clear or write logs.
Each log entry includes `kind: "error"` for `.err.log` files and
`kind: "output"` for ordinary output logs.
Before API key input or real provider calls are enabled, displayed log tails
must redact API keys, authorization headers, bearer tokens, and similar secrets.
Current implementation redacts common assignment and header forms such as
`api_key=...`, `x-api-key: ...`, `token=...`, `secret=...`, `password=...`,
`Authorization: ...`, and `Bearer ...`.
Displayed tails also remove UTF-8 BOM markers, ANSI color escape sequences, and
common UTF-8 mojibake from local tool output. This cleanup is display-only; raw
log files remain unchanged on disk.

Memory endpoints:

```text
GET /memory
POST /memory
DELETE /memory/{item_id}
```

`GET /memory` returns the enabled flag and recent items. `POST /memory` creates
a manual memory item only when `permissions.memory.write` is enabled.
`DELETE /memory/{item_id}` removes an item. Automatic memory writes are not
connected yet.

Future unified memory endpoints are defined by `MEMORY_ARCHITECTURE.md`:

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

The existing manual note endpoints stay as compatibility/debug endpoints until
manual notes migrate to `memory_records(kind=manual_note)`.

Project reader endpoints:

```text
GET /project-reader/status
GET /project-reader/files
```

`GET /project-reader/status` reports whether project reading is enabled, which
roots are authorized, and which text extensions may be read later.
`GET /project-reader/files` lists only the top level of an authorized root and
is blocked unless `permissions.project.read` is enabled.

Reasoning endpoints:

```text
GET /reasoning/status
GET /reasoning/runs
GET /reasoning/runs/{run_id}
```

Rules:

- `GET /reasoning/status` reports whether reasoning is enabled, current run
  state, queue counts, provider availability, and last failure summary.
- `GET /reasoning/runs` returns recent reasoning run summaries for Debug.
- `GET /reasoning/runs/{run_id}` returns one run with steps, provider status,
  schema validation, action proposals, pending actions, memory candidates,
  audit summaries, and failure information.
- These endpoints are read-only.
- Full sensitive action parameters and API keys must not be exposed through
  normal Debug responses unless a future explicit sensitive-audit view is
  added.
- `POST /events/internal` should later route `user.command.submitted` and other
  reasoning-capable events through the Reasoning Orchestrator instead of
  returning the current placeholder bubble sequence directly.

Current Reasoning R1 implementation:

- `GET /reasoning/status`, `GET /reasoning/runs`, and
  `GET /reasoning/runs/{run_id}` exist as read-only Debug endpoints.
- `user.command.submitted` creates a deterministic fallback run with provider
  `deterministic_fallback`.
- R1 builds a `reasoning.v1` output object, validates its required structure,
  records schema-validation state, and stores non-accepted memory write
  candidates for inspection.
- Successful R1 memory candidates create `memory_write_audit` records with
  status `candidate_recorded`. These audit rows explain candidate creation only;
  they do not mean the candidate has been accepted into formal memory.
- R1 action proposals are policy-checked and stored as audit rows. Unauthorized
  or confirmation-required actions create `pending_actions` rows and emit
  `action.proposed` / `action.pending_authorization` events, but R1 never emits
  `action.executed` and never runs the action.
- If R1 schema validation fails, the run is marked `schema_failed`,
  `reasoning.schema.invalid` and `reasoning.failed` are emitted, schema errors
  are available from `GET /reasoning/runs/{run_id}`, and no memory candidates
  are written.
- R1 does not call real models, write formal long-term memory, or execute
  broader actions.

## Internal WebSocket

Initial endpoint:

```text
WS /ws/internal
```

Used for frontend/backend internal communication. External WebSocket adapters
are separate future capability and must default off.

## Event Envelope

All events use this envelope:

```json
{
  "event_id": "uuid",
  "type": "pet.state.changed",
  "source": "backend",
  "timestamp": "2026-05-18T00:00:00Z",
  "correlation_id": "uuid-or-null",
  "payload": {}
}
```

Required fields:

- `event_id`
- `type`
- `source`
- `timestamp`
- `payload`

Optional field:

- `correlation_id`

## Initial Events

- `system.hello`
- `system.health`
- `pet.state.changed`
- `pet.bubble.show`
- `pet.bubble.clear`
- `pet.model.clicked`
- `user.command.submitted`
- `debug.log`
- `error.reported`
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

Memory events above are planned events for the unified memory architecture and
are not fully implemented yet.

## Reasoning Events

Reasoning events are defined by `REASONING_ARCHITECTURE.md`. They are the
stable first reasoning event contract for the Reasoning Orchestrator, although
the current code may still be on the earlier placeholder event path until
Reasoning R1 is implemented.

Initial planned event names:

- `reasoning.started`
- `reasoning.step.completed`
- `reasoning.output.produced`
- `reasoning.schema.invalid`
- `reasoning.repair.requested`
- `reasoning.failed`
- `reasoning.cancelled`
- `action.proposed`
- `action.pending_authorization`
- `action.executed`
- `action.failed`
- `action.audit.logged`

Extended diagnostic event names may also be used later when the Debug UI needs
more granularity, but the list above is the stable first contract.

## Local Event History

Electron keeps a diagnostic local history of internal events in:

```text
runtime/events.jsonl
```

Rules:

- The file is JSON Lines, one event summary per line.
- It is runtime data and is ignored by source control.
- It is for local debugging/history only, not an external adapter.
- Electron loads the latest 80 events into the Debug Window buffer on startup.
- Electron trims the file to the latest 500 events.
- A local `system.hello` event is written when Electron starts, which makes a
  fresh app session visible in Debug History.

## Bubble Event Rule

The bubble overlay is an output renderer inside the pet window. It should only
show, update, or clear text in response to event flow, especially:

- `pet.bubble.show`
- `pet.bubble.clear`

Clicking the pet model must not directly create a bubble. Pet clicks may become
their own input events later, but the bubble remains event-driven output.

`pet.model.clicked` is an input/interaction event. It may later drive state,
animation, or backend logic, but it must not directly bypass the event system to
show the bubble.

Long `pet.bubble.show` text is segmented by the renderer. `pet.bubble.clear`
must interrupt the current typewriter run and cancel pending segment advances.

## State Event Rule

`pet.state.changed` carries:

```json
{
  "state": "idle",
  "previous_state": "thinking"
}
```

Current implemented states:

- `idle`
- `thinking`
- `talking`

The backend is the source of state changes for command/reply flow. Electron may
emit local recovery state such as returning to `idle` when the bubble is cleared.

## Command Input Rule

The command box is the input renderer. `Ctrl+Space` opens the command input
surface. Submitting text creates a `user.command.submitted` event and sends it
to the backend internal event endpoint. Placeholder responses may emit
`pet.bubble.show` until the AI pipeline exists.

Current command UX contract:

- The command window waits for the Electron IPC submit result before clearing
  the draft.
- Successful submit returns `{ "ok": true }`, clears the input, and hides the
  command window.
- Failed submit returns `{ "ok": false, "error": "..." }`; the command window
  keeps the user's draft and shows an inline error state.
- Backend submit failures may also emit a local `pet.bubble.show` error event
  through the normal event renderer path. The command box still remains an
  input surface, not the output bubble.

## Reasoning Output JSON

Primary AI output must parse to schema-versioned JSON. The first schema is
`reasoning.v1`.

This replaces the old rough AI-output draft. The source of truth is
`REASONING_ARCHITECTURE.md`.

Top-level shape:

```json
{
  "schema_version": "reasoning.v1",
  "run_id": "uuid",
  "reply": {
    "should_reply": true,
    "text": "final user-facing reply",
    "bubble_text": "optional shorter bubble text",
    "style": "normal",
    "final": true
  },
  "state": {
    "pet_state": "talking",
    "emotion": "neutral",
    "animation": null
  },
  "actions": [],
  "memory": {
    "write_candidates": [],
    "do_not_write_reason": null,
    "needs_consolidation": false
  },
  "observations": [],
  "voice": {
    "speak": false,
    "text": null,
    "voice_style": null
  },
  "debug": {
    "depth": "standard",
    "needs_deep_retrieval": false,
    "deep_retrieval_query": null,
    "trace": []
  },
  "audit": {
    "safety_notes": [],
    "permission_requests": []
  }
}
```

### Reply

```json
{
  "should_reply": true,
  "text": "final user-facing reply",
  "bubble_text": "optional shorter bubble text",
  "style": "normal|soft|urgent|playful|error",
  "final": true
}
```

Rules:

- Do not show a normal reply bubble until the structured output is accepted.
- `bubble_text` may be shorter than the full reply.
- User-triggered tasks need some perceivable reply, pause, or failure feedback.
- Provider transport may stream later, but replies, actions, memory writes, and
  final state changes may only be accepted after a complete `reasoning.v1` JSON
  object passes schema validation.

### State

```json
{
  "pet_state": "idle|thinking|talking|reading|error|dragging|sleep|listening|observing|interrupted|speaking",
  "emotion": "neutral",
  "animation": null
}
```

Rules:

- State changes should still be emitted as `pet.state.changed`.
- The reasoning output proposes state; the backend/event layer emits the event.

### Run State

Reasoning runs are tracked by `run_id` and move through:

```text
created
-> context_built
-> provider_running
-> schema_validating
-> action_checking
-> memory_checking
-> completed
```

Terminal/failure states:

```text
provider_failed
schema_failed
action_failed
cancelled
```

All reasoning events and action/memory audit records should carry `run_id`.
Step records carry `step_id`. Actions carry `action_id`; memory candidates
carry `candidate_id`.

### Actions

```json
{
  "action_id": "uuid",
  "capability": "memory.write",
  "name": "create_memory_record",
  "params": {},
  "reason": "why this action is useful",
  "risk": "low|medium|high",
  "requires_confirmation": false,
  "retryable": false
}
```

Rules:

- Actions are proposals until the orchestrator checks capability and risk.
- The capability registry uses code-defined safe capabilities plus config
  switches.
- Unauthorized actions emit `action.pending_authorization` and ask the user
  through normal bubble/event flow.
- High-risk actions require secondary confirmation even if generally
  authorized.
- Failed actions emit `action.failed` and can be fed back as observations.
- Actions are deduped by `action_id` inside the same run.
- Failed actions are not retried unless `retryable: true` and the failure reason
  or execution condition changes.

### Memory

```json
{
  "write_candidates": [
    {
      "candidate_id": "uuid",
      "target_layer": "working|short_term|long_term_core|deep_knowledge|entity|review_queue",
      "kind": "fact|preference|task_state|project_decision|entity_observation|visual_feature_link|audio_feature_link|error",
      "content": {},
      "related_entity_id": null,
      "source_event_ids": [],
      "reason": "why this should be remembered",
      "confidence": 0.9,
      "importance": 0.7,
      "review_required": false
    }
  ],
  "do_not_write_reason": null,
  "needs_consolidation": false
}
```

Rules:

- Write candidates are not memory until the Memory Manager accepts them.
- User-interaction schema failure must not write memory from invalid output.
- High-confidence memory may auto-write according to thresholds documented in
  `REASONING_ARCHITECTURE.md`.
- Memory is not physically overwritten. New memory is appended as a version or
  evidence record; old memory may be down-ranked, expired, or marked
  `superseded`.
- Memory cannot directly change capability switches, hard personality config,
  or system prompts. It may only propose such changes as actions.

### Debug Trace

```json
{
  "depth": "lightweight|standard|deep",
  "needs_deep_retrieval": false,
  "deep_retrieval_query": null,
  "trace": [
    {
      "step_index": 1,
      "step_type": "context_check|decision|action_plan|memory_plan|reply_plan|repair",
      "input_refs": [],
      "reasoning_text": "structured reasoning summary",
      "decision": "what was decided",
      "outputs": []
    }
  ]
}
```

Rules:

- Debug trace is structured debug data, not normal UI content.
- SQLite stores full structured trace/action audit.
- `runtime/events.jsonl` stores compact summary events only.
- Action parameters are saved complete/raw in audit and are sensitive data.
- Default action-audit retention is 30 days.
- API keys and authorization tokens must not appear in normal Debug responses,
  logs, or clear-text audit.

### Failure Behavior

If JSON parsing or schema validation fails:

1. Attempt one schema repair.
2. If repair succeeds, continue with the repaired structured output.
3. If repair fails for a user interaction, do not write memory or execute
   actions from that output.
4. If a model is still available, generate a short character-appropriate
   failure line constrained to the correct meaning.
5. If the model itself is unavailable or unusable, use a plain system-level
   error.

Failure copy must not be a fixed robotic template pool. The system constrains
meaning: no fake success, no unsafe memory write, no unsafe action.
