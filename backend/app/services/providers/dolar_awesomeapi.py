import logging
from decimal import Decimal, InvalidOperation

import httpx

from app.core.config import get_settings
from app.services.providers.base import QuoteProvider, QuoteUpdate

logger = logging.getLogger(__name__)
settings = get_settings()


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


class DolarAwesomeApiProvider(QuoteProvider):
    """Dólar comercial (USD/BRL) via AwesomeAPI (economia.awesomeapi.com.br),
    API pública e gratuita, sem necessidade de chave."""

    name = "awesomeapi"

    async def fetch(self) -> list[QuoteUpdate]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.dolar_api_url)
            response.raise_for_status()
            data = response.json()

        quote = data.get("USDBRL")
        if not quote:
            logger.warning("Resposta inesperada da AwesomeAPI: %s", data)
            return []

        bid = _to_decimal(quote.get("bid"))
        high = _to_decimal(quote.get("high"))
        low = _to_decimal(quote.get("low"))
        var_bid = _to_decimal(quote.get("varBid"))
        pct_change = _to_decimal(quote.get("pctChange"))

        return [
            QuoteUpdate(
                praca_codigo="BALCAO",
                praca_nome="Câmbio",
                ativo_codigo="DOLAR",
                ativo_nome="Dólar",
                ticker="USD-BRL",
                vencimento_label="COMERCIAL",
                preco_ultimo=bid,
                preco_maximo=high,
                preco_minimo=low,
                variacao=var_bid,
                variacao_pct=pct_change,
                fonte=self.name,
                ordem=0,
            )
        ]
