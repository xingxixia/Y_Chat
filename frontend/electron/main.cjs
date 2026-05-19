const { app, BrowserWindow, globalShortcut, ipcMain, screen } = require("electron");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const VITE_URL = "http://127.0.0.1:5173";
const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const RUNTIME_DIR = path.join(PROJECT_ROOT, "runtime");
const EVENT_HISTORY_FILE = path.join(RUNTIME_DIR, "events.jsonl");
const RECENT_EVENT_LIMIT = 80;
const PERSISTED_EVENT_LIMIT = 500;

let petWindow;
let commandWindow;
let debugWindow;
let petDragState = null;
let currentPetState = "idle";
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
  recentEvents.unshift(event);
  if (recentEvents.length > RECENT_EVENT_LIMIT) recentEvents.pop();
  persistEvent(event);
  if (isWindowUsable(debugWindow)) {
    debugWindow.webContents.send("debug:events", recentEvents);
  }
}

function sanitizeEventForHistory(event) {
  return {
    event_id: event?.event_id,
    type: event?.type,
    source: event?.source,
    timestamp: event?.timestamp,
    correlation_id: event?.correlation_id ?? null,
    payload: event?.payload ?? {}
  };
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

function trimPersistedEvents() {
  try {
    if (!fs.existsSync(EVENT_HISTORY_FILE)) return;
    const lines = fs.readFileSync(EVENT_HISTORY_FILE, "utf8").split(/\r?\n/).filter(Boolean);
    if (lines.length <= PERSISTED_EVENT_LIMIT) return;
    fs.writeFileSync(EVENT_HISTORY_FILE, `${lines.slice(-PERSISTED_EVENT_LIMIT).join("\n")}\n`, "utf8");
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
        recent_types: []
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

    return {
      path: EVENT_HISTORY_FILE,
      exists: true,
      bytes: stat.size,
      persisted_limit: PERSISTED_EVENT_LIMIT,
      recent_limit: RECENT_EVENT_LIMIT,
      total_lines: lines.length,
      recent_loaded: recentEvents.length,
      recent_types: recentTypes
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
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

function persistEvent(event) {
  try {
    fs.mkdirSync(RUNTIME_DIR, { recursive: true });
    fs.appendFileSync(EVENT_HISTORY_FILE, `${JSON.stringify(sanitizeEventForHistory(event))}\n`, "utf8");
    trimPersistedEvents();
  } catch {
    // Event history is diagnostic only; ignore persistence failures.
  }
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

app.whenReady().then(() => {
  loadRecentEventsFromDisk();
  createPetWindow();
  createCommandWindow();
  createDebugWindow();
  rememberEvent(makeEvent("system.hello", "electron", { app: "test_atri" }));

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

  const submitted = makeEvent("user.command.submitted", "frontend", { text: commandText });
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

app.on("window-all-closed", (event) => {
  event.preventDefault();
});

app.on("will-quit", () => {
  app.isQuitting = true;
  globalShortcut.unregisterAll();
});
