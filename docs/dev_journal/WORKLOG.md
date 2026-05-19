# Worklog

## 2026-05-18

- Confirmed implementation plan from conversation.
- Cleared old tiny LM experiment contents from `E:\File\AIuseing\xai\test1`.
- Created new root directories:
  - `frontend/`
  - `backend/`
  - `assets/`
  - `runtime/`
  - `docs/dev_journal/`
  - `scripts/`
  - `tests/`
- Added root project README and `.gitignore`.
- Added initial `runtime/config.yaml`.
- Began writing the 8-document development journal system to protect against
  context compaction.
- Added backend FastAPI shell with health and internal WebSocket endpoints.
- Added event envelope model and config loader.
- Added Electron/Vite/React frontend shell with:
  - pet window
  - bubble overlay
  - settings/debug window
  - Canvas pixel pet placeholder
- Added PowerShell dev launcher and backend check script.
- Checked backend dependencies in `Atri_2`: `fastapi`, `uvicorn`, `yaml`, and
  `pydantic` import successfully.
- Checked frontend dependencies: `frontend/node_modules` is missing, so Vite and
  Electron cannot run until `npm install` is performed.
- Ran `npm install` in `frontend/` with approval. It timed out after about 304
  seconds.
- After timeout, `frontend/node_modules/` exists but `frontend/package-lock.json`
  does not exist, so dependency installation is not considered verified.
- Attempted to inspect running `npm/node/electron` processes in parallel, but
  one shell call failed due to Windows sandbox setup refresh failure. This still
  needs to be checked on resume.
- Important correction from user: `test1` is the current workspace/project;
  `Atri_2` is only the Python conda environment previously used for backend
  checks, not the workspace name.
- Resumed from docs and checked lingering processes. Found stuck `npm install`
  and Electron `install.js` processes from the previous timeout, then stopped
  only those project installer processes.
- Verified `npm ls --depth=0` could see the dependency tree, but Electron was
  still missing its binary and `package-lock.json` was absent.
- Added `@types/react` and `@types/react-dom` to frontend dev dependencies.
- Re-ran `npm install`; it completed, generated `frontend/package-lock.json`,
  and `npm run typecheck` passed.
- Repaired Electron binary installation with `ELECTRON_MIRROR` set to
  `https://npmmirror.com/mirrors/electron/`; confirmed
  `npx electron --version` returns `v39.8.10`.
- Found and fixed a launcher bug: PowerShell `Start-Process` cannot redirect
  stdout and stderr to the same file. Updated `scripts/start_dev.ps1` to use
  separate `.out.log` and `.err.log` files.
- Updated the launcher to use `npm.cmd` for Vite and Electron on Windows.
- Verified `.\scripts\start_dev.ps1` starts backend, Vite, and Electron.
- Verified `GET http://127.0.0.1:18080/health` returns `ok` and ports `18080`
  and `5173` are listening.
- During visual acceptance, user reported keyboard bubble shortcuts worked but
  clicking the pet did not show a bubble.
- Fixed the pet click target by changing `.pet-hit-area` from Electron drag
  region to `-webkit-app-region: no-drag`; the outer pet window remains the
  drag region.
- Re-ran `npm run typecheck` successfully after the click-region fix.
- Added `scripts/stop_dev.ps1` to stop backend, Vite, Electron, and descendant
  project dev processes by project path and dev ports.
- Verified `stop_dev.ps1` frees ports `18080` and `5173`, then verified
  `start_dev.ps1` starts the full shell again.
- Updated the root README and status document with the stop command.
- User clarified that input and output must not be the same surface; the current
  bubble-like frame is more appropriate as the command input surface.
- User clarified that bubbles should be triggered by events, not by clicking
  the model.
- User clarified that clicking the model must not generate the bubble frame.
- User corrected the wording around "pixel-style manga/comic bubble": the
  current rectangular pixel frame is not the intended visual. The final bubble
  design must be confirmed before implementation.
- Added the documentation rule that every user-requested design or behavior
  change must be recorded in the relevant docs during the same work turn.
- Added a separate Electron command window opened by `Ctrl+Space`.
- Removed the pet click handler that directly showed a bubble.
- Routed command submission through a placeholder event path:
  `user.command.submitted` leads to a placeholder `pet.bubble.show` event.
- Re-ran `npm run typecheck`, `node --check electron/main.cjs`, and
  `node --check electron/preload.cjs` successfully.
- Restarted the dev shell and verified backend health, Vite access, Electron
  processes, and empty error logs.
