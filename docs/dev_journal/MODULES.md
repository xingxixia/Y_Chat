# Modules

## Module Implementation Command

Use `NEXT_MODULE` as the module-by-module implementation command.

Rules:

- Choose one module from `STATUS.md`'s queue.
- Read that module's section and related event contracts before editing.
- Keep the slice thin and independently testable.
- Do not jump ahead to later modules or redesign visuals unless the selected
  module requires it.
- Run checks and update docs in the same work turn.

There are two different planning levels:

- The implementation queue in `STATUS.md` contains thin slices that can be done
  now.
- The discussed backlog contains broader ideas from the design conversation.
  Backlog items are not lost, but some require explicit user selection,
  permission gates, or unresolved design decisions before implementation.

## Frontend Shell

Electron desktop shell. Owns windows, transparency, shortcuts, and connection to
backend events.

Initial windows:

- Pet window
- Command window
- Settings/debug window

The shell keeps a short in-memory recent-event buffer and forwards current pet
state plus recent events to the debug window.

Discussed future shell work:

- Keep the pet, command input, and debug/settings surfaces separate.
- Add richer local history/debug inspection without turning the app into a
  normal chat window.
- Preserve transparent-window pass-through and normal-window-like dragging when
  future visuals become more complex.

## Pet Renderer

Canvas renderer for pixel pet. First version uses program-drawn pixel art.
Future target is layered pseudo-Live2D with fixed model canvas, part transforms,
hit areas, and hard pixel scaling.

Mouse hit testing should not use the full transparent window rectangle.
Transparent non-model pixels must pass clicks through to the desktop; only
visible model pixels or explicit future hit areas should receive interaction.
Visible model pixels should support click/drag interaction. A model click is an
input event and must not directly create output bubbles.

Drag movement should be calculated from an absolute cursor anchor in Electron
main process state, not by accumulating renderer mousemove deltas. This keeps
the cursor and model from drifting apart during long or repeated drags.

Discussed future renderer work:

- Preview 128, 256, and 384 model canvas sizes before choosing the final asset
  size.
- Generate or compare three visual mood concepts before committing to final pet
  assets.
- Move toward layered pseudo-Live2D behavior in Canvas, not a `.moc3` Live2D
  implementation.
- Add explicit future hit areas/parts while preserving pixel-visible hit
  behavior for transparent regions.

## Bubble System

Internal overlay rendered inside the pet window. Displays text with a typewriter
effect. Long text auto-segments into consecutive bubbles.

This is an output surface only. It is driven by events such as
`pet.bubble.show` and `pet.bubble.clear`.

The bubble is anchored to the visible model upper-left using pet-window local
coordinates. It must not be implemented as a separate Electron follower window,
because repeated off-screen dragging previously made the bubble drift farther
from the model.

The final pixel-style manga/comic bubble visual is not defined yet. The current
rectangular pixel frame is a placeholder and should not be treated as the user's
intended bubble design.

The current dialogue bubble is acceptable for now. Do not redesign it until the
user explicitly asks for another pass.

Current behavior slice:

- `pet.bubble.show` text is split into automatic segments for long output.
- Segments play in order with a short pause between them.
- The bubble page height is fixed; text must paginate instead of stretching the
  bubble downward.
- Current placeholder bubble only displays two text lines per segment.
- `pet.bubble.clear` interrupts typing and prevents old timers from writing
  stale text after clear.
- This does not define the final manga/comic bubble visual.

## Command Box

Invoked by `Ctrl+Space`. Sends user text events to the backend. First shell may
use a placeholder flow before AI is connected.

This is the input surface. It must remain separate from the bubble output
surface.

Discussed future command work:

- Improve input ergonomics, focus behavior, and submit/interrupt handling.
- Keep command input as an event source that emits `user.command.submitted`.
- Do not merge command input and output bubble into one chat-style panel.

Current UX slice:

- Command submission is awaitable from the command window.
- While submitting, the command input shows a sending state and prevents repeat
  submits.
- Successful submission clears the input and hides the command window.
- Failed submission keeps the user's text, shows an inline error state, and the
  Electron event path still reports the backend failure through the normal
  bubble/event system.
