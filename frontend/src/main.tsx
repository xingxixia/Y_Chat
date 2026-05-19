import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

declare global {
  interface Window {
    testAtri?: {
      showBubble: (text: string) => Promise<void>;
      hideBubble: () => Promise<void>;
      submitCommand: (text: string) => Promise<CommandSubmitResult>;
      hideCommand: () => Promise<void>;
      setPetMouseIgnored: (ignored: boolean) => Promise<void>;
      beginPetWindowDrag: () => Promise<void>;
      dragPetWindow: () => Promise<void>;
      endPetWindowDrag: () => Promise<void>;
      notifyPetClicked: () => Promise<void>;
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
};

type CommandSubmitResult = {
  ok: boolean;
  error?: string;
};

type PermissionStatus = {
  permissions: Record<string, boolean>;
  enabled: string[];
  disabled: string[];
};

type ModelProviderStatus = {
  enabled: boolean;
  active_provider: string;
  model: string;
  configured: boolean;
};

type MemoryStatus = {
  enabled: boolean;
  items: Array<{ id: string; kind: string; text: string; created_at: string }>;
};

type ProjectReaderStatus = {
  enabled: boolean;
  allowed_roots: string[];
  text_extensions: string[];
};

type LogStatus = {
  logs: Array<{ name: string; kind: string; bytes: number; tail: string[] }>;
};

type ReasoningStatus = {
  enabled: boolean;
  provider: string;
  real_model_calls: boolean;
  runs_total: number;
  queue: { foreground_active: boolean; background_pending: number };
  current_run: ReasoningRunSummary | null;
};

type ReasoningRunSummary = {
  run_id: string;
  source_event_id?: string;
  event_type?: string;
  status: string;
  depth: string;
  provider: string;
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

type ReasoningRunsResponse = {
  runs: ReasoningRunSummary[];
};

type ReasoningRunDetail = {
  run: ReasoningRunSummary;
  steps: ReasoningStep[];
  schema_failures: ReasoningSchemaFailure[];
  memory_candidates: ReasoningCandidate[];
  actions: unknown[];
  pending_actions: unknown[];
  audit: ReasoningAuditRecord[];
};

const BUBBLE_SEGMENT_LENGTH = 44;
const BUBBLE_SEGMENT_PAUSE_MS = 700;

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

function PetCanvas({ petState }: { petState: string }) {
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
    window.testAtri?.setPetMouseIgnored(ignored);
  }

  function endDrag(clientX?: number, clientY?: number) {
    if (dragRef.current.active && !dragRef.current.moved) {
      window.testAtri?.notifyPetClicked();
    }
    dragRef.current.active = false;
    window.testAtri?.endPetWindowDrag();

    if (clientX === undefined || clientY === undefined) {
      setMouseIgnored(true);
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

    const bob = petState === "thinking" ? pose % 20 < 10 ? 0 : 1 : pose < 30 ? 0 : 1;
    const blink = petState === "talking" ? false : pose % 42 > 37;
    const scale = 3;

    ctx.save();
    ctx.scale(scale, scale);
    ctx.translate(20, 12 + bob);

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
    if (petState === "talking" && pose % 12 < 6) {
      ctx.fillRect(51, 49, 7, 4);
    } else if (petState === "thinking") {
      ctx.fillRect(53, 50, 3, 2);
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
          window.testAtri?.dragPetWindow();
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
        window.testAtri?.beginPetWindowDrag();
        setMouseIgnored(false);
      }}
      onPointerUp={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
          event.currentTarget.releasePointerCapture(event.pointerId);
        }
        endDrag(event.clientX, event.clientY);
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
    const offText = window.testAtri?.onBubbleText((nextText) => {
      const nextSegments = segmentBubbleText(nextText);
      interruptRef.current += 1;
      setSegments(nextSegments);
      setSegmentIndex(0);
      setVisibleText("");
      setRunId((value) => value + 1);
    });
    const offInterrupt = window.testAtri?.onBubbleInterrupt(() => {
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
        <div className="bubble-title">test atri</div>
        <div className="bubble-text">{visibleText}</div>
      </div>
    </div>
  );
}

function PetWindow() {
  const [petState, setPetState] = useState("idle");

  useEffect(() => {
    window.testAtri?.setPetMouseIgnored(true);
    const offPetState = window.testAtri?.onPetState((state) => setPetState(state));
    return () => {
      offPetState?.();
      window.testAtri?.setPetMouseIgnored(true);
    };
  }, []);

  return (
    <main className="pet-window">
      <div className="pet-state-badge">{petState}</div>
      <BubbleOverlay />
      <div className="pet-hit-area" title="test atri">
        <PetCanvas petState={petState} />
      </div>
    </main>
  );
}

function CommandWindow() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [value, setValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusText, setStatusText] = useState("");

  useEffect(() => {
    const offFocus = window.testAtri?.onCommandFocus(() => {
      window.setTimeout(() => inputRef.current?.focus(), 0);
    });
    window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => offFocus?.();
  }, []);

  return (
    <main className="command-window">
      <form
        className="command-box"
        data-state={isSubmitting ? "submitting" : statusText ? "error" : "idle"}
        onSubmit={async (event) => {
          event.preventDefault();
          const text = value.trim();
          if (!text || isSubmitting) return;
          setIsSubmitting(true);
          setStatusText("Sending...");
          try {
            const result = await window.testAtri?.submitCommand(text);
            if (result?.ok) {
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
            setValue(event.target.value);
            if (statusText && statusText !== "Sending...") setStatusText("");
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              if (isSubmitting) return;
              setValue("");
              setStatusText("");
              window.testAtri?.hideCommand();
            }
          }}
          aria-label="Command"
          placeholder="Type to test atri..."
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
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [memoryMessage, setMemoryMessage] = useState("");
  const backendStatus = useBackendStatus(refreshKey);
  const permissionStatus = usePermissionStatus(refreshKey);
  const modelStatus = useJsonStatus<ModelProviderStatus>("/model/provider/status", refreshKey);
  const memoryStatus = useJsonStatus<MemoryStatus>("/memory", refreshKey);
  const projectReaderStatus = useJsonStatus<ProjectReaderStatus>("/project-reader/status", refreshKey);
  const logStatus = useJsonStatus<LogStatus>("/logs/status", refreshKey);
  const reasoningStatus = useJsonStatus<ReasoningStatus>("/reasoning/status", refreshKey);
  const reasoningRuns = useJsonStatus<ReasoningRunsResponse>("/reasoning/runs", refreshKey);
  const [petState, setPetState] = useState("idle");
  const [events, setEvents] = useState<DebugEvent[]>([]);
  const [selectedReasoningRunId, setSelectedReasoningRunId] = useState<string | null>(null);
  const [reasoningRunDetail, setReasoningRunDetail] = useState<ReasoningRunDetail | null>(null);
  const navItems = useMemo(
    () => [
      "Overview",
      "Reasoning",
      "Model",
      "Local Model",
      "Events",
      "Memory",
      "History",
      "Permissions",
      "Project Read",
      "External",
      "Visual",
      "Logs",
      "Voice",
      "Screen",
      "VR/OSC"
    ],
    []
  );

  useEffect(() => {
    const offState = window.testAtri?.onDebugState((state) => setPetState(state));
    const offEvents = window.testAtri?.onDebugEvents((nextEvents) => setEvents(nextEvents));
    return () => {
      offState?.();
      offEvents?.();
    };
  }, []);

  useEffect(() => {
    const firstRunId = reasoningRuns?.runs[0]?.run_id ?? null;
    if (!selectedReasoningRunId && firstRunId) setSelectedReasoningRunId(firstRunId);
    if (selectedReasoningRunId && !reasoningRuns?.runs.some((run) => run.run_id === selectedReasoningRunId)) {
      setSelectedReasoningRunId(firstRunId);
    }
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
                <span>{event.source}</span>
              </div>
              <pre>{JSON.stringify(event.payload ?? {}, null, 2)}</pre>
            </article>
          ))
        )}
      </div>
    );
  }

  function renderActiveView() {
    if (activeView === "Events") {
      return (
        <section className="debug-panel">
          <h2>Events</h2>
          {renderEventsPanel(40)}
        </section>
      );
    }

    if (activeView === "Permissions") {
      return (
        <section className="debug-panel">
          <h2>Permissions</h2>
          {permissionStatus ? (
            <div className="permission-grid">
              {Object.entries(permissionStatus.permissions).map(([name, enabled]) => (
                <div className="permission-row" key={name}>
                  <span>{name}</span>
                  <strong data-enabled={enabled}>{enabled ? "on" : "off"}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="debug-empty">Permissions unavailable.</p>
          )}
        </section>
      );
    }

    if (activeView === "Model" || activeView === "Local Model") {
      return (
        <section className="debug-panel">
          <h2>Model Provider</h2>
          <div className="detail-grid">
            <div><span>Enabled</span><strong>{modelStatus?.enabled ? "yes" : "no"}</strong></div>
            <div><span>Configured</span><strong>{modelStatus?.configured ? "yes" : "no"}</strong></div>
            <div><span>Provider</span><strong>{modelStatus?.active_provider ?? "unavailable"}</strong></div>
            <div><span>Model</span><strong>{modelStatus?.model ?? "unavailable"}</strong></div>
          </div>
        </section>
      );
    }

    if (activeView === "Reasoning") {
      return (
        <section className="debug-panel">
          <h2>Reasoning</h2>
          <div className="detail-grid">
            <div><span>Enabled</span><strong>{reasoningStatus?.enabled ? "yes" : "no"}</strong></div>
            <div><span>Provider</span><strong>{reasoningStatus?.provider ?? "unavailable"}</strong></div>
            <div><span>Real model calls</span><strong>{reasoningStatus?.real_model_calls ? "yes" : "no"}</strong></div>
            <div><span>Runs</span><strong>{reasoningStatus?.runs_total ?? 0}</strong></div>
          </div>
          <div className="reasoning-layout">
            <div className="reasoning-run-list">
              {reasoningRuns && reasoningRuns.runs.length > 0 ? (
                reasoningRuns.runs.slice(0, 24).map((run) => (
                  <button
                    key={run.run_id}
                    data-active={selectedReasoningRunId === run.run_id}
                    onClick={() => setSelectedReasoningRunId(run.run_id)}
                    type="button"
                  >
                    <strong>{run.status}</strong>
                    <span>{run.depth} / {run.provider}</span>
                    <small>{new Date(run.updated_at).toLocaleTimeString()}</small>
                  </button>
                ))
              ) : (
                <p className="debug-empty">No reasoning runs yet.</p>
              )}
            </div>
            <div className="reasoning-detail">
              {reasoningRunDetail ? (
                <>
                  <div className="debug-event-head">
                    <strong>{reasoningRunDetail.run.run_id}</strong>
                    <span>{reasoningRunDetail.run.event_type}</span>
                  </div>
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
      return (
        <section className="debug-panel">
          <h2>Memory</h2>
          <div className="detail-grid">
            <div><span>Manual writes</span><strong>{memoryStatus?.enabled ? "enabled" : "disabled"}</strong></div>
            <div><span>Items</span><strong>{memoryStatus?.items.length ?? 0}</strong></div>
          </div>
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
        </section>
      );
    }

    if (activeView === "Project Read") {
      return (
        <section className="debug-panel">
          <h2>Project Reader</h2>
          <div className="detail-grid">
            <div><span>Enabled</span><strong>{projectReaderStatus?.enabled ? "yes" : "no"}</strong></div>
            <div><span>Authorized roots</span><strong>{projectReaderStatus?.allowed_roots.length ?? 0}</strong></div>
            <div><span>Text types</span><strong>{projectReaderStatus?.text_extensions.length ?? 0}</strong></div>
          </div>
          <pre className="debug-code">
            {JSON.stringify(projectReaderStatus?.allowed_roots ?? [], null, 2)}
          </pre>
        </section>
      );
    }

    if (["External", "Voice", "Screen", "VR/OSC"].includes(activeView)) {
      const capabilityMap: Record<string, string[]> = {
        External: ["external.http", "external.websocket", "external.lan", "external.osc"],
        Voice: ["voice.listen", "voice.speak"],
        Screen: ["screen.observe"],
        "VR/OSC": ["vr.output", "external.osc"]
      };
      const capabilities = capabilityMap[activeView] ?? [];
      return (
        <section className="debug-panel">
          <h2>{activeView}</h2>
          <p className="debug-empty">Reserved until explicitly selected. Current permission state:</p>
          <div className="permission-grid">
            {capabilities.map((name) => {
              const enabled = Boolean(permissionStatus?.permissions[name]);
              return (
                <div className="permission-row" key={name}>
                  <span>{name}</span>
                  <strong data-enabled={enabled}>{enabled ? "on" : "off"}</strong>
                </div>
              );
            })}
          </div>
        </section>
      );
    }

    if (activeView === "History") {
      return (
        <section className="debug-panel">
          <h2>History</h2>
          <div className="timeline-list">
            {events.length > 0 ? (
              events.slice(0, 32).map((event) => (
                <article className="timeline-item" key={event.event_id}>
                  <span>{event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "--:--"}</span>
                  <strong>{event.type}</strong>
                  <small>{event.source}</small>
                </article>
              ))
            ) : (
              <p className="debug-empty">No event history yet.</p>
            )}
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
          </div>
          <p className="debug-empty">Final pixel manga/comic bubble visual still needs confirmation.</p>
        </section>
      );
    }

    if (activeView === "Logs") {
      return (
        <section className="debug-panel">
          <h2>Logs</h2>
          <div className="debug-event-list">
            {logStatus && logStatus.logs.length > 0 ? (
              logStatus.logs.map((log) => (
                <article className="debug-event log-card" data-kind={log.kind} key={log.name}>
                  <div className="debug-event-head">
                    <strong>{log.name}</strong>
                    <span>{log.kind} / {log.bytes} bytes</span>
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
          <h2>Recent Events</h2>
          {renderEventsPanel(8)}
        </section>
      </>
    );
  }

  return (
    <main className="debug-window">
      <aside className="debug-sidebar">
        <h1>test atri</h1>
        {navItems.map((item) => (
          <button
            key={item}
            data-active={activeView === item}
            onClick={() => setActiveView(item)}
          >
            {item}
          </button>
        ))}
      </aside>
      <section className="debug-content">
        <header className="debug-toolbar">
          <div>
            <span>Debug</span>
            <h2>{activeView}</h2>
          </div>
          <button onClick={refreshDebugData}>Refresh</button>
        </header>
        {renderActiveView()}
      </section>
    </main>
  );
}

function App() {
  const kind = currentWindowKind();
  if (kind === "command") return <CommandWindow />;
  if (kind === "debug") return <DebugWindow />;
  return <PetWindow />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
