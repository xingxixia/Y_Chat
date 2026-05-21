const { desktopCapturer, ipcRenderer } = require("electron");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

function runtimeRefForScreenshot(fileName) {
  return `runtime://memory_blobs/vision/screenshots/${fileName}`;
}

function safeExtension(value) {
  const extension = String(value || "jpg").replace(/[^a-z0-9]/gi, "").toLowerCase();
  return extension || "jpg";
}

async function captureScreenWorkerFrame(request) {
  const startedAt = Date.now();
  ipcRenderer.send("screen-worker:capture-progress", {
    request_id: request.request_id,
    stage: "started",
    elapsed_ms: 0
  });
  const getSourcesStartedAt = Date.now();
  ipcRenderer.send("screen-worker:capture-progress", {
    request_id: request.request_id,
    stage: "get_sources_started",
    elapsed_ms: Date.now() - startedAt
  });
  const sources = await desktopCapturer.getSources({
    types: ["screen"],
    thumbnailSize: {
      width: Math.max(1, Math.round(request.thumbnail_width || 1)),
      height: Math.max(1, Math.round(request.thumbnail_height || 1))
    }
  });
  const get_sources_ms = Date.now() - getSourcesStartedAt;
  ipcRenderer.send("screen-worker:capture-progress", {
    request_id: request.request_id,
    stage: "get_sources_completed",
    elapsed_ms: Date.now() - startedAt,
    get_sources_ms,
    source_count: sources.length
  });
  const source =
    sources.find((item) => item.display_id === String(request.display_id)) ??
    sources[0];
  if (!source) throw new Error("no screen source available");

  const encodeStartedAt = Date.now();
  ipcRenderer.send("screen-worker:capture-progress", {
    request_id: request.request_id,
    stage: "encode_started",
    elapsed_ms: Date.now() - startedAt
  });
  const quality = Math.max(1, Math.min(100, Math.round(request.jpeg_quality || 70)));
  const imageBytes = source.thumbnail.toJPEG(quality);
  const encode_ms = Date.now() - encodeStartedAt;
  ipcRenderer.send("screen-worker:capture-progress", {
    request_id: request.request_id,
    stage: "encode_completed",
    elapsed_ms: Date.now() - startedAt,
    encode_ms,
    size_bytes: imageBytes.length
  });

  const hashStartedAt = Date.now();
  const sha256 = crypto.createHash("sha256").update(imageBytes).digest("hex");
  const hash_ms = Date.now() - hashStartedAt;

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const fileName = `screen-${timestamp}-${sha256.slice(0, 12)}.${safeExtension(request.file_extension)}`;
  const rawRef = runtimeRefForScreenshot(fileName);

  let write_ms = 0;
  if (request.retain_raw) {
    const screenshotDir = String(request.screenshot_dir || "");
    if (!screenshotDir) throw new Error("screen worker missing screenshot directory");
    const writeStartedAt = Date.now();
    ipcRenderer.send("screen-worker:capture-progress", {
      request_id: request.request_id,
      stage: "write_started",
      elapsed_ms: Date.now() - startedAt
    });
    await fs.promises.mkdir(screenshotDir, { recursive: true });
    await fs.promises.writeFile(path.join(screenshotDir, fileName), imageBytes);
    write_ms = Date.now() - writeStartedAt;
    ipcRenderer.send("screen-worker:capture-progress", {
      request_id: request.request_id,
      stage: "write_completed",
      elapsed_ms: Date.now() - startedAt,
      write_ms
    });
  }

  const size = source.thumbnail.getSize();
  return {
    request_id: request.request_id,
    ok: true,
    raw_ref: rawRef,
    file_name: fileName,
    sha256,
    size_bytes: imageBytes.length,
    width: size.width,
    height: size.height,
    get_sources_ms,
    encode_ms,
    hash_ms,
    write_ms,
    worker_total_ms: Date.now() - startedAt
  };
}

ipcRenderer.on("screen-worker:capture", async (_event, request) => {
  try {
    ipcRenderer.send("screen-worker:capture-result", await captureScreenWorkerFrame(request || {}));
  } catch (error) {
    ipcRenderer.send("screen-worker:capture-result", {
      request_id: request?.request_id,
      ok: false,
      message: error instanceof Error ? error.message : String(error)
    });
  }
});
