"""Rastreamento comportamental — visitantes, sessões, eventos e dispositivos.

Fluxo: visitante anônimo (visitor_id no cookie) → eventos → preenche formulário
→ Inforge.identify() → identity stitching vincula todo o histórico ao Lead.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Visitor(Base):
    """Identidade anônima persistida via cookie/localStorage no site do cliente."""
    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)  # uuid gerado pelo track.js
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), nullable=True, index=True)
    # null = ainda anônimo; preenchido no identity stitching
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions = relationship("TrackSession", back_populates="visitor")


class TrackSession(Base):
    """Uma visita ao site — agrupa eventos. 30min de inatividade = nova sessão."""
    __tablename__ = "track_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    visitor_id: Mapped[int] = mapped_column(ForeignKey("visitors.id"), index=True)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), nullable=True, index=True)
    session_key: Mapped[str] = mapped_column(String(64), index=True)

    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # mobile|tablet|desktop
    os: Mapped[str | None] = mapped_column(String(60), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(60), nullable=True)
    screen: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "1920x1080"
    connection: Mapped[str | None] = mapped_column(String(20), nullable=True)  # wifi|4g|...
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    utm: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    pages_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    visitor = relationship("Visitor", back_populates="sessions")
    lead = relationship("Lead", back_populates="sessions")
    events = relationship("TrackEvent", back_populates="session")


class TrackEvent(Base):
    __tablename__ = "track_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("track_sessions.id"), index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)
    # pageview | click | scroll | form_submit | identify | custom
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # click: {selector, text} · scroll: {depth_pct} · pageview: {title, time_on_page}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    session = relationship("TrackSession", back_populates="events")
