from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, new_jti
from app.models.user import User
from app.models.user_session import UserSession

settings = get_settings()


class SessionLimitError(Exception):
    """Levantado quando o usuário já atingiu o limite de telas simultâneas
    e a política configurada é rejeitar o novo login."""


async def _active_sessions(db: AsyncSession, user_id: int) -> list[UserSession]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .where(UserSession.revoked_at.is_(None))
        .where(UserSession.expires_at > now)
        .order_by(UserSession.last_seen_at.asc())
    )
    return list(result.scalars().all())


async def create_session(
    db: AsyncSession,
    user: User,
    *,
    device_info: str | None,
    ip_address: str | None,
) -> tuple[str, datetime, UserSession]:
    """Cria uma nova sessão (tela) para o usuário, respeitando o limite de
    sessões simultâneas configurado (`user.max_sessions`)."""

    active = await _active_sessions(db, user.id)

    if len(active) >= user.max_sessions:
        if settings.session_limit_policy == "kick_oldest":
            oldest = active[0]
            oldest.revoked_at = datetime.now(timezone.utc)
            db.add(oldest)
        else:
            raise SessionLimitError(
                f"Limite de {user.max_sessions} tela(s) simultânea(s) atingido para este usuário."
            )

    jti = new_jti()
    token, expires_at = create_access_token(user_id=user.id, jti=jti)

    session = UserSession(
        user_id=user.id,
        token_jti=jti,
        device_info=device_info,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return token, expires_at, session


async def get_active_session_by_jti(db: AsyncSession, jti: str) -> UserSession | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserSession)
        .where(UserSession.token_jti == jti)
        .where(UserSession.revoked_at.is_(None))
        .where(UserSession.expires_at > now)
    )
    return result.scalar_one_or_none()


async def touch_session(db: AsyncSession, session: UserSession) -> None:
    idle_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.session_idle_timeout_minutes)
    session.last_seen_at = datetime.now(timezone.utc)
    db.add(session)
    await db.commit()
    _ = idle_cutoff  # limite de ociosidade aplicado por job de limpeza separado


async def revoke_session(db: AsyncSession, session: UserSession) -> None:
    session.revoked_at = datetime.now(timezone.utc)
    db.add(session)
    await db.commit()


async def revoke_idle_sessions(db: AsyncSession) -> int:
    """Libera 'telas' que pararam de mandar heartbeat (ex: aba fechada sem logout
    explícito), para não travar o limite de sessões indefinidamente."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.session_idle_timeout_minutes)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserSession)
        .where(UserSession.revoked_at.is_(None))
        .where(UserSession.last_seen_at < cutoff)
        .where(UserSession.expires_at > now)
    )
    idle_sessions = list(result.scalars().all())
    for session in idle_sessions:
        session.revoked_at = datetime.now(timezone.utc)
        db.add(session)
    if idle_sessions:
        await db.commit()
    return len(idle_sessions)
