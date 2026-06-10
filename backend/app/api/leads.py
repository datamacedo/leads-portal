from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.lead import Lead
from app.models.tenant import User
from app.schemas.schemas import LeadCreate, LeadOut, LeadUpdate, Paginated
from app.services.scoring import refresh_lead_score

router = APIRouter(prefix="/leads", tags=["Leads"])


def _dedupe(db: Session, tenant_id: int, email: str | None, phone: str | None) -> Lead | None:
    q = db.query(Lead).filter(Lead.tenant_id == tenant_id)
    if email:
        existing = q.filter(Lead.email == email).first()
        if existing:
            return existing
    if phone:
        return q.filter(Lead.phone == phone).first()
    return None


def create_or_merge_lead(db: Session, tenant_id: int, data: dict) -> Lead:
    """Deduplicação: mesmo email/telefone no tenant = atualiza em vez de duplicar."""
    lead = _dedupe(db, tenant_id, data.get("email"), data.get("phone"))
    if lead:
        for k, v in data.items():
            if v and not getattr(lead, k, None):
                setattr(lead, k, v)
    else:
        lead = Lead(tenant_id=tenant_id, converted_at=datetime.now(timezone.utc), **data)
        db.add(lead)
    db.flush()
    refresh_lead_score(db, lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.post("", response_model=LeadOut, status_code=201)
def create_lead(body: LeadCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_or_merge_lead(db, user.tenant_id, body.model_dump(exclude_none=True))


@router.get("", response_model=Paginated)
def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = None,
    source: str | None = None,
    propensity: str | None = None,
    search: str | None = None,
    order_by: str = Query("score", pattern="^(score|created_at)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.tenant_id == user.tenant_id)
    if status:
        q = q.filter(Lead.status == status)
    if source:
        q = q.filter(Lead.source == source)
    if propensity:
        q = q.filter(Lead.propensity == propensity)
    if search:
        like = f"%{search}%"
        q = q.filter(Lead.name.ilike(like) | Lead.email.ilike(like) | Lead.company.ilike(like))
    total = q.count()
    col = Lead.score if order_by == "score" else Lead.created_at
    items = q.order_by(col.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return Paginated(total=total, page=page, per_page=per_page,
                     items=[LeadOut.model_validate(i) for i in items])


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == user.tenant_id).first()
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: int, body: LeadUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == user.tenant_id).first()
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(lead, k, v)
    refresh_lead_score(db, lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/{lead_id}/journey")
def lead_journey(lead_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ficha do lead — jornada completa: sessões, dispositivos, eventos."""
    from app.models.tracking import TrackEvent, TrackSession

    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == user.tenant_id).first()
    if not lead:
        raise HTTPException(404, "Lead não encontrado")
    sessions = (
        db.query(TrackSession)
        .filter(TrackSession.lead_id == lead.id)
        .order_by(TrackSession.started_at)
        .all()
    )
    out = []
    for s in sessions:
        events = db.query(TrackEvent).filter(TrackEvent.session_id == s.id).order_by(TrackEvent.created_at).all()
        out.append({
            "started_at": s.started_at,
            "duration_seconds": s.duration_seconds,
            "pages_count": s.pages_count,
            "device": {"type": s.device_type, "os": s.os, "browser": s.browser, "screen": s.screen},
            "referrer": s.referrer,
            "utm": s.utm,
            "events": [{"type": e.type, "url": e.url, "data": e.data, "at": e.created_at} for e in events],
        })
    return {
        "lead_id": lead.id,
        "first_seen_at": lead.first_seen_at,
        "converted_at": lead.converted_at,
        "courtship_days": (
            (lead.converted_at - lead.first_seen_at).days
            if lead.first_seen_at and lead.converted_at else None
        ),
        "sessions": out,
    }