- A small clear button lets the user clear the draft without closing the command
  window.

## Backend API

FastAPI app. First version exposes:

- `GET /health`
- `WebSocket /ws/internal`

Current and near-future backend modules also include internal event posting,
model-provider status, permissions status, logs status, memory debug endpoints,
and project-reader status. These remain internal/local and capability-gated.

## Event Bus

Structured multimodal event flow. All major actions and outputs must be events.
Bubble display is a rendered response to events, not a direct side effect of
clicking the pet model.

Current thin slice:

- Electron records frontend-submitted, backend-returned, and local internal
  events into a recent-event buffer.
- Debug window can inspect the recent event buffer.
- Electron persists local internal event history to `runtime/events.jsonl` as
  JSON Lines diagnostic data.
- Electron reloads the most recent persisted events on startup so Debug History
  survives app restarts.
- The in-memory Debug buffer remains capped at 80 events; the persisted
  diagnostic file is trimmed to the latest 500 events.
- Electron emits a local `system.hello` event on startup so a fresh session is
  visible in History even before the user submits a command.
- Debug History can inspect event-history file status through read-only
  Electron IPC: path, byte size, persisted line count, configured limits, loaded
  event count, and recent event types.

Discussed future event work:

- Persist useful local event history beyond the in-memory buffer.
- Use events for text, state, memory writes, voice, screen, external software,
  VR, errors, and future action proposals.
- Keep bubble display event-driven rather than click-driven.
- Keep a structured JSON AI output path with one schema repair attempt and safe
  degradation when output cannot be trusted.

## Reasoning Orchestrator

Future module. Owns the always-on reasoning chain described in
`REASONING_ARCHITECTURE.md`.

This module is not "the model call." It is the coordinator that turns events
into context, provider calls, validated structured output, permitted actions,
memory write candidates, UI events, and audit records.

Accepted architecture:

- Every user input, model click, visual observation, voice input, project event,
  system event, action result, and memory event enters the reasoning loop.
- There is no non-reasoning path. Depth changes between lightweight, standard,
  and deep.
- Context is entity-first, then falls back to layered memory summaries when no
  related entity exists.
- Context budget is system-owned and must preserve the current event, current
  task, compact core long-term memory, and directly related entities.
- Provider access goes through one interface:
  `generate_reasoning(request) -> response`.
- The provider generates structured output. The orchestrator validates,
  repairs, executes, writes, and audits.
- Output schema starts at `reasoning.v1`.
- Deep mode enters the deep-retrieval path automatically, while lightweight and
  standard turns do not scan deep knowledge by default.
- Model unavailable fallback is a deterministic rule reasoning shell. It must
  not pretend real model reasoning happened.
- The orchestrator uses a single-foreground queue: one foreground run at a time,
  user input can soft-cancel the current foreground run, and background work
  queues or coalesces.
- Runs follow the documented state machine from `created` through `completed`,
  with terminal failures such as `provider_failed`, `schema_failed`,
  `action_failed`, and `cancelled`.
- Action proposals use `capability + name + params + reason + risk`.
- Actions are deduped by `action_id`; failed actions do not retry unless
  explicitly `retryable` and the failure condition changes.
- Unauthorized actions create pending authorization and ask the user through
  normal bubble/event flow.
- High-risk actions require secondary confirmation even if generally enabled.
  Pending reminders are capped by risk: low 3, medium 2, high 1.
- Action failures are fed back as observations for possible second reasoning.
- Trace/action audit is stored in SQLite; compact event summaries go to
  `runtime/events.jsonl`.
- Memory write policy is high-confidence automatic, versioned, and
  non-destructive: new evidence is appended, and old records may be
  down-ranked, expired, or marked `superseded`.
- Memory may propose hard config/persona/permission changes, but it must not
  directly change real capability switches, hard persona config, or system
  prompts.

Planned Debug UI:

- Reasoning run list
- selected depth and step count
- context summary
- provider status and schema validation status
- structured trace
- action proposals and pending authorizations
- memory write candidates
- audit records and schema failures

