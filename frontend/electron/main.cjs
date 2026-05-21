const { app, BrowserWindow, globalShortcut, ipcMain, screen } = require("electron");
const { execFile } = require("child_process");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const VITE_URL = "http://127.0.0.1:5173";
const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const RUNTIME_DIR = path.join(PROJECT_ROOT, "runtime");
const EVENT_HISTORY_FILE = path.join(RUNTIME_DIR, "events.jsonl");
const SCREENSHOT_DIR = path.join(RUNTIME_DIR, "memory_blobs", "vision", "screenshots");
const SCREEN_CAPTURE_SCRIPT = path.join(PROJECT_ROOT, "scripts", "capture_screen.py");
const CONDA_ENV = process.env.Y_CHAT_CONDA_ENV || "y_chat";
const RECENT_EVENT_LIMIT = 80;
const PERSISTED_EVENT_LIMIT = 500;
const EVENT_TRIM_INTERVAL = 50;
const SCREEN_OBSERVATION_BASE_INTERVAL_MS = 3000;
const SCREEN_OBSERVATION_MAX_INTERVAL_MS = 5000;
const SCREEN_OBSERVATION_INTERVAL_STEP_MS = 1000;
const SCREEN_CAPTURE_HISTORY_LIMIT = 8;
const SCREEN_CAPTURE_MAX_ACTIVE_REQUESTS = 2;
const SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH = 640;
const SCREEN_CAPTURE_MIME = "image/jpeg";
const SCREEN_CAPTURE_FILE_EXTENSION = "jpg";
const SCREEN_CAPTURE_JPEG_QUALITY = 70;
const SCREEN_EVIDENCE_QUEUE_LIMIT = 2;
const SCREEN_EVIDENCE_MIN_INTERVAL_MS = 1000;
const VISION_EXTRACTION_QUEUE_LIMIT = 1;
const VISION_EXTRACTION_MIN_INTERVAL_MS = 2500;
const VISION_EXTRACTION_PRESSURE_THRESHOLD_MS = 30000;
const VISION_EXTRACTION_RECOVERY_VISIBLE_MS = 30000;
const REDACTED = "[REDACTED]";
const REDACTED_MULTIMODAL = "[REDACTED_MULTIMODAL_PAYLOAD]";

let petWindow;
let commandWindow;
let debugWindow;
let screenWorkerWindow;
let screenWorkerReady = false;
let screenWorkerReadyPromise = null;
let screenCaptureBackend = "electron_desktop_capturer";
let petDragState = null;
let currentPetState = "idle";
let screenObservationTimer = null;
let activeScreenCaptureRequests = 0;
let screenEvidenceQueue = [];
let screenEvidenceQueueBusy = false;
let screenEvidenceQueueTimer = null;
let screenEvidenceLastStartedAt = 0;
let visionExtractionQueue = [];
let visionExtractionQueueBusy = false;
let visionExtractionQueueTimer = null;
let visionExtractionPressureTimer = null;
let visionExtractionLastStartedAt = 0;
let visionExtractionRunningStartedAt = 0;
let visionExtractionLastRecoveredAtMs = 0;
const screenWorkerRequests = new Map();
let persistedEventAppendCount = 0;
let eventPersistenceQueue = Promise.resolve();
const screenObservationState = {
  active: false,
  startAllowed: false,
  intervalSeconds: SCREEN_OBSERVATION_BASE_INTERVAL_MS / 1000,
  baseIntervalSeconds: SCREEN_OBSERVATION_BASE_INTERVAL_MS / 1000,
  maxIntervalSeconds: SCREEN_OBSERVATION_MAX_INTERVAL_MS / 1000,
  retainRaw: true,
  samplesCaptured: 0,
  samplesSkipped: 0,
  samplesTimedOut: 0,
  samplesQueued: 0,
  samplesPersisted: 0,
  samplesDropped: 0,
  samplesExtractionQueued: 0,
  samplesExtracted: 0,
  samplesExtractionFailed: 0,
  samplesExtractionDropped: 0,
  lastCaptureDurationMs: null,
  lastCaptureStageDurationsMs: null,
  lastEvidencePersistDurationMs: null,
  lastEvidencePersistStageDurationsMs: null,
  evidenceQueueLength: 0,
  evidenceQueueBusy: false,
  evidenceQueueLimit: SCREEN_EVIDENCE_QUEUE_LIMIT,
  evidenceMinIntervalMs: SCREEN_EVIDENCE_MIN_INTERVAL_MS,
  extractionQueueLength: 0,
  extractionQueueBusy: false,
  extractionQueueLimit: VISION_EXTRACTION_QUEUE_LIMIT,
  extractionMinIntervalMs: VISION_EXTRACTION_MIN_INTERVAL_MS,
  extractionPressureThresholdSeconds: VISION_EXTRACTION_PRESSURE_THRESHOLD_MS / 1000,
  extractionPressureMode: false,
  extractionPressureState: "steady",
  extractionPressureReason: "steady",
  extractionEstimatedBacklogMs: 0,
  extractionOldestQueuedMs: null,
  extractionRunningMs: null,
  lastExtractionDurationMs: null,
  lastExtractionProvider: null,
  lastExtractionModel: null,
  lastExtractionStatus: null,
  lastExtractionEvidenceId: null,
  extractionCurrentEvidenceId: null,
  lastExtractionFeatureId: null,
  lastExtractionError: null,
  lastExtractionQueuedAt: null,
  lastExtractionStartedAt: null,
  lastExtractionFinishedAt: null,
  lastExtractionPressureAt: null,
  lastExtractionRecoveredAt: null,
  lastExtractionDroppedAt: null,
  captureAvgDurationMs: null,
  captureMaxDurationMs: null,
  captureHistoryCount: 0,
  recentSkippedCount: 0,
  adaptivePressureMode: false,
  adaptiveReason: "steady",
  lastSkipReason: null,
  lastSkipAt: null,
  lastTimeoutAt: null,
  lastDropReason: null,
  lastDropAt: null,
  lastFrame: null,
  lastError: null,
  lastAuditId: null
};
const screenCaptureHistory = [];
const recentEvents = [];

const PET_WINDOW_SIZE = {
  width: 700,
  height: 540
};

const MODEL_CANVAS_OFFSET = {
  x: 300,
  y: 150
};

const MODEL_VISIBLE_BOUNDS = {
  x: MODEL_CANVAS_OFFSET.x + 60,
  y: MODEL_CANVAS_OFFSET.y + 54,
  width: 192,
  height: 273
};
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
const SENSITIVE_PAYLOAD_KEY_PARTS = [
  "api_key",
  "apikey",
  "x_api_key",
  "x-api-key",
  "token",
  "access_token",
  "refresh_token",
  "secret",
  "password",
  "authorization",
  "cookie",
  "credential"
];
const RAW_MULTIMODAL_PAYLOAD_KEYS = new Set([
  "image",
  "images",
  "audio",
  "video",
  "waveform",
  "screenshot",
  "frame",
  "crop",
  "bytes",
  "blob",
  "base64",
  "raw_payload",
  "raw_bytes",
  "image_bytes",
  "audio_bytes",
  "video_bytes"
]);
const AUTH_HEADER_RE = /\b(authorization)(\s*[:=]\s*)([^\s,;]+(?:\s+[^\s,;]+)?)/gi;
const COOKIE_HEADER_RE = /\b(cookie|set-cookie)(\s*[:=]\s*)([^\r\n]+)/gi;
const BEARER_TOKEN_RE = /\b(bearer)\s+([A-Za-z0-9._~+/=-]{8,})/gi;
const SENSITIVE_ASSIGNMENT_RE =
  /(["']?\b(api[_-]?key|x-api-key|token|access[_-]?token|refresh[_-]?token|secret|password|credential)\b["']?)(\s*[:=]\s*)(["']?)([^"'\s,;}]+)(["']?)/gi;
const DATA_URI_RE = /^data:(image|audio|video)\//i;

function makeEvent(type, source, payload, correlationId = null) {
  return {
    event_id: crypto.randomUUID(),
    type,
    source,
    timestamp: new Date().toISOString(),
    correlation_id: correlationId,
    payload
  };
}

function rememberEvent(event) {
  if (!event) return;
  const diagnosticEvent = sanitizeEventForHistory(event);
  recentEvents.unshift(diagnosticEvent);
  if (recentEvents.length > RECENT_EVENT_LIMIT) recentEvents.pop();
  void persistEvent(diagnosticEvent);
  if (isWindowUsable(debugWindow)) {
    debugWindow.webContents.send("debug:events", recentEvents);
  }
}

function normalizedPayloadKey(key) {
  return String(key || "").trim().toLowerCase().replace(/-/g, "_");
}

function isSensitivePayloadKey(key) {
  const normalized = normalizedPayloadKey(key);
  return SENSITIVE_PAYLOAD_KEY_PARTS.some((part) => normalized.includes(part.replace(/-/g, "_")));
}

function isRawMultimodalPayloadKey(key) {
  return RAW_MULTIMODAL_PAYLOAD_KEYS.has(normalizedPayloadKey(key));
}

function redactString(value) {
  let next = String(value);
  next = next.replace(AUTH_HEADER_RE, (_match, name, sep) => `${name}${sep}${REDACTED}`);
  next = next.replace(COOKIE_HEADER_RE, (_match, name, sep) => `${name}${sep}${REDACTED}`);
  next = next.replace(BEARER_TOKEN_RE, (_match, name) => `${name} ${REDACTED}`);
  next = next.replace(SENSITIVE_ASSIGNMENT_RE, (_match, key, _kind, sep, quoteStart, _secret, quoteEnd) => {
    return `${key}${sep}${quoteStart}${REDACTED}${quoteEnd}`;
  });
  if (DATA_URI_RE.test(next)) return REDACTED_MULTIMODAL;
  return next;
}

function sanitizeDiagnosticValue(value, depth = 0) {
  if (depth >= 8) return "[REDACTED_MAX_DEPTH]";
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeDiagnosticValue(item, depth + 1));
  }
  if (value && typeof value === "object") {
    const next = {};
    for (const [key, item] of Object.entries(value)) {
      if (isSensitivePayloadKey(key)) {
        next[key] = REDACTED;
      } else if (isRawMultimodalPayloadKey(key)) {
        next[key] = REDACTED_MULTIMODAL;
      } else {
        next[key] = sanitizeDiagnosticValue(item, depth + 1);
      }
    }
    return next;
  }
  if (typeof value === "string") return redactString(value);
  return value;
}

