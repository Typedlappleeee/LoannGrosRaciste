"""Application web FastAPI : interface + API pour piloter l'agent."""
from __future__ import annotations

import logging
from collections import deque
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from engine import AgentEngine
from models import Alert
from outputs import send_discord
from settings import Settings
from store import SeenStore

STATIC_DIR = Path(__file__).parent / "static"

# ----- capture des logs en memoire (affiches dans l'UI) ---------------------
LOG_BUFFER: deque[str] = deque(maxlen=200)


class BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            LOG_BUFFER.append(self.format(record))
        except Exception:
            pass


def _setup_logging() -> None:
    handler = BufferHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(logging.StreamHandler())


# ----- etat global ----------------------------------------------------------
app = FastAPI(title="LoanGrosRaciste")
store = SeenStore()
settings = Settings.load()


async def _on_alert(alert: Alert) -> None:
    store.save_alert(alert.to_dict())
    if settings.discord_webhook_url:
        async with httpx.AsyncClient() as c:
            await send_discord(c, settings.discord_webhook_url, alert)


engine = AgentEngine(store, _on_alert)


@app.on_event("startup")
async def _startup() -> None:
    _setup_logging()
    store.prune()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await engine.stop()


# ----- API ------------------------------------------------------------------
@app.get("/api/state")
async def get_state(limit: int = 50) -> JSONResponse:
    return JSONResponse(
        {
            "status": engine.status(),
            "alerts": store.recent_alerts(limit),
            "logs": list(LOG_BUFFER)[-60:],
        }
    )


@app.get("/api/settings")
async def get_settings() -> JSONResponse:
    return JSONResponse(settings.public_dict())


@app.post("/api/settings")
async def post_settings(request: Request) -> JSONResponse:
    data = await request.json()
    settings.update(data)
    settings.save()
    return JSONResponse({"ok": True, "settings": settings.public_dict()})


@app.post("/api/agent/start")
async def start_agent() -> JSONResponse:
    await engine.start(settings)
    return JSONResponse({"ok": True, "status": engine.status()})


@app.post("/api/agent/stop")
async def stop_agent() -> JSONResponse:
    await engine.stop()
    return JSONResponse({"ok": True, "status": engine.status()})


@app.post("/api/scan")
async def scan(request: Request) -> JSONResponse:
    data = await request.json()
    query = (data.get("query") or "").strip()
    if not query:
        return JSONResponse({"error": "query vide"}, status_code=400)
    coins = await engine.scan(query, settings)
    return JSONResponse({"query": query, "coins": [c.to_dict() for c in coins[:10]]})


# ----- interface ------------------------------------------------------------
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
