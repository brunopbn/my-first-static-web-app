"""Script utilitário para criar/atualizar um usuário do painel.

Uso:
    python -m app.seed --email usuario@empresa.com --password "senha-forte" --nome "Nome Completo" --max-sessions 1
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_maker
from app.models.user import User


async def create_or_update_user(email: str, password: str, full_name: str, max_sessions: int, is_admin: bool) -> None:
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                max_sessions=max_sessions,
                is_admin=is_admin,
            )
            db.add(user)
            print(f"Usuário criado: {email}")
        else:
            user.password_hash = hash_password(password)
            user.full_name = full_name
            user.max_sessions = max_sessions
            user.is_admin = is_admin
            print(f"Usuário atualizado: {email}")
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria ou atualiza um usuário do painel de cotações")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--nome", dest="full_name", required=True)
    parser.add_argument("--max-sessions", type=int, default=1)
    parser.add_argument("--admin", action="store_true")
    args = parser.parse_args()

    asyncio.run(
        create_or_update_user(
            email=args.email,
            password=args.password,
            full_name=args.full_name,
            max_sessions=args.max_sessions,
            is_admin=args.admin,
        )
    )


if __name__ == "__main__":
    main()
