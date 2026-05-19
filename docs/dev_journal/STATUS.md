# Status

## Current State

The old `test1` tiny LM learning experiment has been cleared. The repository is
being rebuilt as the `test atri` intelligent desktop pet application.

Created so far:

- Root `README.md`
- Root `.gitignore`
- `runtime/config.yaml`
- `runtime/logs/`
- `runtime/cache/`
- `runtime/vector_store/`
- `docs/dev_journal/`
- Initial documentation files
- Backend FastAPI shell:
  - `GET /health`
  - `POST /events/internal`
  - `WS /ws/internal`
  - event envelope model
  - config loader
- Frontend Electron/Vite/React shell files:
  - pet window
  - bubble overlay inside the pet window
  - settings/debug window
  - Canvas pixel pet placeholder
- PowerShell scripts:
  - `scripts/start_dev.ps1`
  - `scripts/stop_dev.ps1`
  - `scripts/check_backend.ps1`

## Current Stage

Stage 1: runnable shell.

## Next Steps

Module implementation command:

```text
NEXT_MODULE
```

When the user says `NEXT_MODULE` or asks for the next step, pick exactly one
module from the queue below, read that module's docs first, implement only that
module's next thin slice, run checks, update docs, and then stop for user
verification.

Queue:

1. Command Box UX: add the next thin slice for command input ergonomics without
   merging it with the output bubble.
2. Reasoning full route implementation: implement the accepted Reasoning
   R-staged route from `REASONING_ARCHITECTURE.md`, starting with Reasoning R1:
   deterministic fallback executor, SQLite run/audit tables, and Debug
   Reasoning skeleton. Real model calls remain default off. Documentation gaps
   found in the latest review have been fixed; implementation remains pending.
3. Memory schema/docs alignment: implement the next thin slice from
   `MEMORY_ARCHITECTURE.md` without enabling vision, voice, or real model calls.
4. Event Bus / History: add safer inspection and persistence for local internal
   events without enabling external adapters.
5. State Manager / Pet Feedback: add small visible state feedback and recovery
   behavior for existing safe states.
6. Debug Window: continue filling read-only or low-risk diagnostic pages and
   developer controls.
7. Model Provider dry-run/config: improve disabled-by-default status,
   configuration validation, and UI visibility without making real model calls.
8. Project Reader dry-run/status: improve disabled-by-default status and
   authorized-root visibility without reading file contents by default.
9. External Adapters / Voice / Screen / VR: remain reserved and off until
   explicitly selected.

Discussed backlog, not all ready to implement:

- Real AI reply pipeline:
  - Always-on reasoning architecture is accepted in
    `docs/dev_journal/REASONING_ARCHITECTURE.md`.
  - Full reasoning implementation route is accepted and pending
    implementation.
  - All input events enter a reasoning loop; there is no non-reasoning path.
  - Reasoning uses a single-foreground queue with user-input soft cancellation
    and queued/coalesced background work.
  - The Reasoning Orchestrator owns context, provider calls, schema validation,
    permission checks, action execution, memory write candidates, and audit.
  - Provider routes use a unified API/local interface and remain disabled until
    model config and permission gates are explicitly enabled.
  - DeepSeek is the first real provider route. OpenAI-compatible remains an
    interface/config/status placeholder until a later provider stage.
  - Debug may input API keys, switch provider, and enable/disable model calls
    after secondary confirmation and audit.
  - API keys are stored locally in `runtime/config.yaml`, shown masked in Debug,
    and must not be logged, exposed in Debug responses, or audited in clear
    text.
  - Before API key input or real provider calls are enabled, Debug Logs and
    `/logs/status` must redact keys, authorization headers, tokens, and similar
    secrets. This is a Reasoning R2 prerequisite, not later polish.
  - Real model calls are default off, but may be manually enabled during
    development from Debug after secondary confirmation.
  - Use `reasoning.v1` structured JSON as the primary output protocol, with one
    schema repair attempt and safe degradation when parsing fails.
  - Provider transport may stream later, but replies, actions, memory writes,
    and final state changes are accepted only after complete `reasoning.v1`
    JSON passes validation.
  - Memory write policy is high-confidence automatic, non-destructive, and
    versioned; memory cannot directly change real permissions or hard config.
  - Automatic memory writes go to formal memory records such as
    `memory_records`, not the legacy `memory_items` manual-note table.
  - Deep retrieval first reads SQLite memory records, entities, and recent event
    summaries. Vector/embedding retrieval is later work.
  - Keep model calls gated by both `llm.enabled` and `permissions.model.call`.
