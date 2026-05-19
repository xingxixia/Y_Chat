# Always-On Reasoning Architecture

This document is the source of truth for `test atri`'s reasoning loop, model
output contract, action execution policy, and reasoning audit behavior.

It complements `MEMORY_ARCHITECTURE.md`. The memory document defines what is
remembered and how memory is layered. This document defines how each event is
turned into context, reasoning, actions, replies, and memory write candidates.

## Summary

`test atri` is always in reasoning mode. There is no direct non-reasoning reply
path. Every user input, model click, visual observation, voice input, project
event, system event, action result, or memory event enters the same reasoning
loop:

```text
receive event
-> build context
-> select reasoning depth
-> call reasoning provider or deterministic fallback executor
-> validate structured output
-> execute allowed actions or ask for permission
-> emit reply/state/events
-> write approved conclusions to memory
-> store trace/audit
-> schedule background consolidation when needed
```

The difference between turns is depth, not whether thinking happens.

The first implementation target is not a perfect autonomous agent. The target is
a stable reasoning operating system: predictable event intake, entity-first
context, schema-versioned output, permission-gated actions, undoable memory
writes, debug visibility, and safe degradation when a model or JSON output
fails.

## Core Rules

### Always Reason

- Every input or observation enters the reasoning loop.
- There is no "reply without thinking" mode.
- Reasoning depth is selected automatically: lightweight, standard, or deep.
- The normal UI may show only coarse states, but the backend still runs the
  reasoning loop.

### One Orchestrator Owns The Chain

Reasoning is coordinated by a Reasoning Orchestrator module.

The orchestrator owns:

- context construction
- reasoning depth selection
- provider request construction
- provider fallback selection
- JSON schema validation and repair
- action permission checks
- action execution dispatch
- memory write dispatch
- trace and audit persistence
- user-visible error/failure events

The model provider only generates a structured reasoning response. It does not
directly write memory, execute actions, change permissions, or control UI.

### Structured Output First

- Primary model output is schema-versioned JSON, starting with
  `schema_version: "reasoning.v1"`.
- Safe failure replies or degradation notices are allowed only after the
  structured path fails safely. They are not a separate non-reasoning reply
  path, and they must not execute actions or write memory from untrusted output.
- Memory writes and actions are candidates until the orchestrator accepts them.
- Do not show a normal user-facing reply bubble while the structured output is
  invalid and still being repaired.

### Unified Memory, Not Scene Memory

- Reasoning reads from the unified memory system.
- Scene, source, and modality are metadata and retrieval weights, not memory
  isolation boundaries.
- A recent user requirement must not disappear just because the UI state,
  screen state, voice state, or task scene changed.
- Deep knowledge memory is a slow path. It is requested deliberately and is not
  scanned every normal turn.

### Entity-First Context

Reasoning context should prefer identity continuity:

1. entities directly linked to the current event
2. recent active entities
3. confirmed core entities related to the task
4. layered memory summaries if no entity is relevant

The model receives entity summaries, confidence, recent observations, and
feature references. It must not receive high-dimensional raw vectors in the
prompt.

### Permission-Gated Actions

Every action is described as:

```text
capability + name + params + reason + risk
```

The orchestrator checks the capability registry before execution.

- Authorized low-risk actions may execute automatically.
- Unauthorized actions ask the user every time.
- High-risk actions require secondary confirmation even when the capability is
  otherwise authorized.
- Failed actions become observations and can feed a follow-up reasoning step.

### Trace Is Not Long-Term Memory

- Reasoning trace is debug/audit data, not normal long-term memory.
- Full trace is short-lived unless retained for audit.
- Conclusions, facts, state changes, preferences, entity links, and task state
  may become memory.
- The raw reasoning stream must not be promoted into long-term memory as-is.

## Event Intake

Reasoning can start from events such as:

- `user.command.submitted`
- `pet.model.clicked`
- `voice.input.final`
- `vision.observation.created`
- `project.reader.result`
- `memory.record.created`
- `memory.entity.matched`
- `action.result`
- `permission.response`
- `system.hello`
- `system.heartbeat`
- `error.reported`

User events have priority over background events.

If a user event interrupts a background or long-running reasoning task:

- stop future actions from the interrupted run
- preserve completed action audit
- summarize the interruption
- write a short-term interruption conclusion when useful
- start a new reasoning run for the user's event

Background events should queue or coalesce instead of fighting the user for
attention.

## Run State Machine And Concurrency

`test atri` uses a single-foreground reasoning queue.

Rules:

- Only one foreground reasoning run may be active at a time.
- User input is the highest priority event class.
- A new user input may soft-cancel the active foreground run.
- Background consolidation, deep retrieval continuations, pending-action
  reminders, and low-priority system events queue or coalesce.
- Completed actions from a cancelled run stay audited.
- Unexecuted actions from a cancelled run are discarded unless the new run
  proposes them again.
- Background events must not emit user-facing bubbles while a foreground run is
  actively producing a reply, unless they are safety-critical.

Run states:

```text
created
-> context_built
-> provider_running
-> schema_validating
-> action_checking
-> memory_checking
-> completed
```

Failure and terminal states:

```text
provider_failed
schema_failed
action_failed
cancelled
```

Soft-cancellable states:

- `provider_running`
- `schema_validating`
- `action_checking`
- `memory_checking`

State rules:

- `created`: run envelope exists, but context is not built.
- `context_built`: event, memory, entity, permission, capability, and device
  context are frozen for the provider request.
- `provider_running`: provider or fallback executor is producing output.
- `schema_validating`: output is being parsed, validated, and possibly repaired
  once.
- `action_checking`: action proposals are deduped, risk-checked, authorized, or
  converted into pending actions.
- `memory_checking`: memory candidates are scored, written, versioned, or
  rejected according to memory policy.
- `completed`: accepted reply/events/audit have been emitted.
- `provider_failed`: provider was unavailable or timed out and no acceptable
  fallback completed the run.
- `schema_failed`: schema repair failed or produced untrusted output.
- `action_failed`: an action failed in a way that must end or pause the run.
- `cancelled`: the run was soft-cancelled by user interruption, shutdown, or a
  newer higher-priority event.

## ID And Traceability Rules

Every reasoning artifact must be traceable.

Required identifiers:

- `run_id`: every reasoning run
- `step_id`: every provider, repair, deep retrieval, action check, or memory
  check step
- `event_id`: every source event
- `action_id`: every action proposal
- `candidate_id`: every memory write candidate
- `audit_id`: every audit entry

Traceability rules:

- Every step stores `run_id` and `step_id`.
- Every action stores `run_id`, `action_id`, and source `event_id`.
- Every memory candidate stores `run_id`, `candidate_id`, and
  `source_event_ids`.
- Every audit entry stores the related `run_id` plus whichever step/action/
  candidate IDs apply.
- Debug UI must be able to reconstruct a run from event -> context -> provider
  output -> schema validation -> action decisions -> memory decisions -> final
  reply.

## Context Packet

The orchestrator builds a bounded context packet before each provider call.

Recommended shape:

```json
{
  "schema_version": "reasoning_request.v1",
  "run_id": "uuid",
  "event": {
    "event_id": "uuid",
    "type": "user.command.submitted",
    "source": "command_window",
    "timestamp": "2026-05-19T00:00:00Z",
    "payload": {}
  },
  "active_task": {
    "task_id": "optional-id",
    "summary": "current task summary",
    "status": "active"
  },
  "pet_state": {
    "state": "idle",
    "emotion": "neutral"
  },
  "memory_context": {
    "working": [],
    "short_term": [],
    "core_long_term_summary": "",
    "deep_knowledge_loaded": false
  },
  "entity_context": [
    {
      "entity_id": "optional-id",
      "kind": "person|object|voice|project|file|window|device|place",
      "label": "optional-user-facing-label",
      "confidence": 0.92,
      "summary": "stable entity summary",
      "recent_observations": [],
      "feature_refs": []
    }
  ],
  "permissions": {},
  "available_capabilities": [],
  "device_state": {},
  "debug_options": {
    "trace_enabled": true
  }
}
```

Context budget rules:

- Always preserve the current event.
- Always preserve the current active task if one exists.
- Always preserve compact core long-term memory.
- Always preserve directly related entities.
- Trim lower-priority short-term records before trimming the current event or
  directly related entities.
