# Decisions

## Locked Decisions

- Develop only in `E:\File\AIuseing\xai\test1`.
- `ZcChat2` and `Open-LLM-VTuber` are references only.
- Clear the old tiny LM experiment and rebuild `test1` as the desktop pet app.
- User-visible codename: `test atri`.
- Machine name: `test_atri`.
- Use Electron + Vite + React + Canvas frontend.
- Use Python FastAPI backend in conda environment `Atri_2`.
- Use backend port `18080`; Vite port `5173`.
- Use PowerShell for one-command development startup.
- Use a multimodal event bus, not a language-only chat pipeline.
- Use structured JSON as the primary AI output protocol.
- When JSON parsing fails, use one schema repair attempt and safe degradation.
  Do not infer unsafe actions or memory writes from untrusted free text.
- Reserve `ContextInferenceHook` for future context-based guessing; default off.
- Use short-term memory plus long-term memory, with long-term split into
  always-loaded impressions and searchable knowledge memory.
- Unified multimodal memory architecture is accepted; see
  `MEMORY_ARCHITECTURE.md`.
- Always-on reasoning architecture is accepted; see
  `REASONING_ARCHITECTURE.md`.
- Full reasoning implementation route is accepted. Implement in Reasoning
  R-stages: R1 deterministic fallback executor + SQLite + Debug skeleton, then
  DeepSeek, automatic memory, SQLite memory/event deep retrieval, and action
  execution.
- Memory must not be split by scene or mode. Scene, source, and modality are
  metadata and retrieval weights, not isolation boundaries.
- The system is always in reasoning mode. There is no non-reasoning direct
  response path; only reasoning depth changes.
- Every input event, observation, action result, and system event enters the
  reasoning loop. User events have priority; background events queue or
  coalesce.
- Reasoning uses a single-foreground queue. Only one foreground run may be
  active; user input may soft-cancel it, while background work queues or
  coalesces.
- Reasoning runs use the documented state machine from `created` through
  `completed`, with terminal states `provider_failed`, `schema_failed`,
  `action_failed`, and `cancelled`.
- Every run, step, action, memory candidate, and audit entry must carry IDs
  that allow Debug to reconstruct source event -> reasoning -> action/memory
  decision -> reply.
- Reasoning depth defaults are lightweight = 1 step / 10 seconds, standard = 3
  steps / 30 seconds, and deep = 5 steps / 90 seconds.
- Context building is entity-first. If no related entity is available, use
  layered summaries as fallback.
- Context budget is owned by the system. It must preserve the current event,
  current task, compact core long-term memory, and directly related entities
  before trimming lower-priority context.
- The Reasoning Orchestrator owns the full chain: context, provider calls,
  schema validation/repair, permission checks, action execution, memory write
  candidates, and audit.
- API and local model providers must share the same generation interface:
  `generate_reasoning(request) -> response`.
- DeepSeek is the first real provider route.
- OpenAI-compatible is an interface/config/status placeholder until a later
  provider stage.
- Provider transport may stream later, but accepted model output is complete
  structured JSON after schema validation. UI state may update through events
  such as `thinking` and `reading` while the model is running.
- Model providers generate structured output only. They must not directly write
  memory, execute actions, change permissions, or mutate UI state.
- Reasoning output JSON must carry a schema version, starting with
  `reasoning.v1`.
- Deep retrieval is requested by the model and approved or denied by the
  system. Deep knowledge must not be scanned every normal turn.
- Deep mode automatically enters the deep-retrieval path with a default
  90-second total retrieval budget. The model may request multiple rounds
  inside that budget, but the system still approves each round.
- First deep retrieval implementation reads SQLite memory records, entities,
  and recent event summaries. Vector database and embedding retrieval are later
  dedicated work.
- Ordinary operation automatically writes conclusions to short-term memory.
- Reasoning trace is temporary low-weight scratch data with a default 5-minute
  TTL; conclusions, not full reasoning streams, may enter memory.
- Deep knowledge memory is a slow path for background consolidation, explicit
  lookup, project/history questions, and complex reasoning. It must not be
  scanned by default every turn.
- Visual and audio memory must store non-text abstract features. Image memory
  must not degrade into text description, and audio memory must not degrade into
  transcript text.
