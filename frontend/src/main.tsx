import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

declare global {
  interface Window {
    yChat?: {
      showBubble: (text: string) => Promise<void>;
      hideBubble: () => Promise<void>;
      submitCommand: (text: string) => Promise<CommandSubmitResult>;
      hideCommand: () => Promise<void>;
      setPetMouseIgnored: (ignored: boolean) => Promise<void>;
      beginPetWindowDrag: () => Promise<void>;
      dragPetWindow: () => Promise<void>;
      endPetWindowDrag: () => Promise<void>;
      notifyPetClicked: () => Promise<void>;
      getEventHistoryStatus: () => Promise<EventHistoryStatus>;
      getScreenObservationStatus: () => Promise<ScreenObservationStatus>;
      startScreenObservation: (options: ScreenObservationStartOptions) => Promise<ScreenObservationToggleResult>;
      stopScreenObservation: (options?: ScreenObservationStopOptions) => Promise<ScreenObservationToggleResult>;
      onScreenObservationStatus: (handler: (status: ScreenObservationStatus) => void) => () => void;
      onBubbleText: (handler: (text: string) => void) => () => void;
      onBubbleInterrupt: (handler: () => void) => () => void;
      onPetState: (handler: (state: string) => void) => () => void;
      onDebugEvents: (handler: (events: DebugEvent[]) => void) => () => void;
      onDebugState: (handler: (state: string) => void) => () => void;
      onCommandFocus: (handler: () => void) => () => void;
    };
  }
}

type DebugEvent = {
  event_id?: string;
  type?: string;
  source?: string;
  timestamp?: string;
  correlation_id?: string | null;
  payload?: Record<string, unknown>;
  payload_redacted?: boolean;
  raw_payload_stored_in_event?: boolean;
};

type EventHistoryStatus = {
  path: string;
  exists: boolean;
  bytes: number;
  persisted_limit: number;
  recent_limit: number;
  total_lines: number;
  recent_loaded: number;
  recent_types: string[];
  source_counts: Record<string, number>;
  modality_counts: Record<string, number>;
  error?: string;
};

type ScreenObservationFrame = {
  captured_at?: string;
  event_id?: string | null;
  evidence_status?: string;
  evidence_id?: string | null;
  attachment_id?: string | null;
  raw_ref?: string;
  sha256?: string;
  width?: number;
  height?: number;
  size_bytes?: number;
  source_display_width?: number;
  source_display_height?: number;
  thumbnail_max_width?: number;
  mime?: string;
  jpeg_quality?: number;
  capture_duration_ms?: number;
  capture_stage_durations_ms?: Record<string, number>;
  persist_duration_ms?: number | null;
  persist_stage_durations_ms?: Record<string, number> | null;
  raw_available?: boolean;
  vision_reader_status?: string;
  raw_payload_returned?: boolean;
};

type ScreenObservationStatus = {
  schema_version: string;
  enabled: boolean;
  active: boolean;
  permission: string;
  permission_enabled: boolean;
  requires_secondary_confirmation: boolean;
  display: string;
  full_frame: boolean;
  interval_seconds: number;
  base_interval_seconds?: number;
  max_interval_seconds?: number;
  adaptive_interval_seconds?: number;
  retain_raw: boolean;
  pressure_mode: boolean;
  queue_pressure_seconds: number;
  samples_captured: number;
  samples_skipped?: number;
  samples_timed_out?: number;
  samples_queued?: number;
  samples_persisted?: number;
  samples_dropped?: number;
  samples_extraction_queued?: number;
  samples_extracted?: number;
  samples_extraction_failed?: number;
  samples_extraction_dropped?: number;
  last_capture_duration_ms?: number | null;
  last_capture_stage_durations_ms?: Record<string, number> | null;
  last_evidence_persist_duration_ms?: number | null;
  last_evidence_persist_stage_durations_ms?: Record<string, number> | null;
  evidence_queue_length?: number;
  evidence_queue_busy?: boolean;
  evidence_queue_limit?: number;
  evidence_min_interval_ms?: number;
  extraction_queue_length?: number;
  extraction_queue_busy?: boolean;
  extraction_queue_limit?: number;
  extraction_min_interval_ms?: number;
  extraction_pressure_threshold_seconds?: number;
  extraction_pressure_mode?: boolean;
  extraction_pressure_state?: string;
  extraction_pressure_reason?: string;
  extraction_estimated_backlog_ms?: number;
  extraction_oldest_queued_ms?: number | null;
  extraction_running_ms?: number | null;
  last_extraction_duration_ms?: number | null;
  last_extraction_provider?: string | null;
  last_extraction_model?: string | null;
  last_extraction_status?: string | null;
  last_extraction_evidence_id?: string | null;
  extraction_current_evidence_id?: string | null;
  last_extraction_feature_id?: string | null;
  last_extraction_error?: string | null;
  last_extraction_queued_at?: string | null;
  last_extraction_started_at?: string | null;
  last_extraction_finished_at?: string | null;
  last_extraction_pressure_at?: string | null;
  last_extraction_recovered_at?: string | null;
  last_extraction_dropped_at?: string | null;
  capture_avg_duration_ms?: number | null;
  capture_max_duration_ms?: number | null;
  capture_history_count?: number;
  adaptive_pressure_mode?: boolean;
  adaptive_reason?: string;
  last_skip_reason?: string | null;
  last_skip_at?: string | null;
  last_timeout_at?: string | null;
  active_capture_requests?: number;
  last_drop_reason?: string | null;
  last_drop_at?: string | null;
  max_thumbnail_width?: number;
  capture_mime?: string;
  jpeg_quality?: number;
  capture_backend?: string;
  last_frame: ScreenObservationFrame | null;
  last_error?: string | null;
  last_audit_id?: string | null;
  blocked_reasons: string[];
  raw_payload_in_events: boolean;
  raw_payload_in_provider_prompt: boolean;
  raw_payload_returned_in_debug: boolean;
};

type ScreenObservationContract = {
  schema_version: string;
  read_only: boolean;
  permission: string;
  requires_secondary_confirmation: boolean;
  display: string;
  full_frame: boolean;
  interval_seconds: number;
  base_interval_seconds?: number;
  max_interval_seconds?: number;
  sampling_cadence?: string;
  overrun_policy?: string;
  adaptive_policy?: Record<string, unknown>;
  retain_raw_default: boolean;
  raw_backup_path: string;
  event_payload_policy: string;
  provider_prompt_policy: string;
  pressure_threshold_seconds: number;
  rules: string[];
};

type ScreenObservationStartOptions = {
  secondary_confirmed: boolean;
  retain_raw: boolean;
  sample_once?: boolean;
};

type ScreenObservationStopOptions = {
  revoke_permission?: boolean;
};

type ScreenObservationToggleResult = {
  ok: boolean;
  already_active?: boolean;
  backend?: Record<string, unknown>;
  status?: ScreenObservationStatus;
};

type CommandSubmitResult = {
  ok: boolean;
  error?: string;
};

const COMMAND_HISTORY_LIMIT = 20;

const DEBUG_NAV_LABELS: Record<string, string> = {
  Overview: "总览",
  Reasoning: "推理",
  Model: "模型/API",
  "Local Model": "本地模型",
  Events: "事件",
  Memory: "记忆",
  Screen: "屏幕观察",
  History: "历史",
  Permissions: "权限",
  "Project Read": "项目读取",
  External: "外部接口",
  Visual: "视觉",
  Logs: "日志",
  Voice: "语音",
  "VR/OSC": "VR/OSC"
};

function yesNo(value: boolean | undefined | null): string {
  return value ? "是" : "否";
}

function onOff(value: boolean | undefined | null): string {
  return value ? "开" : "关";
}

function readyBlocked(value: boolean | undefined | null): string {
  return value ? "就绪" : "未就绪";
}

function zhScreenValue(value: unknown): string {
  const text = String(value ?? "");
  const map: Record<string, string> = {
    primary: "主屏幕",
    adaptive: "自动调整",
    steady: "稳定",
    busy: "忙碌",
    pressure: "压力中",
    recovering: "恢复中",
    queued: "已排队",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    persisted: "已入库",
    metadata_only: "仅元数据",
    extracted: "已抽取",
    "estimated backlog over threshold": "预计积压超过阈值",
    "current extraction over threshold": "当前抽取超过阈值",
    "last extraction failed": "上次抽取失败",
    "queued or running": "排队或运行中",
    "backlog recovered": "积压已恢复"
  };
  return map[text] ?? text;
}

function optionalMs(value: number | null | undefined): string {
  return typeof value === "number" ? `${value}ms` : "n/a";
}

function optionalTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleTimeString() : "无";
}

type PermissionStatus = {
  permissions: Record<string, boolean>;
  enabled: string[];
  disabled: string[];
  contract_endpoint?: string;
  details?: PermissionDetail[];
};

type PermissionDetail = {
  name: string;
  enabled: boolean;
  group: string;
  risk: string;
  requires_secondary_confirmation: boolean;
  reason: string;
};

type PermissionContract = {
  schema_version: string;
  read_only: boolean;
  mutation_enabled: boolean;
  config_write_enabled: boolean;
  audit_required_for_sensitive_changes: boolean;
  secondary_confirmation_required_for: string[];
  sensitive_capabilities: string[];
  sensitive_enabled: string[];
  blocked_until_explicit_user_selection: string[];
  rules: ContractRule[];
  capabilities: Array<PermissionDetail & { default_enabled: boolean }>;
};

type EventContract = {
  schema_version: string;
  read_only: boolean;
  diagnostic_payload_redaction?: {
    enabled: boolean;
    token: string;
    multimodal_token: string;
    patterns: string[];
    display_cleanup: string[];
    safe_ref_fields_preserved: string[];
  };
  envelope: Array<{ name: string; required: boolean; detail: string }>;
  accepted_sources: string[];
  active_ingress: Array<{
    route: string;
    scope: string;
    external: boolean;
    accepts_raw_capture: boolean;
  }>;
  active_event_types: string[];
  inactive_adapters: string[];
  blocked_until_enabled: string[];
  safety_rules: ContractRule[];
};

type StateContract = {
  schema_version: string;
  read_only: boolean;
  event_type: string;
  payload_fields: Array<{ name: string; required: boolean; detail: string }>;
  implemented_states: Array<{
    name: string;
    implemented: boolean;
    source: string;
    detail: string;
  }>;
  reserved_states: string[];
  state_sources: string[];
  rules: ContractRule[];
  blocked_until_explicit_design: string[];
};

type ContractsIndex = {
  schema_version: string;
  read_only: boolean;
  mutation_enabled: boolean;
  entries: Array<{
    name: string;
    endpoint: string;
    status: string;
    risk_scope: string;
  }>;
  status_endpoints: string[];
  blocked_until_explicit_user_selection: string[];
};

type ContractRule = {
  name: string;
  enabled: boolean;
  detail: string;
};

type ModelProviderStatus = {
  enabled: boolean;
  active_provider: string;
  model: string;
  configured: boolean;
};

type ModelProviderConfig = {
  enabled_requested: boolean;
  permission_allowed: boolean;
  effective_enabled: boolean;
  active_provider: string;
  real_model_calls: boolean;
  read_only: boolean;
  call_route?: string;
  call_url?: string;
  blocked_reasons?: string[];
  next_requirements?: string[];
  save_endpoint?: string;
  real_call_test_endpoint?: string;
  recommended_models?: Record<string, string[]>;
  cadence?: ModelProviderCadenceStatus;
  providers: Record<
    string,
    {
      base_url: string;
      model: string;
      temperature: number | null;
      stream: boolean;
      timeout_seconds?: number;
      max_tokens?: number;
      thinking_type?: string;
      api_key_configured: boolean;
      api_key_masked: string;
    }
  >;
};

type ModelProviderValidationResult = {
  ok: boolean;
  saved: boolean;
  enabled?: boolean;
  real_model_calls: boolean;
  requires_secondary_confirmation_for_save: boolean;
  audit_id: string;
  candidate: Record<string, unknown>;
  errors: string[];
  warnings: string[];
};

type ModelProviderAudit = {
  audits: Array<{
    audit_id: string;
    status: string;
    created_at: string;
    payload?: Record<string, unknown>;
  }>;
};

type ModelProviderReadiness = {
  ready: boolean;
  will_call_model_on_next_reasoning_run: boolean;
  call_route: string;
  active_provider: string;
  blocked_reasons: string[];
  cadence?: ModelProviderCadenceStatus;
  redacted: boolean;
  dry_run_only: boolean;
  api_key_returned: boolean;
};

type ModelProviderCadenceScope = {
  scope: string;
  min_interval_seconds: number;
  purpose: string;
  high_frequency_allowed: boolean;
  active: boolean;
  allowed_now: boolean;
  retry_after_seconds: number;
  seconds_since_last_start: number | null;
  started_count: number;
  blocked_count: number;
  last_provider?: string | null;
  last_model?: string | null;
  last_ok?: boolean | null;
  last_elapsed_ms?: number | null;
  last_error_type?: string | null;
  last_blocked_reason?: string | null;
  last_blocked_retry_after_seconds?: number | null;
};

type ModelProviderCadenceStatus = {
  schema_version: string;
  policy: {
    schema_version: string;
    role: string;
    deepseek_role: string;
    high_frequency_inputs: string;
    provider_receives: string;
    provider_must_not_receive: string[];
    coalescing_required_before_api: boolean;
    scopes: Record<string, Record<string, unknown>>;
  };
  scopes: Record<string, ModelProviderCadenceScope>;
  api_key_returned: boolean;
  raw_payload_returned: boolean;
};

type ModelProviderTestResult = {
  ok: boolean;
  called: boolean;
  provider?: string;
  model?: string;
  status_code?: number | null;
  elapsed_ms?: number;
  content_chars?: number;
  json_object?: Record<string, unknown> | null;
  error_type?: string | null;
  message?: string;
  audit_id?: string;
  api_key_returned: boolean;
};

type VisionExtractResult = {
  ok: boolean;
  called: boolean;
  evidence_id?: string;
  provider?: string;
  model?: string;
  elapsed_ms?: number;
  extraction?: Record<string, unknown>;
  feature_id?: string;
  consolidation_buffer_id?: string;
  message?: string;
  blocked_reasons?: string[];
};

type MemoryStatus = {
  enabled: boolean;
  items: Array<{ id: string; kind: string; text: string; created_at: string }>;
};

type FormalMemoryStatus = {
  manual_enabled: boolean;
  automatic_writes_enabled: boolean;
  capture_enabled: Record<string, boolean>;
  manual_items_count: number;
  records_count: number;
  observations_count: number;
  entities_count: number;
  features_count: number;
  links_count: number;
  review_count: number;
  consolidation_buffer_count: number;
  visual_evidence_count: number;
  text_evidence_count: number;
  audio_evidence_count: number;
  raw_backup_count: number;
  audit_count: number;
  formal_tables_ready: boolean;
  multimodal_tables_ready: boolean;
  visual_evidence_tables_ready: boolean;
  text_evidence_tables_ready: boolean;
  audio_evidence_tables_ready: boolean;
  consolidation_buffer_ready: boolean;
  manual_notes_legacy: boolean;
};

type FormalMemoryRecords = {
  automatic_writes_enabled: boolean;
  records: Array<{
    record_id: string;
    kind: string;
    layer: string;
    status: string;
    version: number;
    content?: Record<string, unknown>;
    evidence?: unknown[];
    created_at: string;
    updated_at: string;
  }>;
};

type MemoryReview = {
  automatic_writes_enabled: boolean;
  review_queue: Record<string, unknown>[];
};

type MemoryAudit = {
  automatic_writes_enabled: boolean;
  audit: Array<{
    audit_id?: string;
    record_id?: string | null;
    action?: string;
    created_at?: string;
    payload?: Record<string, unknown>;
  }>;
};

type MemoryContract = {
  unified_memory: boolean;
  scene_isolation_allowed: boolean;
  automatic_writes_enabled: boolean;
  real_capture_enabled: boolean;
  text_only_identity_allowed: boolean;
  deep_knowledge_default: boolean;
  layers: Array<{
    name: string;
    label: string;
    current_mode: string;
    writes_enabled: boolean;
    purpose: string;
    retention: string;
  }>;
  modalities: Array<{
    modality: string;
    capture_enabled: boolean;
    identity_body: string;
    text_is_auxiliary: boolean;
    required_feature_refs: string[];
    raw_backup: string;
    current_mode: string;
  }>;
  attachment_ref?: AttachmentRefContract;
  vision_reader?: VisionStatus;
  text_reader?: TextStatus;
  audio_reader?: AudioStatus;
  visual_evidence?: {
    schema_ready: boolean;
    writes_enabled: boolean;
    raw_bytes_returned: boolean;
    sources: string[];
    links_to: string[];
  };
  text_evidence?: {
    schema_ready: boolean;
    writes_enabled: boolean;
    raw_bytes_returned: boolean;
    sources: string[];
    links_to: string[];
  };
  audio_evidence?: {
    schema_ready: boolean;
    writes_enabled: boolean;
    raw_bytes_returned: boolean;
    sources: string[];
    links_to: string[];
  };
  consolidation_buffer?: {
    schema_ready: boolean;
    writes_enabled: boolean;
    sleep_consolidation_enabled: boolean;
    purpose: string;
  };
};

type MemoryShell = {
  automatic_writes_enabled: boolean;
  capture_enabled: Record<string, boolean>;
  observations: Record<string, unknown>[];
  entities: Record<string, unknown>[];
  features: Record<string, unknown>[];
  links: Record<string, unknown>[];
  review_queue: Record<string, unknown>[];
  consolidation_buffer: Record<string, unknown>[];
  raw_backups: Record<string, unknown>[];
  visual_evidence: Record<string, unknown>[];
  text_evidence: Record<string, unknown>[];
  audio_evidence: Record<string, unknown>[];
  attachment_ref_contract?: AttachmentRefContract;
  vision_reader?: VisionStatus;
  text_reader?: TextStatus;
  audio_reader?: AudioStatus;
};

type ConsolidationBufferStatus = {
  automatic_writes_enabled: boolean;
  sleep_consolidation_enabled: boolean;
  schema_ready: boolean;
  buffer: Record<string, unknown>[];
};

type AttachmentRefContract = {
  schema_version: string;
  raw_payload_allowed: boolean;
  supported_sources: string[];
  required_fields: string[];
  rules: string[];
};

type VisionStatus = {
  schema_version: string;
  enabled: boolean;
  mode: string;
  capture_enabled: boolean;
  screen_observation_enabled: boolean;
  auto_extract_manual_images: boolean;
  auto_extract_screen_frames: boolean;
  queue_pressure_seconds: number;
  pressure_mode: boolean;
  model_configured: boolean;
  embedding_model_configured: boolean;
  model_download_enabled: boolean;
  supported_statuses: string[];
  blocked_reasons: string[];
  visual_evidence_count?: number;
  pending_extractions?: number;
  attachment_ref_contract?: AttachmentRefContract;
  extraction?: {
    enabled: boolean;
    provider: string;
    model: string;
    blocked_reasons: string[];
  };
};

type TextStatus = {
  schema_version: string;
  enabled: boolean;
  mode: string;
  auto_observe_command_text: boolean;
  raw_payload_in_provider_prompt: boolean;
  supported_statuses: string[];
  blocked_reasons: string[];
  text_evidence_count?: number;
};

type AudioStatus = {
  schema_version: string;
  enabled: boolean;
  mode: string;
  capture_enabled: boolean;
  microphone_enabled: boolean;
  asr_configured: boolean;
  speaker_embedding_configured: boolean;
  model_download_enabled: boolean;
  supported_statuses: string[];
  blocked_reasons: string[];
  audio_evidence_count?: number;
  pending_transcripts?: number;
};

type LocalModelState = {
  name: string;
  modality: string;
  model_id: string;
  purpose: string;
  local_path: string;
  path_exists: boolean;
  downloaded: boolean;
  required_files: string[];
  missing_files: string[];
  packages: Record<string, boolean>;
  packages_ready: boolean;
  text_auxiliary_only: boolean;
};

type VisionReaderAdapterStatus = {
  schema_version: string;
  modality: string;
  role: string;
  adapter_boundary: string;
  api_swap_ready: boolean;
  independent_from: string[];
  deepseek_role: string;
  deepseek_receives_raw_images: boolean;
  scope: string[];
  text_auxiliary_only: boolean;
  image_generation_supported: boolean;
  image_generation_configured: boolean;
  excluded_capabilities: string[];
  cache_dir: string;
  active_adapters: Record<string, string>;
  ready: Record<string, boolean>;
  adapters: Record<string, unknown>;
  blocked_reasons: string[];
  download_commands: string[];
  raw_payload_returned: boolean;
  api_key_returned: boolean;
};

type AudioReaderAdapterStatus = {
  schema_version: string;
  modality: string;
  role: string;
  adapter_boundary: string;
  api_swap_ready: boolean;
  independent_from: string[];
  deepseek_role: string;
  deepseek_receives_raw_audio: boolean;
  scope: string[];
  text_auxiliary_only: boolean;
  cache_dir: string;
  active_adapters: Record<string, string>;
  ready: Record<string, boolean>;
  adapters: Record<string, unknown>;
  blocked_reasons: string[];
  download_commands: string[];
  raw_payload_returned: boolean;
  api_key_returned: boolean;
};