- If no entity matches the event, fall back to layered summaries: working
  summary, short-term summary, core long-term summary, then optional deep
  retrieval.

This fallback is the "layered summary fallback" discussed earlier: it prevents
reasoning from becoming empty when entity identity is unavailable, while still
avoiding scene-isolated memory.

## Reasoning Depth

Reasoning depth is automatic. It is not a user-facing "thinking on/off" switch.

| Depth | Default Steps | Timeout | Typical Use |
| --- | ---: | ---: | --- |
| lightweight | 1 | 10 seconds | simple continuity, short replies, obvious UI feedback |
| standard | 3 | 30 seconds | normal tasks, decisions, memory writes, action proposals |
| deep | 5 | 90 seconds | conflicts, long-range planning, deep retrieval, consolidation, complex project work |

There is no hard token/cost limit in the first plan, but step counts and
timeouts are still required so the app does not hang silently.

The orchestrator may raise or lower depth according to:

- user intent complexity
- current task risk
- action risk
- memory conflict
- missing context
- deep retrieval need
- repeated failure
- background consolidation state

Deep mode automatically enters the deep-retrieval path. It does not require the
user to explicitly say "search memory" or "deep retrieval" first. The system may
still skip or stop retrieval when permissions, budget, relevance, or available
indexes make retrieval unsafe or useless.

## Provider Interface

All API and local model routes use the same provider interface:

```text
generate_reasoning(request) -> response
```

Provider responsibilities:

- accept the orchestrator's bounded request packet
- generate a schema-compatible reasoning response
- report provider/model metadata and errors

Provider non-responsibilities:

- no direct memory writes
- no direct action execution
- no direct permission changes
- no direct UI mutation
- no provider-specific branching in business logic

Supported future provider routes:

- API model provider
- local model provider

Fallback executor:

- When no real model is available, the orchestrator may use a deterministic
  fallback executor for safe placeholder behavior.
- The deterministic fallback is not a model provider and must not be shown as
  DeepSeek/OpenAI-compatible/local model output.
- It must not pretend that real model reasoning happened.
- It may write only low-confidence short-term records for system state, failure
  state, or the user's current input.
- It must not write long-term memory, entity identity, or high-confidence
  preferences.

## Reasoning Response Schema

Primary output uses `reasoning.v1`.

```json
{
  "schema_version": "reasoning.v1",
  "run_id": "uuid",
  "reply": {
    "should_reply": true,
    "text": "final user-facing reply",
    "bubble_text": "optional shorter bubble text",
    "style": "normal|soft|urgent|playful|error",
    "final": true
  },
  "state": {
    "pet_state": "idle|thinking|talking|reading|error|dragging|sleep|listening|observing|interrupted|speaking",
    "emotion": "neutral",
    "animation": null
  },
  "actions": [
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
  ],
  "memory": {
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
  },
  "observations": [
    {
      "kind": "state|error|action_result|user_feedback|environment",
      "content": {},
      "confidence": 1.0
    }
  ],
  "voice": {
    "speak": false,
    "text": null,
    "voice_style": null
  },
  "debug": {
    "depth": "standard",
    "needs_deep_retrieval": false,
    "deep_retrieval_query": null,
    "trace": [
      {
        "step_index": 1,
        "step_type": "context_check|decision|action_plan|memory_plan|reply_plan|repair",
        "input_refs": [],
        "reasoning_text": "structured reasoning summary, not raw hidden chain",
        "decision": "what was decided at this step",
        "outputs": []
      }
    ]
  },
  "audit": {
    "safety_notes": [],
    "permission_requests": []
  }
}
```

Important rules:

- `schema_version` is mandatory.
- `reply.text` is the user-facing final answer when a final answer is needed.
- `bubble_text` may be shorter than `reply.text`.
- `actions` are proposals until permission and capability checks pass.
- `memory.write_candidates` are proposals until memory policy accepts them.
- `debug.trace` is structured debug information. It is not the same as
  long-term memory and should not be shown in the normal UI.

## Deep Retrieval

Normal lightweight/standard reasoning does not scan deep knowledge by default.
Deep reasoning enters the deep-retrieval path automatically.

