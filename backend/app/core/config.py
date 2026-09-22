from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Banco de dados
    database_url: str = "postgresql+asyncpg://painel:painel@localhost:5432/painel_cotacoes"

    # Autenticação
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    # Limite de telas simultâneas
    default_max_sessions: int = 1
    session_limit_policy: Literal["reject", "kick_oldest"] = "reject"
    session_idle_timeout_minutes: int = 5

    # Atualização de cotações
    quote_poll_interval_seconds: float = 5.0
    dolar_api_url: str = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
    cafe_yahoo_symbol: str = "KC=F"
    cafe_yahoo_url: str = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    # Servidor
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    # Caminho para os arquivos estáticos do frontend (login.html, index.html, etc).
    # Se vazio, usa "<repo>/src" (funciona out-of-the-box em dev local).
    frontend_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