function sanitizeEventForHistory(event) {
  const payload = event?.payload && typeof event.payload === "object" ? event.payload : {};
  const sanitizedPayload = sanitizeDiagnosticValue(payload);
  const payloadRedacted = JSON.stringify(payload) !== JSON.stringify(sanitizedPayload);
  return {
    event_id: event?.event_id,
    type: event?.type,
    source: event?.source,
    timestamp: event?.timestamp,
    correlation_id: event?.correlation_id ?? null,
    payload: sanitizedPayload,
    payload_redacted: Boolean(event?.payload_redacted || payloadRedacted),
    raw_payload_stored_in_event: false
  };
}

function addModality(modalities, modality) {
  if (!modalities.includes(modality)) modalities.push(modality);
}

function hasAnyKey(keys, expected) {
  return expected.some((key) => keys.has(key));
}

function inferEventModalities(event) {
  const type = String(event?.type || "").toLowerCase();
  const payload = event?.payload && typeof event.payload === "object" ? event.payload : {};
  const keys = new Set(Object.keys(payload).map((key) => key.toLowerCase()));
  const modalities = [];

  if (type.startsWith("user.command.") || type.startsWith("chat.") || type.startsWith("text.")) {
    addModality(modalities, "text");
  }
  if (
    type.startsWith("screen.") ||
    type.startsWith("vision.") ||
    type.startsWith("visual.") ||
    type.startsWith("camera.") ||
    type.startsWith("ocr.")
  ) {
    addModality(modalities, "vision");
  }
  if (
    type.startsWith("voice.") ||
    type.startsWith("audio.") ||
    type.startsWith("speech.") ||
    type.startsWith("microphone.")
  ) {
    addModality(modalities, "audio");
  }
  if (type.startsWith("pet.state.")) addModality(modalities, "state");
  if (type.startsWith("pet.model.")) addModality(modalities, "interaction");
  if (type.startsWith("memory.")) addModality(modalities, "memory");
  if (type.startsWith("project.")) addModality(modalities, "project");
  if (type.startsWith("action.")) addModality(modalities, "action");
  if (type.startsWith("debug.")) addModality(modalities, "debug");
  if (type.startsWith("system.")) addModality(modalities, "system");
  if (type.startsWith("error.")) addModality(modalities, "error");
  if (type.startsWith("external.")) addModality(modalities, "external");
  if (type.startsWith("vr.")) addModality(modalities, "vr");

  if (hasAnyKey(keys, TEXT_PAYLOAD_KEYS)) addModality(modalities, "text");
  if (hasAnyKey(keys, VISION_PAYLOAD_KEYS)) addModality(modalities, "vision");
  if (hasAnyKey(keys, AUDIO_PAYLOAD_KEYS)) addModality(modalities, "audio");
  if (hasAnyKey(keys, STATE_PAYLOAD_KEYS)) addModality(modalities, "state");
  if (hasAnyKey(keys, PROJECT_PAYLOAD_KEYS)) addModality(modalities, "project");

  return modalities.length > 0 ? modalities : ["event"];
}

function incrementCount(counts, key) {
  counts[key] = (counts[key] || 0) + 1;
}

function readPersistedEvents() {
  try {
    if (!fs.existsSync(EVENT_HISTORY_FILE)) return [];
    const lines = fs
      .readFileSync(EVENT_HISTORY_FILE, "utf8")
      .split(/\r?\n/)
      .filter(Boolean)
      .slice(-RECENT_EVENT_LIMIT);
    return lines
      .map((line) => {
        try {
          return JSON.parse(line);
        } catch {
          return null;
        }
      })
      .filter(Boolean)
      .reverse();
  } catch {
    return [];
  }
}