The model may request or continue deep retrieval by setting:

```json
{
  "debug": {
    "needs_deep_retrieval": true,
    "deep_retrieval_query": "what to retrieve and why"
  }
}
```

The orchestrator decides whether to run retrieval according to:

- permissions
- context budget
- relevance
- current depth
- latency tolerance
- user intent

Deep retrieval budget and flow:

- A deep run has a default total retrieval budget of 90 seconds.
- A deep run starts with a retrieval decision step.
- If permission, budget, relevance, and available indexes allow it, the system
  runs at least one deep retrieval round.
- The model may request additional retrieval rounds within the remaining budget.
- The system approves each round according to permissions, relevance, progress,
  latency, and remaining budget.
- If retrieval stalls or produces no useful progress, the system stops further
  retrieval rounds and records why.
- Foreground UI should show `thinking` or `reading` state first, then provide
  the final result after retrieval and reasoning finish.
- Do not emit a temporary answer and later contradict it unless the UI clearly
  marks the first answer as provisional.

If approved, retrieval results are added to a later reasoning step. If denied,
the denial becomes an observation for the next step.

## Action And Capability Policy

Actions use a capability registry. The registry is defined in code and controlled
by configuration.

Action fields:

- `capability`: permission namespace, such as `memory.write` or
  `project.read`
- `name`: concrete action name
- `params`: full parameter object
- `reason`: why the action is requested
- `risk`: low, medium, or high
- `retryable`: whether the action may be retried after failure

Default policy:

- Authorized low-risk actions may run automatically.
- Missing permissions create a pending action and ask the user.
- High-risk actions require secondary confirmation even if enabled.
- Action failure becomes an observation and can trigger a second reasoning step.
- Missing modality/device access should ask directly for permission or setup
  instead of pretending the capability exists.
- Actions are deduped by `action_id` inside the same run.
- The same action must not execute twice because of schema repair, retry, or
  provider duplication.
- Failed actions do not automatically retry.
- Retry is allowed only when `retryable: true` and the failure reason or
  execution condition has changed.

Conservative high-risk list:

- file writes and deletes
- process execution
- external network calls
- keyboard/mouse input control
- VR output/control
- long screen observation
- long microphone listening
- external adapters
- LAN access
- OSC or other bridge output

## Pending Authorization

Unauthorized or high-risk action proposals create pending actions.

User-facing asking should happen through normal event/bubble flow and should be
written in character. The copy is not a fixed robotic template.

If the user does not answer:

- initial wait is dynamic, usually 15-45 seconds
- low-risk actions may be asked up to 3 times
- medium-risk actions may be asked up to 2 times
- high-risk actions may be asked once
- high-risk actions should not nag aggressively
- the pending action may pause until user activity resumes

Lifecycle:

```text
pending
-> asked
-> paused
-> revived
-> approved / denied / expired / cancelled
```

A pending action may be revived when:

- the user becomes active again
- the active task still needs it
- background thought finds it relevant
- the user asks about the task

Every time an unauthorized action is still needed, the user should be asked
again. Do not silently treat old non-answers as permission.

Paused pending actions are not consent. Expired or cancelled pending actions
must be proposed again by a later reasoning run before they can execute.

## Memory Write Policy

Memory writing is high-confidence automatic by default, but it must be
versioned, reversible, and traceable.

Automatic write thresholds:

| Memory Type | Minimum Confidence |
| --- | ---: |
| short-term conclusion | 0.70 |
| long-term fact | 0.85 |
| preference / behavior style | 0.88 |
| entity identity | 0.92 |
| conflict resolution / correction | 0.95 |

Rules:

- Memory does not physically overwrite earlier memory.
- New memory is appended as a new version or evidence record.
- Older memory may be down-ranked, expired, or marked `superseded`.
- Retrieval and reasoning decide which memory version applies by context, time,
  source, confidence, task relevance, and current reasoning.
- User corrections are evidence, not absolute forced overwrite.
- High-confidence memory may automatically write long-term facts,
  preferences, entity identity, and conflict resolutions when the relevant
  threshold is met.
- Schema-failed output must not write memory.
- Provider-unavailable deterministic fallback output may write only
  low-confidence short-term state/failure/input records.
