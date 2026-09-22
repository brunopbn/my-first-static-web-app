from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class QuoteUpdate:
    praca_codigo: str
    praca_nome: str
    ativo_codigo: str
    ativo_nome: str
    ticker: str
    vencimento_label: str
    preco_ultimo: Decimal | None
    preco_abertura: Decimal | None = None
    preco_maximo: Decimal | None = None
    preco_minimo: Decimal | None = None
    preco_ajuste_anterior: Decimal | None = None
    variacao: Decimal | None = None
    variacao_pct: Decimal | None = None
    volume: Decimal | None = None
    contratos_abertos: Decimal | None = None
    fonte: str = ""
    ordem: int = 0


class QuoteProvider(ABC):
    """Interface para uma fonte de cotações. Cada provider é responsável por
    buscar os dados externos e devolver uma lista de QuoteUpdate prontos
    para serem gravados no banco."""

    name: str = "provider"

    @abstractmethod
    async def fetch(self) -> list[QuoteUpdate]:
        raise NotImplementedError