function readRuntimeConfig() {
  const configPath = path.join(RUNTIME_DIR, "config.yaml");
  if (!fs.existsSync(configPath)) return {};
  const root = {};
  const stack = [{ indent: -1, value: root }];
  const lines = fs.readFileSync(configPath, "utf8").split(/\r?\n/);

  for (const rawLine of lines) {
    if (!rawLine.trim() || rawLine.trimStart().startsWith("#")) continue;
    const indent = rawLine.match(/^\s*/)?.[0].length ?? 0;
    const match = rawLine.trim().match(/^([^:]+):(.*)$/);
    if (!match) continue;
    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) {
      stack.pop();
    }
    const parent = stack[stack.length - 1].value;
    const key = match[1].trim();
    const rawValue = match[2].trim();
    if (!rawValue) {
      const child = {};
      parent[key] = child;
      stack.push({ indent, value: child });
    } else if (rawValue === "true" || rawValue === "false") {
      parent[key] = rawValue === "true";
    } else if (/^-?\d+(\.\d+)?$/.test(rawValue)) {
      parent[key] = Number(rawValue);
    } else {
      parent[key] = rawValue.replace(/^['"]|['"]$/g, "");
    }
  }

  return root;
}

async function trimPersistedEvents() {
  try {
    const content = await fs.promises.readFile(EVENT_HISTORY_FILE, "utf8");
    const lines = content.split(/\r?\n/).filter(Boolean);
    if (lines.length <= PERSISTED_EVENT_LIMIT) return;
    await fs.promises.writeFile(
      EVENT_HISTORY_FILE,
      `${lines.slice(-PERSISTED_EVENT_LIMIT).join("\n")}\n`,
      "utf8"
    );
  } catch {
    // Event history must never break the desktop shell.
  }
}

function eventHistoryStatus() {
  try {
    if (!fs.existsSync(EVENT_HISTORY_FILE)) {
      return {
        path: EVENT_HISTORY_FILE,
        exists: false,
        bytes: 0,
        persisted_limit: PERSISTED_EVENT_LIMIT,
        recent_limit: RECENT_EVENT_LIMIT,
        total_lines: 0,
        recent_loaded: recentEvents.length,
        recent_types: [],
        source_counts: {},
        modality_counts: {}
      };
    }

    const stat = fs.statSync(EVENT_HISTORY_FILE);
    const lines = fs.readFileSync(EVENT_HISTORY_FILE, "utf8").split(/\r?\n/).filter(Boolean);
    const recentTypes = lines
      .slice(-10)
      .map((line) => {
        try {
          return JSON.parse(line)?.type || "unknown";
        } catch {
          return "invalid";
        }
      })
      .reverse();
    const sourceCounts = {};
    const modalityCounts = {};
    for (const line of lines.slice(-RECENT_EVENT_LIMIT)) {
      try {
        const event = JSON.parse(line);
        incrementCount(sourceCounts, String(event?.source || "unknown"));
        for (const modality of inferEventModalities(event)) {
          incrementCount(modalityCounts, modality);
        }
      } catch {
        incrementCount(sourceCounts, "invalid");
        incrementCount(modalityCounts, "invalid");
      }
    }

    return {
      path: EVENT_HISTORY_FILE,
      exists: true,
      bytes: stat.size,
      persisted_limit: PERSISTED_EVENT_LIMIT,
      recent_limit: RECENT_EVENT_LIMIT,
      total_lines: lines.length,
      recent_loaded: recentEvents.length,
      recent_types: recentTypes,
      source_counts: sourceCounts,
      modality_counts: modalityCounts
    };
  } catch (error) {
    return {
      path: EVENT_HISTORY_FILE,
      exists: fs.existsSync(EVENT_HISTORY_FILE),
      bytes: 0,
      persisted_limit: PERSISTED_EVENT_LIMIT,
      recent_limit: RECENT_EVENT_LIMIT,
      total_lines: 0,
      recent_loaded: recentEvents.length,
      recent_types: [],
      source_counts: {},
      modality_counts: {},
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

async function persistEvent(event) {
  eventPersistenceQueue = eventPersistenceQueue
    .then(async () => {
      try {
        await fs.promises.mkdir(RUNTIME_DIR, { recursive: true });
        await fs.promises.appendFile(
          EVENT_HISTORY_FILE,
          `${JSON.stringify(sanitizeEventForHistory(event))}\n`,
          "utf8"
        );
        persistedEventAppendCount += 1;
        if (persistedEventAppendCount % EVENT_TRIM_INTERVAL === 0) {
          await trimPersistedEvents();
        }
      } catch {
        // Event history is diagnostic only; ignore persistence failures.
      }
    })
    .catch(() => {
      // Keep later appends alive even if a previous diagnostic write failed.
    });
  return eventPersistenceQueue;
}

function loadRecentEventsFromDisk() {
  recentEvents.splice(0, recentEvents.length, ...readPersistedEvents());
}

function isWindowUsable(window) {
  return Boolean(window && !window.isDestroyed());
}

function createPetWindow() {
  const display = screen.getPrimaryDisplay();
  const workArea = display.workArea;

  petWindow = new BrowserWindow({
    width: PET_WINDOW_SIZE.width,
    height: PET_WINDOW_SIZE.height,
    x: workArea.x + workArea.width - PET_WINDOW_SIZE.width - 40,
    y: workArea.y + workArea.height - PET_WINDOW_SIZE.height - 40,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    webPreferences: {
      preload: `${__dirname}/preload.cjs`,
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  petWindow.setIgnoreMouseEvents(true, { forward: true });
  petWindow.loadURL(`${VITE_URL}/?window=pet`);
}

function createCommandWindow() {
  commandWindow = new BrowserWindow({
    width: 420,
    height: 86,
    show: false,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    webPreferences: {
      preload: `${__dirname}/preload.cjs`,
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  commandWindow.loadURL(`${VITE_URL}/?window=command`);
}

function createDebugWindow() {
  debugWindow = new BrowserWindow({
    width: 980,
    height: 720,
    show: false,
    webPreferences: {
      preload: `${__dirname}/preload.cjs`,
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  debugWindow.on("close", (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      debugWindow.hide();
    }
  });

  debugWindow.on("closed", () => {
    debugWindow = undefined;
  });

  debugWindow.loadURL(`${VITE_URL}/?window=debug`);
}

function createScreenWorkerWindow() {
  if (isWindowUsable(screenWorkerWindow)) return;
  screenWorkerReady = false;
  screenWorkerWindow = new BrowserWindow({
    width: 1,
    height: 1,
    show: false,
    frame: false,
    skipTaskbar: true,
    webPreferences: {
      preload: `${__dirname}/screen-worker-preload.cjs`,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false
    }
  });

  screenWorkerWindow.on("closed", () => {
    screenWorkerWindow = undefined;
    screenWorkerReady = false;
    screenWorkerReadyPromise = null;
    rejectAllScreenWorkerRequests("screen capture worker closed");
  });

  screenWorkerReadyPromise = new Promise((resolve, reject) => {
    const readyTimer = setTimeout(() => {
      screenWorkerReady = false;
      reject(new Error("screen capture worker load timed out"));
    }, 5000);

    screenWorkerWindow.webContents.once("did-finish-load", () => {
      clearTimeout(readyTimer);
      screenWorkerReady = true;
      rememberEvent(
        makeEvent("screen.worker.ready", "electron", {
          raw_payload_stored_in_event: false
        })
      );
      resolve();
    });
    screenWorkerWindow.webContents.once("did-fail-load", (_event, errorCode, errorDescription) => {
      clearTimeout(readyTimer);
      screenWorkerReady = false;
      rememberEvent(
        makeEvent("screen.worker.load.failed", "electron", {
          error_code: errorCode,
          error_description: errorDescription,
          raw_payload_stored_in_event: false
        })
      );
      reject(new Error(`screen capture worker failed to load: ${errorCode} ${errorDescription}`));
    });
  });
  screenWorkerReadyPromise.catch(() => {});

  screenWorkerWindow.loadURL(`${VITE_URL}/?window=screen-worker`).catch((error) => {
    screenWorkerReady = false;
    screenWorkerReadyPromise = Promise.reject(error);
    screenWorkerReadyPromise.catch(() => {});
  });
}

function rejectAllScreenWorkerRequests(message) {
  for (const { reject, timer } of screenWorkerRequests.values()) {
    clearTimeout(timer);
    reject(new Error(message));
  }
  screenWorkerRequests.clear();
}

function resetScreenWorkerWindow(reason = "screen capture worker reset") {
  rejectAllScreenWorkerRequests(reason);
  screenWorkerReady = false;
  screenWorkerReadyPromise = null;
  if (screenWorkerWindow && !screenWorkerWindow.isDestroyed()) {
    screenWorkerWindow.destroy();
  }
  screenWorkerWindow = undefined;
  createScreenWorkerWindow();
}

async function waitForScreenWorkerReady() {
  if (!isWindowUsable(screenWorkerWindow)) {
    createScreenWorkerWindow();
  }
  if (!isWindowUsable(screenWorkerWindow)) {
    throw new Error("screen capture worker is not ready");
  }
  if (screenWorkerReady) return;
  if (!screenWorkerReadyPromise) {
    throw new Error("screen capture worker readiness is missing");
  }
  await screenWorkerReadyPromise;
}

function showCommandWindow() {
  if (!commandWindow || !petWindow) return;
  syncFollowerWindows({ includeHiddenCommand: true });
  commandWindow.show();
  commandWindow.focus();
  commandWindow.webContents.send("command:focus");
}

function syncFollowerWindows(options = {}) {
  if (!petWindow) return;
  const petBounds = petWindow.getBounds();
  const modelBounds = {
    x: petBounds.x + MODEL_VISIBLE_BOUNDS.x,
    y: petBounds.y + MODEL_VISIBLE_BOUNDS.y,
    width: MODEL_VISIBLE_BOUNDS.width,
    height: MODEL_VISIBLE_BOUNDS.height
  };

  if (commandWindow && (commandWindow.isVisible() || options.includeHiddenCommand)) {
    const width = 420;
    const height = 86;
    commandWindow.setBounds({
      x: Math.round(modelBounds.x + modelBounds.width / 2 - width / 2),
      y: Math.round(modelBounds.y + modelBounds.height + 8),
      width,
      height
    });
  }
}

function hideCommandWindow() {
  if (commandWindow) commandWindow.hide();
}

function toggleDebugWindow() {
  if (!isWindowUsable(debugWindow)) {
    createDebugWindow();
  }

  if (debugWindow.isVisible()) {
    debugWindow.hide();
  } else {
    debugWindow.once("ready-to-show", () => {
      if (!isWindowUsable(debugWindow)) return;
      debugWindow.webContents.send("debug:events", recentEvents);
      debugWindow.webContents.send("debug:state", currentPetState);
    });
    debugWindow.show();
    debugWindow.focus();
    if (!debugWindow.webContents.isLoading()) {
      debugWindow.webContents.send("debug:events", recentEvents);
      debugWindow.webContents.send("debug:state", currentPetState);
    }
  }
}

function showBubble(text) {
  if (!petWindow) return;
  petWindow.webContents.send("bubble:text", text);
}

function sendPetState(state) {
  currentPetState = state;
  if (!petWindow) return;
  petWindow.webContents.send("pet:state", state);
  if (isWindowUsable(debugWindow)) {
    debugWindow.webContents.send("debug:state", state);
  }
}

function clearBubble() {
  if (!petWindow) return;
  petWindow.webContents.send("bubble:interrupt");
  sendPetState("idle");
}

function handleBackendEvent(event) {
  rememberEvent(event);
  if (event?.type === "pet.state.changed") {
    sendPetState(String(event.payload?.state || "idle"));
    return;
  }

  if (event?.type === "pet.bubble.show") {
    showBubble(String(event.payload?.text || ""));
    return;
  }

  if (event?.type === "pet.bubble.clear") {
    clearBubble();
  }
}

async function sendInternalEventToBackend(event) {
  const response = await fetch("http://127.0.0.1:18080/events/internal", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(event)
  });

  if (!response.ok) {
    throw new Error(`backend event failed: ${response.status}`);
  }

  const data = await response.json();
  const events = Array.isArray(data?.events) ? data.events : [];
  for (const backendEvent of events) {
    handleBackendEvent(backendEvent);
  }
  return events;
}

function dispatchInternalEvent(event) {
  rememberEvent(event);
  if (event.type === "pet.bubble.show") {
    showBubble(String(event.payload?.text || ""));
    return;
  }

  if (event.type === "pet.bubble.clear") {
    clearBubble();
  }
}

function screenCaptureThumbnailSize(display) {
  const width = Math.max(1, Math.round(display?.size?.width ?? 1));
  const height = Math.max(1, Math.round(display?.size?.height ?? 1));
  if (width <= SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH) {
    return { width, height };
  }
  const scale = SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH / width;
  return {
    width: SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH,
    height: Math.max(1, Math.round(height * scale))
  };
}

function resetScreenCaptureStats() {
  screenCaptureHistory.splice(0, screenCaptureHistory.length);
  screenEvidenceQueue = [];
  visionExtractionQueue = [];
  screenEvidenceLastStartedAt = 0;
  visionExtractionLastStartedAt = 0;
  visionExtractionRunningStartedAt = 0;
  visionExtractionLastRecoveredAtMs = 0;
  if (screenEvidenceQueueTimer) {
    clearTimeout(screenEvidenceQueueTimer);
    screenEvidenceQueueTimer = null;
  }
  if (visionExtractionQueueTimer) {
    clearTimeout(visionExtractionQueueTimer);
    visionExtractionQueueTimer = null;
  }
  if (visionExtractionPressureTimer) {
    clearTimeout(visionExtractionPressureTimer);
    visionExtractionPressureTimer = null;
  }
  screenObservationState.samplesSkipped = 0;
  screenObservationState.samplesTimedOut = 0;
  screenObservationState.samplesQueued = 0;
  screenObservationState.samplesPersisted = 0;
  screenObservationState.samplesDropped = 0;
  screenObservationState.samplesExtractionQueued = 0;
  screenObservationState.samplesExtracted = 0;
  screenObservationState.samplesExtractionFailed = 0;
  screenObservationState.samplesExtractionDropped = 0;
  screenObservationState.lastCaptureDurationMs = null;
  screenObservationState.lastCaptureStageDurationsMs = null;
  screenObservationState.lastEvidencePersistDurationMs = null;
  screenObservationState.lastEvidencePersistStageDurationsMs = null;
  screenObservationState.evidenceQueueLength = 0;
  screenObservationState.evidenceQueueBusy = false;
  screenObservationState.extractionQueueLength = 0;
  screenObservationState.extractionQueueBusy = false;
  screenObservationState.extractionPressureMode = false;
  screenObservationState.extractionPressureState = "steady";
  screenObservationState.extractionPressureReason = "steady";
  screenObservationState.extractionEstimatedBacklogMs = 0;
  screenObservationState.extractionOldestQueuedMs = null;
  screenObservationState.extractionRunningMs = null;
  screenObservationState.lastExtractionDurationMs = null;
  screenObservationState.lastExtractionProvider = null;
  screenObservationState.lastExtractionModel = null;
  screenObservationState.lastExtractionStatus = null;
  screenObservationState.lastExtractionEvidenceId = null;
  screenObservationState.extractionCurrentEvidenceId = null;
  screenObservationState.lastExtractionFeatureId = null;
  screenObservationState.lastExtractionError = null;
  screenObservationState.lastExtractionQueuedAt = null;
  screenObservationState.lastExtractionStartedAt = null;
  screenObservationState.lastExtractionFinishedAt = null;
  screenObservationState.lastExtractionPressureAt = null;
  screenObservationState.lastExtractionRecoveredAt = null;
  screenObservationState.lastExtractionDroppedAt = null;
  screenObservationState.captureAvgDurationMs = null;
  screenObservationState.captureMaxDurationMs = null;
  screenObservationState.captureHistoryCount = 0;
  screenObservationState.recentSkippedCount = 0;
  screenObservationState.adaptivePressureMode = false;
  screenObservationState.adaptiveReason = "steady";
  screenObservationState.lastSkipReason = null;
  screenObservationState.lastSkipAt = null;
  screenObservationState.lastTimeoutAt = null;
  screenObservationState.lastDropReason = null;
  screenObservationState.lastDropAt = null;
}

function currentScreenIntervalMs() {
  return Math.max(1, Math.round(screenObservationState.intervalSeconds * 1000));
}

function restartScreenObservationTimer() {
  if (!screenObservationState.active) return;
  if (screenObservationTimer) clearInterval(screenObservationTimer);
  screenObservationTimer = setInterval(() => {
    if (activeScreenCaptureRequests >= SCREEN_CAPTURE_MAX_ACTIVE_REQUESTS) {
      screenObservationState.samplesSkipped += 1;
      screenObservationState.recentSkippedCount += 1;
      screenObservationState.lastSkipReason = "active capture limit";
      screenObservationState.lastSkipAt = new Date().toISOString();
      rememberEvent(
        makeEvent("screen.observation.skipped", "electron", {
          reason: "active capture limit",
          active_capture_requests: activeScreenCaptureRequests,
          max_active_capture_requests: SCREEN_CAPTURE_MAX_ACTIVE_REQUESTS,
          interval_seconds: screenObservationState.intervalSeconds,
          samples_skipped: screenObservationState.samplesSkipped,
          raw_payload_stored_in_event: false
        })
      );
      emitScreenObservationStatus();
      return;
    }
    void capturePrimaryScreenFrame();
  }, currentScreenIntervalMs());
}

function updateScreenCapturePressure(durationMs) {
  screenCaptureHistory.push(durationMs);
  if (screenCaptureHistory.length > SCREEN_CAPTURE_HISTORY_LIMIT) {
    screenCaptureHistory.shift();
  }

  const sum = screenCaptureHistory.reduce((total, value) => total + value, 0);
  const avg = Math.round(sum / screenCaptureHistory.length);
  const max = Math.max(...screenCaptureHistory);
  const currentIntervalMs = currentScreenIntervalMs();
  const hasSkipPressure = false;
  const nearInterval = avg >= currentIntervalMs * 0.75 || max >= currentIntervalMs * 0.9;
  let nextIntervalMs = SCREEN_OBSERVATION_BASE_INTERVAL_MS;
  let reason = "steady";

  if (hasSkipPressure || nearInterval) {
    const pressureRatio = Math.max(avg / SCREEN_OBSERVATION_BASE_INTERVAL_MS, max / SCREEN_OBSERVATION_BASE_INTERVAL_MS);
    if (hasSkipPressure || pressureRatio >= 1.2) {
      nextIntervalMs = SCREEN_OBSERVATION_MAX_INTERVAL_MS;
      reason = "capture average/max near interval";
    } else {
      nextIntervalMs = SCREEN_OBSERVATION_BASE_INTERVAL_MS + SCREEN_OBSERVATION_INTERVAL_STEP_MS;
      reason = "capture duration near interval";
    }
  }

  const changed = nextIntervalMs !== currentIntervalMs;
  screenObservationState.lastCaptureDurationMs = durationMs;
  screenObservationState.captureAvgDurationMs = avg;
  screenObservationState.captureMaxDurationMs = max;
  screenObservationState.captureHistoryCount = screenCaptureHistory.length;
  screenObservationState.adaptivePressureMode = nextIntervalMs > SCREEN_OBSERVATION_BASE_INTERVAL_MS;
  screenObservationState.adaptiveReason = reason;
  screenObservationState.intervalSeconds = nextIntervalMs / 1000;
  screenObservationState.recentSkippedCount = 0;

  if (changed) {
    rememberEvent(
      makeEvent("screen.observation.interval.adjusted", "electron", {
        interval_seconds: screenObservationState.intervalSeconds,
        capture_avg_duration_ms: avg,
        capture_max_duration_ms: max,
        reason,
        raw_payload_stored_in_event: false
      })
    );
    restartScreenObservationTimer();
  }
}

function screenObservationStatusPayload() {
  return {
    schema_version: "screen_observation.status.v1",
    active: screenObservationState.active,
    enabled: screenObservationState.active && screenObservationState.startAllowed,
    permission: "screen.observe",
    permission_enabled: screenObservationState.startAllowed,
    requires_secondary_confirmation: true,
    display: "primary",
    full_frame: true,
    interval_seconds: screenObservationState.intervalSeconds,
    base_interval_seconds: screenObservationState.baseIntervalSeconds,
    max_interval_seconds: screenObservationState.maxIntervalSeconds,
    adaptive_interval_seconds: screenObservationState.intervalSeconds,
    retain_raw: screenObservationState.retainRaw,
    pressure_mode: screenObservationState.adaptivePressureMode,
    queue_pressure_seconds: 30,
    samples_captured: screenObservationState.samplesCaptured,
    samples_skipped: screenObservationState.samplesSkipped,
    samples_timed_out: screenObservationState.samplesTimedOut,
    samples_queued: screenObservationState.samplesQueued,
    samples_persisted: screenObservationState.samplesPersisted,
    samples_dropped: screenObservationState.samplesDropped,
    samples_extraction_queued: screenObservationState.samplesExtractionQueued,
    samples_extracted: screenObservationState.samplesExtracted,
    samples_extraction_failed: screenObservationState.samplesExtractionFailed,
    samples_extraction_dropped: screenObservationState.samplesExtractionDropped,
    last_capture_duration_ms: screenObservationState.lastCaptureDurationMs,
    last_capture_stage_durations_ms: screenObservationState.lastCaptureStageDurationsMs,
    last_evidence_persist_duration_ms: screenObservationState.lastEvidencePersistDurationMs,
    last_evidence_persist_stage_durations_ms: screenObservationState.lastEvidencePersistStageDurationsMs,
    evidence_queue_length: screenObservationState.evidenceQueueLength,
    evidence_queue_busy: screenObservationState.evidenceQueueBusy,
    evidence_queue_limit: screenObservationState.evidenceQueueLimit,
    evidence_min_interval_ms: screenObservationState.evidenceMinIntervalMs,
    extraction_queue_length: screenObservationState.extractionQueueLength,
    extraction_queue_busy: screenObservationState.extractionQueueBusy,
    extraction_queue_limit: screenObservationState.extractionQueueLimit,
    extraction_min_interval_ms: screenObservationState.extractionMinIntervalMs,
    extraction_pressure_threshold_seconds: screenObservationState.extractionPressureThresholdSeconds,
    extraction_pressure_mode: screenObservationState.extractionPressureMode,
    extraction_pressure_state: screenObservationState.extractionPressureState,
    extraction_pressure_reason: screenObservationState.extractionPressureReason,
    extraction_estimated_backlog_ms: screenObservationState.extractionEstimatedBacklogMs,
    extraction_oldest_queued_ms: screenObservationState.extractionOldestQueuedMs,
    extraction_running_ms: screenObservationState.extractionRunningMs,
    last_extraction_duration_ms: screenObservationState.lastExtractionDurationMs,
    last_extraction_provider: screenObservationState.lastExtractionProvider,
    last_extraction_model: screenObservationState.lastExtractionModel,
    last_extraction_status: screenObservationState.lastExtractionStatus,
    last_extraction_evidence_id: screenObservationState.lastExtractionEvidenceId,
    extraction_current_evidence_id: screenObservationState.extractionCurrentEvidenceId,
    last_extraction_feature_id: screenObservationState.lastExtractionFeatureId,
    last_extraction_error: screenObservationState.lastExtractionError,
    last_extraction_queued_at: screenObservationState.lastExtractionQueuedAt,
    last_extraction_started_at: screenObservationState.lastExtractionStartedAt,
    last_extraction_finished_at: screenObservationState.lastExtractionFinishedAt,
    last_extraction_pressure_at: screenObservationState.lastExtractionPressureAt,
    last_extraction_recovered_at: screenObservationState.lastExtractionRecoveredAt,
    last_extraction_dropped_at: screenObservationState.lastExtractionDroppedAt,
    capture_avg_duration_ms: screenObservationState.captureAvgDurationMs,
    capture_max_duration_ms: screenObservationState.captureMaxDurationMs,
    capture_history_count: screenObservationState.captureHistoryCount,
    adaptive_pressure_mode: screenObservationState.adaptivePressureMode,
    adaptive_reason: screenObservationState.adaptiveReason,
    last_skip_reason: screenObservationState.lastSkipReason,
    last_skip_at: screenObservationState.lastSkipAt,
    last_timeout_at: screenObservationState.lastTimeoutAt,
    active_capture_requests: activeScreenCaptureRequests,
    last_drop_reason: screenObservationState.lastDropReason,
    last_drop_at: screenObservationState.lastDropAt,
    max_thumbnail_width: SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH,
    capture_mime: SCREEN_CAPTURE_MIME,
    jpeg_quality: SCREEN_CAPTURE_JPEG_QUALITY,
    capture_backend: screenCaptureBackend,
    last_frame: screenObservationState.lastFrame,
    last_error: screenObservationState.lastError,
    last_audit_id: screenObservationState.lastAuditId,
    raw_payload_in_events: false,
    raw_payload_in_provider_prompt: false,
    raw_payload_returned_in_debug: false,
    blocked_reasons: screenObservationState.active
      ? []
      : screenObservationState.lastError
        ? [screenObservationState.lastError]
        : ["screen observation is not active"]
  };
}

function emitScreenObservationStatus() {
  if (isWindowUsable(debugWindow)) {
    debugWindow.webContents.send("screen:observation-status", screenObservationStatusPayload());
  }
}

async function postVisualEvidence(payload) {
  const response = await fetch("http://127.0.0.1:18080/memory/visual-evidence", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`visual evidence write failed: ${response.status}`);
  }

  return response.json();
}

async function postVisionExtraction(evidenceId) {
  const response = await fetch("http://127.0.0.1:18080/vision/extract", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      secondary_confirmed: true,
      evidence_id: evidenceId,
      provider: "local_ocr"
    })
  });

  if (!response.ok) {
    throw new Error(`vision extraction failed: ${response.status}`);
  }

  return response.json();
}

async function requestScreenWorkerFrame(options) {
  await waitForScreenWorkerReady();
  return new Promise((resolve, reject) => {
    const requestId = crypto.randomUUID();
    const timer = setTimeout(() => {
      screenWorkerRequests.delete(requestId);
      screenObservationState.samplesTimedOut += 1;
      screenObservationState.lastTimeoutAt = new Date().toISOString();
      rememberEvent(
        makeEvent("screen.observation.capture.timeout", "electron", {
          request_id: requestId,
          samples_timed_out: screenObservationState.samplesTimedOut,
          active_capture_requests: activeScreenCaptureRequests,
          raw_payload_stored_in_event: false
        })
      );
      resetScreenWorkerWindow("screen capture worker timed out");
      reject(new Error("screen capture worker timed out"));
    }, 10000);
    screenWorkerRequests.set(requestId, { resolve, reject, timer });
    screenWorkerWindow.webContents.send("screen-worker:capture", {
      request_id: requestId,
      ...options
    });
  });
}

function fileNameForScreenCapture() {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `screen-${timestamp}-powershell.${SCREEN_CAPTURE_FILE_EXTENSION}`;
}

function runtimeRefForScreenshot(fileName) {
  return `runtime://memory_blobs/vision/screenshots/${fileName}`;
}

function requestPythonScreenFrame(options) {
  return new Promise((resolve, reject) => {
    const fileName = fileNameForScreenCapture();
    const outputPath = path.join(SCREENSHOT_DIR, fileName);
    const startedAt = Date.now();
    rememberEvent(
      makeEvent("screen.capture.fallback.started", "electron", {
        backend: "python_imagegrab",
        raw_payload_stored_in_event: false
      })
    );
    execFile(
      "conda",
      [
        "run",
        "-n",
        CONDA_ENV,
        "python",
        SCREEN_CAPTURE_SCRIPT,
        "--output",
        outputPath,
        "--quality",
        String(options.jpeg_quality || SCREEN_CAPTURE_JPEG_QUALITY),
        "--max-width",
        String(options.thumbnail_width || SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH)
      ],
      { windowsHide: true, timeout: 10000 },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(stderr.trim() || error.message || "PowerShell screen capture failed"));
          return;
        }
        try {
          const lines = String(stdout || "").trim().split(/\r?\n/).filter(Boolean);
          const result = JSON.parse(lines[lines.length - 1] || "{}");
          if (!result.ok) throw new Error(result.message || "Python screen capture failed");
          resolve({
            request_id: options.request_id,
            ok: true,
            raw_ref: runtimeRefForScreenshot(fileName),
            file_name: fileName,
            sha256: result.sha256,
            size_bytes: result.size_bytes,
            width: result.width,
            height: result.height,
            source_display_width: result.source_display_width,
            source_display_height: result.source_display_height,
            get_sources_ms: 0,
            encode_ms: 0,
            hash_ms: 0,
            write_ms: Math.max(0, Math.round(result.capture_ms ?? Date.now() - startedAt)),
            worker_total_ms: Date.now() - startedAt,
            capture_backend: "python_imagegrab"
          });
        } catch (parseError) {
          reject(parseError instanceof Error ? parseError : new Error(String(parseError)));
        }
      }
    );
  });
}

async function requestScreenFrame(options) {
  if (screenCaptureBackend === "python_imagegrab") {
    return requestPythonScreenFrame(options);
  }
  try {
    const workerFrame = await requestScreenWorkerFrame(options);
    return { ...workerFrame, capture_backend: "electron_desktop_capturer" };
  } catch (error) {
    screenCaptureBackend = "python_imagegrab";
    rememberEvent(
      makeEvent("screen.capture.fallback.selected", "electron", {
        reason: error instanceof Error ? error.message : String(error),
        backend: "python_imagegrab",
        raw_payload_stored_in_event: false
      })
    );
    return requestPythonScreenFrame(options);
  }
}

function updateScreenEvidenceQueueStatus() {
  screenObservationState.evidenceQueueLength = screenEvidenceQueue.length;
  screenObservationState.evidenceQueueBusy = screenEvidenceQueueBusy;
}

function queueAgeMs(job, nowMs = Date.now()) {
  return Math.max(0, nowMs - Math.round(job?.queuedAtMs ?? nowMs));
}

function visionExtractionPressureSnapshot(nowMs = Date.now()) {
  const queueLength = visionExtractionQueue.length;
  const oldestQueuedMs = queueLength > 0 ? queueAgeMs(visionExtractionQueue[0], nowMs) : 0;
  const runningMs = visionExtractionRunningStartedAt > 0 ? Math.max(0, nowMs - visionExtractionRunningStartedAt) : 0;
  const averageWorkMs =
    screenObservationState.lastExtractionDurationMs && screenObservationState.lastExtractionDurationMs > 0
      ? screenObservationState.lastExtractionDurationMs
      : VISION_EXTRACTION_MIN_INTERVAL_MS;
  const estimatedBacklogMs = oldestQueuedMs + runningMs + Math.max(0, queueLength - 1) * averageWorkMs;
  let state = "steady";
  let reason = "steady";

  if (estimatedBacklogMs >= VISION_EXTRACTION_PRESSURE_THRESHOLD_MS) {
    state = "pressure";
    reason = "estimated backlog over threshold";
  } else if (runningMs >= VISION_EXTRACTION_PRESSURE_THRESHOLD_MS) {
    state = "pressure";
    reason = "current extraction over threshold";
  } else if (visionExtractionQueueBusy || queueLength > 0) {
    state = "busy";
    reason = queueLength > 0 ? "queued or running" : "running";
  } else if (screenObservationState.lastExtractionError) {
    state = "failed";
    reason = "last extraction failed";
  } else if (visionExtractionLastRecoveredAtMs > 0 && nowMs - visionExtractionLastRecoveredAtMs < VISION_EXTRACTION_RECOVERY_VISIBLE_MS) {
    state = "recovering";
    reason = "backlog recovered";
  }

  return {
    state,
    reason,
    pressureMode: state === "pressure",
    estimatedBacklogMs: Math.round(estimatedBacklogMs),
    oldestQueuedMs: queueLength > 0 ? Math.round(oldestQueuedMs) : null,
    runningMs: visionExtractionQueueBusy ? Math.round(runningMs) : null
  };
}

function scheduleVisionExtractionPressureRefresh(delayMs = 1000) {
  if (visionExtractionPressureTimer) return;
  visionExtractionPressureTimer = setTimeout(() => {
    visionExtractionPressureTimer = null;
    updateVisionExtractionQueueStatus();
    emitScreenObservationStatus();
  }, Math.max(250, delayMs));
}

function updateVisionExtractionQueueStatus() {
  const previousPressureMode = screenObservationState.extractionPressureMode;
  const previousState = screenObservationState.extractionPressureState;
  const nowMs = Date.now();
  const snapshot = visionExtractionPressureSnapshot(nowMs);
  screenObservationState.extractionQueueLength = visionExtractionQueue.length;
  screenObservationState.extractionQueueBusy = visionExtractionQueueBusy;
  screenObservationState.extractionPressureMode = snapshot.pressureMode;
  screenObservationState.extractionPressureState = snapshot.state;
  screenObservationState.extractionPressureReason = snapshot.reason;
  screenObservationState.extractionEstimatedBacklogMs = snapshot.estimatedBacklogMs;
  screenObservationState.extractionOldestQueuedMs = snapshot.oldestQueuedMs;
  screenObservationState.extractionRunningMs = snapshot.runningMs;

  if (snapshot.pressureMode && !previousPressureMode) {
    screenObservationState.lastExtractionPressureAt = new Date(nowMs).toISOString();
    rememberEvent(
      makeEvent("vision.extraction.pressure.changed", "electron", {
        pressure_mode: true,
        state: snapshot.state,
        reason: snapshot.reason,
        estimated_backlog_ms: snapshot.estimatedBacklogMs,
        queue_length: visionExtractionQueue.length,
        running_ms: snapshot.runningMs,
        raw_payload_stored_in_event: false
      })
    );
  } else if (!snapshot.pressureMode && previousPressureMode) {
    visionExtractionLastRecoveredAtMs = nowMs;
    screenObservationState.lastExtractionRecoveredAt = new Date(nowMs).toISOString();
    rememberEvent(
      makeEvent("vision.extraction.pressure.changed", "electron", {
        pressure_mode: false,
        state: "recovering",
        reason: "backlog recovered",
        estimated_backlog_ms: snapshot.estimatedBacklogMs,
        queue_length: visionExtractionQueue.length,
        raw_payload_stored_in_event: false
      })
    );
    const recoverySnapshot = visionExtractionPressureSnapshot(nowMs);
    screenObservationState.extractionPressureState = recoverySnapshot.state;
    screenObservationState.extractionPressureReason = recoverySnapshot.reason;
  } else if (previousState !== snapshot.state && snapshot.state === "failed") {
    screenObservationState.lastExtractionFinishedAt = screenObservationState.lastExtractionFinishedAt ?? new Date(nowMs).toISOString();
  }

  if (visionExtractionQueueBusy || visionExtractionQueue.length > 0 || screenObservationState.extractionPressureState === "recovering") {
    scheduleVisionExtractionPressureRefresh();
  }
}

function enqueueVisionExtractionJob(job) {
  if (!job?.evidenceId) return;
  while (visionExtractionQueue.length >= VISION_EXTRACTION_QUEUE_LIMIT) {
    const dropped = visionExtractionQueue.shift();
    const droppedAt = new Date().toISOString();
    screenObservationState.samplesExtractionDropped += 1;
    screenObservationState.lastExtractionDroppedAt = droppedAt;
    rememberEvent(
      makeEvent("vision.extraction.dropped", "electron", {
        reason: "vision extraction queue full",
        dropped_evidence_id: dropped?.evidenceId ?? null,
        queue_limit: VISION_EXTRACTION_QUEUE_LIMIT,
        dropped_at: droppedAt,
        raw_payload_stored_in_event: false
      })
    );
  }

  const queuedAtMs = Date.now();
  const queuedAt = new Date(queuedAtMs).toISOString();
  visionExtractionQueue.push({ ...job, queuedAtMs, queuedAt });
  screenObservationState.samplesExtractionQueued += 1;
  screenObservationState.lastExtractionStatus = "queued";
  screenObservationState.lastExtractionEvidenceId = job.evidenceId;
  screenObservationState.lastExtractionQueuedAt = queuedAt;
  updateVisionExtractionQueueStatus();
  rememberEvent(
    makeEvent("vision.extraction.queued", "electron", {
      evidence_id: job.evidenceId,
      source_event_id: job.capturedEvent?.event_id ?? null,
      provider: "local_rapidocr",
      queued_at: queuedAt,
      raw_payload_stored_in_event: false
    })
  );
  void processVisionExtractionQueue();
}

function scheduleVisionExtractionQueue(delayMs) {
  if (visionExtractionQueueTimer) return;
  visionExtractionQueueTimer = setTimeout(() => {
    visionExtractionQueueTimer = null;
    void processVisionExtractionQueue();
  }, Math.max(0, delayMs));
}

async function processVisionExtractionQueue() {
  if (visionExtractionQueueBusy) return;
  if (visionExtractionQueue.length === 0) {
    updateVisionExtractionQueueStatus();
    return;
  }

  const elapsedSinceLastStart = Date.now() - visionExtractionLastStartedAt;
  if (visionExtractionLastStartedAt > 0 && elapsedSinceLastStart < VISION_EXTRACTION_MIN_INTERVAL_MS) {
    scheduleVisionExtractionQueue(VISION_EXTRACTION_MIN_INTERVAL_MS - elapsedSinceLastStart);
    updateVisionExtractionQueueStatus();
    emitScreenObservationStatus();
    return;
  }

  visionExtractionQueueBusy = true;
  visionExtractionLastStartedAt = Date.now();
  visionExtractionRunningStartedAt = visionExtractionLastStartedAt;
  updateVisionExtractionQueueStatus();
  const job = visionExtractionQueue.shift();
  updateVisionExtractionQueueStatus();
  emitScreenObservationStatus();
  const startedAt = Date.now();
  screenObservationState.lastExtractionStatus = "running";
  screenObservationState.lastExtractionEvidenceId = job.evidenceId;
  screenObservationState.extractionCurrentEvidenceId = job.evidenceId;
  screenObservationState.lastExtractionStartedAt = new Date(startedAt).toISOString();
  rememberEvent(
    makeEvent("vision.extraction.started", "electron", {
      evidence_id: job.evidenceId,
      source_event_id: job.capturedEvent?.event_id ?? null,
      provider: "local_rapidocr",
      queued_at: job.queuedAt ?? null,
      wait_ms: queueAgeMs(job, startedAt),
      raw_payload_stored_in_event: false
    })
  );

  try {
    const result = await postVisionExtraction(job.evidenceId);
    const durationMs = Date.now() - startedAt;
    if (result?.ok) {
      screenObservationState.samplesExtracted += 1;
      screenObservationState.lastExtractionStatus = "completed";
      screenObservationState.lastExtractionProvider = result.provider ?? null;
      screenObservationState.lastExtractionModel = result.model ?? null;
      screenObservationState.lastExtractionFeatureId = result.feature_id ?? null;
      screenObservationState.lastExtractionError = null;
      screenObservationState.lastExtractionDurationMs = durationMs;
      screenObservationState.lastExtractionFinishedAt = new Date().toISOString();
      if (screenObservationState.lastFrame?.evidence_id === job.evidenceId) {
        screenObservationState.lastFrame = {
          ...screenObservationState.lastFrame,
          vision_reader_status: "extracted"
        };
      }
      rememberEvent(
        makeEvent(
          "vision.extraction.completed",
          "electron",
          {
            evidence_id: job.evidenceId,
            provider: result.provider ?? null,
            model: result.model ?? null,
            feature_id: result.feature_id ?? null,
            duration_ms: durationMs,
            raw_payload_stored_in_event: false
          },
          job.capturedEvent?.event_id ?? null
        )
      );
    } else {
      throw new Error(result?.message || (Array.isArray(result?.blocked_reasons) ? result.blocked_reasons.join("; ") : "vision extraction returned ok=false"));
    }
  } catch (error) {
    const durationMs = Date.now() - startedAt;
    const message = error instanceof Error ? error.message : String(error);
    screenObservationState.samplesExtractionFailed += 1;
      screenObservationState.lastExtractionStatus = "failed";
      screenObservationState.lastExtractionDurationMs = durationMs;
      screenObservationState.lastExtractionError = message;
      screenObservationState.lastExtractionFinishedAt = new Date().toISOString();
      rememberEvent(
      makeEvent(
        "vision.extraction.failed",
        "electron",
        {
          evidence_id: job.evidenceId,
          reason: message,
          duration_ms: durationMs,
          raw_payload_stored_in_event: false
        },
        job.capturedEvent?.event_id ?? null
      )
    );
  } finally {
    visionExtractionQueueBusy = false;
    visionExtractionRunningStartedAt = 0;
    screenObservationState.extractionCurrentEvidenceId = null;
    updateVisionExtractionQueueStatus();
    emitScreenObservationStatus();
    if (visionExtractionQueue.length > 0) {
      scheduleVisionExtractionQueue(VISION_EXTRACTION_MIN_INTERVAL_MS);
    }
  }
}

function enqueueScreenEvidenceJob(job) {
  while (screenEvidenceQueue.length >= SCREEN_EVIDENCE_QUEUE_LIMIT) {
    const dropped = screenEvidenceQueue.shift();
    const droppedAt = new Date().toISOString();
    screenObservationState.samplesDropped += 1;
    screenObservationState.lastDropAt = droppedAt;
    screenObservationState.lastDropReason = "screen evidence queue full";
    rememberEvent(
      makeEvent("screen.observation.dropped", "electron", {
        reason: screenObservationState.lastDropReason,
        dropped_event_id: dropped?.capturedEvent?.event_id ?? null,
        queue_limit: SCREEN_EVIDENCE_QUEUE_LIMIT,
        raw_payload_stored_in_event: false
      })
    );
  }

  screenEvidenceQueue.push(job);
  screenObservationState.samplesQueued += 1;
  updateScreenEvidenceQueueStatus();
  void processScreenEvidenceQueue();
}

function scheduleScreenEvidenceQueue(delayMs) {
  if (screenEvidenceQueueTimer) return;
  screenEvidenceQueueTimer = setTimeout(() => {
    screenEvidenceQueueTimer = null;
    void processScreenEvidenceQueue();
  }, Math.max(0, delayMs));
}

async function persistScreenEvidenceJob(job) {
  const persistStartedAt = Date.now();
  const backendStartedAt = Date.now();
  const evidence = await postVisualEvidence(job.evidencePayload);
  const backend_ms = Date.now() - backendStartedAt;
  const total_ms = Date.now() - persistStartedAt;
  const persistStageDurations = {
    worker_write_ms: Math.max(0, Math.round(job.workerWriteMs ?? 0)),
    backend_ms,
    total_ms
  };

  screenObservationState.samplesPersisted += 1;
  screenObservationState.lastEvidencePersistDurationMs = total_ms;
  screenObservationState.lastEvidencePersistStageDurationsMs = persistStageDurations;
  screenObservationState.lastError = null;

  const latestFrame =
    screenObservationState.lastFrame?.event_id === job.capturedEvent.event_id
      ? screenObservationState.lastFrame
      : job.frame;
  const persistedFrame = {
    ...latestFrame,
    evidence_status: "persisted",
    evidence_id: evidence?.item?.evidence_id ?? null,
    attachment_id: evidence?.item?.attachment_ref?.attachment_id ?? null,
    persist_duration_ms: total_ms,
    persist_stage_durations_ms: persistStageDurations
  };
  if (screenObservationState.lastFrame?.event_id === job.capturedEvent.event_id) {
    screenObservationState.lastFrame = persistedFrame;
  }

  rememberEvent(
    makeEvent(
      "vision.import.created",
      "electron",
      {
        source: "screen_frame",
        evidence_id: persistedFrame.evidence_id,
        attachment_id: persistedFrame.attachment_id,
        observation_status: "metadata_only",
        evidence_status: "persisted",
        raw_ref: job.storageRef,
        persist_stage_durations_ms: persistStageDurations,
        raw_payload_stored_in_event: false
      },
      job.capturedEvent.event_id
    )
  );
  if (persistedFrame.evidence_id && job.retainRaw !== false) {
    enqueueVisionExtractionJob({
      evidenceId: persistedFrame.evidence_id,
      capturedEvent: job.capturedEvent
    });
  }
}

async function processScreenEvidenceQueue() {
  if (screenEvidenceQueueBusy) return;
  if (screenEvidenceQueue.length === 0) {
    updateScreenEvidenceQueueStatus();
    return;
  }

  const elapsedSinceLastStart = Date.now() - screenEvidenceLastStartedAt;
  if (screenEvidenceLastStartedAt > 0 && elapsedSinceLastStart < SCREEN_EVIDENCE_MIN_INTERVAL_MS) {
    scheduleScreenEvidenceQueue(SCREEN_EVIDENCE_MIN_INTERVAL_MS - elapsedSinceLastStart);
    updateScreenEvidenceQueueStatus();
    emitScreenObservationStatus();
    return;
  }

  screenEvidenceQueueBusy = true;
  screenEvidenceLastStartedAt = Date.now();
  updateScreenEvidenceQueueStatus();
  const job = screenEvidenceQueue.shift();
  updateScreenEvidenceQueueStatus();
  emitScreenObservationStatus();

  try {
    await persistScreenEvidenceJob(job);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    screenObservationState.lastError = message;
    rememberEvent(
      makeEvent(
        "screen.observation.persist.error",
        "electron",
        {
          message,
          source_event_id: job?.capturedEvent?.event_id ?? null,
          raw_payload_stored_in_event: false
        },
        job?.capturedEvent?.event_id ?? null
      )
    );
  } finally {
    screenEvidenceQueueBusy = false;
    updateScreenEvidenceQueueStatus();
    emitScreenObservationStatus();
    if (screenEvidenceQueue.length > 0) {
      void processScreenEvidenceQueue();
    }
  }
}

async function capturePrimaryScreenFrame() {
  if (!screenObservationState.active) return null;
  activeScreenCaptureRequests += 1;
  const captureStartedAt = Date.now();
  try {
    const primaryDisplay = screen.getPrimaryDisplay();
    const thumbnailSize = screenCaptureThumbnailSize(primaryDisplay);
    const workerFrame = await requestScreenFrame({
      display_id: String(primaryDisplay.id),
      thumbnail_width: thumbnailSize.width,
      thumbnail_height: thumbnailSize.height,
      jpeg_quality: SCREEN_CAPTURE_JPEG_QUALITY,
      retain_raw: screenObservationState.retainRaw,
      screenshot_dir: SCREENSHOT_DIR,
      file_extension: SCREEN_CAPTURE_FILE_EXTENSION
    });
    const sha256 = String(workerFrame.sha256 || "");
    if (!sha256) throw new Error("screen capture worker did not return sha256");
    const storageRef = String(workerFrame.raw_ref || "");
    if (!storageRef) throw new Error("screen capture worker did not return raw ref");
    const width = Math.max(1, Math.round(workerFrame.width ?? thumbnailSize.width));
    const height = Math.max(1, Math.round(workerFrame.height ?? thumbnailSize.height));
    const sizeBytes = Math.max(0, Math.round(workerFrame.size_bytes ?? 0));
    rememberEvent(
      makeEvent("screen.worker.capture.result", "electron", {
        raw_ref: storageRef,
        width,
        height,
        capture_backend: workerFrame.capture_backend ?? "unknown",
        size_bytes: sizeBytes,
        worker_total_ms: Math.max(0, Math.round(workerFrame.worker_total_ms ?? 0)),
        get_sources_ms: Math.max(0, Math.round(workerFrame.get_sources_ms ?? 0)),
        encode_ms: Math.max(0, Math.round(workerFrame.encode_ms ?? 0)),
        write_ms: Math.max(0, Math.round(workerFrame.write_ms ?? 0)),
        raw_payload_stored_in_event: false
      })
    );

    const capturedEvent = makeEvent("screen.observation.captured", "electron", {
      attachment_ref: {
        kind: "image",
        source: "screen_frame",
        raw_ref: storageRef,
        mime: SCREEN_CAPTURE_MIME,
        sha256,
        width,
        height,
        source_display_width: Math.max(1, Math.round(workerFrame.source_display_width ?? primaryDisplay.size.width)),
        source_display_height: Math.max(1, Math.round(workerFrame.source_display_height ?? primaryDisplay.size.height)),
        thumbnail_max_width: SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH,
        jpeg_quality: SCREEN_CAPTURE_JPEG_QUALITY,
        raw_available: screenObservationState.retainRaw,
        vision_reader_status: "metadata_only"
      },
      evidence_status: "queued",
      raw_payload_stored_in_event: false
    });
    rememberEvent(capturedEvent);

    const captureDurationMs = Date.now() - captureStartedAt;
    const stageDurations = {
      worker_total_ms: Math.max(0, Math.round(workerFrame.worker_total_ms ?? captureDurationMs)),
      worker_get_sources_ms: Math.max(0, Math.round(workerFrame.get_sources_ms ?? 0)),
      worker_encode_ms: Math.max(0, Math.round(workerFrame.encode_ms ?? 0)),
      worker_hash_ms: Math.max(0, Math.round(workerFrame.hash_ms ?? 0)),
      worker_write_ms: Math.max(0, Math.round(workerFrame.write_ms ?? 0)),
      main_receive_ms: captureDurationMs,
      total_ms: captureDurationMs
    };
    const evidencePayload = {
      source: "screen_frame",
      raw_ref: storageRef,
      sha256,
      source_event_id: capturedEvent.event_id,
      mime: SCREEN_CAPTURE_MIME,
      width,
      height,
      size_bytes: sizeBytes,
      source_display_width: Math.max(1, Math.round(workerFrame.source_display_width ?? primaryDisplay.size.width)),
      source_display_height: Math.max(1, Math.round(workerFrame.source_display_height ?? primaryDisplay.size.height)),
      thumbnail_max_width: SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH,
      raw_available: screenObservationState.retainRaw,
      vision_reader_status: "metadata_only"
    };
    const frame = {
      captured_at: capturedEvent.timestamp,
      event_id: capturedEvent.event_id,
      evidence_status: "queued",
      evidence_id: null,
      attachment_id: null,
      raw_ref: storageRef,
      sha256,
      width,
      height,
      size_bytes: sizeBytes,
      source_display_width: Math.max(1, Math.round(workerFrame.source_display_width ?? primaryDisplay.size.width)),
      source_display_height: Math.max(1, Math.round(workerFrame.source_display_height ?? primaryDisplay.size.height)),
      thumbnail_max_width: SCREEN_CAPTURE_MAX_THUMBNAIL_WIDTH,
      mime: SCREEN_CAPTURE_MIME,
      jpeg_quality: SCREEN_CAPTURE_JPEG_QUALITY,
      capture_duration_ms: captureDurationMs,
      capture_stage_durations_ms: stageDurations,
      persist_duration_ms: null,
      persist_stage_durations_ms: null,
      raw_available: screenObservationState.retainRaw,
      vision_reader_status: "metadata_only",
      raw_payload_returned: false
    };
    screenObservationState.samplesCaptured += 1;
    screenObservationState.lastCaptureStageDurationsMs = stageDurations;
    updateScreenCapturePressure(captureDurationMs);
    screenObservationState.lastSkipReason = null;
    screenObservationState.lastSkipAt = null;
    screenObservationState.lastError = null;
    screenObservationState.lastFrame = frame;
    enqueueScreenEvidenceJob({
      capturedEvent,
      evidencePayload,
      frame,
      retainRaw: screenObservationState.retainRaw,
      storageRef,
      workerWriteMs: workerFrame.write_ms
    });
    emitScreenObservationStatus();
    return screenObservationState.lastFrame;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    screenObservationState.lastError = message;
    screenObservationState.lastCaptureDurationMs = Date.now() - captureStartedAt;
    rememberEvent(makeEvent("screen.observation.error", "electron", { message }));
    emitScreenObservationStatus();
    return null;
  } finally {
    activeScreenCaptureRequests = Math.max(0, activeScreenCaptureRequests - 1);
    emitScreenObservationStatus();
  }
}

async function requestBackendScreenStart(options) {
  const response = await fetch("http://127.0.0.1:18080/screen/observation/start", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(options)
  });
  if (!response.ok) throw new Error(`screen observation start failed: ${response.status}`);
  return response.json();
}

async function requestBackendScreenStop(revokePermission = false) {
  const response = await fetch("http://127.0.0.1:18080/screen/observation/stop", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ revoke_permission: revokePermission })
  });
  if (!response.ok) throw new Error(`screen observation stop failed: ${response.status}`);
  return response.json();
}