- Memory cannot change real capability switches, permission config, hard
  personality config, or system prompts directly.
- Memory may create a proposed configuration change, but that proposal must go
  through action permission and pending authorization.

Personality and behavior style memory:

- Can be automatically remembered as preference/style evidence.
- Gradually influences later reasoning through context and weighting.
- Must not directly rewrite hard persona configuration.
- Repeated consistent evidence may raise weight during consolidation.

## Failure Recovery

### Schema Failure

If provider output fails schema validation:

1. attempt one schema repair
2. validate again
3. if still invalid, enter safe degradation

Schema repair boundary:

- Repair input is limited to the raw provider output, schema errors, and minimal
  format instructions.
- Repair must not introduce new actions, new memory candidates, or new factual
  decisions that were not present in the original output.
- Repaired output must pass the normal action, memory, permission, and audit
  checks again.
- Repair failure is a schema failure, not a normal reply.

For user interactions:

- do not write memory from the failed output
- do not execute actions from the failed output
- tell the user, in character, that this turn was not safely handled or
  remembered
- avoid fixed robotic phrases such as "I forgot" or "I did not remember this"

For backend/background work:

- record the failure
- emit `reasoning.schema.invalid`, `reasoning.failed`, or `error.reported`
- keep the app in a recoverable state
- do not mutate memory or execute actions from invalid output

Copy policy:

- If the model is available, ask it to generate a short, character-appropriate
  failure line constrained to the correct meaning.
- The system constrains the semantic outcome: no memory write, no fake success,
  no hiding uncertainty.
- A hardcoded plain system-level fallback is allowed only when the model itself
  is unavailable or unusable.

### Provider Unavailable

If the provider is unavailable:

- use deterministic fallback only for safe shell behavior
- say clearly that real model reasoning did not run when relevant
- do not create confident memory from placeholder behavior

### Action Failure

If an action fails:

- store the failure in action audit
- emit an action result/error event
- feed the failure as an observation into a follow-up reasoning step when useful
- avoid retry loops without a new reason

## UI Behavior

Normal UI should show:

- state first, such as thinking/talking/error
- final bubble or reply after structured output is accepted
- permission questions when an action needs user approval
- perceivable feedback for user-triggered tasks

Normal UI should not show:

- raw reasoning trace
- raw schema repair attempts
- deep debug fields
- unstable JSON output

Debug UI may show:

- reasoning runs
- reasoning depth
- accepted context summary
- structured trace
- schema validation status
- action proposals
- pending permissions
- memory write candidates
- audit records

Background actions may stay quiet unless they affect the user, require
permission, fail in a way the user needs to know, or complete a user-requested
task. For user-triggered tasks, there must be some perceivable completion,
pause, or failure feedback.

## Trace And Audit Storage

Primary runtime database:

```text
runtime/test_atri.sqlite3
```

Planned reasoning tables:

- `reasoning_runs`
- `reasoning_steps`
- `reasoning_schema_failures`
- `action_audit`
- `pending_actions`
- `permission_audit`
- `memory_write_candidates`
- `memory_write_audit`
- `provider_config_audit`

This is a table-responsibility list only. Field-level SQLite schemas remain a
Reasoning R1 implementation detail and should not be locked here.

`runtime/events.jsonl` stores compact event summaries for local debugging. It is
not the full reasoning or memory store.

Retention:

- reasoning scratch default TTL: 5 minutes
- action audit rolling retention: 30 days
- summary event history may stay shorter and capped for UI performance

Action audit stores full raw action parameters. This makes the audit useful, but
also makes it sensitive data.

Future privacy/debug controls must allow category-based clearing:

- reasoning trace
- action audit
- permission audit
- raw backups
- memory records
- entity records

## Relationship To Visual And Voice Memory

The reasoning loop does not store raw screenshots or audio directly in prompts.

Vision and voice systems produce observations and feature references:

- screenshot/crop/audio paths as raw backup references
- bounding boxes and timestamps
- embeddings or other feature refs
- entity match candidates
- confidence values
- short human-readable summaries

Reasoning uses those summaries and refs to decide whether an entity may be the
same person, object, sound source, window, or device. The detailed storage rules
live in `MEMORY_ARCHITECTURE.md`.

