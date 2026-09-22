import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models.market import Ativo, CotacaoAtual, CotacaoHistorico, Instrumento, Praca
from app.services.providers.base import QuoteProvider, QuoteUpdate
from app.services.providers.cafe_yahoo import CafeYahooProvider
from app.services.providers.dolar_awesomeapi import DolarAwesomeApiProvider
from app.services.session_manager import revoke_idle_sessions
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)
settings = get_settings()

PROVIDERS: list[QuoteProvider] = [DolarAwesomeApiProvider(), CafeYahooProvider()]


async def _get_or_create_praca(db: AsyncSession, codigo: str, nome: str, ordem: int) -> Praca:
    result = await db.execute(select(Praca).where(Praca.codigo == codigo))
    praca = result.scalar_one_or_none()
    if praca is None:
        praca = Praca(codigo=codigo, nome=nome, ordem=ordem)
        db.add(praca)
        await db.flush()
    return praca


async def _get_or_create_ativo(db: AsyncSession, codigo: str, nome: str) -> Ativo:
    result = await db.execute(select(Ativo).where(Ativo.codigo == codigo))
    ativo = result.scalar_one_or_none()
    if ativo is None:
        ativo = Ativo(codigo=codigo, nome=nome)
        db.add(ativo)
        await db.flush()
    return ativo


async def _get_or_create_instrumento(db: AsyncSession, update: QuoteUpdate, praca: Praca, ativo: Ativo) -> Instrumento:
    result = await db.execute(
        select(Instrumento)
        .where(Instrumento.praca_id == praca.id)
        .where(Instrumento.ativo_id == ativo.id)
        .where(Instrumento.ticker == update.ticker)
    )
    instrumento = result.scalar_one_or_none()
    if instrumento is None:
        instrumento = Instrumento(
            praca_id=praca.id,
            ativo_id=ativo.id,
            ticker=update.ticker,
            vencimento_label=update.vencimento_label,
            ordem=update.ordem,
        )
        db.add(instrumento)
        await db.flush()
    elif instrumento.vencimento_label != update.vencimento_label:
        instrumento.vencimento_label = update.vencimento_label
    return instrumento


async def _apply_update(db: AsyncSession, update: QuoteUpdate) -> dict:
    praca = await _get_or_create_praca(db, update.praca_codigo, update.praca_nome, ordem=0)
    ativo = await _get_or_create_ativo(db, update.ativo_codigo, update.ativo_nome)
    instrumento = await _get_or_create_instrumento(db, update, praca, ativo)

    cotacao = await db.get(CotacaoAtual, instrumento.id)
    if cotacao is None:
        cotacao = CotacaoAtual(instrumento_id=instrumento.id)
        db.add(cotacao)

    cotacao.preco_abertura = update.preco_abertura
    cotacao.preco_maximo = update.preco_maximo
    cotacao.preco_minimo = update.preco_minimo
    cotacao.preco_ajuste_anterior = update.preco_ajuste_anterior
    cotacao.preco_ultimo = update.preco_ultimo
    cotacao.variacao = update.variacao
    cotacao.variacao_pct = update.variacao_pct
    cotacao.volume = update.volume
    cotacao.contratos_abertos = update.contratos_abertos
    cotacao.fonte = update.fonte
    cotacao.atualizado_em = datetime.now(timezone.utc)

    db.add(
        CotacaoHistorico(
            instrumento_id=instrumento.id,
            preco_ultimo=update.preco_ultimo,
            variacao_pct=update.variacao_pct,
        )
    )

    return {
        "instrumento_id": instrumento.id,
        "praca": praca.nome,
        "praca_codigo": praca.codigo,
        "ativo": ativo.nome,
        "ticker": instrumento.ticker,
        "vencimento_label": instrumento.vencimento_label,
        "preco_ultimo": float(update.preco_ultimo) if update.preco_ultimo is not None else None,
        "preco_maximo": float(update.preco_maximo) if update.preco_maximo is not None else None,
        "preco_minimo": float(update.preco_minimo) if update.preco_minimo is not None else None,
        "preco_ajuste_anterior": float(update.preco_ajuste_anterior) if update.preco_ajuste_anterior is not None else None,
        "variacao": float(update.variacao) if update.variacao is not None else None,
        "variacao_pct": float(update.variacao_pct) if update.variacao_pct is not None else None,
        "fonte": update.fonte,
        "atualizado_em": cotacao.atualizado_em.isoformat(),
    }


async def build_snapshot() -> list[dict]:
    """Retorna o estado atual de todas as cotações, no mesmo formato usado
    pelo broadcast em tempo real (usado ao abrir uma nova conexão WS)."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(CotacaoAtual, Instrumento, Praca, Ativo)
            .join(Instrumento, CotacaoAtual.instrumento_id == Instrumento.id)
            .join(Praca, Instrumento.praca_id == Praca.id)
            .join(Ativo, Instrumento.ativo_id == Ativo.id)
        )
        rows = result.all()

    snapshot = []
    for cot, inst, praca, ativo in rows:
        snapshot.append(
            {
                "instrumento_id": inst.id,
                "praca": praca.nome,
                "praca_codigo": praca.codigo,
                "ativo": ativo.nome,
                "ticker": inst.ticker,
                "vencimento_label": inst.vencimento_label,
                "preco_ultimo": float(cot.preco_ultimo) if cot.preco_ultimo is not None else None,
                "preco_maximo": float(cot.preco_maximo) if cot.preco_maximo is not None else None,
                "preco_minimo": float(cot.preco_minimo) if cot.preco_minimo is not None else None,
                "preco_ajuste_anterior": float(cot.preco_ajuste_anterior) if cot.preco_ajuste_anterior is not None else None,
                "variacao": float(cot.variacao) if cot.variacao is not None else None,
                "variacao_pct": float(cot.variacao_pct) if cot.variacao_pct is not None else None,
                "fonte": cot.fonte,
                "atualizado_em": cot.atualizado_em.isoformat() if cot.atualizado_em else None,
            }
        )
    return snapshot


async def run_poll_cycle() -> list[dict]:
    changed: list[dict] = []
    async with async_session_maker() as db:
        for provider in PROVIDERS:
            try:
                updates = await provider.fetch()
            except Exception:  # noqa: BLE001 - erro de rede/fonte externa não pode derrubar o loop
                logger.exception("Falha ao buscar cotações do provider %s", provider.name)
                continue

            for update in updates:
                try:
                    changed.append(await _apply_update(db, update))
                except Exception:  # noqa: BLE001
                    logger.exception("Falha ao aplicar cotação %s/%s", update.praca_codigo, update.ticker)

        await db.commit()

        try:
            await revoke_idle_sessions(db)
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao limpar sessões ociosas")

    return changed


async def quote_polling_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        changed = await run_poll_cycle()
        if changed:
            await ws_manager.broadcast({"type": "quotes_update", "instrumentos": changed})
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=settings.quote_poll_interval_seconds)
        except asyncio.TimeoutError:
            pass