- Personality and behavior settings:
  - Personality is editable later, but needs backup, reset, and change-log
    support before it becomes a normal user-facing control.
  - Permission boundaries are also editable later, but must be auditable.
- Pet visual system:
  - Move from the program-drawn placeholder toward a layered pseudo-Live2D
    Canvas renderer.
  - Compare 128, 256, and 384 canvas-size previews before locking the final
    model size.
  - Generate or choose three visual mood concepts before committing to final
    assets.
- Interaction and state:
  - Expand semantic states beyond `idle`, `thinking`, and `talking` toward
    `reading`, `error`, `dragging`, `sleep`, `listening`, `observing`,
    `interrupted`, and `speaking`.
  - Improve pet feedback for safe existing states without adding simulation
    systems such as hunger, shop, quests, currency, levels, feeding, or cleaning.
- Event history and auditability:
  - Persist useful local internal events beyond the current in-memory recent
    buffer.
  - Keep Debug History and Logs useful for diagnosing state, event, permission,
    and future model behavior.
- Permission Manager:
  - Add capability-level toggles and audit logs later.
  - Do not enable computer control, microphone, screenshots, file reading,
    external adapters, LAN access, VR, or real model calls by default.
- Project Reader:
  - Read only explicitly authorized roots.
  - Start with text whitelist files and clear denied states.
  - Full file content reading is a future slice, not enabled by default.
- Memory:
  - Unified multimodal memory architecture is accepted in
    `docs/dev_journal/MEMORY_ARCHITECTURE.md`.
  - Memory must be unified across scenes and modalities.
  - Ordinary operation writes conclusions to short-term memory automatically.
  - Deep knowledge is used by background consolidation and explicit/deep
    retrieval, not scanned every normal turn.
  - Vision/audio memories require non-text abstract features; text descriptions
    and transcripts are auxiliary only.
- Voice:
  - Future voice should support local and API routes.
  - Microphone listening and speech output remain off until explicitly selected.
- Screen perception:
  - Future screen perception should support screenshots, OCR, VLM, mode
    switching, and audit logs.
  - Screenshots/OCR/VLM remain off until explicitly selected.
- External adapters:
  - Future adapters may include internal/external HTTP, WebSocket, CLI, plugins,
    LAN access, and OSC-style bridges.
  - External/LAN adapters remain default off.
- VR / OSC:
  - Future VR should use a general event protocol first, with OSC as an adapter
    rather than the core design.
  - VR control remains off until explicitly selected.

Paused / waiting for user:

- Bubble System visual: the current dialogue bubble is acceptable for now. Do
  not revisit or redesign it until the user explicitly asks for another pass.
- Vision system details, voice system details, vector/embedding retrieval,
  OpenAI-compatible real calls, and final personality failure-copy style still
  need separate detailed plans. The reasoning full route is accepted, but
  visual and voice remain observation/permission interface placeholders only.

## Current Blocker

No current startup blocker.

Resolved on 2026-05-18:

- Lingering `npm install`/Electron installer processes were stopped.
- `frontend/package-lock.json` was generated.
- React type packages were added and `npm run typecheck` passes.
- Electron binary installation was repaired with the Electron mirror.
- `scripts/start_dev.ps1` was fixed for PowerShell log redirection and Windows
  `npm.cmd` startup.
- Backend, Vite, and Electron start successfully from the launcher.
- `scripts/stop_dev.ps1` stops the dev processes and frees the ports.
- `GET /health` returns `{"status":"ok","app":"test_atri"}`.
- Event Bus thin slice is connected: command submission posts
  `user.command.submitted` to `POST /events/internal`, and the backend returns a
  placeholder `pet.bubble.show` event.
