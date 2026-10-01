import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.api.deps import resolve_user_from_token
from app.db.session import async_session_maker
from app.services.quote_updater import build_snapshot
from app.services.session_manager import get_active_session_by_jti, touch_session
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

_AUTH_TIMEOUT_SECONDS = 10.0


@router.websocket("/ws/quotes")
async def ws_quotes(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=_AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
        await websocket.close(code=4000, reason="Autenticação não recebida a tempo")
        return

    token = auth_message.get("token") if isinstance(auth_message, dict) else None
    if not token:
        await websocket.close(code=4001, reason="Token ausente")
        return

    async with async_session_maker() as db:
        try:
            _user, session = await resolve_user_from_token(token, db)
        except Exception:  # noqa: BLE001 - qualquer falha de auth fecha a conexão
            await websocket.close(code=4003, reason="Não autorizado")
            return

    await ws_manager.connect(session.id, websocket)
    try:
        snapshot = await build_snapshot()
        await websocket.send_json({"type": "snapshot", "instrumentos": snapshot})

        while True:
            message = await websocket.receive_json()
            if isinstance(message, dict) and message.get("type") == "ping":
                async with async_session_maker() as db:
                    current = await get_active_session_by_jti(db, session.token_jti)
                    if current is None:
                        await websocket.close(code=4001, reason="Sessão encerrada")
                        break
                    await touch_session(db, current)
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(session.id, websocket)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