- User clarified that transparent non-model areas must not be clickable or
  draggable; clicking transparent parts of the pet window should pass through.
- Recorded the transparent-area hit-test rule in `DECISIONS.md`,
  `ARCHITECTURE.md`, and `MODULES.md`.
- Implemented pet window mouse pass-through by default with
  `setIgnoreMouseEvents(true, { forward: true })`, exposed
  `setPetMouseIgnored` through preload, and switched mouse handling based on
  visible canvas pixel alpha.
- Re-ran `npm run typecheck`, `node --check electron/main.cjs`, and
  `node --check electron/preload.cjs`, then restarted the dev shell and verified
  health, Vite access, Electron processes, and empty error logs.
- User corrected the previous transparent-area fix: the model itself must still
  be clickable/draggable; the fix must not disable model interaction.
- Reworked pet interaction so visible model pixels can be clicked/dragged,
  transparent pixels pass through, and model clicks emit `pet.model.clicked`
  without directly showing a bubble.
- Replaced the rectangular output bubble placeholder with a more manga-bubble
  shaped pixel placeholder with stepped corners and a pixel tail. This is still
  not final art and should be refined with user confirmation.
- User clarified the bubble tail should be smaller, black-pixel outlined, and
  generated at the model's upper-left.
- User clarified again that the model remains unclickable and asked for a
  variable click region based on where pixels exist rather than a fixed region.
- User clarified the bubble tail should be more triangular and sharper.
- User clarified that the bubble should follow the model and remain displayed
  at the model's upper-left while the model moves.
- User clarified that "model" does not include transparent window area; bubble
  and input positioning should use visible model bounds.
- User clarified that the command input was correctly placed below the model and
  should not be moved elsewhere.
- User clarified that the display-edge bug affects model click/drag interaction,
  not just bubble clipping.
- Initially constrained pet dragging to keep visible model bounds inside the
  display work area, then user clarified this was wrong: the model, bubble, and
  input should be movable partially off-screen like normal windows.
- Removed position clamping for the model, bubble, and command input. Kept
  fixed offsets from visible model bounds and kept `mouseup`/`blur` drag-state
  recovery for edge interaction stability.
- User pointed out the command input was still not appearing below the model.
- Fixed the cause: `showCommandWindow()` positioned follower windows before the
  command window was visible, while `syncFollowerWindows()` skipped hidden
  command windows. It now positions the hidden command window before showing it.
- User reported that after repeatedly dragging the model out of and back into
  the display, the bubble moved farther away until it disappeared.
- Reworked the bubble from a separate Electron follower window into an internal
  overlay inside the pet window. The model canvas and bubble now share the same
  local coordinate system, so the bubble keeps a fixed offset from the visible
  model's upper-left instead of accumulating screen-position drift.
- Adjusted pet window layout so the model canvas uses the same fixed local
  offset as Electron's visible-model bounds, and kept the command input anchored
  below the visible model.
- Switched pet dragging to pointer events with pointer capture so dragging can
  continue smoothly when the pointer leaves the visible canvas or crosses a
  display edge. Transparent non-model areas still pass through when not
  actively dragging.
- User reported that the cursor and model still drift apart during dragging,
  and after enough movement the model can be flung far away.
- Replaced accumulated drag deltas with an absolute cursor-anchor drag model:
  Electron records the cursor offset from the pet window at drag start, then
  each drag update positions the pet window from the current screen cursor
  minus that fixed offset.
- User reminded that work should follow the documented module-by-module
  implementation command instead of ad hoc visual changes.
- Added `NEXT_MODULE` as the module implementation command and documented the
  module queue in `STATUS.md` plus execution rules in `MODULES.md`.
- Reverted the unconfirmed bubble visual tweak made before checking the module
  command, keeping the current placeholder bubble until Bubble System is the
  selected module and the visual is confirmed.
- Started `NEXT_MODULE` with the Event Bus thin slice.
- Added backend `POST /events/internal`, accepting event envelopes and returning
  response events.
- Changed Electron command submission so `user.command.submitted` is posted to
  the backend event endpoint. The backend now returns the placeholder
  `pet.bubble.show` event instead of Electron generating the reply locally.
- Continued `NEXT_MODULE` with the State Manager thin slice.
- Backend command flow now emits `pet.state.changed` events for `thinking` and
  `talking` around the placeholder bubble response.
- Electron forwards `pet.state.changed` to the pet window and returns to `idle`
  when the bubble is cleared.