Current R1 backend slice:

- Added SQLite-backed reasoning run and step trace tables.
- Added read-only endpoints: `GET /reasoning/status`, `GET /reasoning/runs`,
  and `GET /reasoning/runs/{run_id}`.
- Routed `user.command.submitted` through a deterministic fallback executor
  instead of the older direct placeholder bubble path.
- Emits `reasoning.started`, `reasoning.step.completed`, and
  `reasoning.output.produced` before the normal state and bubble events.
- R1 now builds a `reasoning_request.v1` context packet and calls a
  provider-neutral `generate_reasoning(request)` interface. The only current
  implementation is still the deterministic fallback route; no real model is
  called.
- Deterministic fallback now returns a `reasoning.v1` output object, validates
  the required structure, records schema-validation state, and only then emits
  accepted reply/memory-candidate events.
- R1 has one structural schema-repair attempt. It may fill missing required
  containers such as `actions: []` or `memory.write_candidates: []`, but it must
  not invent facts, actions, or memory candidates.
- Schema validation failures are stored in `reasoning_schema_failures`, exposed
  in run detail, and shown in Debug. Failed schema output does not emit a normal
  reply and does not create memory write candidates.
- Records memory write candidates for Debug inspection only; they are not
  accepted as formal memory records.
- Records a `memory_write_audit` entry when an R1 memory candidate is produced,
  so Debug can show why a candidate exists without treating it as accepted
  memory.
- Records action proposals and pending-authorization rows for R1 structured
  outputs that contain actions. R1 emits `action.proposed` and
  `action.pending_authorization` events when appropriate, but it does not
  execute actions or treat pending actions as consent.
- Real model calls, action execution, and automatic memory acceptance are still
  future slices.

Accepted full implementation route:

- Reasoning R1: deterministic fallback executor, SQLite reasoning tables, and
  Debug Reasoning skeleton.
- Reasoning R2: provider config management plus DeepSeek real calls.
- Reasoning R3: automatic memory writes from `memory.write_candidates`.
- Reasoning R4: SQLite memory/entity/recent-event deep retrieval.
- Reasoning R5: action execution under capability policy and secondary confirmation
  for high-risk actions.

The first implementation must prioritize Debug traceability and safety before
polishing natural reply quality.

Still separate follow-up plans:

- Visual capture/observation flow.
- Voice capture/ASR/TTS flow.
- OpenAI-compatible real provider calls.
- Vector/embedding retrieval.

## State Manager

Owns semantic pet state such as `idle`, `thinking`, `talking`, `reading`,
`error`, `dragging`, and `sleep`.

Current thin slice:

- Backend emits `pet.state.changed` events for command flow:
  `thinking` before placeholder response, then `talking` after bubble response.
- Electron forwards state events to the pet window.
- Pet renderer shows a small state badge and adjusts placeholder animation
  slightly for `thinking` and `talking`.
- Clearing the bubble returns the pet to `idle`.

Discussed future state work:

- Add safe visible feedback for `reading`, `error`, `dragging`, `sleep`, and
  later `listening`, `observing`, `interrupted`, and `speaking`.
- States should drive animation, interruption, bubbles, and future voice/screen
  flows.
- Do not add pet-sim systems such as hunger, feeding, shop, quests, levels,
  currency, or cleanliness.

## Debug Window

Shows backend health, current pet state, and recent event envelopes. It is a
developer surface for checking the event/state path before AI, memory, voice, or
external adapters are implemented.

Current thin slice:

- Shows backend health, pet state, recent events, configured permissions, and
  read-only status for Model Provider, Memory, and Project Reader.
- Sidebar buttons switch real debug pages instead of leaving every panel stacked
  on Overview.
- Includes a read-only refresh action for backend-derived status panels.
- Renderer IPC listeners return unsubscribe callbacks to avoid duplicate event
  handlers after React remounts.
- History page shows recent events as a compact timeline.
- Visual page shows current layout constants and notes that final bubble art is
  still unconfirmed.
- Logs page shows read-only log file sizes and tail excerpts from the backend,
  with error logs and ordinary output logs colored differently.
