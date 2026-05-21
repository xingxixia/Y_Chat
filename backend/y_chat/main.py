from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import audio as audio_router
from .routers import events as events_router
from .routers import local_models as local_models_router
from .routers import memory as memory_router
from .routers import model_provider as model_provider_router
from .routers import project_reader as project_reader_router
from .routers import reasoning as reasoning_router
from .routers import screen as screen_router
from .routers import system as system_router
from .routers import vision as vision_router


app = FastAPI(title="Y_Chat backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system_router.router)
app.include_router(local_models_router.router)
app.include_router(model_provider_router.router)
app.include_router(reasoning_router.router)
app.include_router(project_reader_router.router)
app.include_router(memory_router.router)
app.include_router(vision_router.router)
app.include_router(audio_router.router)
app.include_router(screen_router.router)
app.include_router(events_router.router)