Visual-system capture flow and voice-system capture flow are still separate
future plans. Discussed starting points were short-time screen observation and
press/button-to-speak voice input, but those are not fully locked designs yet.

## Event Plan

Stable first reasoning events:

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

Optional future Debug granularity may add more specific internal events, such as
context-built, provider-requested, deep-retrieval-requested, or
memory-write-candidate events. Those are not the stable first contract.

## Post-Write Review Checklist

Before implementation, audit whether this document is detailed enough to answer:

- Can a developer write the `ReasoningOrchestrator` responsibilities from the
  docs?
- Can a developer write the provider interface?
- Can a developer write the reasoning request and response schemas?
- Can a developer decide whether an action is authorized, high-risk, or needs
  secondary confirmation?
- Can a developer handle JSON parsing/schema failure?
- Can a developer handle model unavailability?
- Can a developer handle user interruption?
- Can a developer handle multiple concurrent events?
- Can a developer handle a pending action when nobody answers?
- Can a developer distinguish user-interaction failure from background failure?
- Can a developer know where trace/audit records are stored and how long action
  audit is retained?
- Can a developer know what Debug should display?
- Can a developer tell which parts still belong to later visual/voice plans and
  must not be treated as finalized by the reasoning-chain document?

## Config Plan

Future config shape:

```yaml
reasoning:
  enabled: true
  always_on: true
  default_depth: auto
  scratch_ttl_minutes: 5
  schema_version: reasoning.v1
  timeouts:
    lightweight_seconds: 10
    standard_seconds: 30
    deep_seconds: 90
  steps:
    lightweight: 1
    standard: 3
    deep: 5
  schema_repair:
    enabled: true
    max_attempts: 1
  deep_retrieval:
    auto_for_deep_depth: true
    max_total_seconds: 90
  pending_actions:
    reminder_cap_low: 3
    reminder_cap_medium: 2
    reminder_cap_high: 1
  memory_write:
    auto_write_high_confidence: true
    threshold_short_term: 0.70
    threshold_long_term_fact: 0.85
    threshold_preference_style: 0.88
    threshold_entity_identity: 0.92
    threshold_conflict_correction: 0.95
    physical_overwrite: false
    deterministic_shell_long_term_writes: false
  fallback:
    deterministic_shell: true
  trace:
    enabled: true
    store_structured_trace: true
    expose_in_debug: true

permissions:
  reasoning.trace.view: true
  reasoning.audit.view: true
  action.execute.low_risk: false
```

Real model calls still require both model configuration and explicit permission
gates from the Model Provider plan.

## Full Implementation Route

The full reasoning implementation route is accepted. It is implemented in
Reasoning R-stages so each stage can be tested and audited without confusing
the route with the project's `Stage 1: runnable shell`.

Reasoning stage order:

```text
Reasoning R1: deterministic fallback executor + SQLite + Debug skeleton
-> Reasoning R2: provider configuration and DeepSeek real provider call
-> Reasoning R3: automatic memory writes
-> Reasoning R4: SQLite memory/event deep retrieval
-> Reasoning R5: action execution under capability policy
```

Reasoning R1: deterministic fallback executor + SQLite + Debug skeleton.

- Add config placeholders for reasoning without enabling real model calls.
- Add SQLite tables for reasoning runs, steps, schema failures, action audit,
  pending actions, memory candidates, and provider config audit.
- Implement deterministic fallback responses for development and tests.
- Route `user.command.submitted` through the Reasoning Orchestrator while real
  model calls remain disabled.
- Emit reasoning events into the internal event bus.
- Add read-only Debug Reasoning page showing run, step, provider, schema,
  action, memory candidate, audit, and failure state.

Reasoning R1 behavior contract:

- R1 uses only the deterministic fallback executor. It must not call DeepSeek,
  OpenAI-compatible providers, local models, or any real model route.
- `user.command.submitted` enters the Reasoning Orchestrator instead of
  returning the current placeholder bubble sequence directly.
- Each handled user command creates traceable run/step records, records schema
  or check status, emits reasoning events, and is visible in Debug.
- R1 may record memory candidates for inspection, but it must not write formal
  long-term memory records.