- Pet renderer displays a small state badge and uses minor placeholder animation
  changes for `thinking` and `talking`.
- Skipped Bubble System visual refinement while the user is away because the
  final manga/comic bubble shape needs user confirmation.
- Continued with the Debug Window thin slice.
- Electron now keeps an in-memory recent-event buffer and forwards recent events
  plus current pet state to the debug window.
- Debug window now displays backend status, current pet state, and recent event
  payloads.
- Continued with the Model Provider thin slice without enabling real AI calls.
- Added `backend/test_atri/model_provider.py` for provider config/status.
- Added `GET /model/provider/status`.
- Added `llm.enabled: false` and `permissions.model.call: false` as explicit
  gates in `runtime/config.yaml`.
- Continued with the Memory Manager thin slice without connecting automatic
  memory writes.
- Added `backend/test_atri/memory.py` with SQLite-backed manual memory items in
  `runtime/test_atri.sqlite3`.
- Added `GET /memory`, `POST /memory`, and `DELETE /memory/{item_id}`.
- Continued with the Project Reader thin slice.
- Added `backend/test_atri/project_reader.py`.
- Added `GET /project-reader/status` and gated `GET /project-reader/files`.
- Added `project_reader.allowed_roots: []` while keeping
  `permissions.project.read: false` by default.
- Added backend contract smoke tests in `tests/test_backend_contracts.py` for
  health, command event flow, disabled model provider status, and default
  project-reader denial.
- `pytest` is not installed in `Atri_2`, so added standalone
  `tests/smoke_backend_contracts.py` to run the same contract checks without
  installing dependencies.
- User reported the debug window opens once, then reopening after closing shows
  an error notification that cannot be dismissed.
- Fixed debug window lifecycle: closing now hides the window during normal app
  runtime, destroyed windows are recreated before reuse, and debug event sends
  check that the window is still usable.
- Continued with the Bubble System behavior slice.
- Added renderer-side long-text segmentation, automatic segment advance, page
  counter, and interrupt-safe typewriter cancellation.
- Kept the final pixel-style manga/comic bubble visual unconfirmed and
  unchanged except for the small page counter.
- User reported long text stretched the bubble downward instead of truly
  changing pages.
- Fixed bubble pagination by reducing per-page segment length and making the
  bubble/text area fixed height so long output paginates rather than extending
  the frame.
- User clarified the current bubble size can only display two lines and asked
  to set it to two lines.
- Removed the page counter, shortened segment length, and fixed the placeholder
  bubble text area to two lines.
- Continued with a Permission Manager thin slice while external/voice/screen/VR
  remain blocked until explicit selection.
- Added `backend/test_atri/permissions.py` and `GET /permissions/status`.
- Added a read-only permission list to the debug window.
- Extended the backend smoke contract check to verify permission status.
- Added a read-only Debug Window Modules section showing Model Provider,
  Memory, and Project Reader status.
- User reported the Debug window could not scroll far enough to show everything
  and asked that small UI fixes be accumulated before reporting.
- Added scroll safety to the Debug content area: `min-height: 0`, bottom padding,
  contained overscroll, and non-sticky final panel spacing.
- Recorded the workstyle preference to batch small UI fix reports before asking
  the user to test each item.
- Batched a larger Debug Window polish pass before asking for testing.
- Changed Debug sidebar buttons into real page navigation with active state.
- Added a Debug toolbar with a refresh action for backend-derived status.
- Split Events, Permissions, Model Provider, Memory, Project Reader, reserved
  modules, and placeholder pages into separate views.
- Updated preload IPC listener helpers to return unsubscribe callbacks and added
  React cleanup for bubble, pet state, debug, and command focus listeners.
- User reported Debug sidebar buttons became too dark while pressing and lacked
  clear feedback about which item was being clicked.
- Added clearer Debug sidebar button hover, active, focus-visible, and selected
  states, including an active indicator bar.
- Added read-only `GET /logs/status` and smoke coverage for it.
- Filled Debug History with a compact recent-event timeline.
- Filled Debug Visual with current layout constants and bubble status notes.
- Filled Debug Logs with log file sizes and tail excerpts.
- User asked for ordinary logs and error logs to use different colors.
- Added `kind` to log status entries and color-coded Debug Logs cards: error
  logs use red styling and ordinary output logs use green styling.
- Replaced External, Voice, Screen, and VR/OSC placeholder pages with read-only
  capability permission state lists.
- Added manual memory management in the Debug Memory page: create note, list
  manual memory items, and delete items.
