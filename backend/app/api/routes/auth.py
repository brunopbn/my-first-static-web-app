from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_session, get_current_user, select_user_by_email
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.auth import LoginRequest, LoginResponse, SessionOut, UserOut
from app.services.session_manager import (
    SessionLimitError,
    create_session,
    revoke_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    user = await select_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo")

    try:
        token, expires_at, _session = await create_session(
            db,
            user,
            device_info=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except SessionLimitError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return LoginResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    session: UserSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    await revoke_session(db, session)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/sessions", response_model=list[SessionOut])
async def list_my_sessions(
    user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    from app.services.session_manager import _active_sessions  # import local para evitar API pública desnecessária

    active = await _active_sessions(db, user.id)
    return [
        SessionOut(
            id=s.id,
            device_info=s.device_info,
            ip_address=s.ip_address,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            is_current=s.id == session.id,
        )
        for s in active
    ]
