# Architecture

## Product Goal

`test atri` is a local intelligent desktop pet. It is not a web deployment. It
should feel like a desktop presence with a pixel-game pet body, speech bubbles,
memory, debugging visibility, and future support for voice, screen perception,
VR, and external software integration.

## Locked Technical Stack

- Frontend: Electron + Vite + React + Canvas.
- Backend: Python FastAPI running in conda environment `Atri_2`.
- Runtime data: `runtime/`.
- Config: YAML for editable configuration, SQLite for runtime state.
- Vector memory interface: future Chroma-compatible placeholder, not current
  implementation.
- Communication: HTTP + WebSocket.
- Backend port: `18080`.
- Vite dev port: `5173`.
- Dev startup: PowerShell script starts backend and frontend as separate processes.

## Core Principle

The application must not be a language-only chat pipeline. It is built around a
multimodal event bus. Text, bubbles, state changes, memory writes, voice events,
screen events, external software events, VR events, and errors all become
structured events.

The backend produces events and state. The frontend renders those events. The
backend must not directly control pixels in the normal path.

## Unified Multimodal Memory

The accepted memory architecture is documented in
`docs/dev_journal/MEMORY_ARCHITECTURE.md`.

Key principles:

- Memory is unified across text, vision, audio, events, state, and project
  context.
- Do not split memory by scene or mode in a way that causes context loss.
- The system is always in reasoning mode; reasoning depth changes, but there is
  no non-reasoning response path.
- Conclusions auto-write to short-term memory.
- Deep knowledge is a slow path for background consolidation and explicit/deep
  retrieval.
- Visual and audio memory require non-text abstract features. Text descriptions
  and transcripts are auxiliary, not the identity body.
- Raw source material is backup data with rolling retention, not the main
  memory body.

## Always-On Reasoning

The accepted reasoning-chain architecture is documented in
`docs/dev_journal/REASONING_ARCHITECTURE.md`.

Key principles:

- Every input event, observation, action result, and system event enters the
  reasoning loop.
- There is no non-reasoning response path. The system selects lightweight,
  standard, or deep reasoning according to the event and risk.
- A Reasoning Orchestrator owns the full chain: context construction, provider
  call, schema validation, permission checks, action execution, memory writes,
  and audit.
- Context is entity-first. If no related entity is available, reasoning falls
  back to layered memory summaries.
- Deep knowledge retrieval is requested deliberately and approved by the
  system; it is not scanned every normal turn.
- The Model Provider is a generation interface, not the owner of memory,
  permissions, actions, or UI state.
- Debug and audit surfaces may expose structured trace and action records.
  Normal UI should show state, replies, and permission questions instead of raw
  reasoning trace.

The reasoning chain connects the Event Bus, Memory Manager, Permission Manager,
Model Provider, Action execution layer, and Debug Window. Real model calls stay
disabled until both configuration and permission gates are explicitly enabled.

## First Implementation Slice

Stage 1 is a runnable shell:

- FastAPI backend with `GET /health` and `/ws/internal`.
- Backend internal event endpoint `POST /events/internal`.
- Electron shell with transparent desktop pet window.
- Canvas-rendered pixel pet placeholder.
- Event-driven bubble overlay inside the pet window.
- Settings/debug window skeleton.
- PowerShell launcher.
- Development journal documents.

Real AI replies, automatic memory, voice, screen perception, VR, and external
adapters remain planned but inactive in the first shell. Manual Debug Memory is
available as a development/debug surface.

## Window Model

Electron uses three primary windows:

- Pet window: transparent, always-on-top, draggable, pixel pet rendering, and
  internal bubble overlay.
- Command window: independent transparent input surface near the pet.
- Settings/debug window: ordinary window with left-side navigation.

History is planned as a dedicated panel or debug-window page.

The pet has an internal fixed model canvas, but the desktop presentation should
avoid a visible fixed box. The bubble is anchored in the pet window's local
coordinates near the visible model upper-left, so dragging off-screen and back
does not introduce follower-window drift.

Transparent pixels around the pet must not receive mouse events. The pet window
should pass mouse interaction through non-model transparent areas, while visible
model pixels or future explicit hit areas may be interactive/draggable.
The correct behavior is not to disable model interaction; visible model pixels
should remain clickable/draggable while transparent pixels pass through.

Dragging uses an absolute cursor anchor owned by the Electron main process.
At drag start, the main process records the cursor's offset from the pet window.
During dragging, it positions the pet window from the current screen cursor
minus that fixed offset. This avoids accumulated delta drift and prevents the
model from being flung away after long drags.

For layout anchoring, "model" means the visible pet pixel bounds rather than the
full transparent pet window. Bubbles should anchor near the visible model's
upper-left, while the command input should remain below the visible model.
The command input may remain an independent follower window; the bubble must not
be a separate follower window.

## Visual Direction

- Pixel-game pet.
- Low-resolution true pixel style.
- Complex layered pseudo-Live2D in Canvas.
- Hard pixel edges with nearest-neighbor scaling.
- Default desktop scale: 3x, adjustable.
- Final model canvas size is not locked. Preview 128, 256, and 384 before
  choosing.

First placeholder is program-drawn Canvas pixel art, not final generated assets.

## Interaction

- `Ctrl+Space`: command box. It is an input surface, not the output bubble.
- `Esc`: interrupt current reply, stop typing, clear pending bubble text, return
  to idle.
- `Ctrl+Shift+P`: settings/debug window.
- Bubble text uses typewriter display, adjustable speed, optional instant reveal.
- The bubble is an event-driven output surface, not a direct click handler
  result.
- Command submission emits `user.command.submitted` to the backend event
  endpoint. The current placeholder backend response emits `pet.bubble.show`.
- The final pixel-style manga/comic bubble visual is not defined yet. Current
  rectangular frames are placeholders until the user confirms the visual
  reference and shape.
- Long text auto-segments into consecutive bubbles; there is no manual page
  button.

No feeding, props, shop, minigames, quests, currency, levels, hunger, or
cleanliness systems.

## State System

Use a semantic state machine, not pet simulation numbers.

Initial states:

- `idle`
- `thinking`
- `talking`
- `reading`
- `error`
- `dragging`
- `sleep`

Future states:

- `listening`
- `observing`
- `interrupted`
- `speaking`

States drive animation, bubbles, interruption behavior, and future voice/screen
flows.

## Safety

Initial app must not control the computer. It must not write files, run commands,
open software, click the mouse, type keys, control VR, take screenshots by
default, listen to the microphone by default, or expose external interfaces by
default.

Use capability-level permissions.