- Extended backend smoke contracts to create and delete a smoke memory item.
- User clarified that the memory problem is multimodal identity continuity:
  if the AI later has vision, text notes alone cannot guarantee recognizing the
  same person or object.
- User then clarified that the memory plan is not decided and asked to put it
  aside for now.
- Reverted the in-progress multimodal memory schema/code direction back to the
  simple manual text-note debug surface, while recording the unresolved identity
  continuity question in docs.
- After context compaction, followed the documented recovery flow:
  - Read `docs/dev_journal/README.md`, `STATUS.md`, `ARCHITECTURE.md`,
    `DECISIONS.md`, `MODULES.md`, `API_EVENTS.md`, `WORKLOG.md`, and
    `TROUBLESHOOTING.md`.
  - Confirmed existing backend, Vite, and Electron project processes were
    already running, so no duplicate dev shell was started.
  - Verified frontend dependencies and lockfile exist.
  - Ran backend import check, Electron main/preload syntax checks, frontend
    typecheck, backend smoke contracts, backend health check, Vite HTTP check,
    and error-log size check successfully.
  - Confirmed `test1` is not currently a git repository, so `git status` is not
    available.
- User confirmed the current dialogue bubble is acceptable for now and asked to
  leave it alone until they explicitly request another pass. Updated the module
  queue and decisions so Bubble System visual is paused instead of being the
  next automatic module.
- User questioned whether there were no other next modules after pausing bubble
  visual and memory design. Expanded the safe module queue with non-sensitive
  foundation work: Command Box UX, Event Bus / History, State Manager / Pet
  Feedback, Debug Window, Model Provider dry-run/config, and Project Reader
  dry-run/status. External adapters, voice, screen, and VR remain explicitly
  blocked until selected.
- User pointed out that many more ideas had been discussed earlier. Split the
  planning docs into an immediate implementation queue and a broader discussed
  backlog so the long-term design is not lost: AI reply pipeline, personality,
  permission boundaries, layered pet visuals, state expansion, event history,
  permission audit, project reader, memory, voice, screen perception, external
  adapters, and VR/OSC.
- Continued with the Command Box UX module.
- Made command submission awaitable so the command window can distinguish
  success from failure.
- Added a sending state that prevents repeated submits while the backend event
  request is in flight.
- On success, the command input clears and the command window hides. On failure,
  the user's draft is preserved and an inline error state is shown while the
  normal event/bubble path still reports the backend failure.
- Added a small clear button for command drafts without changing the separation
  between command input and output bubble.
- Verified with `npm run typecheck`, `node --check electron/main.cjs`,
  `node --check electron/preload.cjs`, backend smoke contracts, dev-shell
  restart, backend health, Vite HTTP check, and empty error logs.
- Continued with the Event Bus / History module.
- Added local diagnostic event persistence in Electron:
  `runtime/events.jsonl` stores one JSON event summary per line.
- Electron now reloads the latest 80 persisted events on startup for Debug
  History and trims the persisted file to the latest 500 events.
- Added a local `system.hello` startup event so each Electron session is visible
  in History.
- Added `runtime/*.jsonl` and `runtime/*.sqlite3` to `.gitignore` because these
  are runtime state files, not source files.
- Verified with `node --check electron/main.cjs`, `npm run typecheck`, backend
  smoke contracts, dev-shell restarts, backend health, Vite HTTP check, empty
  error logs, and confirmed `runtime/events.jsonl` was created with a
  `system.hello` event.
- User asked to find and formalize the previously drafted unified multimodal
  memory plan.
- Added `docs/dev_journal/MEMORY_ARCHITECTURE.md` as the source of truth for the
  accepted memory architecture.
- Recorded core memory decisions: memory is unified across scenes and
  modalities; scene/source/modality are metadata and retrieval weights, not
  isolation boundaries; the system is always in reasoning mode; reasoning
  scratch is temporary with a default 5-minute TTL; conclusions auto-write to
  short-term memory; deep knowledge is a slow path; visual/audio memory must use
  non-text abstract features; raw backup uses 20 GB and 30 day rolling
  retention.
- Updated `README.md`, `docs/dev_journal/README.md`, `ARCHITECTURE.md`,
  `DECISIONS.md`, `MODULES.md`, `API_EVENTS.md`, and `STATUS.md` to point to the
  new memory architecture and remove the old "memory architecture undecided"
  framing.
- Kept visual-system details, voice-system details, and the full
  reasoning-model chain as separate follow-up design topics.

