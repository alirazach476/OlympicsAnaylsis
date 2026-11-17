"""FastAPI entrypoint for the Olympics historical data platform."""

from __future__ import annotations

import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.explorer import router as explorer_router
from backend.api.olympic import router as olympic_router
from backend.api.pages import router as pages_router
from backend.api.platform import router as platform_router
from backend.api.routes import router
from backend.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Olympics Historical Data Platform API",
    description=(
        "Monitoring and control API for Summer (1960–2024) and Winter (1960–2026) "
        "Olympic data collection, including the recursive Wikipedia crawler."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(olympic_router, prefix="/api")  # Olympedia-style event / match / medal / country-edition pages
if os.environ.get("OLY_LAZY_VIZ"):
    # Serverless cold start: the chart stack (pandas, numpy, scipy) is only imported when the first /api/viz request arrives.
    _viz_lock = threading.Lock()
    _viz_loaded = False

    @app.middleware("http")
    async def _load_viz_on_demand(request, call_next):
        global _viz_loaded
        if not _viz_loaded and request.url.path.startswith("/api/viz"):
            with _viz_lock:
                if not _viz_loaded:
                    from backend.api.viz import router as viz_router

                    app.include_router(viz_router, prefix="/api")
                    _viz_loaded = True
        return await call_next(request)
else:
    from backend.api.viz import router as viz_router

    app.include_router(viz_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(platform_router, prefix="/api")  # new platform endpoints take precedence over legacy /overview and /games
app.include_router(router, prefix="/api")
app.include_router(explorer_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "name": "Olympics Historical Data Platform",
        "docs": "/docs",
        "api": "/api/health",
    }
