from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.market import Instrumento, Praca
from app.models.user import User
from app.schemas.quotes import InstrumentoQuoteOut, PracaQuotesOut, QuotesSnapshotOut

router = APIRouter(prefix="/api/quotes", tags=["quotes"])


@router.get("", response_model=QuotesSnapshotOut)
async def get_quotes_snapshot(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuotesSnapshotOut:
    result = await db.execute(
        select(Praca)
        .options(
            selectinload(Praca.instrumentos).selectinload(Instrumento.ativo),
            selectinload(Praca.instrumentos).selectinload(Instrumento.cotacao_atual),
        )
        .order_by(Praca.ordem, Praca.nome)
    )
    pracas = result.scalars().all()

    pracas_out: list[PracaQuotesOut] = []
    for praca in pracas:
        instrumentos_out: list[InstrumentoQuoteOut] = []
        for inst in sorted(praca.instrumentos, key=lambda i: (i.ordem, i.vencimento_data or i.vencimento_label)):
            cot = inst.cotacao_atual
            instrumentos_out.append(
                InstrumentoQuoteOut(
                    instrumento_id=inst.id,
                    praca=praca.nome,
                    ativo=inst.ativo.nome,
                    ticker=inst.ticker,
                    vencimento_label=inst.vencimento_label,
                    preco_abertura=cot.preco_abertura if cot else None,
                    preco_maximo=cot.preco_maximo if cot else None,
                    preco_minimo=cot.preco_minimo if cot else None,
                    preco_ajuste_anterior=cot.preco_ajuste_anterior if cot else None,
                    preco_ultimo=cot.preco_ultimo if cot else None,
                    variacao=cot.variacao if cot else None,
                    variacao_pct=cot.variacao_pct if cot else None,
                    volume=cot.volume if cot else None,
                    contratos_abertos=cot.contratos_abertos if cot else None,
                    fonte=cot.fonte if cot else "",
                    atualizado_em=cot.atualizado_em if cot else None,
                )
            )
        pracas_out.append(PracaQuotesOut(praca=praca.nome, instrumentos=instrumentos_out))

    return QuotesSnapshotOut(pracas=pracas_out, servidor_em=datetime.now(timezone.utc))