async function startScreenObservation(options = {}) {
  if (screenObservationState.active) {
    return { ok: true, already_active: true, status: screenObservationStatusPayload() };
  }
  const sampleOnce = Boolean(options.sample_once);

  const backend = await requestBackendScreenStart({
    secondary_confirmed: Boolean(options.secondary_confirmed),
    interval_seconds: SCREEN_OBSERVATION_BASE_INTERVAL_MS / 1000,
    retain_raw: options.retain_raw !== false
  });
  if (!backend?.start_allowed) {
    screenObservationState.startAllowed = false;
    screenObservationState.lastError = backend?.message || "screen observation was not allowed";
    emitScreenObservationStatus();
    return { ok: false, backend, status: screenObservationStatusPayload() };
  }

  screenObservationState.active = true;
  screenObservationState.startAllowed = true;
  screenObservationState.intervalSeconds = SCREEN_OBSERVATION_BASE_INTERVAL_MS / 1000;
  screenObservationState.baseIntervalSeconds = SCREEN_OBSERVATION_BASE_INTERVAL_MS / 1000;
  screenObservationState.maxIntervalSeconds = SCREEN_OBSERVATION_MAX_INTERVAL_MS / 1000;
  screenObservationState.retainRaw = options.retain_raw !== false;
  resetScreenCaptureStats();
  screenObservationState.lastError = null;
  screenObservationState.lastAuditId = backend.audit_id ?? null;
  rememberEvent(
    makeEvent("screen.observation.enabled", "electron", {
      display: "primary",
      full_frame: true,
      interval_seconds: screenObservationState.intervalSeconds,
      sample_once: sampleOnce,
      base_interval_seconds: screenObservationState.baseIntervalSeconds,
      max_interval_seconds: screenObservationState.maxIntervalSeconds,
      retain_raw: screenObservationState.retainRaw,
      audit_id: screenObservationState.lastAuditId,
      raw_payload_stored_in_event: false
    })
  );
  sendPetState("observing");
  emitScreenObservationStatus();
  if (sampleOnce) {
    await capturePrimaryScreenFrame();
    screenObservationState.active = false;
    try {
      const stopBackend = await requestBackendScreenStop(false);
      screenObservationState.lastAuditId = stopBackend.audit_id ?? screenObservationState.lastAuditId;
    } catch (error) {
      screenObservationState.lastError = error instanceof Error ? error.message : String(error);
    }
    rememberEvent(
      makeEvent("screen.observation.sample_once.completed", "electron", {
        samples_captured: screenObservationState.samplesCaptured,
        audit_id: screenObservationState.lastAuditId,
        raw_payload_stored_in_event: false
      })
    );
    sendPetState("idle");
    emitScreenObservationStatus();
    return { ok: true, backend, sample_once: true, status: screenObservationStatusPayload() };
  }
  void capturePrimaryScreenFrame();
  restartScreenObservationTimer();
  return { ok: true, backend, status: screenObservationStatusPayload() };
}

