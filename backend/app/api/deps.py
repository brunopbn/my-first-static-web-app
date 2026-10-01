from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.models.user_session import UserSession
from app.services.session_manager import get_active_session_by_jti, touch_session

_bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_user_and_session(
    token: str, db: AsyncSession
) -> tuple[User, UserSession]:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    session = await get_active_session_by_jti(db, jti)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada ou encerrada em outra tela.",
        )

    user = await db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")

    await touch_session(db, session)
    return user, session


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    user, _session = await _resolve_user_and_session(credentials.credentials, db)
    request.state.current_session = _session
    return user


async def get_current_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserSession:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado")
    _user, session = await _resolve_user_and_session(credentials.credentials, db)
    return session


async def resolve_user_from_token(token: str, db: AsyncSession) -> tuple[User, UserSession]:
    """Usado pelo endpoint WebSocket, onde o token chega via mensagem de auth
    em vez de header Authorization."""
    return await _resolve_user_and_session(token, db)


async def select_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
