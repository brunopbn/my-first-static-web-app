import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.quotes import router as quotes_router
from app.api.ws import router as ws_router
from app.core.config import get_settings
from app.services.quote_updater import quote_polling_loop

logging.basicConfig(level=logging.INFO)
settings = get_settings()

FRONTEND_DIR = (
    Path(settings.frontend_dir) if settings.frontend_dir else Path(__file__).resolve().parent.parent.parent / "src"
)

_stop_event = asyncio.Event()
_background_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _background_task
    _background_task = asyncio.create_task(quote_polling_loop(_stop_event))
    try:
        yield
    finally:
        _stop_event.set()
        if _background_task:
            await _background_task


app = FastAPI(title="Painel de Cotações", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(quotes_router)
app.include_router(ws_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


if FRONTEND_DIR.exists():
    # Serve o frontend estático (login.html, index.html, styles.css, js/*)
    # na raiz. Registrado por último: as rotas /api/* e /ws/* acima têm
    # prioridade sobre este catch-all.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