function restoreScreenObservationFromConfig() {
  try {
    const config = readRuntimeConfig();
    const permissions = config.permissions || {};
    const screenConfig = config.screen_observation || {};
    if (!permissions["screen.observe"]) return;

    screenObservationState.active = false;
    screenObservationState.startAllowed = true;
    screenObservationState.intervalSeconds = SCREEN_OBSERVATION_BASE_INTERVAL_MS / 1000;
    screenObservationState.baseIntervalSeconds = SCREEN_OBSERVATION_BASE_INTERVAL_MS / 1000;
    screenObservationState.maxIntervalSeconds = SCREEN_OBSERVATION_MAX_INTERVAL_MS / 1000;
    screenObservationState.retainRaw = screenConfig.retain_raw !== false;
    screenObservationState.lastError = null;
    if (screenConfig.enabled) {
      rememberEvent(
        makeEvent("screen.observation.restore.skipped", "electron", {
          reason: "startup requires explicit Debug start",
          previous_config_enabled: true,
          permission_enabled: true,
          display: "primary",
          full_frame: true,
          interval_seconds: screenObservationState.intervalSeconds,
          retain_raw: screenObservationState.retainRaw,
          raw_payload_stored_in_event: false
        })
      );
    }
    sendPetState("idle");
    emitScreenObservationStatus();
  } catch (error) {
    screenObservationState.lastError = error instanceof Error ? error.message : String(error);
    rememberEvent(
      makeEvent("screen.observation.restore.error", "electron", {
        message: screenObservationState.lastError,
        raw_payload_stored_in_event: false
      })
    );
    emitScreenObservationStatus();
  }
}

