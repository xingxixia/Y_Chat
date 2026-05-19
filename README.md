# Y_Chat

`Y_Chat` is a local intelligent desktop pet application. It is not a web
deployment project. The current goal is a runnable development shell with an
Electron desktop pet frontend and a Python FastAPI backend.

## Current Stage

Stage 1: runnable shell.

- Electron desktop shell with a transparent pet window.
- Canvas-rendered pixel pet placeholder.
- Event-driven bubble overlay inside the pet window.
- FastAPI backend with health and internal WebSocket endpoints.
- Manual Debug Memory list/create/delete is available for development.
- PowerShell development launcher for both backend and frontend.

Real AI replies, automatic memory, voice, screen perception, VR, and external
adapters are planned but intentionally not active in the first shell.

## Environment

- Windows
- conda environment: set `Y_CHAT_CONDA_ENV` or use a compatible local env
- backend port: `18080`
- frontend dev port: `5173`

## Development

Install dependencies after reviewing the dependency files:

```powershell
cd <repo>
conda activate y_chat
pip install -r backend\requirements.txt
cd frontend
npm install
```

Start both processes:

```powershell
cd <repo>
.\scripts\start_dev.ps1
```

Stop all development processes:

```powershell
cd <repo>
.\scripts\stop_dev.ps1
```

## Local Config

`runtime/config.yaml` is local-only and ignored by git because it may later hold
API keys, local paths, or private pet codenames. Start from
`runtime/config.example.yaml` when setting up a new checkout.

Optional machine-specific development overrides can be placed in
`runtime/dev.local.ps1`, starting from `runtime/dev.local.example.ps1`.

The public repository name is `Y_Chat`. A private local runtime may still use a
separate pet codename, but that name stays in ignored local config.

## License

Code is licensed under Apache-2.0. Branding, character names, character
likenesses, sprites, icons, voice designs, screenshots, and other creative
assets are not granted by the code license; see `BRANDING.md`.

## Documentation

The project memory and recovery documents live in:

```text
docs/dev_journal/
```

Read order:

1. `STATUS.md`
2. `ARCHITECTURE.md`
3. `MEMORY_ARCHITECTURE.md`
4. `REASONING_ARCHITECTURE.md`
5. `DECISIONS.md`
6. `MODULES.md`
7. `API_EVENTS.md`
8. `WORKLOG.md`
9. `TROUBLESHOOTING.md`