- Debug Logs receives backend-redacted log tails from `/logs/status`; it must
  not display raw API keys, authorization headers, bearer tokens, or similar
  secrets.
- `/logs/status` also cleans display-only log noise such as UTF-8 BOM, ANSI
  color escapes, and common UTF-8 mojibake before returning tails to Debug.
- Reasoning page shows read-only Reasoning R1 status, recent runs, selected run
  detail, steps, schema failures, memory candidates, action proposals, pending
  actions, and audit records from `/reasoning/*` endpoints.
- External, Voice, Screen, and VR/OSC pages show their current read-only
  capability permissions instead of blank placeholders.

Discussed future debug work:

- Add clearer event/history inspection and local audit views.
- Add permission/audit surfaces before sensitive capabilities are enabled.
- Keep reserved module pages honest: show disabled state and requirements
  instead of pretending capabilities are active.
- Extend Debug Reasoning beyond the current R1 read-only view when schema
  repair, action proposals, provider calls, and richer audit records exist.
- Add provider config controls for API key input, provider switching, and model
  enable/disable. These controls require secondary confirmation and provider
  config audit.
- API keys must be displayed only as masked values and must not appear in logs,
  Debug responses, or audit.
- Before API key input is enabled, Debug Logs and `/logs/status` must redact
  API keys, authorization headers, tokens, and similar secrets from displayed
  log tails.

## Memory Manager

Future module. Owns the unified multimodal memory system described in
`MEMORY_ARCHITECTURE.md`.

Accepted architecture:

- Memory is unified across text, vision, audio, events, state, and project
  context. Do not split memory by scene or mode.
- Scene, source, and modality are metadata and retrieval weights, not isolation
  boundaries.
- The system is always in reasoning mode. Reasoning depth changes, but there is
  no non-reasoning response path.
- Reasoning scratch is temporary low-weight data with a default 5-minute TTL.
- Conclusions are written automatically to short-term memory.
- Deep knowledge memory is used through background consolidation and explicit
  deep retrieval, not by scanning the whole knowledge store every turn.
- Entity identity memory handles same-person, same-object, same-sound-source,
  same-project, same-file, same-device, same-place, and same-window continuity.
- Visual memory must use non-text abstract features such as embeddings,
  perceptual hashes, local features, color, shape, and texture features.
- Audio memory must use non-text abstract features such as audio embeddings,
  timbre/voiceprint, pitch, rhythm, and spectrum summaries.
- Raw screenshots, crops, audio clips, and full logs are backup material with
  default rolling retention of 20 GB and 30 days.

Current thin slice:

- SQLite-backed `memory_items` table in `runtime/test_atri.sqlite3`.
- `GET /memory`, `POST /memory`, and `DELETE /memory/{item_id}`.
- Manual writes are gated by `permissions.memory.write`.
- Debug Memory page can add and delete manual memory notes.
- Automatic memory writes are not connected yet.

Planned layers:

- Reasoning Scratch
- Working Memory
- Short-Term Memory
- Long-Term Core Memory
- Deep Knowledge Memory
- Entity Identity Memory
- Raw Backup
- Audit and Review

Automatic memory route:

- Reasoning output `memory.write_candidates` writes to formal memory tables such
  as `memory_records`, not to the legacy manual `memory_items` table.
- The existing `memory_items` table remains a manual-note compatibility/debug
  surface until manual notes migrate to `memory_records(kind=manual_note)`.
- Automatic writes follow high-confidence thresholds and non-destructive
  version/evidence rules from `REASONING_ARCHITECTURE.md`.

Planned Debug UI:

- Fixed-height large Memory panel, not an infinitely growing page.
- Tabs for Overview, Working, Short-Term, Core Long-Term, Deep Knowledge,
  Entities, Features, Review Queue, Raw Backups, Audit, and Consolidation.
- Automatic writes must be visible, undoable, deletable, mergeable,
  down-rankable, and auditable.

Still separate follow-up plans:

- Visual-system capture/observation flow.
- Voice-system capture/ASR/TTS flow.
- Reasoning chain integration is accepted; Memory Manager should follow
  `memory.write_candidates`, permission, and audit rules from
  `REASONING_ARCHITECTURE.md`.

## Permission Manager

Future module. Owns capability-level permissions and audit logs.

Current thin slice:

- Added `GET /permissions/status`.
- Debug window shows all configured permissions as read-only `on` / `off`
  values.
- No permission toggle UI is implemented yet.

Discussed future permission work:

- Capability-level toggles.
- Audit logs for sensitive actions and permission changes.
- Backup/reset/change-log behavior for special editable boundaries.
- Default-off handling for model calls, project reads, microphone, screenshots,
  external adapters, LAN access, VR, and computer-control-like abilities.
- High-risk action execution requires both config permission and secondary
  confirmation, even if the capability switch is already enabled.
- Provider config writes, API key saves, provider switching, and model enable
  changes require secondary confirmation and audit.

## Model Provider

Future module. Owns provider configuration, DeepSeek real calls, and
OpenAI-compatible interface placeholders.

Current thin slice:

- Added provider config reader and status payload.
- Added `GET /model/provider/status`.
- Added read-only `GET /model/provider/config` with masked API-key state,
  provider names, active provider, model/base URL, stream flag, and enablement
  gates. It does not save config and does not call a model.
- No real model calls are implemented yet.
- Calls are gated by `llm.enabled` and `permissions.model.call`, both off by
  default.
- `/logs/status` now redacts common secret patterns before Debug provider config
  input or real model calls are implemented.

Accepted future model work:

- Provider-neutral `generate_reasoning(request) -> response` interface.
- DeepSeek is the first real provider route.
- OpenAI-compatible remains an interface/config/status placeholder until a
  later provider stage.
- Provider transport may stream bytes/tokens later, but accepted model output is
  complete structured `reasoning.v1` JSON after schema validation. UI state may
  still update through events while the provider is running.
- Debug can input API keys, switch provider, and enable/disable model calls.
- Provider config writes require secondary confirmation and audit.
- API keys are stored locally in `runtime/config.yaml`, shown only as masked
  values, and never logged, exposed in Debug responses, or stored in clear text
  audit.
- Structured JSON response parsing with one schema repair attempt and safe
  degradation when output cannot be trusted.
- Real model calls are default off. During development, they may be manually
  enabled from Debug after secondary confirmation.
- No model calls until both config and permission gates are explicitly enabled.

## Project Reader

Future module. Reads only user-authorized project directories and only text
whitelist files.

Current thin slice:

- Added status endpoint and top-level file listing endpoint.
- Status now includes per-root existence/listability metadata and explicitly
  reports `content_reading_enabled: false`.
- Default permission remains `permissions.project.read: false`.
- Default `project_reader.allowed_roots` is empty.
- File listing is blocked unless project reading is enabled and a root is
  explicitly configured.
- Full file content reading is not implemented yet.

Discussed future project-reader work:

- Explicitly authorized roots only.
- Text whitelist first.
- Clear denied states when permission or root config is missing.
- Later integration with the event/debug surfaces so reads are auditable.

## External Adapters

Future modules. HTTP/WebSocket external access, OSC, CLI, plugins, and VR
adapters are reserved but default off.

Discussed future adapter work:

- Internal and external HTTP/WebSocket separation.
- LAN and external adapters default off.
- CLI/plugin bridge possibilities.
- OSC-style bridge as an adapter, not the core protocol.

## Voice

Future module. Voice remains default off.

Discussed future voice work:

- Support both local and API routes.
- Future states include `listening` and `speaking`.
- Microphone access must be explicitly selected and permission-gated.

## Screen Perception

Future module. Screen perception remains default off.

Discussed future screen work:

- Screenshots.
- OCR.
- VLM/image understanding.
- Mode switching.
- Audit logs.
- No screenshot, OCR, or VLM behavior is active in the first shell.

## VR / OSC

Future module. VR remains default off.

Discussed future VR work:

- Use a general event protocol first.
- Treat OSC as an adapter.
- Do not control VR or external software until explicitly selected and
  permission-gated.