- R1 may emit low-risk UI, state, and debug events. Broader action execution is
  not part of R1.
- R1 failures must be auditable and visible in Debug, and must not pretend that
  real model reasoning happened.

Reasoning R2: provider configuration and DeepSeek.

- Add the provider-neutral `generate_reasoning(request) -> response`
  interface.
- Implement DeepSeek as the first real provider route.
- Keep OpenAI-compatible as an interface/config/status placeholder in this
  stage; do not make real OpenAI-compatible calls yet.
- Before API key input, provider config writes, provider switching, model
  enablement, or real provider calls are implemented, `/logs/status` and Debug
  Logs must already redact API keys, authorization headers, bearer tokens, and
  similar secrets.
- Provider transport may stream bytes/tokens in a later implementation, but the
  system only accepts output after it has a complete `reasoning.v1` JSON object
  that passes schema validation.
- UI state may update through events such as `thinking` and `reading` while the
  provider is running.
- Debug may input API keys, switch provider, and enable/disable model calling.
- Saving API keys, switching provider, and enabling model calls require explicit
  secondary confirmation and provider-config audit.
- API keys are stored locally in `runtime/config.yaml`, shown only as masked
  values in Debug, and must not be written in clear text to logs, Debug
  responses, or audit.
- Real model calls remain off by default. During development, they may be
  manually enabled from Debug after secondary confirmation.

Reasoning R3: automatic memory.

- Connect `reasoning.v1.memory.write_candidates` to the formal memory schema.
- Write accepted candidates to `memory_records` and related audit tables.
- Do not store automatic memory in the legacy `memory_items` manual-note table.
- Keep manual notes as compatibility/debug entries until they migrate to
  `memory_records(kind=manual_note)`.

Reasoning R4: deep retrieval.

- Deep retrieval first reads SQLite memory records, entities, and recent event
  summaries.
- Do not add vector database or embedding retrieval in this route.
- Chroma/embedding integration remains a later dedicated memory-retrieval
  stage.

Reasoning R5: action execution.

- Action execution follows configured capability switches.
- High-risk actions require secondary confirmation even when the capability is
  enabled in config.
- Low-risk internal actions such as bubble, state, memory, and debug actions may
  execute automatically when authorized.
- File writes, process execution, external network, input control, VR output,
  long screen observation, long microphone listening, LAN, OSC, and external
  adapters require capability enablement plus secondary confirmation.

Acceptance priority:

- Debug traceability and safety are first.
- Desktop pet experience is second, but every user-triggered task must provide
  visible state, completion, pause, or failure feedback.
- Failure behavior must be safe: provider failure, schema failure, and action
  failure must not write unsafe memory or execute unsafe actions.

## Implementation Order

1. Keep this document and `MEMORY_ARCHITECTURE.md` as the design source of
   truth.
2. Add config placeholders for reasoning without enabling real model calls.
3. Add database tables for reasoning runs, structured steps, action audit,
   pending actions, memory candidates, and provider config audit.
4. Add the provider-neutral `generate_reasoning(request) -> response`
   interface.
5. Implement deterministic fallback responses for development and tests.
6. Add `reasoning.v1` schema validation and one-attempt repair path.
7. Route `user.command.submitted` through the Reasoning Orchestrator while real
   model calls remain disabled.
8. Emit reasoning events into the internal event bus.
9. Add read-only Debug Reasoning page.
10. Add action proposal and pending-authorization storage.
11. Connect accepted memory write candidates to the Memory Manager.
12. Add provider config endpoints, Debug key input, masked key display, provider
    switching, secondary confirmation, and provider config audit.
13. Add DeepSeek real provider calls after config and permission gates are
    visible and testable.
14. Keep OpenAI-compatible as an interface/config/status placeholder until the
    later local/API provider stage.
15. Add SQLite memory/event deep retrieval before any vector store or embedding
    integration.
16. Add action execution under capability policy and high-risk secondary
    confirmation.

## Current Status

This architecture and full implementation route are accepted. Implementation is
pending.

The memory architecture is already documented separately. Visual capture, voice
capture, final personality/failure-copy style, vector/embedding retrieval, and
OpenAI-compatible real calls still need their own later implementation passes.
