"""Endpoints para BI externo (Power BI, Tableau, Metabase).

Autenticação: header X-API-Key. Schema estável, paginado, filtrável.
Power BI: Obter Dados → Web → URL + header X-API-Key.
"""
import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_tenant_from_api_key
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.models.tracking import TrackSession

router = APIRouter(prefix="/bi", tags=["BI / Integrações"])


@router.get("/leads")
def bi_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(500, ge=1, le=5000),
    created_after: str | None = None,  # ISO date — carga incremental no BI
    tenant: Tenant = Depends(get_tenant_from_api_key),
    db: Session = Depends(get_db),
):
    q = db.query(Lead).filter(Lead.tenant_id == tenant.id)
    if created_after:
        q = q.filter(Lead.created_at >= created_after)
    total = q.count()
    rows = q.order_by(Lead.id).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total, "page": page, "per_page": per_page,
        "items": [
            {
                "id": l.id, "name": l.name, "email": l.email, "phone": l.phone,
                "company": l.company, "city": l.city, "state": l.state,
                "source": l.source, "status": l.status, "score": l.score,
                "propensity": l.propensity, "enrichment_status": l.enrichment_status,
                "first_seen_at": l.first_seen_at, "converted_at": l.converted_at,
                "created_at": l.created_at,
            }
            for l in rows
        ],
    }


@router.get("/leads.csv")
def bi_leads_csv(tenant: Tenant = Depends(get_tenant_from_api_key), db: Session = Depends(get_db)):
    rows = db.query(Lead).filter(Lead.tenant_id == tenant.id).order_by(Lead.id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "email", "phone", "company", "city", "state",
                "source", "status", "score", "propensity", "created_at"])
    for l in rows:
        w.writerow([l.id, l.name, l.email, l.phone, l.company, l.city, l.state,
                    l.source, l.status, l.score, l.propensity, l.created_at])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=leads.csv"})


@router.get("/metrics")
def bi_metrics(tenant: Tenant = Depends(get_tenant_from_api_key), db: Session = Depends(get_db)):
    """Agregados prontos para dashboards."""
    base = db.query(Lead).filter(Lead.tenant_id == tenant.id)
    by_source = dict(
        db.query(Lead.source, func.count(Lead.id))
        .filter(Lead.tenant_id == tenant.id).group_by(Lead.source).all()
    )
    by_status = dict(
        db.query(Lead.status, func.count(Lead.id))
        .filter(Lead.tenant_id == tenant.id).group_by(Lead.status).all()
    )
    by_propensity = dict(
        db.query(Lead.propensity, func.count(Lead.id))
        .filter(Lead.tenant_id == tenant.id, Lead.propensity.isnot(None))
        .group_by(Lead.propensity).all()
    )
    avg_score = db.query(func.avg(Lead.score)).filter(Lead.tenant_id == tenant.id).scalar() or 0
    sessions = db.query(func.count(TrackSession.id)).filter(TrackSession.tenant_id == tenant.id).scalar()
    return {
        "total_leads": base.count(),
        "avg_score": round(float(avg_score), 1),
        "by_source": by_source,
        "by_status": by_status,
        "by_propensity": by_propensity,
        "track_sessions": sessions,
    }