async function stopScreenObservation(options = {}) {
  if (screenObservationTimer) {
    clearInterval(screenObservationTimer);
    screenObservationTimer = null;
  }
  screenEvidenceQueue = [];
  visionExtractionQueue = [];
  if (screenEvidenceQueueTimer) {
    clearTimeout(screenEvidenceQueueTimer);
    screenEvidenceQueueTimer = null;
  }
  if (visionExtractionQueueTimer) {
    clearTimeout(visionExtractionQueueTimer);
    visionExtractionQueueTimer = null;
  }
  if (visionExtractionPressureTimer) {
    clearTimeout(visionExtractionPressureTimer);
    visionExtractionPressureTimer = null;
  }
  updateScreenEvidenceQueueStatus();
  updateVisionExtractionQueueStatus();
  const wasActive = screenObservationState.active;
  screenObservationState.active = false;
  screenObservationState.startAllowed = !options.revoke_permission && screenObservationState.startAllowed;
  try {
    const backend = await requestBackendScreenStop(Boolean(options.revoke_permission));
    screenObservationState.lastAuditId = backend.audit_id ?? screenObservationState.lastAuditId;
  } catch (error) {
    screenObservationState.lastError = error instanceof Error ? error.message : String(error);
  }
  if (wasActive) {
    rememberEvent(
      makeEvent("screen.observation.disabled", "electron", {
        revoke_permission: Boolean(options.revoke_permission),
        samples_captured: screenObservationState.samplesCaptured,
        audit_id: screenObservationState.lastAuditId,
        raw_payload_stored_in_event: false
      })
    );
  }
  sendPetState("idle");
  emitScreenObservationStatus();
  return { ok: true, status: screenObservationStatusPayload() };
}

