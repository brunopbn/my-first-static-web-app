from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class InstrumentoQuoteOut(BaseModel):
    instrumento_id: int
    praca: str
    ativo: str
    ticker: str
    vencimento_label: str
    preco_abertura: Decimal | None = None
    preco_maximo: Decimal | None = None
    preco_minimo: Decimal | None = None
    preco_ajuste_anterior: Decimal | None = None
    preco_ultimo: Decimal | None = None
    variacao: Decimal | None = None
    variacao_pct: Decimal | None = None
    volume: Decimal | None = None
    contratos_abertos: Decimal | None = None
    fonte: str
    atualizado_em: datetime | None = None

    model_config = {"from_attributes": True}


class PracaQuotesOut(BaseModel):
    praca: str
    instrumentos: list[InstrumentoQuoteOut]


class QuotesSnapshotOut(BaseModel):
    pracas: list[PracaQuotesOut]
    servidor_em: datetime