- Event History thin slice is connected: Electron persists local diagnostic
  event summaries to `runtime/events.jsonl`, reloads recent events on startup,
  caps the Debug buffer at 80 events, and trims persisted history to 500 events.
- State Manager thin slice is connected: backend emits `pet.state.changed` for
  `thinking` and `talking`, Electron forwards it, and the pet window shows the
  current state plus small placeholder animation changes.
- Debug Window thin slice is connected: it shows backend health, current pet
  state, and a recent event list from Electron's in-memory event buffer.
- Model Provider thin slice is added: provider status endpoint and config reader
  exist, but real model calls remain disabled by default.
- Memory Manager thin slice is added: manual SQLite-backed list/create/delete
  endpoints exist, and automatic memory writes remain unconnected.
- Unified Memory Architecture is documented: scene/mode must not isolate
  memory; reasoning is always on; conclusions auto-write to short-term memory;
  reasoning scratch uses short TTL; visual/audio memory must use non-text
  abstract features; raw backup uses 20 GB / 30 day rolling retention.
- Always-On Reasoning Architecture is documented: every event enters the
  reasoning loop; depth is lightweight/standard/deep; context is entity-first
  with layered-summary fallback; providers use a unified interface; output uses
  `reasoning.v1`; actions are capability/risk checked; failures do not write
  unsafe memory or execute unsafe actions; trace/action audit is planned for
  SQLite with JSONL summaries.
- Reasoning architecture supplement is documented: single-foreground queue,
  run state machine, ID traceability, deep-mode retrieval budget, action
  dedupe/retry rules, pending authorization lifecycle, high-confidence
  non-destructive memory writes, and hard-config permission boundaries.
- Reasoning full implementation route is accepted: Reasoning R1 deterministic
  fallback executor + SQLite + Debug skeleton first, then DeepSeek real calls,
  automatic memory, SQLite memory/event deep retrieval, and capability-gated
  action execution.
  Provider config, API key input, provider switching, and model enablement go
  through Debug with secondary confirmation and audit.
- Reasoning documentation gap review completed on 2026-05-19: old wording that
  treated the full reasoning chain as an unspecified follow-up was corrected;
  Reasoning R1 now has a behavior-level contract; planned trace/audit table
  responsibilities include memory candidates and provider config audit; and log
  redaction is recorded as a prerequisite before API key input or real provider
  calls.
- Current overall runtime architecture is listed in `ARCHITECTURE.md`, including
  the three Electron windows, Electron main process responsibilities, FastAPI
  backend endpoints, runtime data, current command event flow, implemented
  module boundaries, and inactive/future module boundaries.
- Project Reader thin slice is added: status and gated top-level listing
  endpoints exist, but reading is disabled by default and no roots are
  authorized.
- Permission Manager thin slice is added: `GET /permissions/status` and a
  read-only Debug Window permission list.
- Debug Window module status slice is added: it shows read-only Model Provider,
  Memory, and Project Reader status.
- Bubble System behavior slice is added: long output segments automatically,
  segment timers are interruptible, and the final visual remains unconfirmed.
- Backend contract smoke checks cover health, command event flow, disabled model
  provider status, permission status, memory listing, and default-blocked
  project reader access.
  Use `python tests/smoke_backend_contracts.py` in the `Atri_2` environment;
  `pytest` is not currently installed.

## Resume Checklist After Context Compaction

1. Read `docs/dev_journal/README.md`, then this file.
2. Check for existing project processes before starting another copy.
3. Verify frontend dependency state if startup fails:
   - `frontend/node_modules/`
   - `frontend/package-lock.json`
   - `npm ls --depth=0`
4. Run backend import check.
5. Start backend, Vite, and Electron with `.\scripts\start_dev.ps1`.
6. Stop them with `.\scripts\stop_dev.ps1` when done.
7. Verify ports `18080` and `5173`, then `GET /health`.
8. Verify the pet window, bubble overlay, command input, and debug window.
9. Update `WORKLOG.md` and troubleshooting notes after changes.

## Known Constraints

- Do not implement AI chat in the first shell.
- Do not implement voice, OCR, screen perception, VR, or external adapters yet.
- Do not enable computer control capabilities.
- If dependencies are missing, report what is missing and why before installing.