app.whenReady().then(() => {
  loadRecentEventsFromDisk();
  createPetWindow();
  createCommandWindow();
  createDebugWindow();
  createScreenWorkerWindow();
  rememberEvent(makeEvent("system.hello", "electron", { app: "y_chat" }));
  restoreScreenObservationFromConfig();

  globalShortcut.register("CommandOrControl+Space", showCommandWindow);

  globalShortcut.register("Escape", () => {
    hideCommandWindow();
    dispatchInternalEvent(makeEvent("pet.bubble.clear", "electron", {}));
  });

  globalShortcut.register("CommandOrControl+Shift+P", toggleDebugWindow);
});

ipcMain.handle("pet:show-bubble", (_event, text) => {
  dispatchInternalEvent(makeEvent("pet.bubble.show", "electron", { text: String(text || "") }));
});

ipcMain.handle("bubble:hide", () => {
  dispatchInternalEvent(makeEvent("pet.bubble.clear", "electron", {}));
});

ipcMain.handle("command:submit", async (_event, text) => {
  const commandText = String(text || "").trim();
  if (!commandText) return { ok: false, error: "empty command" };

  const payload = { text: commandText };
  const latestFrame = screenObservationState.active ? screenObservationState.lastFrame : null;
  if (latestFrame?.raw_ref) {
    payload.screenshot_ref = latestFrame.raw_ref;
    payload.visual_evidence_id = latestFrame.evidence_id ?? null;
    payload.screen_frame_created_at = latestFrame.captured_at ?? null;
    payload.screen_frame_evidence_status = latestFrame.evidence_status ?? null;
  }
  const submitted = makeEvent("user.command.submitted", "frontend", payload);
  rememberEvent(submitted);
  try {
    await sendInternalEventToBackend(submitted);
    hideCommandWindow();
    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    dispatchInternalEvent(
      makeEvent(
        "pet.bubble.show",
        "electron",
        {
          text: `Backend event failed.\n\n${message}`
        },
        submitted.event_id
      )
    );
    return { ok: false, error: message };
  }
});