type LocalModelsStatus = {
  schema_version: string;
  cache_dir: string;
  download_enabled: boolean;
  download_requires_explicit_user_action: boolean;
  deepseek_role: string;
  vision_role: string;
  audio_role: string;
  adapter_boundary: string;
  independent_readers: Record<string, string>;
  vision_reader: VisionReaderAdapterStatus;
  audio_reader: AudioReaderAdapterStatus;
  image_generation_supported: boolean;
  image_generation_configured: boolean;
  models: Record<string, LocalModelState>;
  ready: Record<string, boolean>;
  blocked_reasons: string[];
  download_commands: string[];
  raw_payload_returned: boolean;
  api_key_returned: boolean;
};

type ProjectReaderStatus = {
  enabled: boolean;
  read_only?: boolean;
  allowed_roots: string[];
  roots?: Array<{
    index: number;
    path: string;
    exists: boolean;
    is_dir: boolean;
    listing_allowed: boolean;
    blocked_reason?: string | null;
  }>;
  text_extensions: string[];
  content_reading_enabled?: boolean;
  raw_content_return_enabled?: boolean;
  recursive_content_scan_enabled?: boolean;
  path_escape_blocking?: boolean;
  authorized_roots_required?: boolean;
  text_whitelist_required?: boolean;
  contract_endpoint?: string;
  listing_enabled?: boolean;
  blocked_reasons?: string[];
  safety_rules?: ProjectReaderSafetyRule[];
};

type ProjectReaderFiles = {
  items: Array<Record<string, unknown>>;
  detail?: string;
};

type ProjectReaderSafetyRule = {
  name: string;
  enabled: boolean;
  detail: string;
};

type ProjectReaderContract = {
  schema_version: string;
  read_only: boolean;
  permission_gate: string;
  config_gate: string;
  authorized_roots_required: boolean;
  text_whitelist_required: boolean;
  text_extensions: string[];
  content_reading_enabled: boolean;
  raw_content_return_enabled: boolean;
  recursive_content_scan_enabled: boolean;
  path_escape_blocking: boolean;
  listing_scope: string;
  path_policy: Record<string, string | boolean>;
  blocked_until_enabled: string[];
  safety_rules: ProjectReaderSafetyRule[];
};

type LogStatus = {
  redaction_enabled?: boolean;
  redaction_token?: string;
  redaction_patterns?: string[];
  display_cleanup?: string[];
  logs: Array<{
    name: string;
    kind: string;
    bytes: number;
    tail: string[];
    redacted_lines?: number;
    display_cleaned?: boolean;
  }>;
};

type ReasoningStatus = {
  enabled: boolean;
  provider: string;
  real_model_calls: boolean;
  provider_mode?: string;
  model_blocked_reasons?: string[];
  supported_input_modalities: string[];
  capture_enabled: Record<string, boolean>;
  capture_blocked_reasons?: Record<string, string>;
  write_paths?: Record<string, string>;
  runs_total: number;
  queue: { foreground_active: boolean; background_pending: number };
  current_run: ReasoningRunSummary | null;
};

type ReasoningContract = {
  schema_version: string;
  transport_may_stream: boolean;
  execution_requires_complete_json: boolean;
  repair_attempts: number;
  repair_policy: string;
  real_model_calls: boolean;
  provider_mode: string;
  top_level_required: string[];
  top_level_sections: Array<{
    name: string;
    required: string[];
    acceptance_rules: string[];
  }>;
  blocked_until_valid: string[];
  failure_events: string[];
};

type ReasoningRunSummary = {
  run_id: string;
  source_event_id?: string;
  event_type?: string;
  status: string;
  depth: string;
  provider: string;
  primary_modality?: string;
  modalities?: string[];
  created_at?: string;
  updated_at: string;
  reply_text?: string | null;
  failure_summary?: string | null;
};

type ReasoningStep = {
  step_id: string;
  step_index: number;
  step_type: string;
  status: string;
  summary: string;
  created_at: string;
};

type ReasoningContextSnapshot = {
  snapshot_id: string;
  schema_version: string;
  created_at: string;
  payload?: Record<string, unknown>;
};

type ReasoningCandidate = {
  candidate_id: string;
  target_layer: string;
  kind: string;
  confidence: number;
  accepted: number;
  created_at: string;
  payload?: Record<string, unknown>;
};

type ReasoningSchemaFailure = {
  failure_id: string;
  run_id: string;
  error: string;
  created_at: string;
};

type ReasoningAuditRecord = {
  audit_id: string;
  kind: string;
  status: string;
  created_at: string;
  candidate_id?: string | null;
  payload?: Record<string, unknown>;
};

type ReasoningActionRecord = {
  action_id: string;
  status: string;
  created_at: string;
  payload?: Record<string, unknown>;
};

type ReasoningPendingAction = {
  pending_id: string;
  action_id: string;
  status: string;
  created_at: string;
  payload?: Record<string, unknown>;
};

type ReasoningRunsResponse = {
  runs: ReasoningRunSummary[];
};

type ReasoningRunDetail = {
  run: ReasoningRunSummary;
  steps: ReasoningStep[];
  context_snapshots: ReasoningContextSnapshot[];
  schema_failures: ReasoningSchemaFailure[];
  memory_candidates: ReasoningCandidate[];
  actions: ReasoningActionRecord[];
  pending_actions: ReasoningPendingAction[];
  audit: ReasoningAuditRecord[];
};

type SnapshotPayload = Record<string, unknown> & {
  context_summary?: {
    current_event_ref_counts?: Record<string, number>;
    recent_visual_evidence_count?: number;
    recent_ocr_text_count?: number;
    recent_audio_evidence_count?: number;
    recent_audio_transcript_count?: number;
    has_current_event_text?: boolean;
    current_event_text_chars?: number;
    modality_context?: Record<string, unknown>;
  };
  current_event_refs?: {
    vision?: Record<string, unknown>[];
    audio?: Record<string, unknown>[];
    attachments?: Record<string, unknown>[];
    raw_payload_included?: boolean;
    absolute_local_paths_included?: boolean;
    ref_values_redacted?: boolean;
  };
  visual_context?: {
    recent_visual_evidence?: Record<string, unknown>[];
    recent_ocr_text?: Record<string, unknown>[];
    raw_image_bytes_included?: boolean;
    absolute_local_paths_included?: boolean;
    provider_must_not_claim_unparsed_images?: boolean;
  };
  audio_context?: {
    recent_audio_evidence?: Record<string, unknown>[];
    raw_audio_bytes_included?: boolean;
    absolute_local_paths_included?: boolean;
    provider_must_not_claim_unparsed_audio?: boolean;
  };
  raw_payload_stored?: boolean;
};

const BUBBLE_SEGMENT_LENGTH = 44;
const BUBBLE_SEGMENT_PAUSE_MS = 700;
const TEXT_PAYLOAD_KEYS = ["text", "message", "prompt", "command", "transcript", "ocr_text"];
const VISION_PAYLOAD_KEYS = [
  "image",
  "image_ref",
  "image_refs",
  "screenshot",
  "screenshot_ref",
  "frame_ref",
  "crop_ref",
  "ocr",
  "visual_features"
];
const AUDIO_PAYLOAD_KEYS = [
  "audio",
  "audio_ref",
  "audio_refs",
  "voice",
  "voice_ref",
  "waveform",
  "speaker_id",
  "audio_features"
];
const STATE_PAYLOAD_KEYS = ["state", "pet_state", "emotion", "animation"];
const PROJECT_PAYLOAD_KEYS = ["path", "file", "files", "root", "project", "workspace"];
const TRACE_ID_KEYS = new Set([
  "run_id",
  "step_id",
  "action_id",
  "candidate_id",
  "audit_id",
  "snapshot_id",
  "failure_id",
  "pending_id",
  "record_id",
  "entity_id",
  "observation_id",
  "source_event_id",
]);

type TraceRef = {
  label: string;
  value: string;
};

function segmentBubbleText(text: string): string[] {
  const normalized = text.trim();
  if (!normalized) return [];

  const paragraphs = normalized.split(/\n{2,}/);
  const segments: string[] = [];
  for (const paragraph of paragraphs) {
    let remaining = paragraph.trim();
    while (remaining.length > BUBBLE_SEGMENT_LENGTH) {
      let cut = remaining.lastIndexOf(" ", BUBBLE_SEGMENT_LENGTH);
      if (cut < 18) cut = BUBBLE_SEGMENT_LENGTH;
      segments.push(remaining.slice(0, cut).trim());
      remaining = remaining.slice(cut).trim();
    }
    if (remaining) segments.push(remaining);
  }
  return segments;
}

function currentWindowKind(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get("window") ?? "pet";
}

function addDebugModality(modalities: string[], modality: string) {
  if (!modalities.includes(modality)) modalities.push(modality);
}

function hasAnyPayloadKey(keys: Set<string>, expected: string[]) {
  return expected.some((key) => keys.has(key));
}

function inferDebugEventModalities(event: DebugEvent): string[] {
  const type = String(event.type ?? "").toLowerCase();
  const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
  const keys = new Set(Object.keys(payload).map((key) => key.toLowerCase()));
  const modalities: string[] = [];

  if (type.startsWith("user.command.") || type.startsWith("chat.") || type.startsWith("text.")) {
    addDebugModality(modalities, "text");
  }
  if (
    type.startsWith("screen.") ||
    type.startsWith("vision.") ||
    type.startsWith("visual.") ||
    type.startsWith("camera.") ||
    type.startsWith("ocr.")
  ) {
    addDebugModality(modalities, "vision");
  }
  if (
    type.startsWith("voice.") ||
    type.startsWith("audio.") ||
    type.startsWith("speech.") ||
    type.startsWith("microphone.")
  ) {
    addDebugModality(modalities, "audio");
  }
  if (type.startsWith("pet.state.")) addDebugModality(modalities, "state");
  if (type.startsWith("pet.model.")) addDebugModality(modalities, "interaction");
  if (type.startsWith("memory.")) addDebugModality(modalities, "memory");
  if (type.startsWith("project.")) addDebugModality(modalities, "project");
  if (type.startsWith("action.")) addDebugModality(modalities, "action");
  if (type.startsWith("debug.")) addDebugModality(modalities, "debug");
  if (type.startsWith("system.")) addDebugModality(modalities, "system");
  if (type.startsWith("error.")) addDebugModality(modalities, "error");
  if (type.startsWith("external.")) addDebugModality(modalities, "external");
  if (type.startsWith("vr.")) addDebugModality(modalities, "vr");

  if (hasAnyPayloadKey(keys, TEXT_PAYLOAD_KEYS)) addDebugModality(modalities, "text");
  if (hasAnyPayloadKey(keys, VISION_PAYLOAD_KEYS)) addDebugModality(modalities, "vision");
  if (hasAnyPayloadKey(keys, AUDIO_PAYLOAD_KEYS)) addDebugModality(modalities, "audio");
  if (hasAnyPayloadKey(keys, STATE_PAYLOAD_KEYS)) addDebugModality(modalities, "state");
  if (hasAnyPayloadKey(keys, PROJECT_PAYLOAD_KEYS)) addDebugModality(modalities, "project");

  return modalities.length > 0 ? modalities : ["event"];
}

function eventTimeLabel(event: DebugEvent): string {
  return event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "--:--";
}

function eventStableKey(event: DebugEvent, index: number): string {
  return event.event_id ?? `${event.type ?? "event"}-${event.timestamp ?? "no-time"}-${index}`;
}

function addTraceRef(refs: TraceRef[], seen: Set<string>, label: string, value: unknown) {
  if (refs.length >= 12) return;
  if (typeof value !== "string" && typeof value !== "number") return;
  const text = String(value);
  if (!text) return;
  const key = `${label}:${text}`;
  if (seen.has(key)) return;
  seen.add(key);
  refs.push({ label, value: text });
}

function collectPayloadTraceRefs(value: unknown, refs: TraceRef[], seen: Set<string>, depth = 0) {
  if (refs.length >= 12 || depth > 3 || !value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    for (const item of value.slice(0, 8)) collectPayloadTraceRefs(item, refs, seen, depth + 1);
    return;
  }

  for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
    if (TRACE_ID_KEYS.has(key)) addTraceRef(refs, seen, key, entry);
    collectPayloadTraceRefs(entry, refs, seen, depth + 1);
  }
}

function eventTraceRefs(event: DebugEvent): TraceRef[] {
  const refs: TraceRef[] = [];
  const seen = new Set<string>();
  addTraceRef(refs, seen, "event_id", event.event_id);
  addTraceRef(refs, seen, "correlation_id", event.correlation_id ?? undefined);
  collectPayloadTraceRefs(event.payload ?? {}, refs, seen);
  return refs;
}

