from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Praca(Base):
    """Praça/bolsa onde o contrato é negociado (ex: NOVA YORK, BM&F, LONDRES)."""

    __tablename__ = "pracas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    instrumentos = relationship("Instrumento", back_populates="praca")


class Ativo(Base):
    """Tipo de ativo negociado (ex: CAFE, DOLAR)."""

    __tablename__ = "ativos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    unidade: Mapped[str] = mapped_column(String(20), nullable=False, default="")

    instrumentos = relationship("Instrumento", back_populates="ativo")


class Instrumento(Base):
    """Um contrato/vencimento específico de um ativo em uma praça
    (ex: café em Nova York, vencimento DEZ/26, ticker KCZ6)."""

    __tablename__ = "instrumentos"
    __table_args__ = (UniqueConstraint("praca_id", "ativo_id", "ticker", name="uq_instrumento_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    praca_id: Mapped[int] = mapped_column(ForeignKey("pracas.id", ondelete="CASCADE"), nullable=False)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativos.id", ondelete="CASCADE"), nullable=False)

    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    vencimento_label: Mapped[str] = mapped_column(String(20), nullable=False)
    vencimento_data: Mapped[date | None] = mapped_column(Date, nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ativo_flag: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    praca = relationship("Praca", back_populates="instrumentos")
    ativo = relationship("Ativo", back_populates="instrumentos")
    cotacao_atual = relationship(
        "CotacaoAtual", back_populates="instrumento", uselist=False, cascade="all, delete-orphan"
    )


class CotacaoAtual(Base):
    """Última cotação conhecida de cada instrumento (1 linha por instrumento, sempre atualizada)."""

    __tablename__ = "cotacoes_atuais"

    instrumento_id: Mapped[int] = mapped_column(
        ForeignKey("instrumentos.id", ondelete="CASCADE"), primary_key=True
    )

    preco_abertura: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    preco_maximo: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    preco_minimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    preco_ajuste_anterior: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    preco_ultimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    variacao: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    variacao_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    volume: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    contratos_abertos: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    fonte: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instrumento = relationship("Instrumento", back_populates="cotacao_atual")


class CotacaoHistorico(Base):
    """Série histórica (append-only) usada para gráficos e auditoria."""

    __tablename__ = "cotacoes_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrumento_id: Mapped[int] = mapped_column(
        ForeignKey("instrumentos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    preco_ultimo: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    variacao_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    capturado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