## 2026-05-19

- User provided the previously drafted plan for landing the always-on reasoning
  chain into docs and clarified that the plan, not the compressed summary alone,
  should be used as the source for this pass.
- Added `docs/dev_journal/REASONING_ARCHITECTURE.md` as the source of truth for
  the reasoning chain.
- Recorded that every input event, observation, action result, and system event
  enters reasoning. There is no non-reasoning path; only depth changes.
- Recorded reasoning depth defaults: lightweight = 1 step / 10 seconds,
  standard = 3 steps / 30 seconds, deep = 5 steps / 90 seconds.
- Recorded entity-first context construction and layered-summary fallback when
  no related entity exists.
- Recorded that the system owns context-budget trimming and must preserve the
  current event, current task, compact core long-term memory, and directly
  related entities.
- Recorded the Reasoning Orchestrator responsibilities: context construction,
  provider call, schema validation/repair, permission checks, action execution,
  memory write candidates, UI events, trace, and audit.
- Recorded the provider-neutral `generate_reasoning(request) -> response`
  interface for API and local model routes.
- Recorded that model providers generate structured output only; they do not
  directly write memory, execute actions, change permissions, or mutate UI.
- Recorded `reasoning.v1` as the first structured output schema and expanded
  the API/events document with field-level reply, state, action, memory, debug,
  audit, and failure behavior sections.
- Replaced the old rough `Future AI Output JSON` draft with the new reasoning
  output contract.
- Recorded action schema as `capability + name + params + reason + risk`.
- Recorded capability policy: code-defined safe registry plus config switches,
  auto-execute authorized low-risk actions, ask through bubble/event flow for
  unauthorized actions, and require secondary confirmation for high-risk
  actions.
- Recorded the first high-risk action list: file write/delete, process run,
  external network, input control, VR output, long screen observation, long
  microphone listening, external adapters, LAN, and OSC.
- Recorded pending authorization behavior: dynamic wait, pause when unanswered,
  and possible revival when the user is active again, background reasoning
  recalls it, or the task requires it again.
- Recorded failure behavior: one schema repair attempt, no memory write/action
  execution from invalid user-interaction output, model-generated character
  failure copy when possible, and plain system-level error only when the model
  itself is unavailable or unusable.
- Recorded audit rules: full structured trace/action audit goes to SQLite,
  JSONL stores compact summaries, action parameters are saved raw/complete,
  audit is sensitive data, and action-audit retention defaults to 30 days.
- Added concrete visual/audio memory storage details to
  `MEMORY_ARCHITECTURE.md`: raw screenshot/crop/audio backup paths,
  observation metadata, non-text feature records, entity prototypes, and
  prompt-facing summaries/feature refs instead of raw high-dimensional vectors.
- Updated root README, development-journal README, architecture, decisions,
  modules, API/events, and status docs to include the reasoning architecture.
- Corrected the stable first reasoning event list to match the discussed plan:
  `reasoning.started`, `reasoning.step.completed`,
  `reasoning.output.produced`, `reasoning.schema.invalid`,
  `reasoning.repair.requested`, `reasoning.failed`,
  `reasoning.cancelled`, `action.proposed`,
  `action.pending_authorization`, `action.executed`, `action.failed`, and
  `action.audit.logged`.
- Added the post-write review checklist directly to
  `REASONING_ARCHITECTURE.md` so implementation must be audited against it
  before code changes.
- Renamed planned memory scratch events from `memory.reasoning.*` to
  `memory.scratch.*` so memory scratch lifecycle events do not conflict with
  reasoning-run events.
- Kept this as a docs-only pass. No backend schema, frontend UI, or real model
  implementation was changed.
- User reopened planning and selected the remaining reasoning-chain boundary
  decisions.
- Locked reasoning concurrency as a single-foreground queue: one foreground run
  at a time, user input can soft-cancel it, and background work queues or
  coalesces.
- Added the reasoning run state machine:
  `created -> context_built -> provider_running -> schema_validating ->
  action_checking -> memory_checking -> completed`, with terminal states
  `provider_failed`, `schema_failed`, `action_failed`, and `cancelled`.
- Added ID traceability requirements for `run_id`, `step_id`, `event_id`,
  `action_id`, `candidate_id`, and `audit_id`.
- Locked memory writing as high-confidence automatic with non-destructive
  version/evidence append. Old records may be down-ranked, expired, or marked
  `superseded`, but not physically overwritten.
