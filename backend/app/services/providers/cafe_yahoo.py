import logging
from datetime import date
from decimal import Decimal

import httpx

from app.core.config import get_settings
from app.services.providers.base import QuoteProvider, QuoteUpdate

logger = logging.getLogger(__name__)
settings = get_settings()

# Spread aproximado (em relação ao contrato de NY) usado apenas para ESTIMAR
# os preços de BM&F e Londres enquanto não há uma fonte gratuita dedicada
# para essas praças. Ajuste ou remova assim que plugar uma fonte real.
_SPREAD_ESTIMADO_BMF = Decimal("-0.10")  # BM&F historicamente cotado um pouco abaixo de NY (aprox.)
_SPREAD_ESTIMADO_LONDRES = Decimal("0.05")


def _current_front_month_label(today: date | None = None) -> str:
    """Café arábica (ICE) tem vencimentos em mar/mai/jul/set/dez.
    Aproxima o contrato corrente com base no mês atual."""
    today = today or date.today()
    meses_vencimento = [3, 5, 7, 9, 12]
    nomes = {3: "MAR", 5: "MAI", 7: "JUL", 9: "SET", 12: "DEZ"}
    mes = next((m for m in meses_vencimento if m >= today.month), meses_vencimento[0])
    ano = today.year if mes >= today.month else today.year + 1
    return f"{nomes[mes]}/{str(ano)[-2:]}"


class CafeYahooProvider(QuoteProvider):
    """Café (contrato futuro corrente) via Yahoo Finance (endpoint público
    não-oficial, sem necessidade de chave). BM&F e Londres são estimados a
    partir do preço de Nova York até que uma fonte gratuita dedicada seja
    integrada (ver comentário acima)."""

    name = "yahoo_finance"

    async def fetch(self) -> list[QuoteUpdate]:
        url = settings.cafe_yahoo_url.format(symbol=settings.cafe_yahoo_symbol)
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url, params={"interval": "1d", "range": "1d"})
            response.raise_for_status()
            data = response.json()

        try:
            result = data["chart"]["result"][0]
            meta = result["meta"]
        except (KeyError, IndexError, TypeError):
            logger.warning("Resposta inesperada do Yahoo Finance para %s: %s", settings.cafe_yahoo_symbol, data)
            return []

        preco_ultimo = _to_decimal(meta.get("regularMarketPrice"))
        preco_ajuste_anterior = _to_decimal(meta.get("previousClose") or meta.get("chartPreviousClose"))
        preco_maximo = _to_decimal(meta.get("regularMarketDayHigh"))
        preco_minimo = _to_decimal(meta.get("regularMarketDayLow"))

        if preco_ultimo is None:
            return []

        variacao = None
        variacao_pct = None
        if preco_ajuste_anterior:
            variacao = preco_ultimo - preco_ajuste_anterior
            if preco_ajuste_anterior != 0:
                variacao_pct = (variacao / preco_ajuste_anterior) * 100

        vencimento_label = _current_front_month_label()

        quotes = [
            QuoteUpdate(
                praca_codigo="NY",
                praca_nome="Nova York",
                ativo_codigo="CAFE",
                ativo_nome="Café",
                ticker=settings.cafe_yahoo_symbol,
                vencimento_label=vencimento_label,
                preco_ultimo=preco_ultimo,
                preco_maximo=preco_maximo,
                preco_minimo=preco_minimo,
                preco_ajuste_anterior=preco_ajuste_anterior,
                variacao=variacao,
                variacao_pct=variacao_pct,
                fonte=self.name,
                ordem=0,
            )
        ]

        quotes.append(
            _estimativa(
                base=quotes[0],
                praca_codigo="BMF",
                praca_nome="BM&F",
                ticker="ICF" + vencimento_label.replace("/", ""),
                spread=_SPREAD_ESTIMADO_BMF,
            )
        )
        quotes.append(
            _estimativa(
                base=quotes[0],
                praca_codigo="LONDRES",
                praca_nome="Londres",
                ticker="RC" + vencimento_label.replace("/", ""),
                spread=_SPREAD_ESTIMADO_LONDRES,
            )
        )
        return quotes


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 - dado externo, qualquer formato inesperado vira None
        return None


def _estimativa(*, base: QuoteUpdate, praca_codigo: str, praca_nome: str, ticker: str, spread: Decimal) -> QuoteUpdate:
    preco_ultimo = base.preco_ultimo + spread if base.preco_ultimo is not None else None
    preco_ajuste_anterior = (
        base.preco_ajuste_anterior + spread if base.preco_ajuste_anterior is not None else None
    )
    return QuoteUpdate(
        praca_codigo=praca_codigo,
        praca_nome=praca_nome,
        ativo_codigo="CAFE",
        ativo_nome="Café",
        ticker=ticker,
        vencimento_label=base.vencimento_label,
        preco_ultimo=preco_ultimo,
        preco_ajuste_anterior=preco_ajuste_anterior,
        variacao=base.variacao,
        variacao_pct=base.variacao_pct,
        fonte="estimado_a_partir_de_ny",
        ordem=1,
    )