- Raw screenshots, crops, audio clips, and full text logs are backup material,
  not the primary memory body. Default raw-backup retention is 20 GB and 30
  days.
- Automatic memory writes are allowed, but important writes, entity updates,
  and conflicts must be visible, undoable, deletable, mergeable, down-rankable,
  and auditable in Debug UI.
- Full structured trace and action audit are stored in SQLite. JSONL event
  history stores summaries only.
- Action audit stores complete raw action parameters and is sensitive data.
  Default action-audit retention is 30 days.
- Action requests use `capability + name + params + reason + risk`.
- The capability registry uses code-defined safe capabilities plus config
  switches.
- Authorized low-risk actions may execute automatically. Unauthorized actions
  ask the user every time through the bubble/event flow.
- High-risk actions require secondary confirmation even if the capability is
  already authorized.
- Actions are deduped by `action_id` inside a run. Failed actions do not retry
  unless marked `retryable` and the failure condition changes.
- First high-risk action list: file write/delete, process run, external
  network, input control, VR output, long screen observation, long microphone
  listening, external adapters, LAN, and OSC.
- Action failure becomes an observation and may trigger a second reasoning
  step.
- Pending actions use dynamic waiting and pause when the user does not answer.
  They may be raised again when the user becomes active, background reasoning
  recalls them, or the task needs them again.
- Pending reminders are capped by risk: low-risk up to 3 asks, medium-risk up
  to 2 asks, and high-risk 1 ask before pausing.
- Pending actions follow `pending -> asked -> paused -> revived ->
  approved/denied/expired/cancelled`.
- If a visual or voice capability is requested but permission/device access is
  missing, the system asks the user to enable or configure it instead of
  pretending the modality is available.
- User interruption uses soft cancellation: stop future actions, keep completed
  audit, summarize the interruption, and continue from the user's new event.
- If JSON/schema validation fails for a user interaction, do not write memory
  or execute actions from that output.
- Schema repair may use only raw provider output, schema errors, and minimal
  format instructions. It must not introduce new decisions.
- Memory write policy is high-confidence automatic. First thresholds:
  short-term 0.70, long-term fact 0.85, preference/style 0.88, entity identity
  0.92, conflict/correction 0.95.
- Memory does not physically overwrite earlier memory. New memory is appended
  as version/evidence; old memory may be down-ranked, expired, or marked
  `superseded`.
- User corrections are evidence, not absolute forced overwrite.
- Deterministic shell fallback may write only low-confidence short-term
  state/failure/input records.
- Memory cannot directly change real capability switches, permission config,
  hard personality config, or system prompts. It may only propose such changes
  as actions.
- Personality and behavior style memory may auto-write as preference evidence
  and gradually influence reasoning, but must not rewrite hard persona config.
- Failure wording must not be a fixed robotic template pool. If a model is
  still available, it generates short character-appropriate copy constrained by
  the correct failure semantics. A plain system-level error is used only when
  the model itself is unavailable or unusable.
- Personality and permission boundaries are special and editable, but require
  backup, reset, and change log support later.
- Use capability-level permissions.
- Model calls require both `llm.enabled: true` and `permissions.model.call:
  true`; default is off.
- During development, real model calls may be manually enabled from Debug after
  secondary confirmation. Final/default state remains off.
- Debug may input API keys, switch provider, and enable/disable model calls, but
  these operations require secondary confirmation and provider-config audit.
- API keys are stored locally in `runtime/config.yaml`, shown masked in Debug,
  and must not be written in clear text to logs, Debug responses, or audit.
- Before API key input or real provider calls are enabled, Debug Logs and
  `/logs/status` must redact keys, authorization headers, tokens, and similar
  secrets.
- Automatic memory writes from reasoning output must use formal memory records
  such as `memory_records`, not the legacy `memory_items` manual-note table.
- High-risk actions may be available when config allows them, but still require
  secondary confirmation before execution.
- External interfaces are designed as adapters. First implementation only needs
  internal HTTP + WebSocket.
- LAN and external adapters default off.
- Future voice must support local and API routes.
- Future screen perception must support screenshots, OCR, VLM, mode switch, and
  audit logs, but OCR is not part of the first stage.
