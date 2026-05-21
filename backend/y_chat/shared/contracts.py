from __future__ import annotations


RUNTIME_REF_PREFIX = "runtime://"


class SchemaVersion:
    BACKEND_STATUS = "backend.status.v1"
    CONTRACTS_INDEX = "contracts.index.v1"
    DATA_STATUS = "data.status.v1"
    EVENTS_CONTRACT = "events.contract.v1"
    PERMISSIONS_CONTRACT = "permissions.contract.v1"
    REASONING = "reasoning.v1"
    REASONING_CONTEXT_SNAPSHOT = "reasoning_context_snapshot.v1"
    REASONING_REQUEST = "reasoning_request.v1"
    REASONING_VISUAL_CONTEXT = "reasoning_visual_context.v1"
    SCREEN_OBSERVATION_STATUS = "screen_observation.status.v1"
    SCREEN_OBSERVATION_CONTRACT = "screen_observation.contract.v1"
    STATE_CONTRACT = "state.contract.v1"
    VISION_CONFIG = "vision.config.v1"
    VISION_EXTRACTION_STATUS = "vision_extraction.status.v1"


class PermissionName:
    MODEL_CALL = "model.call"
    MEMORY_WRITE = "memory.write"
    PROJECT_READ = "project.read"
    SCREEN_OBSERVE = "screen.observe"
    VISION_EXTRACT = "vision.extract"
    VOICE_LISTEN = "voice.listen"
    VOICE_SPEAK = "voice.speak"
    EXTERNAL_HTTP = "external.http"
    EXTERNAL_WEBSOCKET = "external.websocket"
    EXTERNAL_LAN = "external.lan"
    EXTERNAL_OSC = "external.osc"
    FILES_WRITE = "files.write"
    INPUT_CONTROL = "input.control"
    PROCESS_RUN = "process.run"
    VR_OUTPUT = "vr.output"


class EventType:
    USER_COMMAND_SUBMITTED = "user.command.submitted"
    PET_STATE_CHANGED = "pet.state.changed"
    PET_BUBBLE_SHOW = "pet.bubble.show"
    PET_BUBBLE_CLEAR = "pet.bubble.clear"
    REASONING_STARTED = "reasoning.started"
    REASONING_STEP_COMPLETED = "reasoning.step.completed"
    REASONING_OUTPUT_PRODUCED = "reasoning.output.produced"
    REASONING_SCHEMA_INVALID = "reasoning.schema.invalid"
    REASONING_REPAIR_REQUESTED = "reasoning.repair.requested"
    REASONING_FAILED = "reasoning.failed"
    SCREEN_OBSERVATION_ENABLED = "screen.observation.enabled"
    SCREEN_OBSERVATION_DISABLED = "screen.observation.disabled"
    SYSTEM_HELLO = "system.hello"