function shortTraceValue(value: string): string {
  if (value.length <= 18) return value;
  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function snapshotPayload(payload?: Record<string, unknown>): SnapshotPayload {
  return (payload ?? {}) as SnapshotPayload;
}

function snapshotCount(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function snapshotFlag(value: unknown): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  return "unknown";
}

function compactRefValue(item: Record<string, unknown>): string {
  const value =
    item.ref ??
    item.raw_ref ??
    item.evidence_id ??
    item.attachment_id ??
    item.feature_id ??
    item.observation_id ??
    "";
  return String(value || "").trim() || "(metadata)";
}

function compactEvidenceTitle(item: Record<string, unknown>, fallback: string): string {
  return String(item.evidence_id ?? item.source ?? item.feature_id ?? fallback);
}

function compactEvidenceMeta(item: Record<string, unknown>): string {
  const parts = [
    item.source,
    item.vision_reader_status ?? item.audio_reader_status,
    item.mime,
    typeof item.duration_ms === "number" ? `${item.duration_ms}ms` : null,
    item.raw_available === false ? "raw unavailable" : null
  ].filter(Boolean);
  return parts.map(String).join(" / ") || "metadata";
}

function reservedModulePlan(view: string) {
  const plans: Record<
    string,
    {
      title: string;
      capabilities: string[];
      mode: string;
      blocked: string[];
      required: string[];
      events: string[];
    }
  > = {
    External: {
      title: "External Adapters",
      capabilities: ["external.http", "external.websocket", "external.lan", "external.osc"],
      mode: "adapter shell only",
      blocked: ["external permissions are off", "no adapter registry", "no outbound network route"],
      required: ["capability audit", "adapter allowlist", "data redaction policy"],
      events: ["external.request.proposed", "external.response.received", "external.adapter.failed"]
    },
    Voice: {
      title: "Voice",
      capabilities: ["voice.listen", "voice.speak"],
      mode: "capture and output off",
      blocked: ["microphone permission is off", "speech output permission is off", "ASR/TTS route not selected"],
      required: ["voice permission confirmation", "ASR/TTS provider choice", "audio memory feature policy"],
      events: ["voice.input.detected", "voice.transcript.created", "voice.output.started"]
    },
    Screen: {
      title: "Screen Perception",
      capabilities: ["screen.observe"],
      mode: "observation off",
      blocked: ["screen observation permission is off", "screenshot/OCR/VLM capture not implemented"],
      required: ["secondary confirmation", "local raw backup policy", "VisionReader extraction path"],
      events: ["screen.observation.enabled", "screen.observation.captured", "vision.import.created"]
    },
    "VR/OSC": {
      title: "VR / OSC",
      capabilities: ["vr.output", "external.osc"],
      mode: "output adapter off",
      blocked: ["VR output permission is off", "OSC adapter permission is off", "no external target configured"],
      required: ["target allowlist", "secondary confirmation", "action audit trail"],
      events: ["vr.output.proposed", "external.osc.sent", "vr.adapter.failed"]
    }
  };
  return plans[view];
}

function useBackendStatus(refreshKey = 0) {
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    let cancelled = false;
    setStatus("checking");
    fetch("http://127.0.0.1:18080/health")
      .then((response) => response.json())
      .then((data) => {
        if (!cancelled) setStatus(data.status === "ok" ? "backend ok" : "backend unknown");
      })
      .catch(() => {
        if (!cancelled) setStatus("backend offline");
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return status;
}

function usePermissionStatus(refreshKey = 0) {
  const [status, setStatus] = useState<PermissionStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus(null);
    fetch("http://127.0.0.1:18080/permissions/status")
      .then((response) => response.json())
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return status;
}

function useJsonStatus<T>(path: string, refreshKey = 0) {
  const [status, setStatus] = useState<T | null>(null);

  useEffect(() => {
    let cancelled = false;
    setStatus(null);
    fetch(`http://127.0.0.1:18080${path}`)
      .then((response) => response.json())
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [path, refreshKey]);

  return status;
}

function screenFramePreviewUrl(rawRef?: string) {
  if (!rawRef?.startsWith("runtime://")) return null;
  return `http://127.0.0.1:18080/screen/observation/preview?raw_ref=${encodeURIComponent(rawRef)}`;
}

function PetCanvas({
  petState,
  onLocalState
}: {
  petState: string;
  onLocalState?: (state: string | null) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [pose, setPose] = useState(0);
  const mouseIgnoredRef = useRef(true);
  const dragRef = useRef<{
    active: boolean;
    moved: boolean;
    startX: number;
    startY: number;
  }>({ active: false, moved: false, startX: 0, startY: 0 });

  function setMouseIgnored(ignored: boolean) {
    if (mouseIgnoredRef.current === ignored) return;
    mouseIgnoredRef.current = ignored;
    window.yChat?.setPetMouseIgnored(ignored);
  }

  function endDrag(clientX?: number, clientY?: number) {
    const wasDragging = dragRef.current.active;
    if (wasDragging && !dragRef.current.moved) {
      window.yChat?.notifyPetClicked();
    }
    dragRef.current.active = false;
    if (wasDragging) onLocalState?.(null);
    window.yChat?.endPetWindowDrag();

    if (clientX === undefined || clientY === undefined) {
      setMouseIgnored(true);
      return;
    }

    if (wasDragging) {
      setMouseIgnored(true);
      window.requestAnimationFrame(() => {
        setMouseIgnored(!isVisiblePixel(clientX, clientY));
      });
      return;
    }

    setMouseIgnored(!isVisiblePixel(clientX, clientY));
  }

  function isVisiblePixel(clientX: number, clientY: number): boolean {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return false;

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor(((clientX - rect.left) / rect.width) * canvas.width);
    const y = Math.floor(((clientY - rect.top) / rect.height) * canvas.height);
    if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) return false;

    return ctx.getImageData(x, y, 1, 1).data[3] >= 12;
  }

  useEffect(() => {
    const timer = window.setInterval(() => setPose((value) => (value + 1) % 60), 120);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const handleMouseUp = () => endDrag();
    const handleBlur = () => endDrag();
    window.addEventListener("mouseup", handleMouseUp);
    window.addEventListener("blur", handleBlur);
    return () => {
      window.removeEventListener("mouseup", handleMouseUp);
      window.removeEventListener("blur", handleBlur);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const isThinking = petState === "thinking";
    const isTalking = petState === "talking";
    const isDragging = petState === "dragging";
    const isReading = petState === "reading";
    const isError = petState === "error";
    const bob = isDragging ? 0 : isThinking ? pose % 20 < 10 ? 0 : 1 : pose < 30 ? 0 : 1;
    const blink = isTalking ? false : pose % 42 > 37;
    const scale = 3;

    ctx.save();
    ctx.scale(scale, scale);
    ctx.translate(20 + (isDragging && pose % 12 < 6 ? 1 : 0), 12 + bob);

    // Shadow
    ctx.fillStyle = "rgba(31, 27, 38, 0.28)";
    ctx.fillRect(32, 88, 44, 5);

    // Hair back
    ctx.fillStyle = "#5b5b8f";
    ctx.fillRect(28, 24, 52, 48);
    ctx.fillRect(24, 40, 10, 36);
    ctx.fillRect(74, 40, 10, 36);

    // Body
    ctx.fillStyle = "#f3f1ff";
    ctx.fillRect(38, 62, 32, 30);
    ctx.fillStyle = "#8fb7ff";
    ctx.fillRect(34, 78, 40, 12);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(42, 66, 8, 18);
    ctx.fillRect(58, 66, 8, 18);

    // Head
    ctx.fillStyle = "#ffe7da";
    ctx.fillRect(32, 24, 44, 34);
    ctx.fillRect(36, 18, 36, 10);

    // Hair front
    ctx.fillStyle = "#f9f3ff";
    ctx.fillRect(30, 18, 46, 12);
    ctx.fillRect(34, 28, 8, 18);
    ctx.fillRect(48, 24, 8, 16);
    ctx.fillRect(62, 28, 8, 18);

    // Eyes
    ctx.fillStyle = "#2f376b";
    if (blink) {
      ctx.fillRect(40, 42, 8, 2);
      ctx.fillRect(60, 42, 8, 2);
    } else {
      ctx.fillRect(41, 38, 6, 8);
      ctx.fillRect(61, 38, 6, 8);
      ctx.fillStyle = "#b9d4ff";
      ctx.fillRect(43, 39, 2, 2);
      ctx.fillRect(63, 39, 2, 2);
    }

    // Mouth
    ctx.fillStyle = "#b56b7a";
    if (isTalking && pose % 12 < 6) {
      ctx.fillRect(51, 49, 7, 4);
    } else if (isThinking) {
      ctx.fillRect(53, 50, 3, 2);
    } else if (isError) {
      ctx.fillRect(51, 50, 3, 2);
      ctx.fillRect(56, 50, 3, 2);
    } else {
      ctx.fillRect(52, 50, 5, 2);
    }

    // Arms
    ctx.fillStyle = "#ffe7da";
    ctx.fillRect(30, 66, 8, 18);
    ctx.fillRect(70, 66, 8, 18);
    ctx.fillStyle = "#f3f1ff";
    ctx.fillRect(28, 62, 10, 18);
    ctx.fillRect(70, 62, 10, 18);

    if (isReading) {
      ctx.fillStyle = "#2c2740";
      ctx.fillRect(37, 73, 34, 16);
      ctx.fillStyle = "#7ed7a8";
      ctx.fillRect(39, 75, 14, 12);
      ctx.fillStyle = "#fff7d1";
      ctx.fillRect(55, 75, 14, 12);
      ctx.fillStyle = "#2c2740";
      ctx.fillRect(53, 74, 3, 15);
      ctx.fillRect(42, 78, 7, 2);
      ctx.fillRect(59, 78, 7, 2);
      ctx.fillStyle = "#ffe7da";
      ctx.fillRect(30, 82, 8, 5);
      ctx.fillRect(70, 82, 8, 5);
    }

    // Legs
    ctx.fillStyle = "#ffe7da";
    ctx.fillRect(43, 90, 8, 15);
    ctx.fillRect(58, 90, 8, 15);
    ctx.fillStyle = "#6f8ed8";
    ctx.fillRect(40, 104, 12, 5);
    ctx.fillRect(57, 104, 12, 5);

    // Star accessory
    ctx.fillStyle = "#ffe08a";
    ctx.fillRect(70, 24, 4, 4);
    ctx.fillRect(68, 26, 8, 2);
    ctx.fillRect(71, 22, 2, 8);

    if (isThinking) {
      ctx.fillStyle = "#2c2740";
      ctx.fillRect(24, 20, 5, 5);
      ctx.fillRect(18, 14, 4, 4);
      ctx.fillRect(14, 8, 3, 3);
      ctx.fillStyle = "#fffdf4";
      ctx.fillRect(25, 21, 3, 3);
      ctx.fillRect(19, 15, 2, 2);
      ctx.fillRect(15, 9, 1, 1);
    }

    if (isTalking) {
      ctx.fillStyle = "#2c2740";
      ctx.fillRect(80, 44, 6, 3);
      ctx.fillRect(84, 39, 4, 3);
      ctx.fillRect(84, 51, 4, 3);
      ctx.fillStyle = "#ffd65e";
      ctx.fillRect(81, 45, 4, 1);
      ctx.fillRect(85, 40, 2, 1);
      ctx.fillRect(85, 52, 2, 1);
    }

    if (isDragging) {
      ctx.fillStyle = "#2c2740";
      ctx.fillRect(24, 58, 6, 4);
      ctx.fillRect(78, 58, 6, 4);
      ctx.fillRect(26, 54, 2, 12);
      ctx.fillRect(80, 54, 2, 12);
      ctx.fillStyle = "#8be1ff";
      ctx.fillRect(26, 59, 3, 1);
      ctx.fillRect(79, 59, 3, 1);
    }

    if (isError) {
      ctx.fillStyle = "#2c2740";
      ctx.fillRect(78, 16, 10, 24);
      ctx.fillStyle = "#ff6b72";
      ctx.fillRect(81, 19, 4, 13);
      ctx.fillRect(81, 35, 4, 3);
    }

    ctx.restore();
  }, [pose, petState]);

  return (
    <canvas
      ref={canvasRef}
      width={360}
      height={360}
      className="pet-canvas"
      onPointerMove={(event) => {
        if (dragRef.current.active) {
          const totalDx = event.screenX - dragRef.current.startX;
          const totalDy = event.screenY - dragRef.current.startY;
          dragRef.current.moved =
            dragRef.current.moved || Math.abs(totalDx) + Math.abs(totalDy) > 2;
          window.yChat?.dragPetWindow();
          return;
        }

        setMouseIgnored(!isVisiblePixel(event.clientX, event.clientY));
      }}
      onPointerLeave={() => {
        if (!dragRef.current.active) setMouseIgnored(true);
      }}
      onPointerDown={(event) => {
        if (!isVisiblePixel(event.clientX, event.clientY)) {
          setMouseIgnored(true);
          return;
        }

        event.currentTarget.setPointerCapture(event.pointerId);
        dragRef.current = {
          active: true,
          moved: false,
          startX: event.screenX,
          startY: event.screenY
        };
        window.yChat?.beginPetWindowDrag();
        onLocalState?.("dragging");
        setMouseIgnored(false);
      }}
      onPointerUp={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
          event.currentTarget.releasePointerCapture(event.pointerId);
        }
        endDrag(event.clientX, event.clientY);
      }}
      onPointerCancel={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
          event.currentTarget.releasePointerCapture(event.pointerId);
        }
        endDrag();
      }}
    />
  );
}

function BubbleOverlay() {
  const [segments, setSegments] = useState<string[]>([]);
  const [segmentIndex, setSegmentIndex] = useState(0);
  const [visibleText, setVisibleText] = useState("");
  const [runId, setRunId] = useState(0);
  const interruptRef = useRef(0);

  useEffect(() => {
    const offText = window.yChat?.onBubbleText((nextText) => {
      const nextSegments = segmentBubbleText(nextText);
      interruptRef.current += 1;
      setSegments(nextSegments);
      setSegmentIndex(0);
      setVisibleText("");
      setRunId((value) => value + 1);
    });
    const offInterrupt = window.yChat?.onBubbleInterrupt(() => {
      interruptRef.current += 1;
      setSegments([]);
      setSegmentIndex(0);
      setVisibleText("");
    });
    return () => {
      offText?.();
      offInterrupt?.();
    };
  }, []);

  useEffect(() => {
    const text = segments[segmentIndex] ?? "";
    if (!text) return;

    const interruptId = interruptRef.current;
    let index = 0;
    const timer = window.setInterval(() => {
      if (interruptRef.current !== interruptId) {
        window.clearInterval(timer);
        return;
      }

      index += 1;
      setVisibleText(text.slice(0, index));
      if (index >= text.length) {
        window.clearInterval(timer);
        if (segmentIndex < segments.length - 1) {
          window.setTimeout(() => {
            if (interruptRef.current !== interruptId) return;
            setVisibleText("");
            setSegmentIndex((value) => value + 1);
          }, BUBBLE_SEGMENT_PAUSE_MS);
        }
      }
    }, 28);
    return () => window.clearInterval(timer);
  }, [segments, segmentIndex, runId]);

  if (segments.length === 0) return null;

  return (
    <div className="pet-bubble-layer" aria-live="polite">
      <div className="pixel-bubble">
        <div className="bubble-title">Y_Chat</div>
        <div className="bubble-text">{visibleText}</div>
      </div>
    </div>
  );
}

function PetWindow() {
  const [backendPetState, setBackendPetState] = useState("idle");
  const [localPetState, setLocalPetState] = useState<string | null>(null);
  const petState = localPetState ?? backendPetState;

  useEffect(() => {
    window.yChat?.setPetMouseIgnored(true);
    const offPetState = window.yChat?.onPetState((state) => setBackendPetState(state));
    return () => {
      offPetState?.();
      window.yChat?.setPetMouseIgnored(true);
    };
  }, []);

  return (
    <main className="pet-window">
      <div className="pet-state-badge" data-state={petState}>{petState}</div>
      <BubbleOverlay />
      <div className="pet-hit-area" title="Y_Chat">
        <PetCanvas petState={petState} onLocalState={setLocalPetState} />
      </div>
    </main>
  );
}

function CommandWindow() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const composingRef = useRef(false);
  const historyRef = useRef<string[]>([]);
  const historyIndexRef = useRef<number | null>(null);
  const draftBeforeHistoryRef = useRef("");
  const [value, setValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusText, setStatusText] = useState("");

  useEffect(() => {
    const offFocus = window.yChat?.onCommandFocus(() => {
      window.setTimeout(() => inputRef.current?.focus(), 0);
    });
    window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => offFocus?.();
  }, []);

  function resetHistoryNavigation() {
    historyIndexRef.current = null;
    draftBeforeHistoryRef.current = "";
  }

  function rememberCommand(text: string) {
    const deduped = historyRef.current.filter((item) => item !== text);
    historyRef.current = [...deduped, text].slice(-COMMAND_HISTORY_LIMIT);
    resetHistoryNavigation();
  }

  function setInputValue(nextValue: string, options: { moveCaretToEnd?: boolean } = {}) {
    setValue(nextValue);
    if (statusText && statusText !== "Sending...") setStatusText("");
    if (options.moveCaretToEnd) {
      window.setTimeout(() => {
        const input = inputRef.current;
        if (!input) return;
        input.focus();
        input.setSelectionRange(nextValue.length, nextValue.length);
      }, 0);
    }
  }

  function recallPreviousCommand() {
    if (isSubmitting || historyRef.current.length === 0) return;
    const nextIndex =
      historyIndexRef.current === null
        ? historyRef.current.length - 1
        : Math.max(0, historyIndexRef.current - 1);
    if (historyIndexRef.current === null) draftBeforeHistoryRef.current = value;
    historyIndexRef.current = nextIndex;
    setInputValue(historyRef.current[nextIndex], { moveCaretToEnd: true });
  }

  function recallNextCommand() {
    if (isSubmitting || historyIndexRef.current === null) return;
    const nextIndex = historyIndexRef.current + 1;
    if (nextIndex >= historyRef.current.length) {
      historyIndexRef.current = null;
      setInputValue(draftBeforeHistoryRef.current, { moveCaretToEnd: true });
      draftBeforeHistoryRef.current = "";
      return;
    }
    historyIndexRef.current = nextIndex;
    setInputValue(historyRef.current[nextIndex], { moveCaretToEnd: true });
  }

  return (
    <main className="command-window">
      <form
        className="command-box"
        data-state={isSubmitting ? "submitting" : statusText ? "error" : value ? "active" : "idle"}
        onSubmit={async (event) => {
          event.preventDefault();
          const text = value.trim();
          if (!text || isSubmitting || composingRef.current) return;
          setIsSubmitting(true);
          setStatusText("Sending...");
          try {
            const result = await window.yChat?.submitCommand(text);
            if (result?.ok) {
              rememberCommand(text);
              setValue("");
              setStatusText("");
            } else {
              setStatusText(result?.error || "Command failed.");
            }
          } catch (error) {
            setStatusText(error instanceof Error ? error.message : "Command failed.");
          } finally {
            setIsSubmitting(false);
            window.setTimeout(() => inputRef.current?.focus(), 0);
          }
        }}
      >
        <input
          ref={inputRef}
          value={value}
          disabled={isSubmitting}
          onChange={(event) => {
            resetHistoryNavigation();
            setInputValue(event.target.value);
          }}
          onCompositionStart={() => {
            composingRef.current = true;
          }}
          onCompositionEnd={() => {
            composingRef.current = false;
          }}
          onKeyDown={(event) => {
            const isComposing =
              composingRef.current ||
              (event.nativeEvent as KeyboardEvent & { isComposing?: boolean }).isComposing;
            if (isComposing) {
              if (event.key === "Enter") event.preventDefault();
              return;
            }
            if (event.key === "ArrowUp") {
              event.preventDefault();
              recallPreviousCommand();
              return;
            }
            if (event.key === "ArrowDown") {
              event.preventDefault();
              recallNextCommand();
              return;
            }
            if (event.key === "Escape") {
              event.preventDefault();
              if (isSubmitting) return;
              setValue("");
              setStatusText("");
              resetHistoryNavigation();
              window.yChat?.hideCommand();
            }
          }}
          aria-label="Command"
          placeholder="Type to Y_Chat..."
        />
        {statusText ? <span className="command-status">{statusText}</span> : null}
        {value && !isSubmitting ? (
          <button
            type="button"
            className="command-clear"
            aria-label="Clear command"
            onClick={() => {
              setValue("");
              setStatusText("");
              resetHistoryNavigation();
              inputRef.current?.focus();
            }}
          >
            x
          </button>
        ) : null}
      </form>
    </main>
  );
}

