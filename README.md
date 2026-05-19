# test atri

`test atri` is a local intelligent desktop pet application rebuilt in this
workspace. It is not a web deployment project. The current goal is a runnable
development shell with an Electron desktop pet frontend and a Python FastAPI
backend.

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
- conda environment: `Atri_2`
- backend port: `18080`
- frontend dev port: `5173`

## Development

Install dependencies after reviewing the dependency files:

```powershell
cd E:\File\AIuseing\xai\test1
conda activate Atri_2
pip install -r backend\requirements.txt
cd frontend
npm install
```

Start both processes:

```powershell
cd E:\File\AIuseing\xai\test1
.\scripts\start_dev.ps1
```

Stop all development processes:

```powershell
cd E:\File\AIuseing\xai\test1
.\scripts\stop_dev.ps1
```

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