- Recorded first automatic memory thresholds: short-term 0.70, long-term fact
  0.85, preference/style 0.88, entity identity 0.92, and conflict/correction
  0.95.
- Recorded that user corrections are evidence, not absolute forced overwrite.
- Recorded that deterministic shell fallback can write only low-confidence
  short-term state/failure/input records.
- Recorded that memory cannot directly change real capability switches,
  permission config, hard personality config, or system prompts; it may only
  propose such changes as actions.
- Recorded that personality/behavior style memory may auto-write as preference
  evidence and gradually influence reasoning without rewriting hard persona
  config.
- Locked action dedupe/retry behavior: dedupe by `action_id`; failed actions do
  not retry unless marked `retryable` and the failure condition changes.
- Locked pending authorization lifecycle:
  `pending -> asked -> paused -> revived -> approved/denied/expired/cancelled`,
  with reminder caps low=3, medium=2, high=1.
- Locked deep-mode retrieval behavior: deep mode automatically allows deep
  retrieval; the model may request multiple rounds inside a default 90-second
  total budget, but the system approves each round.
- Updated `REASONING_ARCHITECTURE.md`, `API_EVENTS.md`, `MODULES.md`,
  `DECISIONS.md`, and `STATUS.md` with these decisions.
- Re-audited the reasoning and memory docs for consistency after writing the
  supplement.
- Fixed the old memory rule that implied long-term/entity/conflict writes must
  always enter review. It now matches the accepted high-confidence automatic
  memory policy: high-confidence writes may auto-write, while lower-confidence,
  ambiguous, or failed candidates enter review.
- Tightened deep retrieval wording: deep mode automatically enters the
  deep-retrieval path, while lightweight/standard turns do not scan deep
  knowledge by default.
- Added config placeholders for deep retrieval budget, pending reminder caps,
  high-confidence memory thresholds, non-physical overwrite, and deterministic
  shell memory limits.
- User requested implementation of the full reasoning documentation update plan
  after leaving Plan mode.
- Updated `REASONING_ARCHITECTURE.md` from architecture-only pending status to
  an accepted full implementation route.
- Recorded the staged implementation order: deterministic shell + SQLite +
  Debug skeleton, then DeepSeek real provider calls, automatic memory writes,
  SQLite memory/event deep retrieval, and capability-gated action execution.
- Recorded provider strategy: DeepSeek is the first real provider route;
  OpenAI-compatible is an interface/config/status placeholder for a later
  provider stage.
- Recorded model output strategy: UI state may update through events while the
  provider runs, but provider output is accepted only as complete non-streaming
  `reasoning.v1` JSON after validation.
- Recorded Debug provider config management: API key input, provider switching,
  and model enable/disable require secondary confirmation and provider-config
  audit.
- Recorded key safety: API keys are stored locally in `runtime/config.yaml`,
  shown masked in Debug, and must not appear in logs or clear-text audit.
- Recorded that real model calls remain default off, but may be manually enabled
  during development from Debug after secondary confirmation.
- Recorded automatic-memory implementation direction: accepted
  `memory.write_candidates` write to formal memory records such as
  `memory_records`, not the legacy `memory_items` manual-note table.
- Recorded deep retrieval implementation direction: first version reads SQLite
  memory records, entities, and recent event summaries; vector/embedding
  retrieval is later work.
- Recorded that visual and voice remain observation/permission interface
  placeholders in this route; capture, ASR/TTS, and matching thresholds remain
  later topics.
- Updated `API_EVENTS.md`, `MODULES.md`, `DECISIONS.md`, and `STATUS.md` to
  match the accepted full reasoning route.
- User asked to correct document wording without changing code, config, or the
  accepted memory architecture.
- Renamed the reasoning implementation route from ambiguous Stage 1/2/3 wording
  to Reasoning R1/R2/R3/R4/R5, while keeping the project stage as
  `Stage 1: runnable shell`.
- Clarified that deterministic fallback is a fallback executor, not a real
  model provider. DeepSeek and OpenAI-compatible remain the model provider
  routes.
- Clarified model output handling: provider transport may stream later, but the
  system only accepts complete `reasoning.v1` JSON after schema validation.
- Updated README/read-order wording and current feature status: manual Debug
  Memory exists, while automatic memory and real AI replies remain inactive.
- Added documentation requirements that Debug Logs and `/logs/status` must
  redact API keys, authorization headers, tokens, and similar secrets before API
  key input or real provider calls are enabled.
- Downgraded Chroma/vector wording in architecture to a future placeholder, not
  current implementation.
