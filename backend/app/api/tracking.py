"""Recebe eventos do track.js — endpoint público autenticado pelo tracking_token.

POST /track/event    → eventos (pageview, click, scroll...)
POST /track/identify → identity stitching: anônimo vira lead
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.models.tracking import TrackEvent, TrackSession, Visitor
from app.schemas.schemas import IdentifyIn, TrackEventIn
from app.services.scoring import refresh_lead_score

router = APIRouter(prefix="/track", tags=["Tracking"])


def _tenant_by_token(db: Session, token: str) -> Tenant:
    t = db.query(Tenant).filter(Tenant.tracking_token == token, Tenant.is_active.is_(True)).first()
    if not t:
        raise HTTPException(401, "Tracking token inválido")
    return t


def _get_or_create_visitor(db: Session, tenant_id: int, visitor_id: str) -> Visitor:
    v = db.query(Visitor).filter(Visitor.tenant_id == tenant_id, Visitor.visitor_id == visitor_id).first()
    if not v:
        v = Visitor(tenant_id=tenant_id, visitor_id=visitor_id)
        db.add(v)
        db.flush()
    v.last_seen_at = datetime.now(timezone.utc)
    return v


def _get_or_create_session(db: Session, tenant_id: int, visitor: Visitor, body: TrackEventIn, request: Request) -> TrackSession:
    s = (
        db.query(TrackSession)
        .filter(TrackSession.tenant_id == tenant_id, TrackSession.session_key == body.session_key)
        .first()
    )
    if not s:
        d = body.device or {}
        s = TrackSession(
            tenant_id=tenant_id,
            visitor_id=visitor.id,
            lead_id=visitor.lead_id,
            session_key=body.session_key,
            device_type=d.get("type"),
            os=d.get("os"),
            browser=d.get("browser"),
            screen=d.get("screen"),
            connection=d.get("connection"),
            ip=request.client.host if request.client else None,
            referrer=body.referrer,
            utm=body.utm,
        )
        db.add(s)
        db.flush()
    return s


@router.post("/event", status_code=202)
def track_event(body: TrackEventIn, request: Request, db: Session = Depends(get_db)):
    tenant = _tenant_by_token(db, body.token)
    visitor = _get_or_create_visitor(db, tenant.id, body.visitor_id)
    session = _get_or_create_session(db, tenant.id, visitor, body, request)

    db.add(TrackEvent(
        tenant_id=tenant.id, session_id=session.id,
        type=body.type, url=body.url, data=body.data,
    ))

    # Atualiza agregados da sessão
    if body.type == "pageview":
        session.pages_count = (session.pages_count or 0) + 1
    if body.data and isinstance(body.data.get("time_on_page"), (int, float)):
        session.duration_seconds = (session.duration_seconds or 0) + body.data["time_on_page"]
    session.ended_at = datetime.now(timezone.utc)

    db.commit()
    return {"ok": True}


@router.post("/identify")
def identify(body: IdentifyIn, db: Session = Depends(get_db)):
    """O momento mágico: cruza histórico anônimo com o lead real."""
    if not body.email and not body.phone:
        raise HTTPException(422, "Informe email ou phone")

    tenant = _tenant_by_token(db, body.token)
    visitor = _get_or_create_visitor(db, tenant.id, body.visitor_id)

    # Lead existente (dedupe) ou novo
    from app.api.leads import create_or_merge_lead
    lead = create_or_merge_lead(db, tenant.id, {
        "name": body.name, "email": body.email,
        "phone": body.phone, "company": body.company,
        "source": "website",
    })

    # Stitching: vincula visitante + todas as sessões antigas ao lead
    visitor.lead_id = lead.id
    sessions = db.query(TrackSession).filter(TrackSession.visitor_id == visitor.id).all()
    for s in sessions:
        s.lead_id = lead.id

    # first_seen = primeira visita anônima (o início do "namoro")
    if sessions:
        first = min(s.started_at for s in sessions)
        if not lead.first_seen_at or first < lead.first_seen_at:
            lead.first_seen_at = first
    if not lead.converted_at:
        lead.converted_at = datetime.now(timezone.utc)

    refresh_lead_score(db, lead)
    db.commit()
    return {"ok": True, "lead_id": lead.id, "score": lead.score, "sessions_linked": len(sessions)}
