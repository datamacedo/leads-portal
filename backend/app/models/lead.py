"""Leads e enriquecimento — o coração da base."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        # Deduplicação: mesmo email ou telefone no mesmo tenant = mesmo lead
        UniqueConstraint("tenant_id", "email", name="uq_lead_tenant_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)

    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), index=True, nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cpf_cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    source: Mapped[str] = mapped_column(String(40), default="manual")
    # manual | meta_ads | google_ads | tiktok | website | import
    source_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)  # campanha/form

    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    # new | mql | sql | won | lost | cold
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    propensity: Mapped[str | None] = mapped_column(String(10), nullable=True)  # alta | media | baixa

    enrichment_status: Mapped[str] = mapped_column(String(20), default="none")
    # none | pending | done | failed
    enrichment_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # {faturamento_estimado, funcionarios, setor, socios, telefone_atualizado, ...}

    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # campos livres do form
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # primeira visita anônima ao site (preenchido pelo identity stitching)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    tenant = relationship("Tenant", back_populates="leads")
    sessions = relationship("TrackSession", back_populates="lead")


class EnrichmentRequest(Base):
    """Solicitação de qualificação — cliente pede, a InForge processa e devolve."""
    __tablename__ = "enrichment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    service: Mapped[str] = mapped_column(String(30))  # enrichment | reactivation
    provider: Mapped[str] = mapped_column(String(30), default="mock")
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    # received | analyzing | processing | done | failed
    records_sent: Mapped[int] = mapped_column(Integer, default=1)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    credits_charged: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
