const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("testAtri", {
  showBubble: (text) => ipcRenderer.invoke("pet:show-bubble", text),
  hideBubble: () => ipcRenderer.invoke("bubble:hide"),
  submitCommand: (text) => ipcRenderer.invoke("command:submit", text),
  hideCommand: () => ipcRenderer.invoke("command:hide"),
  setPetMouseIgnored: (ignored) => ipcRenderer.invoke("pet:set-mouse-ignored", ignored),
  beginPetWindowDrag: () => ipcRenderer.invoke("pet:begin-drag-window"),
  dragPetWindow: () => ipcRenderer.invoke("pet:drag-window"),
  endPetWindowDrag: () => ipcRenderer.invoke("pet:end-drag-window"),
  notifyPetClicked: () => ipcRenderer.invoke("pet:model-clicked"),
  onBubbleText: (handler) => {
    const listener = (_event, text) => handler(text);
    ipcRenderer.on("bubble:text", listener);
    return () => ipcRenderer.removeListener("bubble:text", listener);
  },
  onBubbleInterrupt: (handler) => {
    ipcRenderer.on("bubble:interrupt", handler);
    return () => ipcRenderer.removeListener("bubble:interrupt", handler);
  },
  onPetState: (handler) => {
    const listener = (_event, state) => handler(state);
    ipcRenderer.on("pet:state", listener);
    return () => ipcRenderer.removeListener("pet:state", listener);
  },
  onDebugEvents: (handler) => {
    const listener = (_event, events) => handler(events);
    ipcRenderer.on("debug:events", listener);
    return () => ipcRenderer.removeListener("debug:events", listener);
  },
  onDebugState: (handler) => {
    const listener = (_event, state) => handler(state);
    ipcRenderer.on("debug:state", listener);
    return () => ipcRenderer.removeListener("debug:state", listener);
  },
  onCommandFocus: (handler) => {
    ipcRenderer.on("command:focus", handler);
    return () => ipcRenderer.removeListener("command:focus", handler);
  }
});
