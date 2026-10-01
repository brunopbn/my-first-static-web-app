import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Mantém as conexões WebSocket autenticadas e permite broadcast das
    cotações para todas as telas conectadas."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.setdefault(session_id, set()).add(websocket)

    async def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(session_id)
            if connections:
                connections.discard(websocket)
                if not connections:
                    self._connections.pop(session_id, None)

    async def disconnect_all_for_session(self, session_id: int) -> None:
        """Força o encerramento de uma sessão específica (ex: revogada por
        limite de telas ou logout em outro dispositivo)."""
        async with self._lock:
            connections = self._connections.pop(session_id, set())
        for ws in connections:
            try:
                await ws.close(code=4001, reason="Sessão encerrada")
            except Exception:  # noqa: BLE001
                pass

    async def broadcast(self, payload: dict) -> None:
        async with self._lock:
            snapshot = {sid: set(conns) for sid, conns in self._connections.items()}
        stale: list[tuple[int, WebSocket]] = []
        for session_id, conns in snapshot.items():
            for ws in conns:
                try:
                    await ws.send_json(payload)
                except Exception:  # noqa: BLE001
                    stale.append((session_id, ws))
        for session_id, ws in stale:
            await self.disconnect(session_id, ws)


ws_manager = WebSocketManager()
