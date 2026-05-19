# Troubleshooting

## General Rule

Do not guess when rendering, encoding, process, or dependency failures occur.

Order:

1. Check this document and `STATUS.md`.
2. Check source code.
3. Check runtime logs.
4. Check running processes and ports.
5. Fix the issue and update docs.

## Garbled Text

Do not rewrite text blindly. Check:

- File encoding.
- Terminal encoding.
- Browser/Electron font fallback.
- JSON/YAML encoding.
- Source file save encoding.

## Logs Status Redaction Or Cleanup Looks Wrong

Expected behavior:

- `/logs/status` redacts API keys, authorization headers, bearer tokens, token,
  secret, and password values before tails reach Debug Logs.
- `/logs/status` cleans display-only noise such as UTF-8 BOM markers, ANSI
  color escapes, and common UTF-8 mojibake. Raw log files remain unchanged.

Check:

- First test `y_chat.logs.clean_log_line` and `redact_log_line` directly.
- Then test the FastAPI app through `TestClient`.
- Then test the running `http://127.0.0.1:18080/logs/status` service.

If direct/TestClient checks pass but the running service fails, the dev backend
has not reloaded the latest source. Restart with `scripts/stop_dev.ps1` and
`scripts/start_dev.ps1`, then retest the real endpoint.

Do not assume `uvicorn reload=True` picked up every edit on Windows.

PowerShell may display valid UTF-8 symbols from Vite logs as mojibake in command
output. If the API appears garbled, inspect HTTP response bytes or Unicode
codepoints before treating it as an application bug.

## Black or Blank Window

Check:

- Vite dev server is running.
- Electron loaded the expected URL.
- DevTools console errors.
- Canvas render loop is running.
- Transparent window CSS does not hide the root element.

## Pet Click Shows Bubble

Symptom:

- Clicking the pet model shows a bubble or frame.

Check:

- The pet model should not directly call `showBubble`.
- Bubble display should be caused by `pet.bubble.show` events.
- `Ctrl+Space` should open the command input window, not directly show output.

Cause:

This violates the input/output separation rule. The bubble is event-driven
output, not a click-generated UI frame. Do not assume the current rectangular
pixel frame is the user's intended pixel-style manga/comic bubble.

## Pet Edge Interaction Breaks

Symptom:

- After dragging the model into a display edge, the model no longer clicks or
  drags normally.

Check:

- The app should not clamp the model, bubble, or command input to the display
  work area; they may move partially off-screen like normal windows.
- Drag state should reset on `mouseup` and window `blur`.
- Mouse pass-through should return to a sane state after drag cancellation.

Cause:

Dragging to an edge can drop mouse events or leave the pet window in the wrong
mouse-ignore state if drag end is not handled defensively.

## Debug Window Errors After Reopening

Symptom:

```text
Debug window opens once, then reopening after closing shows a renderer or
destroyed-object error.
```

Expected behavior:

- Closing the debug window should hide it, not destroy it.
- `Ctrl+Shift+P` should reopen the existing debug window.
- If the debug window was destroyed anyway, Electron should recreate it before
  sending debug events.

Implementation notes:

- Check `debugWindow && !debugWindow.isDestroyed()` before `webContents.send`.
- On debug window `close`, prevent default and hide while the app is running.
- On app quit, allow real close after setting `app.isQuitting`.

## Backend Unreachable

Check:

- Port `18080`.
- `GET /health`.
- FastAPI process logs.
- Conda environment is selected by local setup. Scripts load
  `runtime/dev.local.ps1` first, then `Y_CHAT_CONDA_ENV`, then default to
  `y_chat`.

## Debug History Missing Events

Expected behavior:

- Electron writes local event summaries to `runtime/events.jsonl`.
- On startup, Electron loads the latest 80 events into the Debug Window event
  buffer.
- A fresh Electron session should add a `system.hello` event.

Check:

- `runtime/events.jsonl` exists after Electron starts.
- `electron.err.log` is empty.
- The file is not source data; it is ignored by `.gitignore`.
- Persistence failures should not crash the desktop shell, so an empty History
  page can mean the file could not be written.

## Frontend Dependencies Missing

Symptom:

```text
frontend/node_modules missing
```

Action:

1. Review `frontend/package.json`.
2. Run `npm install` in `frontend/` only after approval.
3. Re-run Vite/Electron startup checks.

## npm Install Timeout

Observed:

```text
npm install timed out after about 304 seconds
node_modules exists
package-lock.json is missing
```

Treat this as an incomplete install.

Resume steps:

1. Check lingering processes:
   - `npm`
   - `node`
   - `electron`
2. Check dependency tree with `npm ls --depth=0`.
3. If dependency tree is invalid, report the state before retrying install.
4. Do not assume Electron/Vite is usable until `npm ls` and startup checks pass.

Resolution used on 2026-05-18:

- Stopped the lingering project `npm install` and Electron `install.js`
  processes after confirming they were stale.
- Re-ran `npm install` in `frontend/`; it generated `package-lock.json`.
- Added missing React type packages and verified `npm run typecheck`.

## Electron Binary Missing

Symptom:

```text
Electron failed to install correctly, please delete node_modules/electron and try installing again
```

Check:

- `frontend/node_modules/electron/dist/electron.exe`
- `frontend/node_modules/electron/path.txt`
- `npx electron --version`

Resolution used on 2026-05-18:

```powershell
$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'
npm rebuild electron
```

The first 30 seconds may show no terminal output. Check temp download files and
stop if there is no file growth or process progress.

## PowerShell Start-Process Redirect Failure

Symptom:

```text
RedirectStandardOutput and RedirectStandardError are same
```

Cause:

PowerShell `Start-Process` cannot redirect stdout and stderr to the same file.

Resolution:

- Use separate `.out.log` and `.err.log` files per process.
- On Windows, use `npm.cmd` instead of plain `npm` in `Start-Process`.

## Workspace vs Python Environment

The repository root is the project workspace.

The conda environment is only the Python environment for backend commands. Do
not refer to it as the workspace.

## WebSocket Fails

Check:

- `/ws/internal` path.
- Browser console.
- Backend logs.
- Event JSON envelope validity.

## Process Stuck

If startup, install, build, or tests exceed the expected timeout, report:

- Command.
- Process/PID if available.
- Last logs.
- Impact.
- Proposed next step.

Do not silently wait forever and do not kill unrelated user processes.