function DebugWindow() {
  const [activeView, setActiveView] = useState("Overview");
  const [refreshKey, setRefreshKey] = useState(0);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [memoryView, setMemoryView] = useState("Overview");
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [memoryMessage, setMemoryMessage] = useState("");
  const [providerDraft, setProviderDraft] = useState({
    provider: "deepseek",
    base_url: "https://api.deepseek.com",
    model: "deepseek-v4-flash",
    api_key: "",
    temperature: "0.7",
    stream: false,
    timeout_seconds: "45",
    max_tokens: "1200",
    thinking_type: "disabled",
    use_for_vision: false,
    enabled_requested: false,
    secondary_confirmed: false
  });
  const [providerValidation, setProviderValidation] = useState<ModelProviderValidationResult | null>(null);
  const [providerTestResult, setProviderTestResult] = useState<ModelProviderTestResult | null>(null);
  const [visionExtractResult, setVisionExtractResult] = useState<VisionExtractResult | null>(null);
  const [providerAudit, setProviderAudit] = useState<ModelProviderAudit | null>(null);
  const [providerBusy, setProviderBusy] = useState(false);
  const [providerMessage, setProviderMessage] = useState("");
  const [screenStatus, setScreenStatus] = useState<ScreenObservationStatus | null>(null);
  const [screenBusy, setScreenBusy] = useState(false);
  const [screenMessage, setScreenMessage] = useState("");
  const [screenSecondaryConfirmed, setScreenSecondaryConfirmed] = useState(false);
  const [screenRetainRaw, setScreenRetainRaw] = useState(true);
  const backendStatus = useBackendStatus(refreshKey);
  const permissionStatus = usePermissionStatus(refreshKey);
  const permissionContract = useJsonStatus<PermissionContract>("/permissions/contract", refreshKey);
  const eventContract = useJsonStatus<EventContract>("/events/contract", refreshKey);
  const stateContract = useJsonStatus<StateContract>("/state/contract", refreshKey);
  const contractsIndex = useJsonStatus<ContractsIndex>("/contracts", refreshKey);
  const modelStatus = useJsonStatus<ModelProviderStatus>("/model/provider/status", refreshKey);
  const modelConfig = useJsonStatus<ModelProviderConfig>("/model/provider/config", refreshKey);
  const modelReadiness = useJsonStatus<ModelProviderReadiness>("/model/provider/readiness", refreshKey);
  const modelCadence = useJsonStatus<ModelProviderCadenceStatus>("/model/provider/cadence", refreshKey);
  const memoryStatus = useJsonStatus<MemoryStatus>("/memory", refreshKey);
  const formalMemoryStatus = useJsonStatus<FormalMemoryStatus>("/memory/status", refreshKey);
  const formalMemoryRecords = useJsonStatus<FormalMemoryRecords>("/memory/records", refreshKey);
  const memoryReview = useJsonStatus<MemoryReview>("/memory/review", refreshKey);
  const memoryAudit = useJsonStatus<MemoryAudit>("/memory/audit", refreshKey);
  const memoryContract = useJsonStatus<MemoryContract>("/memory/contract", refreshKey);
  const memoryShell = useJsonStatus<MemoryShell>("/memory/shell", refreshKey);
  const consolidationStatus = useJsonStatus<ConsolidationBufferStatus>("/memory/consolidation-buffer", refreshKey);
  const visionStatus = useJsonStatus<VisionStatus>("/vision/status", refreshKey);
  const textStatus = useJsonStatus<TextStatus>("/text/status", refreshKey);
  const audioStatus = useJsonStatus<AudioStatus>("/audio/status", refreshKey);
  const visionReaderStatus = useJsonStatus<VisionReaderAdapterStatus>("/vision/reader/status", refreshKey);
  const audioReaderStatus = useJsonStatus<AudioReaderAdapterStatus>("/audio/reader/status", refreshKey);
  const localModelsStatus = useJsonStatus<LocalModelsStatus>("/local-models/status", refreshKey);
  const backendScreenStatus = useJsonStatus<ScreenObservationStatus>("/screen/observation/status", refreshKey);
  const screenContract = useJsonStatus<ScreenObservationContract>("/screen/observation/contract", refreshKey);
  const projectReaderStatus = useJsonStatus<ProjectReaderStatus>("/project-reader/status", refreshKey);
  const projectReaderContract = useJsonStatus<ProjectReaderContract>("/project-reader/contract", refreshKey);
  const projectReaderFiles = useJsonStatus<ProjectReaderFiles>("/project-reader/files", refreshKey);
  const logStatus = useJsonStatus<LogStatus>("/logs/status", refreshKey);
  const reasoningStatus = useJsonStatus<ReasoningStatus>("/reasoning/status", refreshKey);
  const reasoningContract = useJsonStatus<ReasoningContract>("/reasoning/contract", refreshKey);
  const reasoningRuns = useJsonStatus<ReasoningRunsResponse>("/reasoning/runs", refreshKey);
  const [petState, setPetState] = useState("idle");
  const [events, setEvents] = useState<DebugEvent[]>([]);
  const [eventHistoryStatus, setEventHistoryStatus] = useState<EventHistoryStatus | null>(null);
  const [historySourceFilter, setHistorySourceFilter] = useState("all");
  const [historyModalityFilter, setHistoryModalityFilter] = useState("all");
  const [selectedHistoryEventId, setSelectedHistoryEventId] = useState<string | null>(null);
  const [selectedReasoningRunId, setSelectedReasoningRunId] = useState<string | null>(null);
  const [reasoningRunDetail, setReasoningRunDetail] = useState<ReasoningRunDetail | null>(null);
  const [reasoningStatusFilter, setReasoningStatusFilter] = useState("all");
  const [reasoningModalityFilter, setReasoningModalityFilter] = useState("all");
  const navItems = useMemo(
    () => [
      "Overview",
      "Reasoning",
      "Model",
      "Local Model",
      "Events",
      "Memory",
      "Screen",
      "History",
      "Permissions",
      "Project Read",
      "External",
      "Visual",
      "Logs",
      "Voice",
      "VR/OSC"
    ],
    []
  );

  useEffect(() => {
    const offState = window.yChat?.onDebugState((state) => setPetState(state));
    const offEvents = window.yChat?.onDebugEvents((nextEvents) => setEvents(nextEvents));
    const offScreen = window.yChat?.onScreenObservationStatus((status) => setScreenStatus(status));
    window.yChat?.getScreenObservationStatus()
      .then((status) => setScreenStatus(status))
      .catch(() => setScreenStatus(null));
    return () => {
      offState?.();
      offEvents?.();
      offScreen?.();
    };
  }, []);

  useEffect(() => {
    if (backendScreenStatus && !screenStatus?.active) {
      setScreenStatus((status) => status?.active ? status : backendScreenStatus);
    }
  }, [backendScreenStatus, screenStatus?.active]);

  useEffect(() => {
    let cancelled = false;
    window.yChat?.getEventHistoryStatus()
      .then((status) => {
        if (!cancelled) setEventHistoryStatus(status);
      })
      .catch(() => {
        if (!cancelled) setEventHistoryStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, events.length]);

  useEffect(() => {
    const firstRunId = reasoningRuns?.runs[0]?.run_id ?? null;
    if (!selectedReasoningRunId && firstRunId) setSelectedReasoningRunId(firstRunId);
  }, [reasoningRuns, selectedReasoningRunId]);

  useEffect(() => {
    if (!selectedReasoningRunId) {
      setReasoningRunDetail(null);
      return;
    }

    let cancelled = false;
    fetch(`http://127.0.0.1:18080/reasoning/runs/${selectedReasoningRunId}`)
      .then((response) => response.json())
      .then((data) => {
        if (!cancelled) setReasoningRunDetail(data);
      })
      .catch(() => {
        if (!cancelled) setReasoningRunDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedReasoningRunId, refreshKey]);

  useEffect(() => {
    let cancelled = false;
    fetch("http://127.0.0.1:18080/model/provider/config/audit")
      .then((response) => response.json())
      .then((data) => {
        if (!cancelled) setProviderAudit(data);
      })
      .catch(() => {
        if (!cancelled) setProviderAudit(null);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  async function refreshDebugData() {
    setRefreshKey((value) => value + 1);
  }

  async function addManualMemory() {
    const text = memoryDraft.trim();
    if (!text || memoryBusy) return;
    setMemoryBusy(true);
    setMemoryMessage("");
    try {
      const response = await fetch("http://127.0.0.1:18080/memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind: "manual", text })
      });
      if (!response.ok) throw new Error(`memory add failed: ${response.status}`);
      setMemoryDraft("");
      setMemoryMessage("Manual memory saved.");
      await refreshDebugData();
    } catch (error) {
      setMemoryMessage(error instanceof Error ? error.message : "Memory add failed.");
    } finally {
      setMemoryBusy(false);
    }
  }

  async function validateProviderDraft() {
    if (providerBusy) return;
    setProviderBusy(true);
    setProviderMessage("");
    setProviderValidation(null);
    setProviderTestResult(null);
    const temperature = providerDraft.temperature.trim() === "" ? null : Number(providerDraft.temperature);
    const timeoutSeconds = Number(providerDraft.timeout_seconds);
    const maxTokens = Number(providerDraft.max_tokens);
    try {
      const response = await fetch("http://127.0.0.1:18080/model/provider/config/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...providerDraft,
          temperature,
          timeout_seconds: Number.isFinite(timeoutSeconds) ? timeoutSeconds : 45,
          max_tokens: Number.isFinite(maxTokens) ? maxTokens : 1200
        })
      });
      const data = await response.json();
      setProviderValidation(data);
      setProviderMessage(data.ok ? "校验已记录，未保存配置。" : "校验失败，未保存配置。");
      setRefreshKey((value) => value + 1);
    } catch (error) {
      setProviderMessage(error instanceof Error ? error.message : "模型配置校验失败。");
    } finally {
      setProviderBusy(false);
    }
  }

  async function saveProviderDraft() {
    if (providerBusy) return;
    setProviderBusy(true);
    setProviderMessage("");
    setProviderValidation(null);
    setProviderTestResult(null);
    const temperature = providerDraft.temperature.trim() === "" ? null : Number(providerDraft.temperature);
    const timeoutSeconds = Number(providerDraft.timeout_seconds);
    const maxTokens = Number(providerDraft.max_tokens);
    try {
      const response = await fetch("http://127.0.0.1:18080/model/provider/config/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...providerDraft,
          temperature,
          timeout_seconds: Number.isFinite(timeoutSeconds) ? timeoutSeconds : 45,
          max_tokens: Number.isFinite(maxTokens) ? maxTokens : 1200
        })
      });
      const data = await response.json();
      setProviderValidation(data);
      setProviderMessage(data.saved ? "模型配置已保存到本机，API Key 输入框已清空。" : "模型配置没有保存。");
      if (data.saved) setProviderDraft((draft) => ({ ...draft, api_key: "" }));
      setRefreshKey((value) => value + 1);
    } catch (error) {
      setProviderMessage(error instanceof Error ? error.message : "模型配置保存失败。");
    } finally {
      setProviderBusy(false);
    }
  }

  async function testProviderCall() {
    if (providerBusy) return;
    setProviderBusy(true);
    setProviderMessage("");
    setProviderTestResult(null);
    try {
      const response = await fetch("http://127.0.0.1:18080/model/provider/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          secondary_confirmed: providerDraft.secondary_confirmed,
          prompt: "Return JSON: {\"ok\": true, \"source\": \"provider_test\"}."
        })
      });
      const data: ModelProviderTestResult = await response.json();
      setProviderTestResult(data);
      setProviderMessage(data.ok ? "模型 API 测试成功。" : data.called ? "模型 API 测试失败。" : "模型 API 测试被拦截。");
      await refreshDebugData();
    } catch (error) {
      setProviderMessage(error instanceof Error ? error.message : "模型 API 测试失败。");
    } finally {
      setProviderBusy(false);
    }
  }

  async function extractLatestVisionEvidence() {
    if (providerBusy) return;
    setProviderBusy(true);
    setProviderMessage("");
    setVisionExtractResult(null);
    try {
      const response = await fetch("http://127.0.0.1:18080/vision/reader/recognize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          secondary_confirmed: providerDraft.secondary_confirmed,
          prompt: "Recognize this image for a multimodal assistant. Return JSON with description, visible_text, objects, and uncertainty."
        })
      });
      const data: VisionExtractResult = await response.json();
      setVisionExtractResult(data);
      setProviderMessage(data.ok ? "本地视觉识别成功。" : data.called ? "本地视觉识别失败。" : "本地视觉识别未就绪/被拦截。");
      await refreshDebugData();
    } catch (error) {
      setProviderMessage(error instanceof Error ? error.message : "本地视觉识别失败。");
    } finally {
      setProviderBusy(false);
    }
  }

  async function deleteManualMemory(id: string) {
    if (memoryBusy) return;
    setMemoryBusy(true);
    setMemoryMessage("");
    try {
      const response = await fetch(`http://127.0.0.1:18080/memory/${id}`, {
        method: "DELETE"
      });
      if (!response.ok) throw new Error(`memory delete failed: ${response.status}`);
      setMemoryMessage("Manual memory deleted.");
      await refreshDebugData();
    } catch (error) {
      setMemoryMessage(error instanceof Error ? error.message : "Memory delete failed.");
    } finally {
      setMemoryBusy(false);
    }
  }

  async function startScreenObservation() {
    if (screenBusy) return;
    setScreenBusy(true);
    setScreenMessage("");
    try {
      const result = await window.yChat?.startScreenObservation({
        secondary_confirmed: screenSecondaryConfirmed,
        retain_raw: screenRetainRaw
      });
      if (result?.status) setScreenStatus(result.status);
      setScreenMessage(result?.ok ? "屏幕观察已开始采样主屏幕。" : "屏幕观察被拦截。");
      await refreshDebugData();
    } catch (error) {
      setScreenMessage(error instanceof Error ? error.message : "屏幕观察启动失败。");
    } finally {
      setScreenBusy(false);
    }
  }

  async function sampleScreenOnce() {
    if (screenBusy) return;
    setScreenBusy(true);
    setScreenMessage("");
    try {
      const result = await window.yChat?.startScreenObservation({
        secondary_confirmed: screenSecondaryConfirmed,
        retain_raw: screenRetainRaw,
        sample_once: true
      });
      if (result?.status) setScreenStatus(result.status);
      setScreenMessage(result?.ok ? "已采样一帧屏幕并停止。" : "屏幕单次采样被拦截。");
      await refreshDebugData();
    } catch (error) {
      setScreenMessage(error instanceof Error ? error.message : "屏幕单次采样失败。");
    } finally {
      setScreenBusy(false);
    }
  }

  async function stopScreenObservation(revokePermission = false) {
    if (screenBusy) return;
    setScreenBusy(true);
    setScreenMessage("");
    try {
      const result = await window.yChat?.stopScreenObservation({ revoke_permission: revokePermission });
      if (result?.status) setScreenStatus(result.status);
      setScreenMessage(revokePermission ? "屏幕观察已停止，权限已撤销。" : "屏幕观察已停止。");
      await refreshDebugData();
    } catch (error) {
      setScreenMessage(error instanceof Error ? error.message : "屏幕观察停止失败。");
    } finally {
      setScreenBusy(false);
    }
  }

  const moduleTiles = (
    <div className="module-grid">
      <div className="module-tile">
        <span>Model Provider</span>
        <strong>{modelStatus?.enabled ? "enabled" : "disabled"}</strong>
        <small>{modelStatus ? `${modelStatus.active_provider} / ${modelStatus.model}` : "unavailable"}</small>
      </div>
      <div className="module-tile">
        <span>Memory</span>
        <strong>{memoryStatus?.enabled ? "enabled" : "disabled"}</strong>
        <small>{memoryStatus ? `${memoryStatus.items.length} manual item(s)` : "unavailable"}</small>
      </div>
      <div className="module-tile">
        <span>Project Reader</span>
        <strong>{projectReaderStatus?.enabled ? "enabled" : "disabled"}</strong>
        <small>
          {projectReaderStatus
            ? `${projectReaderStatus.allowed_roots.length} authorized root(s)`
            : "unavailable"}
        </small>
      </div>
    </div>
  );

  const historySources = useMemo(() => {
    const values = new Set<string>();
    for (const event of events) values.add(String(event.source ?? "unknown"));
    return ["all", ...Array.from(values).sort()];
  }, [events]);

  const historyModalities = useMemo(() => {
    const values = new Set<string>();
    for (const event of events) {
      for (const modality of inferDebugEventModalities(event)) values.add(modality);
    }
    return ["all", ...Array.from(values).sort()];
  }, [events]);

  const filteredHistoryEvents = useMemo(() => {
    return events.filter((event) => {
      const source = String(event.source ?? "unknown");
      const modalities = inferDebugEventModalities(event);
      const sourceMatches = historySourceFilter === "all" || source === historySourceFilter;
      const modalityMatches =
        historyModalityFilter === "all" || modalities.includes(historyModalityFilter);
      return sourceMatches && modalityMatches;
    });
  }, [events, historySourceFilter, historyModalityFilter]);

  useEffect(() => {
    if (historySourceFilter !== "all" && !historySources.includes(historySourceFilter)) {
      setHistorySourceFilter("all");
    }
  }, [historySourceFilter, historySources]);

  useEffect(() => {
    if (historyModalityFilter !== "all" && !historyModalities.includes(historyModalityFilter)) {
      setHistoryModalityFilter("all");
    }
  }, [historyModalityFilter, historyModalities]);

  useEffect(() => {
    if (
      selectedHistoryEventId &&
      !filteredHistoryEvents.some((event, index) => eventStableKey(event, index) === selectedHistoryEventId)
    ) {
      setSelectedHistoryEventId(null);
    }
  }, [filteredHistoryEvents, selectedHistoryEventId]);

  const selectedHistoryEvent =
    filteredHistoryEvents.find((event, index) => eventStableKey(event, index) === selectedHistoryEventId) ??
    filteredHistoryEvents[0] ??
    null;
  const selectedHistoryTraceRefs = useMemo(
    () => (selectedHistoryEvent ? eventTraceRefs(selectedHistoryEvent) : []),
    [selectedHistoryEvent]
  );

  const reasoningStatusOptions = useMemo(() => {
    const statuses = new Set((reasoningRuns?.runs ?? []).map((run) => run.status));
    return ["all", ...Array.from(statuses).sort()];
  }, [reasoningRuns]);

  const reasoningModalityOptions = useMemo(() => {
    const modalities = new Set<string>();
    for (const run of reasoningRuns?.runs ?? []) {
      const runModalities = run.modalities?.length ? run.modalities : [run.primary_modality ?? "event"];
      for (const modality of runModalities) modalities.add(modality);
    }
    return ["all", ...Array.from(modalities).sort()];
  }, [reasoningRuns]);

  const filteredReasoningRuns = useMemo(() => {
    return (reasoningRuns?.runs ?? []).filter((run) => {
      const runModalities = run.modalities?.length ? run.modalities : [run.primary_modality ?? "event"];
      const statusMatches = reasoningStatusFilter === "all" || run.status === reasoningStatusFilter;
      const modalityMatches = reasoningModalityFilter === "all" || runModalities.includes(reasoningModalityFilter);
      return statusMatches && modalityMatches;
    });
  }, [reasoningModalityFilter, reasoningRuns, reasoningStatusFilter]);

  const reasoningRunStats = useMemo(() => {
    const runs = reasoningRuns?.runs ?? [];
    return {
      shown: filteredReasoningRuns.length,
      total: runs.length,
      completed: runs.filter((run) => run.status === "completed").length,
      failed: runs.filter((run) => run.status.includes("failed")).length,
      withReply: runs.filter((run) => Boolean(run.reply_text)).length,
      withFailureSummary: runs.filter((run) => Boolean(run.failure_summary)).length,
    };
  }, [filteredReasoningRuns.length, reasoningRuns]);

  useEffect(() => {
    if (reasoningStatusFilter !== "all" && !reasoningStatusOptions.includes(reasoningStatusFilter)) {
      setReasoningStatusFilter("all");
    }
  }, [reasoningStatusFilter, reasoningStatusOptions]);

  useEffect(() => {
    if (reasoningModalityFilter !== "all" && !reasoningModalityOptions.includes(reasoningModalityFilter)) {
      setReasoningModalityFilter("all");
    }
  }, [reasoningModalityFilter, reasoningModalityOptions]);

  useEffect(() => {
    if (!reasoningRuns) return;
    const firstFilteredRunId = filteredReasoningRuns[0]?.run_id ?? reasoningRuns.runs[0]?.run_id ?? null;
    if (!selectedReasoningRunId && firstFilteredRunId) {
      setSelectedReasoningRunId(firstFilteredRunId);
      return;
    }
    if (selectedReasoningRunId && !filteredReasoningRuns.some((run) => run.run_id === selectedReasoningRunId)) {
      setSelectedReasoningRunId(firstFilteredRunId);
    }
  }, [filteredReasoningRuns, reasoningRuns, selectedReasoningRunId]);

  const permissionDetails = useMemo<PermissionDetail[]>(() => {
    if (permissionStatus?.details?.length) return permissionStatus.details;
    return Object.entries(permissionStatus?.permissions ?? {}).map(([name, enabled]) => ({
      name,
      enabled,
      group: "other",
      risk: "medium",
      requires_secondary_confirmation: true,
      reason: "Unclassified capability; keep gated until it has an explicit policy."
    }));
  }, [permissionStatus]);

  const permissionGroups = useMemo(() => {
    const groups = new Map<string, PermissionDetail[]>();
    for (const detail of permissionDetails) {
      const items = groups.get(detail.group) ?? [];
      items.push(detail);
      groups.set(detail.group, items);
    }
    return Array.from(groups.entries()).sort(([left], [right]) => left.localeCompare(right));
  }, [permissionDetails]);

  const safetySnapshot = useMemo(() => {
    const captureState = reasoningStatus?.capture_enabled ?? formalMemoryStatus?.capture_enabled ?? {};
    const enabledCaptures = Object.entries(captureState)
      .filter(([, enabled]) => Boolean(enabled))
      .map(([name]) => name);
    const sensitiveEnabled = permissionDetails
      .filter((detail) => {
        const sensitiveGroup = ["external", "system", "vision", "voice", "vr"].includes(detail.group);
        return detail.enabled && (detail.risk === "high" || sensitiveGroup);
      })
      .map((detail) => detail.name);
    const modelBlockedReason =
      modelConfig?.blocked_reasons?.[0] ??
      (modelConfig ? "real model calls are gated" : "waiting for provider status");
    const projectBlockedReason =
      projectReaderStatus?.blocked_reasons?.[0] ??
      (projectReaderStatus ? "content reading remains disabled" : "waiting for project reader status");

    return [
      {
        label: "Reasoning route",
        value: reasoningStatus?.provider_mode ?? "unavailable",
        detail: reasoningStatus?.real_model_calls
          ? "real provider calls may run"
          : "deterministic fallback; output still goes through reasoning.v1 validation",
        state: reasoningStatus ? "ready" : "waiting"
      },
      {
        label: "Real model calls",
        value: modelConfig?.real_model_calls ? "enabled" : "off",
        detail: modelBlockedReason,
        state: modelConfig?.real_model_calls ? "warn" : "locked"
      },
      {
        label: "Input capture",
        value: enabledCaptures.length > 0 ? enabledCaptures.join(", ") : "off",
        detail: enabledCaptures.length > 0 ? "capture gate is no longer fully closed" : "vision and audio capture remain disabled",
        state: enabledCaptures.length > 0 ? "warn" : "locked"
      },
      {
        label: "Project reader",
        value: projectReaderStatus?.listing_enabled ? "listing enabled" : "blocked",
        detail: projectBlockedReason,
        state: projectReaderStatus?.listing_enabled ? "warn" : "locked"
      },
      {
        label: "Automatic memory",
        value: formalMemoryStatus?.automatic_writes_enabled ? "enabled" : "inspect only",
        detail: formalMemoryStatus?.automatic_writes_enabled
          ? "formal memory writes may be accepted"
          : "R1 candidates remain visible but are not accepted as formal memory",
        state: formalMemoryStatus?.automatic_writes_enabled ? "warn" : "locked"
      },
      {
        label: "External/system actions",
        value: sensitiveEnabled.length > 0 ? `${sensitiveEnabled.length} enabled` : "off",
        detail: sensitiveEnabled.length > 0 ? sensitiveEnabled.join(", ") : "network, files, process, input, and VR outputs are gated",
        state: sensitiveEnabled.length > 0 ? "warn" : "locked"
      }
    ];
  }, [formalMemoryStatus, modelConfig, permissionDetails, projectReaderStatus, reasoningStatus]);

  function renderEventsPanel(limit = 12) {
    return (
      <div className="debug-event-list">
        {events.length === 0 ? (
          <p className="debug-empty">No events yet.</p>
        ) : (
          events.slice(0, limit).map((event) => (
            <article className="debug-event" key={event.event_id}>
              <div className="debug-event-head">
                <strong>{event.type}</strong>
                <span>{event.payload_redacted ? `${event.source} / redacted` : event.source}</span>
              </div>
              {event.raw_payload_stored_in_event === false ? (
                <div className="log-flags">
                  <span>raw payload not stored</span>
                  {event.payload_redacted ? <span>diagnostic payload redacted</span> : null}
                </div>
              ) : null}
              <pre>{JSON.stringify(event.payload ?? {}, null, 2)}</pre>
            </article>
          ))
        )}
      </div>
    );
  }

  function renderContractRules(rules: ContractRule[] | undefined) {
    return (
      <div className="contract-rule-list">
        {(rules ?? []).map((rule) => (
          <article className="contract-rule-card" data-enabled={rule.enabled} key={rule.name}>
            <strong>{rule.name}</strong>
            <span>{rule.enabled ? "active" : "disabled"}</span>
            <small>{rule.detail}</small>
          </article>
        ))}
      </div>
    );
  }

  function renderActiveView() {
    if (activeView === "Events") {
      return (
        <section className="debug-panel">
          <h2>Events</h2>
          <div className="detail-grid">
            <div><span>Contract</span><strong>{eventContract?.schema_version ?? "unavailable"}</strong></div>
            <div><span>Ingress</span><strong>{eventContract?.active_ingress.length ?? 0}</strong></div>
            <div><span>External adapters</span><strong>off</strong></div>
            <div><span>Raw capture</span><strong>blocked</strong></div>
            <div><span>Diagnostics</span><strong>{eventContract?.diagnostic_payload_redaction?.enabled ? "redacted" : "unknown"}</strong></div>
            <div><span>Redaction token</span><strong>{eventContract?.diagnostic_payload_redaction?.token ?? "[REDACTED]"}</strong></div>
          </div>
          <section className="debug-subsection">
            <h3>Diagnostic Redaction</h3>
            <div className="project-reader-reasons">
              {(eventContract?.diagnostic_payload_redaction?.patterns ?? []).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
            <div className="project-reader-reasons">
              {(eventContract?.diagnostic_payload_redaction?.safe_ref_fields_preserved ?? []).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Event Contract</h3>
            {renderContractRules(eventContract?.safety_rules)}
            <div className="trace-ref-grid">
              {(eventContract?.active_ingress ?? []).map((ingress) => (
                <span key={ingress.route}>
                  <strong>{ingress.route}</strong>
                  {ingress.scope}; external {ingress.external ? "yes" : "no"}; raw capture {ingress.accepts_raw_capture ? "yes" : "no"}
                </span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Envelope Fields</h3>
            <div className="trace-ref-grid">
              {(eventContract?.envelope ?? []).map((field) => (
                <span key={field.name}>
                  <strong>{field.name}</strong>
                  {field.required ? "required" : "optional"}; {field.detail}
                </span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Blocked Event Paths</h3>
            <div className="project-reader-reasons">
              {(eventContract?.blocked_until_enabled ?? []).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </section>
          {renderEventsPanel(40)}
        </section>
      );
    }

    if (activeView === "Permissions") {
      return (
        <section className="debug-panel">
          <h2>Permissions</h2>
          {permissionStatus ? (
            <>
              <div className="detail-grid">
                <div><span>Enabled</span><strong>{permissionStatus.enabled.length}</strong></div>
                <div><span>Disabled</span><strong>{permissionStatus.disabled.length}</strong></div>
                <div><span>Groups</span><strong>{permissionGroups.length}</strong></div>
                <div><span>Contract</span><strong>{permissionContract?.schema_version ?? "unavailable"}</strong></div>
                <div><span>Mode</span><strong>{permissionContract?.read_only ? "read only" : "unknown"}</strong></div>
                <div><span>Mutation</span><strong>{permissionContract?.mutation_enabled ? "enabled" : "blocked"}</strong></div>
                <div><span>Config write</span><strong>{permissionContract?.config_write_enabled ? "enabled" : "blocked"}</strong></div>
                <div><span>Sensitive on</span><strong>{permissionContract?.sensitive_enabled.length ?? 0}</strong></div>
              </div>
              <section className="debug-subsection">
                <h3>Permission Contract</h3>
                {renderContractRules(permissionContract?.rules)}
              </section>
              <section className="debug-subsection">
                <h3>Blocked Until Explicit Selection</h3>
                <div className="project-reader-reasons">
                  {(permissionContract?.blocked_until_explicit_user_selection ?? []).map((item) => (
                    <span key={item}>{item}</span>
                  ))}
                </div>
              </section>
              <div className="permission-map">
                {permissionGroups.map(([group, details]) => (
                  <section className="permission-group" key={group}>
                    <div className="permission-group-head">
                      <strong>{group}</strong>
                      <span>{details.filter((detail) => detail.enabled).length} / {details.length} on</span>
                    </div>
                    <div className="permission-grid">
                      {details.map((detail) => (
                        <article className="permission-row" data-risk={detail.risk} key={detail.name}>
                          <div>
                            <span>{detail.name}</span>
                            <small>{detail.reason}</small>
                          </div>
                          <div className="permission-flags">
                            <strong data-enabled={detail.enabled}>{detail.enabled ? "on" : "off"}</strong>
                            <em>{detail.risk}</em>
                            {detail.requires_secondary_confirmation ? <em>confirm</em> : null}
                          </div>
                        </article>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </>
          ) : (
            <p className="debug-empty">Permissions unavailable.</p>
          )}
        </section>
      );
    }

    if (activeView === "Model" || activeView === "Local Model") {
      const localModelCards = Object.values(localModelsStatus?.models ?? {});
      const visionReader = visionReaderStatus ?? localModelsStatus?.vision_reader ?? null;
      const audioReader = audioReaderStatus ?? localModelsStatus?.audio_reader ?? null;
      return (
        <section className="debug-panel">
          <h2>模型/API 接入</h2>
          <section className="debug-subsection">
            <h3>职责边界</h3>
            <div className="detail-grid">
              <div><span>DeepSeek</span><strong>{localModelsStatus?.deepseek_role ?? "text_reasoning_api_only"}</strong></div>
              <div><span>视觉 reader</span><strong>{visionReader?.adapter_boundary ?? "independent_vision_reader"}</strong></div>
              <div><span>语音 reader</span><strong>{audioReader?.adapter_boundary ?? "independent_audio_reader"}</strong></div>
              <div><span>图像生成功能</span><strong>{visionReader?.image_generation_supported ? "enabled" : "unsupported"}</strong></div>
              <div><span>OCR/转写</span><strong>辅助证据，不是主记忆体</strong></div>
            </div>
          </section>
          <div className="detail-grid">
            <div><span>已启用</span><strong>{yesNo(modelStatus?.enabled)}</strong></div>
            <div><span>已配置</span><strong>{yesNo(modelStatus?.configured)}</strong></div>
            <div><span>供应商</span><strong>{modelStatus?.active_provider ?? "不可用"}</strong></div>
            <div><span>模型</span><strong>{modelStatus?.model ?? "不可用"}</strong></div>
            <div><span>请求启用</span><strong>{yesNo(modelConfig?.enabled_requested)}</strong></div>
            <div><span>权限</span><strong>{modelConfig?.permission_allowed ? "允许" : "拦截"}</strong></div>
            <div><span>真实调用</span><strong>{yesNo(modelConfig?.real_model_calls)}</strong></div>
            <div><span>调用路线</span><strong>{modelConfig?.call_route ?? "不可用"}</strong></div>
            <div><span>调用地址</span><strong>{modelConfig?.call_url ?? "不可用"}</strong></div>
            <div><span>测试接口</span><strong>{modelConfig?.real_call_test_endpoint ?? "/model/provider/test"}</strong></div>
            <div><span>下次推理</span><strong>{modelReadiness?.will_call_model_on_next_reasoning_run ? "真实模型" : "本地兜底"}</strong></div>
            <div><span>就绪状态</span><strong>{readyBlocked(modelReadiness?.ready)}</strong></div>
            <div><span>配置模式</span><strong>{modelConfig?.read_only ? "只读" : "可编辑"}</strong></div>
          </div>
          <section className="debug-subsection">
            <h3>拦截原因</h3>
            <div className="reserved-list">
              {(modelConfig?.blocked_reasons ?? []).map((reason) => (
                <span key={reason}>{reason}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>真实调用前还需要</h3>
            <div className="reserved-list">
              {(modelConfig?.next_requirements ?? []).map((requirement) => (
                <span key={requirement}>{requirement}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>就绪检查</h3>
            <pre className="debug-code">
              {JSON.stringify(
                modelReadiness ?? {
                  ready: false,
                  dry_run_only: true,
                  blocked_reasons: ["waiting for backend readiness status"]
                },
                null,
                2
              )}
            </pre>
          </section>
          <section className="debug-subsection">
            <h3>API 调用频率</h3>
            <div className="detail-grid">
              <div><span>DeepSeek 职责</span><strong>{modelCadence?.policy.deepseek_role ?? "text_reasoning_api_only"}</strong></div>
              <div><span>高频输入</span><strong>{modelCadence?.policy.high_frequency_inputs ?? "local_adapters_only"}</strong></div>
              <div><span>API 收到</span><strong>{modelCadence?.policy.provider_receives ?? "sanitized summaries"}</strong></div>
              <div><span>先合并再调用</span><strong>{yesNo(modelCadence?.policy.coalescing_required_before_api)}</strong></div>
              <div><span>推理调用</span><strong>{modelCadence?.scopes.reasoning_foreground?.allowed_now ? "ready" : "cooldown"}</strong></div>
              <div><span>测试调用</span><strong>{modelCadence?.scopes.provider_test?.allowed_now ? "ready" : "cooldown"}</strong></div>
            </div>
            <div className="debug-event-list">
              {Object.values(modelCadence?.scopes ?? {}).map((scope) => (
                <article className="debug-event" data-kind={scope.allowed_now ? "ok" : "warn"} key={scope.scope}>
                  <div className="debug-event-head">
                    <strong>{scope.scope}</strong>
                    <span>{scope.allowed_now ? "可调用" : `等待 ${scope.retry_after_seconds}s`}</span>
                  </div>
                  <div className="reserved-list">
                    <span>{scope.purpose}</span>
                    <span>最小间隔 {scope.min_interval_seconds}s</span>
                    <span>已调用 {scope.started_count}</span>
                    <span>已拦截 {scope.blocked_count}</span>
                    <span>{scope.high_frequency_allowed ? "允许高频" : "不允许高频"}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>推荐模型</h3>
            <div className="reserved-list">
              {Object.entries(modelConfig?.recommended_models ?? {}).flatMap(([provider, models]) =>
                models.map((model) => <span key={`${provider}-${model}`}>{provider}: {model}</span>)
              )}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>视觉识别 reader</h3>
            <div className="detail-grid">
              <div><span>边界</span><strong>{visionReader?.adapter_boundary ?? "unavailable"}</strong></div>
              <div><span>可单独换 API</span><strong>{yesNo(visionReader?.api_swap_ready)}</strong></div>
              <div><span>图像 embedding</span><strong>{visionReader?.ready?.embedding ? "ready" : "missing"}</strong></div>
              <div><span>识别 adapter</span><strong>{visionReader?.active_adapters?.recognition ?? "not_ready"}</strong></div>
              <div><span>DeepSeek 收原图</span><strong>{visionReader?.deepseek_receives_raw_images ? "yes" : "no"}</strong></div>
              <div><span>生图</span><strong>{visionReader?.image_generation_supported ? "supported" : "unsupported"}</strong></div>
            </div>
            <div className="reserved-list">
              {(visionReader?.scope ?? []).map((item) => (
                <span key={item}>{item}</span>
              ))}
              {(visionReader?.excluded_capabilities ?? []).map((item) => (
                <span key={item}>excluded: {item}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>语音处理 reader</h3>
            <div className="detail-grid">
              <div><span>边界</span><strong>{audioReader?.adapter_boundary ?? "unavailable"}</strong></div>
              <div><span>可单独换 API</span><strong>{yesNo(audioReader?.api_swap_ready)}</strong></div>
              <div><span>ASR</span><strong>{audioReader?.ready?.asr ? "ready" : "missing"}</strong></div>
              <div><span>当前 ASR</span><strong>{audioReader?.active_adapters?.asr ?? "not_ready"}</strong></div>
              <div><span>说话人特征</span><strong>{audioReader?.ready?.speaker_features ? "ready" : "not_configured"}</strong></div>
              <div><span>DeepSeek 收原音频</span><strong>{audioReader?.deepseek_receives_raw_audio ? "yes" : "no"}</strong></div>
            </div>
            <div className="reserved-list">
              {(audioReader?.scope ?? []).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>本地图像/语音模型</h3>
            <div className="detail-grid">
              <div><span>缓存目录</span><strong>{localModelsStatus?.cache_dir ?? "unavailable"}</strong></div>
              <div><span>下载门禁</span><strong>{localModelsStatus?.download_requires_explicit_user_action ? "需要显式动作" : "可自动下载"}</strong></div>
              <div><span>图像 embedding</span><strong>{localModelsStatus?.ready?.vision_embedding ? "ready" : "missing"}</strong></div>
              <div><span>本地 VLM</span><strong>{localModelsStatus?.ready?.vision_vlm ? "ready" : "missing"}</strong></div>
              <div><span>本地 ASR</span><strong>{localModelsStatus?.ready?.audio_asr ? "ready" : "missing"}</strong></div>
            </div>
            <div className="debug-event-list">
              {localModelCards.map((model) => (
                <article className="debug-event" data-kind={model.downloaded ? "ok" : "warn"} key={model.name}>
                  <div className="debug-event-head">
                    <strong>{model.name}</strong>
                    <span>{model.modality} / {model.downloaded ? "downloaded" : "missing files"}</span>
                  </div>
                  <div className="reserved-list">
                    <span>{model.model_id}</span>
                    <span>{model.purpose}</span>
                    <span>{model.packages_ready ? "packages ready" : "packages missing"}</span>
                    <span>{model.text_auxiliary_only ? "text is auxiliary" : "text may be primary"}</span>
                  </div>
                  <pre>{JSON.stringify(model, null, 2)}</pre>
                </article>
              ))}
            </div>
            <section className="debug-subsection">
              <h3>本地模型阻塞项</h3>
              <div className="reserved-list">
                {(localModelsStatus?.blocked_reasons ?? []).map((reason) => (
                  <span key={reason}>{reason}</span>
                ))}
              </div>
            </section>
            <section className="debug-subsection">
              <h3>下载命令</h3>
              <pre className="debug-code">{(localModelsStatus?.download_commands ?? []).join("\n")}</pre>
            </section>
          </section>
          <div className="debug-event-list">
            {modelConfig && Object.keys(modelConfig.providers).length > 0 ? (
              Object.entries(modelConfig.providers).map(([name, provider]) => (
                <article className="debug-event" key={name}>
                  <div className="debug-event-head">
                    <strong>{name}</strong>
                      <span>{name === modelConfig.active_provider ? "当前" : "备用"}</span>
                  </div>
                  <pre>
                    {JSON.stringify(
                      {
                        base_url: provider.base_url,
                        model: provider.model,
                        temperature: provider.temperature,
                        stream: provider.stream,
                        timeout_seconds: provider.timeout_seconds,
                        max_tokens: provider.max_tokens,
                        thinking_type: provider.thinking_type,
                        api_key_configured: provider.api_key_configured,
                        api_key_masked: provider.api_key_masked || "(empty)"
                      },
                      null,
                      2
                    )}
                  </pre>
                </article>
              ))
            ) : (
              <p className="debug-empty">模型配置不可用。</p>
            )}
          </div>
          <section className="debug-subsection">
            <h3>配置校验/保存</h3>
            <form
              className="provider-form"
              onSubmit={(event) => {
                event.preventDefault();
                validateProviderDraft();
              }}
            >
              <label>
                <span>供应商</span>
                <select
                  value={providerDraft.provider}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, provider: event.target.value }))}
                >
                  <option value="deepseek">deepseek</option>
                  <option value="openai_compatible">openai_compatible</option>
                </select>
              </label>
              <label>
                <span>接口地址</span>
                <input
                  value={providerDraft.base_url}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, base_url: event.target.value }))}
                />
              </label>
              <label>
                <span>模型名</span>
                <input
                  value={providerDraft.model}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, model: event.target.value }))}
                />
              </label>
              <label>
                <span>API Key</span>
                <input
                  autoComplete="off"
                  type="password"
                  value={providerDraft.api_key}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, api_key: event.target.value }))}
                />
              </label>
              <label>
                <span>温度</span>
                <input
                  inputMode="decimal"
                  value={providerDraft.temperature}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, temperature: event.target.value }))}
                />
              </label>
              <label>
                <span>超时秒数</span>
                <input
                  inputMode="numeric"
                  value={providerDraft.timeout_seconds}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, timeout_seconds: event.target.value }))}
                />
              </label>
              <label>
                <span>最大 token</span>
                <input
                  inputMode="numeric"
                  value={providerDraft.max_tokens}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, max_tokens: event.target.value }))}
                />
              </label>
              <label>
                <span>思考模式</span>
                <select
                  value={providerDraft.thinking_type}
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, thinking_type: event.target.value }))}
                >
                  <option value="disabled">disabled</option>
                  <option value="enabled">enabled</option>
                </select>
              </label>
              <label className="provider-check">
                <input
                  checked={providerDraft.stream}
                  type="checkbox"
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, stream: event.target.checked }))}
                />
                <span>以后再启用流式传输</span>
              </label>
              <label className="provider-check">
                <input
                  checked={providerDraft.enabled_requested}
                  type="checkbox"
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, enabled_requested: event.target.checked }))}
                />
                <span>请求启用模型调用</span>
              </label>
              <label className="provider-check">
                <input
                  checked={providerDraft.use_for_vision}
                  type="checkbox"
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, use_for_vision: event.target.checked }))}
                />
                <span>同时作为视觉抽取模型</span>
              </label>
              <label className="provider-check">
                <input
                  checked={providerDraft.secondary_confirmed}
                  type="checkbox"
                  onChange={(event) => setProviderDraft((draft) => ({ ...draft, secondary_confirmed: event.target.checked }))}
                />
                <span>二次确认：允许保存 API Key 和模型开关</span>
              </label>
              <button disabled={providerBusy} type="submit">
                {providerBusy ? "校验中..." : "只校验"}
              </button>
              <button
                disabled={providerBusy}
                type="button"
                onClick={saveProviderDraft}
              >
                {providerBusy ? "处理中..." : providerDraft.enabled_requested ? "保存并启用" : "保存到本机"}
              </button>
              <button
                disabled={providerBusy}
                type="button"
                onClick={testProviderCall}
              >
                {providerBusy ? "处理中..." : "测试 API 调用"}
              </button>
              <button
                disabled={providerBusy}
                type="button"
                onClick={extractLatestVisionEvidence}
              >
                {providerBusy ? "处理中..." : "本地识别最新图片"}
              </button>
            </form>
            {providerMessage ? <p className="debug-message">{providerMessage}</p> : null}
            {providerValidation ? (
              <article className="debug-event" data-kind={providerValidation.ok ? "ok" : "error"}>
                <div className="debug-event-head">
                  <strong>{providerValidation.ok ? "有效" : "无效"}</strong>
                  <span>{providerValidation.saved ? "已保存" : "未保存"}</span>
                </div>
                <pre>{JSON.stringify(providerValidation, null, 2)}</pre>
              </article>
            ) : null}
            {providerTestResult ? (
              <article className="debug-event" data-kind={providerTestResult.ok ? "ok" : "error"}>
                <div className="debug-event-head">
                  <strong>{providerTestResult.ok ? "测试成功" : "测试失败"}</strong>
                  <span>{providerTestResult.called ? "已调用" : "未调用"}</span>
                </div>
                <pre>{JSON.stringify(providerTestResult, null, 2)}</pre>
              </article>
            ) : null}
            {visionExtractResult ? (
              <article className="debug-event" data-kind={visionExtractResult.ok ? "ok" : "error"}>
                <div className="debug-event-head">
                  <strong>{visionExtractResult.ok ? "视觉已识别" : "视觉未就绪/失败"}</strong>
                  <span>{visionExtractResult.called ? "已调用" : "未调用"}</span>
                </div>
                <pre>{JSON.stringify(visionExtractResult, null, 2)}</pre>
              </article>
            ) : null}
          </section>
          <section className="debug-subsection">
            <h3>模型配置审计</h3>
            <div className="debug-event-list">
              {providerAudit && providerAudit.audits.length > 0 ? (
                providerAudit.audits.slice(0, 8).map((audit) => (
                  <article className="debug-event" key={audit.audit_id}>
                    <div className="debug-event-head">
                      <strong>{audit.status}</strong>
                      <span>{new Date(audit.created_at).toLocaleTimeString()}</span>
                    </div>
                    <pre>{JSON.stringify(audit.payload ?? {}, null, 2)}</pre>
                  </article>
                ))
              ) : (
                <p className="debug-empty">还没有模型配置审计记录。</p>
              )}
            </div>
          </section>
        </section>
      );
    }

    if (activeView === "Reasoning") {
      return (
        <section className="debug-panel">
          <h2>Reasoning</h2>
          <section className="debug-subsection">
            <h3>Real Model Readiness</h3>
            <div className="detail-grid">
              <div><span>Next run</span><strong>{modelReadiness?.will_call_model_on_next_reasoning_run ? "real model" : "deterministic fallback"}</strong></div>
              <div><span>Ready</span><strong>{modelReadiness?.ready ? "yes" : "no"}</strong></div>
              <div><span>Provider</span><strong>{modelReadiness?.active_provider ?? reasoningStatus?.provider ?? "unknown"}</strong></div>
              <div><span>Route</span><strong>{modelReadiness?.call_route ?? "unavailable"}</strong></div>
              <div><span>Dry run status</span><strong>{modelReadiness?.dry_run_only ? "no network here" : "can call when reasoning runs"}</strong></div>
              <div><span>API key returned</span><strong>{modelReadiness?.api_key_returned ? "unsafe" : "no"}</strong></div>
            </div>
            <div className="reserved-list">
              {(modelReadiness?.blocked_reasons ?? []).map((reason) => (
                <span key={reason}>{reason}</span>
              ))}
            </div>
          </section>
          <div className="detail-grid">
            <div><span>Enabled</span><strong>{reasoningStatus?.enabled ? "yes" : "no"}</strong></div>
            <div><span>Provider</span><strong>{reasoningStatus?.provider ?? "unavailable"}</strong></div>
            <div><span>Provider mode</span><strong>{reasoningStatus?.provider_mode ?? "unknown"}</strong></div>
            <div><span>Real model calls</span><strong>{reasoningStatus?.real_model_calls ? "yes" : "no"}</strong></div>
            <div><span>Runs</span><strong>{reasoningStatus?.runs_total ?? 0}</strong></div>
            <div><span>Inputs</span><strong>{reasoningStatus?.supported_input_modalities?.length ?? 0} modes</strong></div>
            <div><span>Capture</span><strong>{reasoningStatus?.capture_enabled?.vision || reasoningStatus?.capture_enabled?.audio ? "partly on" : "off"}</strong></div>
          </div>
          <section className="debug-subsection">
            <h3>Safety Gates</h3>
            <div className="reserved-list">
              {(reasoningStatus?.model_blocked_reasons ?? []).map((reason) => (
                <span key={reason}>{reason}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Input And Capture</h3>
            <div className="reasoning-mode-grid">
              {(reasoningStatus?.supported_input_modalities ?? []).map((modality) => (
                <article key={modality}>
                  <span>{modality}</span>
                  <strong>
                    {reasoningStatus?.capture_enabled?.[modality] ? "capture on" : "event only"}
                  </strong>
                  {reasoningStatus?.capture_blocked_reasons?.[modality] ? (
                    <small>{reasoningStatus.capture_blocked_reasons[modality]}</small>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Write Paths</h3>
            <div className="reserved-list">
              {Object.entries(reasoningStatus?.write_paths ?? {}).map(([name, mode]) => (
                <span key={name}>{name}: {mode}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Output Contract</h3>
            <div className="detail-grid">
              <div><span>Schema</span><strong>{reasoningContract?.schema_version ?? "unavailable"}</strong></div>
              <div><span>Provider mode</span><strong>{reasoningContract?.provider_mode ?? "unknown"}</strong></div>
              <div><span>Transport stream</span><strong>{reasoningContract?.transport_may_stream ? "allowed later" : "no"}</strong></div>
              <div><span>Execute after</span><strong>{reasoningContract?.execution_requires_complete_json ? "complete JSON" : "unknown"}</strong></div>
              <div><span>Repair attempts</span><strong>{reasoningContract?.repair_attempts ?? 0}</strong></div>
              <div><span>Repair policy</span><strong>{reasoningContract?.repair_policy ?? "unavailable"}</strong></div>
            </div>
            <div className="reserved-list">
              {(reasoningContract?.blocked_until_valid ?? []).map((item) => (
                <span key={item}>blocked: {item}</span>
              ))}
            </div>
            <div className="reasoning-contract-grid">
              {(reasoningContract?.top_level_sections ?? []).map((section) => (
                <article key={section.name}>
                  <div className="debug-event-head">
                    <strong>{section.name}</strong>
                    <span>{section.required.length} field(s)</span>
                  </div>
                  <div className="history-chip-row">
                    {section.required.map((field) => (
                      <span key={field}>{field}</span>
                    ))}
                  </div>
                  <ul>
                    {section.acceptance_rules.map((rule) => (
                      <li key={rule}>{rule}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
            <div className="reserved-list">
              {(reasoningContract?.failure_events ?? []).map((event) => (
                <span key={event}>{event}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Run Filters</h3>
            <div className="reasoning-toolbar">
              <label>
                <span>Status</span>
                <select
                  value={reasoningStatusFilter}
                  onChange={(event) => setReasoningStatusFilter(event.target.value)}
                >
                  {reasoningStatusOptions.map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Modality</span>
                <select
                  value={reasoningModalityFilter}
                  onChange={(event) => setReasoningModalityFilter(event.target.value)}
                >
                  {reasoningModalityOptions.map((modality) => (
                    <option key={modality} value={modality}>{modality}</option>
                  ))}
                </select>
              </label>
              <div>
                <span>Shown</span>
                <strong>
                  {reasoningRuns ? `${reasoningRunStats.shown} / ${reasoningRunStats.total}` : "loading"}
                </strong>
              </div>
              <div><span>Completed</span><strong>{reasoningRunStats.completed}</strong></div>
              <div><span>Failed</span><strong>{reasoningRunStats.failed}</strong></div>
              <div><span>Replies</span><strong>{reasoningRunStats.withReply}</strong></div>
            </div>
          </section>
          <div className="reasoning-layout">
            <div className="reasoning-run-list">
              {filteredReasoningRuns.length > 0 ? (
                filteredReasoningRuns.slice(0, 24).map((run) => (
                  <button
                    key={run.run_id}
                    data-active={selectedReasoningRunId === run.run_id}
                    onClick={() => setSelectedReasoningRunId(run.run_id)}
                    type="button"
                  >
                    <strong>{run.status}</strong>
                    <span>{run.primary_modality ?? "event"} / {run.depth}</span>
                    <small>{new Date(run.updated_at).toLocaleTimeString()}</small>
                  </button>
                ))
              ) : !reasoningRuns ? (
                <p className="debug-empty">Loading reasoning runs...</p>
              ) : (
                <p className="debug-empty">No reasoning runs match the current filters.</p>
              )}
            </div>
            <div className="reasoning-detail">
              {reasoningRunDetail ? (
                <>
                  <div className="debug-event-head">
                    <strong>{reasoningRunDetail.run.run_id}</strong>
                    <span>{reasoningRunDetail.run.primary_modality ?? reasoningRunDetail.run.event_type}</span>
                  </div>
                  <pre className="debug-code">
                    {JSON.stringify(
                      {
                        event_type: reasoningRunDetail.run.event_type,
                        provider: reasoningRunDetail.run.provider,
                        primary_modality: reasoningRunDetail.run.primary_modality,
                        modalities: reasoningRunDetail.run.modalities ?? []
                      },
                      null,
                      2
                    )}
                  </pre>
                  {reasoningRunDetail.run.failure_summary ? (
                    <article className="debug-event reasoning-failure">
                      <div className="debug-event-head">
                        <strong>Failure</strong>
                        <span>{reasoningRunDetail.run.status}</span>
                      </div>
                      <pre>{reasoningRunDetail.run.failure_summary}</pre>
                    </article>
                  ) : null}
                  <pre>{reasoningRunDetail.run.reply_text || "(no reply)"}</pre>
                  <h3>Context Snapshots</h3>
                  {reasoningRunDetail.context_snapshots.length > 0 ? (
                    reasoningRunDetail.context_snapshots.map((snapshot) => {
                      const payload = snapshotPayload(snapshot.payload);
                      const summary = payload.context_summary ?? {};
                      const refCounts = summary.current_event_ref_counts ?? {};
                      const eventRefs = payload.current_event_refs ?? {};
                      const visualContext = payload.visual_context ?? {};
                      const audioContext = payload.audio_context ?? {};
                      const visualRefs = eventRefs.vision ?? [];
                      const audioRefs = eventRefs.audio ?? [];
                      const attachmentRefs = eventRefs.attachments ?? [];
                      const visualEvidence = visualContext.recent_visual_evidence ?? [];
                      const audioEvidence = audioContext.recent_audio_evidence ?? [];
                      const ocrText = visualContext.recent_ocr_text ?? [];

                      return (
                        <article className="debug-event reasoning-snapshot" key={snapshot.snapshot_id}>
                          <div className="debug-event-head">
                            <strong>{snapshot.schema_version}</strong>
                            <span>{new Date(snapshot.created_at).toLocaleTimeString()}</span>
                          </div>
                          <div className="reasoning-context-summary">
                            <div><span>raw payload stored</span><strong>{snapshotFlag(payload.raw_payload_stored)}</strong></div>
                            <div><span>raw image bytes</span><strong>{snapshotFlag(visualContext.raw_image_bytes_included)}</strong></div>
                            <div><span>raw audio bytes</span><strong>{snapshotFlag(audioContext.raw_audio_bytes_included)}</strong></div>
                            <div><span>local paths</span><strong>{snapshotFlag(Boolean(visualContext.absolute_local_paths_included || audioContext.absolute_local_paths_included || eventRefs.absolute_local_paths_included))}</strong></div>
                            <div><span>current vision refs</span><strong>{snapshotCount(refCounts.vision)}</strong></div>
                            <div><span>current audio refs</span><strong>{snapshotCount(refCounts.audio)}</strong></div>
                            <div><span>recent visual evidence</span><strong>{snapshotCount(summary.recent_visual_evidence_count)}</strong></div>
                            <div><span>recent audio evidence</span><strong>{snapshotCount(summary.recent_audio_evidence_count)}</strong></div>
                          </div>
                          <div className="reasoning-ref-section">
                            <div className="debug-event-head">
                              <strong>Current event refs</strong>
                              <span>{visualRefs.length + audioRefs.length + attachmentRefs.length} item(s)</span>
                            </div>
                            <div className="reasoning-ref-list">
                              {[...visualRefs.map((item) => ({ ...item, modality: "vision" })), ...audioRefs.map((item) => ({ ...item, modality: "audio" })), ...attachmentRefs.map((item) => ({ ...item, modality: "attachment" }))].slice(0, 12).map((item, index) => (
                                <span key={`${String(item.modality)}-${index}`}>
                                  {String(item.modality)}: {compactRefValue(item)}
                                </span>
                              ))}
                              {visualRefs.length + audioRefs.length + attachmentRefs.length === 0 ? (
                                <span>no current multimodal refs</span>
                              ) : null}
                            </div>
                          </div>
                          <div className="reasoning-evidence-grid">
                            <section>
                              <div className="debug-event-head">
                                <strong>Visual evidence</strong>
                                <span>{visualEvidence.length} row(s)</span>
                              </div>
                              {visualEvidence.slice(0, 4).map((item, index) => (
                                <article key={`${String(item.evidence_id ?? index)}-visual`}>
                                  <strong>{compactEvidenceTitle(item, "visual")}</strong>
                                  <span>{compactEvidenceMeta(item)}</span>
                                </article>
                              ))}
                              {ocrText.length > 0 ? <small>OCR text rows: {ocrText.length}</small> : null}
                            </section>
                            <section>
                              <div className="debug-event-head">
                                <strong>Audio evidence</strong>
                                <span>{audioEvidence.length} row(s)</span>
                              </div>
                              {audioEvidence.slice(0, 4).map((item, index) => (
                                <article key={`${String(item.evidence_id ?? index)}-audio`}>
                                  <strong>{compactEvidenceTitle(item, "audio")}</strong>
                                  <span>{compactEvidenceMeta(item)}</span>
                                  {item.transcript ? <small>transcript metadata present, raw text hidden</small> : null}
                                </article>
                              ))}
                            </section>
                          </div>
                          <details className="reasoning-json-details">
                            <summary>Raw snapshot JSON</summary>
                            <pre>{JSON.stringify(snapshot.payload ?? {}, null, 2)}</pre>
                          </details>
                        </article>
                      );
                    })
                  ) : (
                    <p className="debug-empty">No context snapshots.</p>
                  )}
                  <h3>Steps</h3>
                  {reasoningRunDetail.steps.map((step) => (
                    <article className="debug-event" key={step.step_id}>
                      <div className="debug-event-head">
                        <strong>{step.step_index}. {step.step_type}</strong>
                        <span>{step.status}</span>
                      </div>
                      <pre>{step.summary}</pre>
                    </article>
                  ))}
                  <h3>Schema Failures</h3>
                  {reasoningRunDetail.schema_failures.length > 0 ? (
                    reasoningRunDetail.schema_failures.map((failure) => (
                      <article className="debug-event reasoning-failure" key={failure.failure_id}>
                        <div className="debug-event-head">
                          <strong>{failure.error}</strong>
                          <span>{new Date(failure.created_at).toLocaleTimeString()}</span>
                        </div>
                      </article>
                    ))
                  ) : (
                    <p className="debug-empty">No schema failures.</p>
                  )}
                  <h3>Memory Candidates</h3>
                  {reasoningRunDetail.memory_candidates.length > 0 ? (
                    reasoningRunDetail.memory_candidates.map((candidate) => (
                      <article className="debug-event" key={candidate.candidate_id}>
                        <div className="debug-event-head">
                          <strong>{candidate.kind}</strong>
                          <span>{candidate.accepted ? "accepted" : "inspect only"}</span>
                        </div>
                        <pre>{JSON.stringify(candidate.payload ?? {}, null, 2)}</pre>
                      </article>
                    ))
                  ) : (
                    <p className="debug-empty">No memory candidates.</p>
                  )}
                  <h3>Actions</h3>
                  {reasoningRunDetail.actions.length > 0 ? (
                    reasoningRunDetail.actions.map((action) => (
                      <article className="debug-event" key={action.action_id}>
                        <div className="debug-event-head">
                          <strong>{String(action.payload?.name ?? action.action_id)}</strong>
                          <span>{action.status}</span>
                        </div>
                        <pre>{JSON.stringify(action.payload ?? {}, null, 2)}</pre>
                      </article>
                    ))
                  ) : (
                    <p className="debug-empty">No action proposals.</p>
                  )}
                  <h3>Pending Actions</h3>
                  {reasoningRunDetail.pending_actions.length > 0 ? (
                    reasoningRunDetail.pending_actions.map((pending) => (
                      <article className="debug-event reasoning-pending" key={pending.pending_id}>
                        <div className="debug-event-head">
                          <strong>{String(pending.payload?.name ?? pending.action_id)}</strong>
                          <span>{pending.status}</span>
                        </div>
                        <pre>{JSON.stringify(pending.payload ?? {}, null, 2)}</pre>
                      </article>
                    ))
                  ) : (
                    <p className="debug-empty">No pending actions.</p>
                  )}
                  <h3>Audit</h3>
                  {reasoningRunDetail.audit.length > 0 ? (
                    reasoningRunDetail.audit.map((record) => (
                      <article className="debug-event" key={record.audit_id}>
                        <div className="debug-event-head">
                          <strong>{record.kind}</strong>
                          <span>{record.status}</span>
                        </div>
                        <pre>{JSON.stringify(record.payload ?? {}, null, 2)}</pre>
                      </article>
                    ))
                  ) : (
                    <p className="debug-empty">No audit records.</p>
                  )}
                </>
              ) : (
                <p className="debug-empty">Select a reasoning run.</p>
              )}
            </div>
          </div>
        </section>
      );
    }

    if (activeView === "Memory") {
      const activeTextStatus = textStatus ?? memoryShell?.text_reader ?? null;
      const textEvidenceRows = memoryShell?.text_evidence ?? [];
      const activeAudioStatus = audioStatus ?? memoryShell?.audio_reader ?? null;
      const audioEvidenceRows = memoryShell?.audio_evidence ?? [];
      const memoryViews = [
        "Overview",
        "Layers",
        "Modality Rules",
        "Manual Notes",
        "Formal Records",
        "Review Queue",
        "Audit",
        "Text Evidence",
        "Vision Evidence",
        "Audio Evidence",
        "Consolidation",
        "Multimodal Shell"
      ];
      const shellCounts = [
        ["Observations", memoryShell?.observations.length ?? 0],
        ["Text evidence", memoryShell?.text_evidence.length ?? 0],
        ["Visual evidence", memoryShell?.visual_evidence.length ?? 0],
        ["Audio evidence", memoryShell?.audio_evidence.length ?? 0],
        ["Entities", memoryShell?.entities.length ?? 0],
        ["Features", memoryShell?.features.length ?? 0],
        ["Links", memoryShell?.links.length ?? 0],
        ["Review", memoryShell?.review_queue.length ?? 0],
        ["Consolidation", memoryShell?.consolidation_buffer.length ?? 0],
        ["Raw backups", memoryShell?.raw_backups.length ?? 0]
      ];

      return (
        <section className="debug-panel">
          <h2>Memory</h2>
          <div className="memory-tabs" role="tablist" aria-label="Memory debug sections">
            {memoryViews.map((view) => (
              <button
                data-active={memoryView === view}
                key={view}
                onClick={() => setMemoryView(view)}
                type="button"
              >
                {view}
              </button>
            ))}
          </div>

          {memoryView === "Overview" ? (
            <>
              <div className="detail-grid">
                <div><span>Manual writes</span><strong>{memoryStatus?.enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Manual notes</span><strong>{memoryStatus?.items.length ?? 0}</strong></div>
                <div><span>Formal tables</span><strong>{formalMemoryStatus?.formal_tables_ready ? "ready" : "unavailable"}</strong></div>
                <div><span>Multimodal tables</span><strong>{formalMemoryStatus?.multimodal_tables_ready ? "ready" : "unavailable"}</strong></div>
                <div><span>Auto writes</span><strong>{formalMemoryStatus?.automatic_writes_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Capture</span><strong>{formalMemoryStatus?.capture_enabled?.vision || formalMemoryStatus?.capture_enabled?.audio ? "partly on" : "off"}</strong></div>
                <div><span>Records</span><strong>{formalMemoryStatus?.records_count ?? 0}</strong></div>
                <div><span>Audit rows</span><strong>{formalMemoryStatus?.audit_count ?? 0}</strong></div>
                <div><span>Review queue</span><strong>{formalMemoryStatus?.review_count ?? 0}</strong></div>
                <div><span>Text evidence</span><strong>{formalMemoryStatus?.text_evidence_count ?? 0}</strong></div>
                <div><span>Visual evidence</span><strong>{formalMemoryStatus?.visual_evidence_count ?? 0}</strong></div>
                <div><span>Audio evidence</span><strong>{formalMemoryStatus?.audio_evidence_count ?? 0}</strong></div>
                <div><span>Consolidation</span><strong>{formalMemoryStatus?.consolidation_buffer_count ?? 0}</strong></div>
                <div><span>TextReader</span><strong>{activeTextStatus?.mode ?? "unavailable"}</strong></div>
                <div><span>VisionReader</span><strong>{visionStatus?.mode ?? "unavailable"}</strong></div>
                <div><span>AudioReader</span><strong>{activeAudioStatus?.mode ?? "unavailable"}</strong></div>
                <div><span>Unified</span><strong>{memoryContract?.unified_memory ? "yes" : "unknown"}</strong></div>
                <div><span>Text-only identity</span><strong>{memoryContract?.text_only_identity_allowed ? "allowed" : "blocked"}</strong></div>
                <div><span>Deep default</span><strong>{memoryContract?.deep_knowledge_default ? "on" : "off"}</strong></div>
              </div>
              <div className="memory-shell-grid">
                {shellCounts.map(([label, count]) => (
                  <article key={label}>
                    <span>{label}</span>
                    <strong>{count}</strong>
                  </article>
                ))}
              </div>
              <div className="visual-note">
                <strong>Unified memory boundary</strong>
                <span>Manual notes are a legacy/debug surface. Automatic multimodal memory remains disabled and will write through formal records plus evidence/version/audit rules later.</span>
              </div>
              <div className="visual-note">
                <strong>Multimodal evidence boundary</strong>
                <span>Text, visual, and audio evidence share observations, features, links, buffer, and audit. Raw image/audio bytes stay in local raw backup only, and model downloads or external APIs remain disabled.</span>
              </div>
            </>
          ) : null}

          {memoryView === "Layers" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>Unified memory</span><strong>{memoryContract?.unified_memory ? "yes" : "unknown"}</strong></div>
                <div><span>Scene isolation</span><strong>{memoryContract?.scene_isolation_allowed ? "allowed" : "blocked"}</strong></div>
                <div><span>Auto writes</span><strong>{memoryContract?.automatic_writes_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Real capture</span><strong>{memoryContract?.real_capture_enabled ? "enabled" : "disabled"}</strong></div>
              </div>
              <div className="memory-contract-grid">
                {(memoryContract?.layers ?? []).map((layer) => (
                  <article key={layer.name}>
                    <div className="debug-event-head">
                      <strong>{layer.label}</strong>
                      <span>{layer.current_mode}</span>
                    </div>
                    <p>{layer.purpose}</p>
                    <div className="history-chip-row">
                      <span>{layer.writes_enabled ? "writes enabled" : "writes disabled"}</span>
                      <span>{layer.retention}</span>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {memoryView === "Modality Rules" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>Text-only identity</span><strong>{memoryContract?.text_only_identity_allowed ? "allowed" : "blocked"}</strong></div>
                <div><span>Deep knowledge default</span><strong>{memoryContract?.deep_knowledge_default ? "on" : "off"}</strong></div>
                <div><span>Modalities</span><strong>{memoryContract?.modalities.length ?? 0}</strong></div>
                <div><span>Capture</span><strong>{memoryContract?.real_capture_enabled ? "enabled" : "disabled"}</strong></div>
              </div>
              <div className="memory-contract-grid">
                {(memoryContract?.modalities ?? []).map((modality) => (
                  <article key={modality.modality}>
                    <div className="debug-event-head">
                      <strong>{modality.modality}</strong>
                      <span>{modality.current_mode}</span>
                    </div>
                    <p>{modality.identity_body}</p>
                    <div className="history-chip-row">
                      <span>{modality.capture_enabled ? "capture on" : "capture off"}</span>
                      <span>{modality.text_is_auxiliary ? "text auxiliary" : "text allowed as body"}</span>
                    </div>
                    <div className="reserved-list">
                      {modality.required_feature_refs.map((feature) => (
                        <span key={feature}>{feature}</span>
                      ))}
                    </div>
                    <small>{modality.raw_backup}</small>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {memoryView === "Manual Notes" ? (
            <>
              <form
                className="memory-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  addManualMemory();
                }}
              >
                <textarea
                  value={memoryDraft}
                  onChange={(event) => setMemoryDraft(event.target.value)}
                  placeholder="Add a manual memory note..."
                  rows={3}
                />
                <button disabled={memoryBusy || !memoryDraft.trim()} type="submit">
                  Add memory
                </button>
              </form>
              {memoryMessage ? <p className="debug-message">{memoryMessage}</p> : null}
              <div className="memory-list-box">
                {memoryStatus && memoryStatus.items.length > 0 ? (
                  memoryStatus.items.slice(0, 20).map((item) => (
                    <details className="memory-item" key={item.id}>
                      <summary>
                        <span>
                          <strong>{item.text}</strong>
                          <small>{item.kind} / {new Date(item.created_at).toLocaleString()}</small>
                        </span>
                      </summary>
                      <pre>{item.text}</pre>
                      <div className="memory-actions">
                        <button
                          disabled={memoryBusy}
                          onClick={() => deleteManualMemory(item.id)}
                          type="button"
                        >
                          Delete
                        </button>
                      </div>
                    </details>
                  ))
                ) : (
                  <p className="debug-empty">No manual memory items.</p>
                )}
              </div>
            </>
          ) : null}

          {memoryView === "Formal Records" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>Auto writes</span><strong>{formalMemoryRecords?.automatic_writes_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Records</span><strong>{formalMemoryRecords?.records.length ?? 0}</strong></div>
              </div>
              {formalMemoryRecords && formalMemoryRecords.records.length > 0 ? (
                <div className="debug-event-list">
                  {formalMemoryRecords.records.slice(0, 20).map((record) => (
                    <article className="debug-event" key={record.record_id}>
                      <div className="debug-event-head">
                        <strong>{record.kind}</strong>
                        <span>{record.layer} / v{record.version}</span>
                      </div>
                      <pre>{JSON.stringify(record, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="debug-empty">No formal memory records yet. Automatic writes are disabled.</p>
              )}
            </section>
          ) : null}

          {memoryView === "Review Queue" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>Auto writes</span><strong>{memoryReview?.automatic_writes_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Queued</span><strong>{memoryReview?.review_queue.length ?? 0}</strong></div>
                <div><span>Mode</span><strong>read only</strong></div>
                <div><span>Action controls</span><strong>not enabled</strong></div>
              </div>
              {memoryReview && memoryReview.review_queue.length > 0 ? (
                <div className="debug-event-list">
                  {memoryReview.review_queue.slice(0, 30).map((item, index) => (
                    <article className="debug-event reasoning-pending" key={String(item.review_id ?? index)}>
                      <div className="debug-event-head">
                        <strong>{String(item.reason ?? "review item")}</strong>
                        <span>{String(item.status ?? "unknown")}</span>
                      </div>
                      <pre>{JSON.stringify(item, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="debug-empty">No memory review items. Automatic writes are disabled.</p>
              )}
            </section>
          ) : null}

          {memoryView === "Audit" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>Auto writes</span><strong>{memoryAudit?.automatic_writes_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Audit rows</span><strong>{memoryAudit?.audit.length ?? 0}</strong></div>
                <div><span>Mode</span><strong>read only</strong></div>
                <div><span>Clear/export</span><strong>not enabled</strong></div>
              </div>
              {memoryAudit && memoryAudit.audit.length > 0 ? (
                <div className="debug-event-list">
                  {memoryAudit.audit.slice(0, 30).map((entry, index) => (
                    <article className="debug-event" key={String(entry.audit_id ?? index)}>
                      <div className="debug-event-head">
                        <strong>{entry.action ?? "memory audit"}</strong>
                        <span>{entry.created_at ? new Date(entry.created_at).toLocaleTimeString() : "unknown"}</span>
                      </div>
                      <pre>{JSON.stringify(entry, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="debug-empty">No formal memory audit rows yet.</p>
              )}
            </section>
          ) : null}

          {memoryView === "Vision Evidence" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>VisionReader</span><strong>{visionStatus?.mode ?? memoryShell?.vision_reader?.mode ?? "unknown"}</strong></div>
                <div><span>Capture</span><strong>{visionStatus?.capture_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Screen observation</span><strong>{visionStatus?.screen_observation_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Model configured</span><strong>{visionStatus?.model_configured ? "yes" : "no"}</strong></div>
                <div><span>Embedding model</span><strong>{visionStatus?.embedding_model_configured ? "yes" : "no"}</strong></div>
                <div><span>Model download</span><strong>{visionStatus?.model_download_enabled ? "enabled" : "blocked"}</strong></div>
                <div><span>Evidence rows</span><strong>{memoryShell?.visual_evidence.length ?? 0}</strong></div>
                <div><span>Pending extraction</span><strong>{visionStatus?.pending_extractions ?? 0}</strong></div>
              </div>
              <section className="debug-subsection">
                <h3>Attachment Ref Shape</h3>
                <div className="reserved-list">
                  {(memoryShell?.attachment_ref_contract?.required_fields ?? memoryContract?.attachment_ref?.required_fields ?? []).map((field) => (
                    <span key={field}>{field}</span>
                  ))}
                </div>
              </section>
              <section className="debug-subsection">
                <h3>VisionReader Blocked Reasons</h3>
                <div className="reserved-list">
                  {(visionStatus?.blocked_reasons ?? memoryShell?.vision_reader?.blocked_reasons ?? []).map((reason) => (
                    <span key={reason}>{reason}</span>
                  ))}
                </div>
              </section>
              {memoryShell && memoryShell.visual_evidence.length > 0 ? (
                <div className="debug-event-list">
                  {memoryShell.visual_evidence.slice(0, 30).map((item, index) => (
                    <article className="debug-event" key={String(item.evidence_id ?? index)}>
                      <div className="debug-event-head">
                        <strong>{String(item.source ?? "visual evidence")}</strong>
                        <span>{String(item.vision_reader_status ?? "unknown")}</span>
                      </div>
                      <pre>{JSON.stringify(item, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="debug-empty">No visual evidence rows. Manual image import and screen capture are not enabled.</p>
              )}
            </section>
          ) : null}

          {memoryView === "Text Evidence" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>TextReader</span><strong>{activeTextStatus?.mode ?? "unknown"}</strong></div>
                <div><span>Enabled</span><strong>{activeTextStatus?.enabled ? "yes" : "no"}</strong></div>
                <div><span>Command text</span><strong>{activeTextStatus?.auto_observe_command_text ? "observed" : "off"}</strong></div>
                <div><span>Provider raw text</span><strong>{activeTextStatus?.raw_payload_in_provider_prompt ? "allowed" : "bounded"}</strong></div>
                <div><span>Evidence rows</span><strong>{textEvidenceRows.length}</strong></div>
                <div><span>Status count</span><strong>{activeTextStatus?.text_evidence_count ?? textEvidenceRows.length}</strong></div>
              </div>
              <section className="debug-subsection">
                <h3>Supported Sources</h3>
                <div className="reserved-list">
                  {(memoryContract?.text_evidence?.sources ?? []).map((source) => (
                    <span key={source}>{source}</span>
                  ))}
                </div>
              </section>
              {textEvidenceRows.length > 0 ? (
                <div className="debug-event-list">
                  {textEvidenceRows.slice(0, 30).map((item, index) => (
                    <article className="debug-event" key={String(item.evidence_id ?? index)}>
                      <div className="debug-event-head">
                        <strong>{String(item.source ?? "text evidence")}</strong>
                        <span>{String(item.text_reader_status ?? "unknown")}</span>
                      </div>
                      <pre>{JSON.stringify(item, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="debug-empty">No text evidence rows are loaded in Debug yet. Click Refresh; if the status count is nonzero, restart the dev shell so the Debug window reloads current data.</p>
              )}
            </section>
          ) : null}

          {memoryView === "Audio Evidence" ? (
            <section className="debug-subsection">
              <div className="detail-grid">
                <div><span>AudioReader</span><strong>{activeAudioStatus?.mode ?? "unknown"}</strong></div>
                <div><span>Capture</span><strong>{activeAudioStatus?.capture_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Microphone</span><strong>{activeAudioStatus?.microphone_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>ASR</span><strong>{activeAudioStatus?.asr_configured ? "configured" : "not configured"}</strong></div>
                <div><span>Speaker features</span><strong>{activeAudioStatus?.speaker_embedding_configured ? "configured" : "not configured"}</strong></div>
                <div><span>Model download</span><strong>{activeAudioStatus?.model_download_enabled ? "enabled" : "blocked"}</strong></div>
                <div><span>Evidence rows</span><strong>{audioEvidenceRows.length}</strong></div>
                <div><span>Pending transcripts</span><strong>{activeAudioStatus?.pending_transcripts ?? 0}</strong></div>
              </div>
              <section className="debug-subsection">
                <h3>Audio Blocked Reasons</h3>
                <div className="reserved-list">
                  {(activeAudioStatus?.blocked_reasons ?? []).map((reason) => (
                    <span key={reason}>{reason}</span>
                  ))}
                </div>
              </section>
              {audioEvidenceRows.length > 0 ? (
                <div className="debug-event-list">
                  {audioEvidenceRows.slice(0, 30).map((item, index) => (
                    <article className="debug-event" key={String(item.evidence_id ?? index)}>
                      <div className="debug-event-head">
                        <strong>{String(item.source ?? "audio evidence")}</strong>
                        <span>{String(item.audio_reader_status ?? "unknown")}</span>
                      </div>
                      <pre>{JSON.stringify(item, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="debug-empty">No audio evidence rows. Microphone and ASR are still disabled.</p>
              )}
            </section>
          ) : null}

          {memoryView === "Consolidation" ? (
            <section className="debug-subsection">
              {(() => {
                const consolidationRows = consolidationStatus?.buffer ?? memoryShell?.consolidation_buffer ?? [];
                return (
                  <>
              <div className="detail-grid">
                <div><span>Schema</span><strong>{consolidationStatus?.schema_ready ?? formalMemoryStatus?.consolidation_buffer_ready ? "ready" : "unavailable"}</strong></div>
                <div><span>Auto writes</span><strong>{consolidationStatus?.automatic_writes_enabled ?? memoryShell?.automatic_writes_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Sleep consolidation</span><strong>{consolidationStatus?.sleep_consolidation_enabled ?? memoryContract?.consolidation_buffer?.sleep_consolidation_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Buffered items</span><strong>{consolidationRows.length}</strong></div>
              </div>
              {consolidationRows.length > 0 ? (
                <div className="debug-event-list">
                  {consolidationRows.slice(0, 30).map((item, index) => (
                    <article className="debug-event reasoning-pending" key={String(item.buffer_id ?? index)}>
                      <div className="debug-event-head">
                        <strong>{String(item.kind ?? "buffer item")}</strong>
                        <span>{String(item.status ?? "unknown")}</span>
                      </div>
                      <pre>{JSON.stringify(item, null, 2)}</pre>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="debug-empty">No Consolidation Buffer rows. Sleep consolidation and automatic evidence writes are disabled.</p>
              )}
                  </>
                );
              })()}
            </section>
          ) : null}

          {memoryView === "Multimodal Shell" ? (
            <section className="debug-subsection">
              <div className="memory-shell-grid">
                {shellCounts.map(([label, count]) => (
                  <article key={label}>
                    <span>{label}</span>
                    <strong>{count}</strong>
                  </article>
                ))}
              </div>
              <pre className="debug-code">
                {JSON.stringify(
                  {
                    automatic_writes_enabled: memoryShell?.automatic_writes_enabled ?? false,
                    capture_enabled: memoryShell?.capture_enabled ?? {},
                    observations: memoryShell?.observations ?? [],
                    entities: memoryShell?.entities ?? [],
                    features: memoryShell?.features ?? [],
                    links: memoryShell?.links ?? [],
                    review_queue: memoryShell?.review_queue ?? [],
                    consolidation_buffer: memoryShell?.consolidation_buffer ?? [],
                    raw_backups: memoryShell?.raw_backups ?? [],
                    text_evidence: memoryShell?.text_evidence ?? [],
                    visual_evidence: memoryShell?.visual_evidence ?? [],
                    audio_evidence: memoryShell?.audio_evidence ?? [],
                    attachment_ref_contract: memoryShell?.attachment_ref_contract ?? null,
                    text_reader: memoryShell?.text_reader ?? null,
                    vision_reader: memoryShell?.vision_reader ?? null,
                    audio_reader: memoryShell?.audio_reader ?? null
                  },
                  null,
                  2
                )}
              </pre>
            </section>
          ) : null}
        </section>
      );
    }

    if (activeView === "Project Read") {
      return (
        <section className="debug-panel">
          <h2>Project Reader</h2>
          <div className="detail-grid">
            <div><span>Enabled</span><strong>{projectReaderStatus?.enabled ? "yes" : "no"}</strong></div>
            <div><span>Contract</span><strong>{projectReaderContract?.schema_version ?? "unavailable"}</strong></div>
            <div><span>Read-only</span><strong>{projectReaderStatus?.read_only ? "yes" : "unknown"}</strong></div>
            <div><span>Authorized roots</span><strong>{projectReaderStatus?.allowed_roots.length ?? 0}</strong></div>
            <div><span>Listing</span><strong>{projectReaderStatus?.listing_enabled ? "enabled" : "blocked"}</strong></div>
            <div><span>Text types</span><strong>{projectReaderStatus?.text_extensions.length ?? 0}</strong></div>
            <div><span>Content reads</span><strong>{projectReaderStatus?.content_reading_enabled ? "enabled" : "disabled"}</strong></div>
            <div><span>Raw content</span><strong>{projectReaderStatus?.raw_content_return_enabled ? "enabled" : "blocked"}</strong></div>
            <div><span>Recursive scan</span><strong>{projectReaderStatus?.recursive_content_scan_enabled ? "enabled" : "blocked"}</strong></div>
            <div><span>Path escape block</span><strong>{projectReaderStatus?.path_escape_blocking ? "active" : "unknown"}</strong></div>
          </div>
          <section className="debug-subsection">
            <h3>Safety Contract</h3>
            <div className="contract-rule-list">
              {(projectReaderContract?.safety_rules ?? projectReaderStatus?.safety_rules ?? []).map((rule) => (
                <article className="contract-rule-card" data-enabled={rule.enabled} key={rule.name}>
                  <strong>{rule.name}</strong>
                  <span>{rule.enabled ? "active" : "disabled"}</span>
                  <small>{rule.detail}</small>
                </article>
              ))}
            </div>
            {projectReaderContract ? (
              <div className="trace-ref-grid">
                <span><strong>Permission gate</strong>{projectReaderContract.permission_gate}</span>
                <span><strong>Config gate</strong>{projectReaderContract.config_gate}</span>
                <span><strong>Listing scope</strong>{projectReaderContract.listing_scope}</span>
                <span><strong>Root selection</strong>{String(projectReaderContract.path_policy.root_selection)}</span>
                <span><strong>Path input</strong>{projectReaderContract.path_policy.caller_supplied_paths_accepted ? "accepted" : "not accepted"}</span>
              </div>
            ) : null}
          </section>
          <section className="debug-subsection">
            <h3>Blocked Reasons</h3>
            {projectReaderStatus?.blocked_reasons && projectReaderStatus.blocked_reasons.length > 0 ? (
              <div className="project-reader-reasons">
                {projectReaderStatus.blocked_reasons.map((reason) => (
                  <span key={reason}>{reason}</span>
                ))}
              </div>
            ) : (
              <p className="debug-empty">No global block reason reported.</p>
            )}
          </section>
          <section className="debug-subsection">
            <h3>Blocked Outputs</h3>
            {projectReaderContract?.blocked_until_enabled.length ? (
              <div className="project-reader-reasons">
                {projectReaderContract.blocked_until_enabled.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            ) : (
              <p className="debug-empty">Waiting for Project Reader contract.</p>
            )}
          </section>
          <section className="debug-subsection">
            <h3>Authorized Roots</h3>
            {projectReaderStatus?.roots && projectReaderStatus.roots.length > 0 ? (
              <div className="project-root-list">
                {projectReaderStatus.roots.map((root) => (
                  <article className="project-root-card" data-allowed={root.listing_allowed} key={root.index}>
                    <div>
                      <strong>Root {root.index}</strong>
                      <span>{root.path}</span>
                    </div>
                    <div className="history-chip-row">
                      <span>{root.exists ? "exists" : "missing"}</span>
                      <span>{root.is_dir ? "directory" : "not directory"}</span>
                      <span>{root.listing_allowed ? "listable" : "blocked"}</span>
                    </div>
                    {root.blocked_reason ? <small>{root.blocked_reason}</small> : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="debug-empty">No authorized roots configured.</p>
            )}
          </section>
          <section className="debug-subsection">
            <h3>Top-Level Files</h3>
            {projectReaderFiles?.items && projectReaderFiles.items.length > 0 ? (
              <div className="debug-event-list">
                {projectReaderFiles.items.slice(0, 50).map((item, index) => (
                  <article className="debug-event" key={String(item.path ?? item.name ?? index)}>
                    <div className="debug-event-head">
                      <strong>{String(item.name ?? item.path ?? `item-${index}`)}</strong>
                      <span>{String(item.kind ?? item.type ?? "entry")}</span>
                    </div>
                    <pre>{JSON.stringify(item, null, 2)}</pre>
                  </article>
                ))}
              </div>
            ) : (
              <p className="debug-empty">
                {projectReaderFiles?.detail ? String(projectReaderFiles.detail) : "No authorized root listing is available."}
              </p>
            )}
          </section>
          <section className="debug-subsection">
            <h3>Text Extension Whitelist</h3>
            <div className="project-reader-reasons">
              {(projectReaderStatus?.text_extensions ?? []).map((extension) => (
                <span key={extension}>{extension}</span>
              ))}
            </div>
          </section>
        </section>
      );
    }

    if (activeView === "Screen") {
      const screenPermission = permissionDetails.find((item) => item.name === "screen.observe");
      const activeScreenStatus = screenStatus ?? backendScreenStatus;
      const lastFrame = activeScreenStatus?.last_frame ?? null;
      const lastFramePreviewUrl = screenFramePreviewUrl(lastFrame?.raw_ref);
      return (
        <section className="debug-panel">
          <h2>屏幕观察</h2>
          <div className="detail-grid">
            <div><span>运行中</span><strong>{yesNo(activeScreenStatus?.active)}</strong></div>
            <div><span>权限</span><strong>{onOff(activeScreenStatus?.permission_enabled)}</strong></div>
            <div><span>目标屏幕</span><strong>{zhScreenValue(activeScreenStatus?.display ?? "primary")}</strong></div>
            <div><span>采样间隔</span><strong>{activeScreenStatus?.interval_seconds ?? 3}s</strong></div>
            <div><span>基础间隔</span><strong>{activeScreenStatus?.base_interval_seconds ?? 3}s</strong></div>
            <div><span>最大间隔</span><strong>{activeScreenStatus?.max_interval_seconds ?? 5}s</strong></div>
            <div><span>压力状态</span><strong>{activeScreenStatus?.adaptive_pressure_mode || activeScreenStatus?.pressure_mode ? "自动调整" : "稳定"}</strong></div>
            <div><span>调整原因</span><strong>{zhScreenValue(activeScreenStatus?.adaptive_reason ?? "steady")}</strong></div>
            <div><span>保留原图</span><strong>{onOff(activeScreenStatus?.retain_raw)}</strong></div>
            <div><span>已采样</span><strong>{activeScreenStatus?.samples_captured ?? 0}</strong></div>
            <div><span>入库排队</span><strong>{activeScreenStatus?.samples_queued ?? 0}</strong></div>
            <div><span>已入库</span><strong>{activeScreenStatus?.samples_persisted ?? 0}</strong></div>
            <div><span>丢弃</span><strong>{activeScreenStatus?.samples_dropped ?? 0}</strong></div>
            <div><span>跳过</span><strong>{activeScreenStatus?.samples_skipped ?? 0}</strong></div>
            <div><span>超时</span><strong>{activeScreenStatus?.samples_timed_out ?? 0}</strong></div>
            <div><span>活跃请求</span><strong>{activeScreenStatus?.active_capture_requests ?? 0}</strong></div>
            <div><span>入库队列</span><strong>{activeScreenStatus?.evidence_queue_length ?? 0}/{activeScreenStatus?.evidence_queue_limit ?? 2}</strong></div>
            <div><span>入库忙</span><strong>{yesNo(activeScreenStatus?.evidence_queue_busy)}</strong></div>
            <div><span>入库限速</span><strong>{activeScreenStatus?.evidence_min_interval_ms ?? 1000}ms</strong></div>
            <div><span>抽取队列</span><strong>{activeScreenStatus?.extraction_queue_length ?? 0}/{activeScreenStatus?.extraction_queue_limit ?? 1}</strong></div>
            <div><span>抽取忙</span><strong>{yesNo(activeScreenStatus?.extraction_queue_busy)}</strong></div>
            <div><span>抽取限速</span><strong>{activeScreenStatus?.extraction_min_interval_ms ?? 2500}ms</strong></div>
            <div><span>抽取压力</span><strong>{activeScreenStatus?.extraction_pressure_mode ? "压力中" : zhScreenValue(activeScreenStatus?.extraction_pressure_state ?? "steady")}</strong></div>
            <div><span>压力原因</span><strong>{zhScreenValue(activeScreenStatus?.extraction_pressure_reason ?? "steady")}</strong></div>
            <div><span>压力阈值</span><strong>{activeScreenStatus?.extraction_pressure_threshold_seconds ?? activeScreenStatus?.queue_pressure_seconds ?? 30}s</strong></div>
            <div><span>预计积压</span><strong>{optionalMs(activeScreenStatus?.extraction_estimated_backlog_ms)}</strong></div>
            <div><span>最老等待</span><strong>{optionalMs(activeScreenStatus?.extraction_oldest_queued_ms)}</strong></div>
            <div><span>当前抽取</span><strong>{optionalMs(activeScreenStatus?.extraction_running_ms)}</strong></div>
            <div><span>抽取排队</span><strong>{activeScreenStatus?.samples_extraction_queued ?? 0}</strong></div>
            <div><span>已抽取</span><strong>{activeScreenStatus?.samples_extracted ?? 0}</strong></div>
            <div><span>抽取失败</span><strong>{activeScreenStatus?.samples_extraction_failed ?? 0}</strong></div>
            <div><span>抽取丢弃</span><strong>{activeScreenStatus?.samples_extraction_dropped ?? 0}</strong></div>
            <div><span>抽取状态</span><strong>{zhScreenValue(activeScreenStatus?.last_extraction_status ?? "n/a")}</strong></div>
            <div><span>当前证据</span><strong>{activeScreenStatus?.extraction_current_evidence_id ?? "无"}</strong></div>
            <div><span>截图耗时</span><strong>{optionalMs(activeScreenStatus?.last_capture_duration_ms)}</strong></div>
            <div><span>入库耗时</span><strong>{optionalMs(activeScreenStatus?.last_evidence_persist_duration_ms)}</strong></div>
            <div><span>抽取耗时</span><strong>{optionalMs(activeScreenStatus?.last_extraction_duration_ms)}</strong></div>
            <div><span>抽取方式</span><strong>{activeScreenStatus?.last_extraction_provider ?? "n/a"}</strong></div>
            <div><span>平均耗时</span><strong>{optionalMs(activeScreenStatus?.capture_avg_duration_ms)}</strong></div>
            <div><span>最大耗时</span><strong>{optionalMs(activeScreenStatus?.capture_max_duration_ms)}</strong></div>
            <div><span>统计窗口</span><strong>{activeScreenStatus?.capture_history_count ?? 0}</strong></div>
            <div><span>上次排队</span><strong>{optionalTime(activeScreenStatus?.last_extraction_queued_at)}</strong></div>
            <div><span>上次开始抽取</span><strong>{optionalTime(activeScreenStatus?.last_extraction_started_at)}</strong></div>
            <div><span>上次抽取结束</span><strong>{optionalTime(activeScreenStatus?.last_extraction_finished_at)}</strong></div>
            <div><span>上次压力</span><strong>{optionalTime(activeScreenStatus?.last_extraction_pressure_at)}</strong></div>
            <div><span>上次恢复</span><strong>{optionalTime(activeScreenStatus?.last_extraction_recovered_at)}</strong></div>
            <div><span>上次抽取丢弃</span><strong>{optionalTime(activeScreenStatus?.last_extraction_dropped_at)}</strong></div>
            <div><span>上次跳过</span><strong>{activeScreenStatus?.last_skip_reason ?? "无"}</strong></div>
            <div><span>上次超时</span><strong>{optionalTime(activeScreenStatus?.last_timeout_at)}</strong></div>
            <div><span>上次丢弃</span><strong>{activeScreenStatus?.last_drop_reason ?? "无"}</strong></div>
            <div><span>缩略图上限</span><strong>{activeScreenStatus?.max_thumbnail_width ?? "n/a"}px</strong></div>
            <div><span>格式</span><strong>{activeScreenStatus?.capture_mime ?? "image/jpeg"}</strong></div>
            <div><span>JPEG 质量</span><strong>{activeScreenStatus?.jpeg_quality ?? 70}</strong></div>
          </div>
          {screenMessage ? <p className="debug-message">{screenMessage}</p> : null}
          <section className="debug-subsection">
            <h3>观察开关</h3>
            <div className="screen-control-row">
              <label>
                <input
                  type="checkbox"
                  checked={screenSecondaryConfirmed}
                  onChange={(event) => setScreenSecondaryConfirmed(event.target.checked)}
                />
                <span>二次确认：允许屏幕观察</span>
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={screenRetainRaw}
                  disabled={activeScreenStatus?.active}
                  onChange={(event) => setScreenRetainRaw(event.target.checked)}
                />
                <span>保留本地截图原图</span>
              </label>
              <div className="screen-action-row">
                <button
                  type="button"
                  disabled={screenBusy || Boolean(activeScreenStatus?.active)}
                  onClick={startScreenObservation}
                >
                  开始
                </button>
                <button
                  type="button"
                  disabled={screenBusy || Boolean(activeScreenStatus?.active)}
                  onClick={sampleScreenOnce}
                >
                  单次采样
                </button>
                <button
                  type="button"
                  disabled={screenBusy || !activeScreenStatus?.active}
                  onClick={() => stopScreenObservation(false)}
                >
                  停止
                </button>
                <button
                  type="button"
                  disabled={screenBusy}
                  onClick={() => stopScreenObservation(true)}
                >
                  撤销权限
                </button>
              </div>
            </div>
          </section>
          <section className="debug-subsection">
            <h3>权限门控</h3>
            <div className="permission-grid">
              <article className="permission-row" data-risk={screenPermission?.risk ?? "high"}>
                <div>
                  <span>screen.observe</span>
                  <small>{screenPermission?.reason ?? "高风险屏幕观察能力。"}</small>
                </div>
                <div className="permission-flags">
                  <strong data-enabled={Boolean(activeScreenStatus?.permission_enabled)}>
                    {onOff(activeScreenStatus?.permission_enabled)}
                  </strong>
                  <em>{screenPermission?.risk ?? "high"}</em>
                  <em>confirm</em>
                </div>
              </article>
            </div>
          </section>
          <section className="debug-subsection">
            <h3>屏幕观察合同</h3>
            <div className="detail-grid">
              <div><span>版本</span><strong>{screenContract?.schema_version ?? "不可用"}</strong></div>
              <div><span>权限名</span><strong>{screenContract?.permission ?? "screen.observe"}</strong></div>
              <div><span>默认间隔</span><strong>{screenContract?.interval_seconds ?? 3}s</strong></div>
              <div><span>最大间隔</span><strong>{screenContract?.max_interval_seconds ?? 5}s</strong></div>
              <div><span>节奏</span><strong>{screenContract?.sampling_cadence ?? "adaptive_fixed_tick"}</strong></div>
              <div><span>超时策略</span><strong>{screenContract?.overrun_policy ?? "average_duration_pressure_adjusts_interval"}</strong></div>
              <div><span>原图备份</span><strong>{screenContract?.raw_backup_path ?? "runtime/memory_blobs/vision/screenshots/"}</strong></div>
              <div><span>事件内容</span><strong>{screenContract?.event_payload_policy ?? "refs_and_metadata_only"}</strong></div>
              <div><span>模型提示</span><strong>{screenContract?.provider_prompt_policy ?? "refs_status_summaries_only"}</strong></div>
            </div>
            <div className="reserved-list">
              {(screenContract?.rules ?? []).map((rule) => (
                <span key={rule}>{rule}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>最新一帧证据</h3>
            {lastFrame ? (
              <div className="screen-frame-detail">
                {lastFramePreviewUrl ? (
                  <img className="screen-frame-preview" src={lastFramePreviewUrl} alt="最新屏幕截图" />
                ) : (
                  <p className="debug-empty">这一帧没有可预览的本地截图。</p>
                )}
                <pre className="debug-code">
                {JSON.stringify(
                  {
                    event_id: lastFrame.event_id,
                    evidence_status: lastFrame.evidence_status,
                    evidence_id: lastFrame.evidence_id,
                    attachment_id: lastFrame.attachment_id,
                    raw_ref: lastFrame.raw_ref,
                    sha256: lastFrame.sha256,
                    width: lastFrame.width,
                    height: lastFrame.height,
                    source_display_width: lastFrame.source_display_width,
                    source_display_height: lastFrame.source_display_height,
                    thumbnail_max_width: lastFrame.thumbnail_max_width,
                    mime: lastFrame.mime,
                    jpeg_quality: lastFrame.jpeg_quality,
                    capture_duration_ms: lastFrame.capture_duration_ms,
                    capture_stage_durations_ms: lastFrame.capture_stage_durations_ms,
                    persist_duration_ms: lastFrame.persist_duration_ms,
                    persist_stage_durations_ms: lastFrame.persist_stage_durations_ms,
                    size_bytes: lastFrame.size_bytes,
                    raw_available: lastFrame.raw_available,
                    vision_reader_status: lastFrame.vision_reader_status,
                    raw_payload_returned: lastFrame.raw_payload_returned
                  },
                  null,
                  2
                )}
                </pre>
              </div>
            ) : (
              <p className="debug-empty">本次 Debug 会话还没有采样屏幕帧。</p>
            )}
          </section>
          <section className="debug-subsection">
            <h3>拦截原因</h3>
            <div className="reserved-list">
              {(activeScreenStatus?.blocked_reasons ?? []).map((reason) => (
                <span key={reason}>{reason}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>数据策略</h3>
            <div className="visual-status-grid">
              <article>
                <span>事件历史</span>
                <strong>{activeScreenStatus?.raw_payload_in_events ? "原始字节" : "只存引用"}</strong>
                <small>screen.observation.captured 只存附件引用和元数据。</small>
              </article>
              <article>
                <span>模型提示词</span>
                <strong>{activeScreenStatus?.raw_payload_in_provider_prompt ? "原始字节" : "引用/状态"}</strong>
                <small>文本模型不会被假装成直接看过截图。</small>
              </article>
              <article>
                <span>视觉读取器</span>
                <strong>{visionStatus?.mode ?? "metadata_only"}</strong>
                <small>这个开关不会偷偷下载大模型。</small>
              </article>
            </div>
          </section>
        </section>
      );
    }

    if (["External", "Voice", "VR/OSC"].includes(activeView)) {
      const plan = reservedModulePlan(activeView);
      const capabilities = plan?.capabilities ?? [];
      const enabledCount = capabilities.filter((name) => Boolean(permissionStatus?.permissions[name])).length;
      return (
        <section className="debug-panel">
          <h2>{plan?.title ?? activeView}</h2>
          <div className="detail-grid">
            <div><span>Mode</span><strong>{plan?.mode ?? "reserved"}</strong></div>
            <div><span>Capabilities</span><strong>{enabledCount} / {capabilities.length} on</strong></div>
            <div><span>Execution</span><strong>disabled</strong></div>
            <div><span>Config</span><strong>not configured</strong></div>
          </div>
          <section className="debug-subsection">
            <h3>Capability Gates</h3>
            <div className="permission-grid">
              {capabilities.map((name) => {
                const enabled = Boolean(permissionStatus?.permissions[name]);
                const detail = permissionDetails.find((item) => item.name === name);
                return (
                  <article className="permission-row" data-risk={detail?.risk ?? "medium"} key={name}>
                    <div>
                      <span>{name}</span>
                      <small>{detail?.reason ?? "Reserved capability."}</small>
                    </div>
                    <div className="permission-flags">
                      <strong data-enabled={enabled}>{enabled ? "on" : "off"}</strong>
                      {detail?.risk ? <em>{detail.risk}</em> : null}
                      {detail?.requires_secondary_confirmation ? <em>confirm</em> : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Blocked Reasons</h3>
            <div className="reserved-list">
              {(plan?.blocked ?? []).map((item) => <span key={item}>{item}</span>)}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Before Enabling</h3>
            <div className="reserved-list">
              {(plan?.required ?? []).map((item) => <span key={item}>{item}</span>)}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Planned Events</h3>
            <div className="reserved-list">
              {(plan?.events ?? []).map((item) => <span key={item}>{item}</span>)}
            </div>
          </section>
        </section>
      );
    }

    if (activeView === "History") {
      return (
        <section className="debug-panel">
          <h2>History</h2>
          <div className="detail-grid">
            <div><span>Persisted</span><strong>{eventHistoryStatus?.exists ? "yes" : "no"}</strong></div>
            <div><span>File bytes</span><strong>{eventHistoryStatus?.bytes ?? 0}</strong></div>
            <div><span>Lines</span><strong>{eventHistoryStatus?.total_lines ?? 0}</strong></div>
            <div><span>Loaded</span><strong>{eventHistoryStatus?.recent_loaded ?? events.length}</strong></div>
            <div><span>Recent limit</span><strong>{eventHistoryStatus?.recent_limit ?? 80}</strong></div>
            <div><span>Persisted limit</span><strong>{eventHistoryStatus?.persisted_limit ?? 500}</strong></div>
          </div>
          <div className="history-toolbar">
            <label>
              <span>Source</span>
              <select
                value={historySourceFilter}
                onChange={(event) => setHistorySourceFilter(event.target.value)}
              >
                {historySources.map((source) => (
                  <option key={source} value={source}>{source}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Modality</span>
              <select
                value={historyModalityFilter}
                onChange={(event) => setHistoryModalityFilter(event.target.value)}
              >
                {historyModalities.map((modality) => (
                  <option key={modality} value={modality}>{modality}</option>
                ))}
              </select>
            </label>
            <div>
              <span>Shown</span>
              <strong>{filteredHistoryEvents.length} / {events.length}</strong>
            </div>
          </div>
          {eventHistoryStatus?.error ? (
            <article className="debug-event reasoning-failure">
              <div className="debug-event-head">
                <strong>History Read Error</strong>
                <span>diagnostic only</span>
              </div>
              <pre>{eventHistoryStatus.error}</pre>
            </article>
          ) : null}
          <pre className="debug-code">
            {JSON.stringify(
              {
                path: eventHistoryStatus?.path,
                recent_types: eventHistoryStatus?.recent_types ?? [],
                source_counts: eventHistoryStatus?.source_counts ?? {},
                modality_counts: eventHistoryStatus?.modality_counts ?? {}
              },
              null,
              2
            )}
          </pre>
          <div className="history-layout">
            <div className="timeline-list">
              {filteredHistoryEvents.length > 0 ? (
                filteredHistoryEvents.slice(0, 48).map((event, index) => {
                  const modalities = inferDebugEventModalities(event);
                  const traceRefs = eventTraceRefs(event);
                  const eventKey = eventStableKey(event, index);
                  const selected = selectedHistoryEvent === event;
                  return (
                    <button
                      className="timeline-item"
                      data-selected={selected}
                      key={eventKey}
                      type="button"
                      onClick={() => setSelectedHistoryEventId(eventKey)}
                    >
                      <span>{eventTimeLabel(event)}</span>
                      <strong>{event.type}</strong>
                      <small>{String(event.source ?? "unknown")}</small>
                      <em>{modalities.join(", ")}</em>
                      {traceRefs.length > 0 ? (
                        <i>{traceRefs.slice(0, 3).map((ref) => `${ref.label}: ${shortTraceValue(ref.value)}`).join(" | ")}</i>
                      ) : null}
                    </button>
                  );
                })
              ) : (
                <p className="debug-empty">No event history matches the current filters.</p>
              )}
            </div>
            <article className="history-detail">
              {selectedHistoryEvent ? (
                <>
                  <div className="debug-event-head">
                    <strong>{selectedHistoryEvent.type}</strong>
                    <span>{eventTimeLabel(selectedHistoryEvent)}</span>
                  </div>
                  <div className="history-chip-row">
                    <span>{String(selectedHistoryEvent.source ?? "unknown")}</span>
                    {inferDebugEventModalities(selectedHistoryEvent).map((modality) => (
                      <span key={modality}>{modality}</span>
                    ))}
                  </div>
                  <section className="debug-subsection">
                    <h3>Trace References</h3>
                    <div className="trace-ref-grid">
                      {selectedHistoryTraceRefs.length > 0 ? (
                        selectedHistoryTraceRefs.map((ref) => (
                          <span key={`${ref.label}-${ref.value}`}>
                            <strong>{ref.label}</strong>
                            {ref.value}
                          </span>
                        ))
                      ) : (
                        <em>No trace IDs found.</em>
                      )}
                    </div>
                  </section>
                  <pre>
                    {JSON.stringify(
                      {
                        event_id: selectedHistoryEvent.event_id,
                        correlation_id: selectedHistoryEvent.correlation_id ?? null,
                        payload: selectedHistoryEvent.payload ?? {}
                      },
                      null,
                      2
                    )}
                  </pre>
                </>
              ) : (
                <p className="debug-empty">Select an event to inspect its payload.</p>
              )}
            </article>
          </div>
        </section>
      );
    }

    if (activeView === "Visual") {
      return (
        <section className="debug-panel">
          <h2>Visual</h2>
          <div className="detail-grid">
            <div><span>Pet window</span><strong>700 x 540</strong></div>
            <div><span>Model canvas offset</span><strong>300, 150</strong></div>
            <div><span>Visible model bounds</span><strong>192 x 273</strong></div>
            <div><span>Bubble lines</span><strong>2</strong></div>
            <div><span>State contract</span><strong>{stateContract?.schema_version ?? "unavailable"}</strong></div>
            <div><span>State event</span><strong>{stateContract?.event_type ?? "pet.state.changed"}</strong></div>
          </div>
          <section className="debug-subsection">
            <h3>State Contract</h3>
            {renderContractRules(stateContract?.rules)}
          </section>
          <section className="debug-subsection">
            <h3>Implemented States</h3>
            <div className="visual-status-grid">
              {(stateContract?.implemented_states ?? []).map((state) => (
                <article key={state.name}>
                  <span>{state.name}</span>
                  <strong>{state.source}</strong>
                  <small>{state.detail}</small>
                </article>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Reserved States</h3>
            <div className="project-reader-reasons">
              {(stateContract?.reserved_states ?? []).map((state) => (
                <span key={state}>{state}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Blocked State Side Effects</h3>
            <div className="project-reader-reasons">
              {(stateContract?.blocked_until_explicit_design ?? []).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </section>
          <div className="visual-status-grid">
            <article>
              <span>Current model</span>
              <strong>placeholder</strong>
              <small>Program-drawn pixel stand-in for shell, hit-test, drag, and state validation.</small>
            </article>
            <article>
              <span>Renderer target</span>
              <strong>layered canvas</strong>
              <small>Future pseudo-Live2D style parts, transforms, explicit hit areas, and hard pixel scaling.</small>
            </article>
            <article>
              <span>Locked now</span>
              <strong>behavior only</strong>
              <small>Window drag, transparent pass-through, event-driven bubble, separate input, and state feedback.</small>
            </article>
            <article>
              <span>Not locked</span>
              <strong>final art</strong>
              <small>Final model look, character sheet, canvas size, and manga/comic bubble art remain future decisions.</small>
            </article>
          </div>
          <div className="visual-note">
            <strong>Next visual asset pass</strong>
            <span>Compare model scale previews, choose visual mood concepts, then replace this placeholder without changing the event/state contracts.</span>
          </div>
        </section>
      );
    }

    if (activeView === "Logs") {
      return (
        <section className="debug-panel">
          <h2>Logs</h2>
          <div className="detail-grid">
            <div><span>Redaction</span><strong>{logStatus?.redaction_enabled ? "enabled" : "unknown"}</strong></div>
            <div><span>Token</span><strong>{logStatus?.redaction_token ?? "unavailable"}</strong></div>
            <div><span>Cleanup</span><strong>{logStatus?.display_cleanup?.length ?? 0} rule(s)</strong></div>
            <div><span>Secret patterns</span><strong>{logStatus?.redaction_patterns?.length ?? 0} rule(s)</strong></div>
          </div>
          <section className="debug-subsection">
            <h3>Secret Redaction Rules</h3>
            <div className="reserved-list">
              {(logStatus?.redaction_patterns ?? []).map((pattern) => (
                <span key={pattern}>{pattern}</span>
              ))}
            </div>
          </section>
          <section className="debug-subsection">
            <h3>Display Cleanup</h3>
            <div className="reserved-list">
              {(logStatus?.display_cleanup ?? []).map((rule) => (
                <span key={rule}>{rule}</span>
              ))}
            </div>
          </section>
          <div className="debug-event-list">
            {logStatus && logStatus.logs.length > 0 ? (
              logStatus.logs.map((log) => (
                <article className="debug-event log-card" data-kind={log.kind} key={log.name}>
                  <div className="debug-event-head">
                    <strong>{log.name}</strong>
                    <span>{log.kind} / {log.bytes} bytes / {log.redacted_lines ?? 0} redacted</span>
                  </div>
                  <div className="log-flags">
                    <span>{log.display_cleaned ? "display cleaned" : "raw display"}</span>
                    <span>{log.redacted_lines ?? 0} line(s) redacted</span>
                  </div>
                  <pre>{log.tail.length > 0 ? log.tail.join("\n") : "(empty)"}</pre>
                </article>
              ))
            ) : (
              <p className="debug-empty">No log files found.</p>
            )}
          </div>
        </section>
      );
    }

    return (
      <>
        <div className="debug-summary">
          <div>
            <span>Backend</span>
            <strong>{backendStatus}</strong>
          </div>
          <div>
            <span>Pet state</span>
            <strong>{petState}</strong>
          </div>
          <div>
            <span>Events</span>
            <strong>{events.length}</strong>
          </div>
        </div>
        <section className="debug-panel">
          <h2>Modules</h2>
          {moduleTiles}
        </section>
        <section className="debug-panel">
          <h2>Safety Snapshot</h2>
          <div className="safety-grid">
            {safetySnapshot.map((item) => (
              <article className="safety-card" data-state={item.state} key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.detail}</small>
              </article>
            ))}
          </div>
        </section>
        <section className="debug-panel">
          <h2>Contracts Index</h2>
          <div className="detail-grid">
            <div><span>Schema</span><strong>{contractsIndex?.schema_version ?? "unavailable"}</strong></div>
            <div><span>Contracts</span><strong>{contractsIndex?.entries.length ?? 0}</strong></div>
            <div><span>Status endpoints</span><strong>{contractsIndex?.status_endpoints.length ?? 0}</strong></div>
            <div><span>Mutation</span><strong>{contractsIndex?.mutation_enabled ? "enabled" : "blocked"}</strong></div>
          </div>
          <div className="visual-status-grid">
            {(contractsIndex?.entries ?? []).map((entry) => (
              <article key={entry.endpoint}>
                <span>{entry.name}</span>
                <strong>{entry.endpoint}</strong>
                <small>{entry.risk_scope}</small>
              </article>
            ))}
          </div>
          <section className="debug-subsection">
            <h3>Still Blocked</h3>
            <div className="project-reader-reasons">
              {(contractsIndex?.blocked_until_explicit_user_selection ?? []).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </section>
        </section>
        <section className="debug-panel">
          <h2>Recent Events</h2>
          {renderEventsPanel(8)}
        </section>
      </>
    );
  }

  return (
    <main className="debug-window">
      <aside className="debug-sidebar">
        <h1>Y_Chat</h1>
        {navItems.map((item) => (
          <button
            key={item}
            data-active={activeView === item}
            onClick={() => setActiveView(item)}
          >
            {DEBUG_NAV_LABELS[item] ?? item}
          </button>
        ))}
      </aside>
      <section className="debug-content">
        <header className="debug-toolbar">
          <div>
            <span>调试</span>
            <h2>{DEBUG_NAV_LABELS[activeView] ?? activeView}</h2>
          </div>
          <button onClick={refreshDebugData}>刷新</button>
        </header>
        {renderActiveView()}
      </section>
    </main>
  );
}

function App() {
  const kind = currentWindowKind();
  if (kind === "screen-worker") return null;
  if (kind === "command") return <CommandWindow />;
  if (kind === "debug") return <DebugWindow />;
  return <PetWindow />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