ipcMain.handle("command:hide", () => {
  hideCommandWindow();
});

ipcMain.handle("pet:set-mouse-ignored", (_event, ignored) => {
  if (petWindow) {
    petWindow.setIgnoreMouseEvents(Boolean(ignored), { forward: true });
  }
});

ipcMain.handle("pet:begin-drag-window", () => {
  if (!petWindow) return;
  const cursor = screen.getCursorScreenPoint();
  const bounds = petWindow.getBounds();
  petDragState = {
    offsetX: cursor.x - bounds.x,
    offsetY: cursor.y - bounds.y
  };
});

ipcMain.handle("pet:drag-window", () => {
  if (!petWindow) return;
  if (!petDragState) return;

  const cursor = screen.getCursorScreenPoint();
  petWindow.setPosition(
    Math.round(cursor.x - petDragState.offsetX),
    Math.round(cursor.y - petDragState.offsetY),
    false
  );
  syncFollowerWindows();
});

ipcMain.handle("pet:end-drag-window", () => {
  petDragState = null;
});

ipcMain.handle("pet:model-clicked", () => {
  return makeEvent("pet.model.clicked", "frontend", {});
});

ipcMain.handle("debug:event-history-status", () => {
  return eventHistoryStatus();
});

ipcMain.handle("screen:observation-status", () => {
  return screenObservationStatusPayload();
});

ipcMain.on("screen-worker:capture-result", (_event, result) => {
  const requestId = result?.request_id;
  const pending = screenWorkerRequests.get(requestId);
  if (!pending) return;
  clearTimeout(pending.timer);
  screenWorkerRequests.delete(requestId);
  if (result?.ok) {
    pending.resolve(result);
  } else {
    pending.reject(new Error(result?.message || "screen capture worker failed"));
  }
});

ipcMain.on("screen-worker:capture-progress", (_event, progress) => {
  rememberEvent(
    makeEvent("screen.worker.capture.progress", "electron", {
      request_id: progress?.request_id ?? null,
      stage: progress?.stage ?? "unknown",
      elapsed_ms: Math.max(0, Math.round(progress?.elapsed_ms ?? 0)),
      get_sources_ms:
        progress?.get_sources_ms == null ? null : Math.max(0, Math.round(progress.get_sources_ms)),
      encode_ms: progress?.encode_ms == null ? null : Math.max(0, Math.round(progress.encode_ms)),
      write_ms: progress?.write_ms == null ? null : Math.max(0, Math.round(progress.write_ms)),
      source_count: progress?.source_count == null ? null : Math.max(0, Math.round(progress.source_count)),
      size_bytes: progress?.size_bytes == null ? null : Math.max(0, Math.round(progress.size_bytes)),
      raw_payload_stored_in_event: false
    })
  );
});

ipcMain.handle("screen:observation-start", async (_event, options) => {
  return startScreenObservation(options || {});
});

ipcMain.handle("screen:observation-stop", async (_event, options) => {
  return stopScreenObservation(options || {});
});

app.on("window-all-closed", (event) => {
  event.preventDefault();
});

app.on("will-quit", () => {
  app.isQuitting = true;
  if (screenObservationTimer) {
    clearInterval(screenObservationTimer);
    screenObservationTimer = null;
  }
  for (const { reject, timer } of screenWorkerRequests.values()) {
    clearTimeout(timer);
    reject(new Error("app is quitting"));
  }
  screenWorkerRequests.clear();
  globalShortcut.unregisterAll();
});