- Future VR should use a general event protocol first; OSC can be an adapter.
- The reasoning full route is accepted and owned by
  `REASONING_ARCHITECTURE.md`. Visual capture, voice capture,
  OpenAI-compatible real calls, vector/embedding retrieval, and final
  personality failure-copy style remain separate follow-up plans. Visual and
  voice remain observation/permission interface placeholders in the accepted
  reasoning route.

## Visual Decisions

- Pixel-game pet, not a normal chat window.
- Low-resolution true pixel style.
- Complex layered pseudo-Live2D target.
- Do not start with a complex `.moc3` Live2D model.
- First visual placeholder is program-drawn Canvas pixel art.
- Later generate three visual mood concepts before committing to final assets.
- Render with hard pixel edges.
- Default scale is 3x.
- Canvas size is undecided until 128/256/384 previews are compared.
- Output bubble is separate from the command input, but it is rendered as an
  internal overlay inside the pet window. Do not use a second Electron window
  to make the bubble follow the model, because repeated off-screen dragging can
  accumulate follower-window offset errors.
- The command box is the input surface; the bubble is the output surface.
- Input and output must not be merged into one chat box.
- The bubble should be shown, updated, or cleared by events such as
  `pet.bubble.show` and `pet.bubble.clear`, not directly by arbitrary click
  handlers.
- The intended "pixel-style manga/comic bubble" visual has not been confirmed
  yet. The current rectangular pixel frame is only a temporary placeholder and
  must not be treated as the final bubble design.
- Before implementing the final bubble visual, confirm the exact shape,
  placement, tail/pointer behavior, border style, and reference examples with
  the user.
- The current dialogue bubble is acceptable for now. Do not change, revisit, or
  redesign the bubble visual until the user explicitly asks for another pass.
- Current bubble direction from user: the pointed tail should be smaller, it
  should be a sharper triangle enclosed by black pixel outline, and the bubble
  should appear at the model's upper-left.
- Bubble position should follow the model. When the model moves, any visible
  bubble should keep its upper-left relationship to the model instead of staying
  behind at the old screen position.
- "Model" means the visible pet pixels, not the transparent pet window bounds.
  Bubble and command input positioning must be anchored to visible model bounds.
- The command input should stay below the visible model, not move to another
  position because of bubble placement changes.
- Hit detection target is parts/hit areas, not the full rectangle.
- Transparent non-model areas of the pet window must not be clickable or
  draggable. Mouse interaction should pass through transparent pixels and only
  apply to visible model pixels or explicitly defined future hit areas.
- Visible model pixels must remain interactive. Do not solve transparent-area
  pass-through by disabling model interaction.
- Clicking the model may emit a model interaction event, but must not directly
  show a bubble.
- Model hit testing should be dynamic and based on visible pixel area where
  practical, not a fixed full-window rectangle.
- Dragging should behave like moving a normal window: the model, bubble, and
  command input may move partially out of the display. Do not clamp them to the
  visible work area.
- Model dragging must use absolute cursor anchoring: record the cursor's offset
  from the pet window at drag start, then position the window from the current
  screen cursor minus that offset. Do not use accumulated mousemove deltas,
  because repeated deltas can drift and fling the model away from the cursor.
- When the model touches or crosses a display edge, click/drag state must still
  recover normally and remain interactive.
- Bubble and command input positions are fixed offsets from the visible model
  bounds and should move with the model, even when partially off-screen.
- Bubble placement must be computed in the pet window's local coordinates and
  stay bound to the visible model's upper-left with a fixed local offset. It
  must not drift toward the pet window frame or become farther away after the
  model is dragged out and back in repeatedly.
- Pixel-level control hook is reserved but disabled by default.

## Documentation Decisions

- Keep the recovery documents in `docs/dev_journal` and maintain the documented
  read order whenever a source document is added.
- Read docs first, then source, then runtime/process/logs.
- Update docs after every module change.
- Every user-requested design or behavior change must be recorded in the
  relevant docs during the same work turn.
- Small UI fixes may be accumulated into a short batch report before asking the
  user to test them one by one.
- If runtime/source conflicts with docs, source/runtime wins and docs must be
  corrected.
