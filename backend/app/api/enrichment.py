"""Qualificação sob demanda — cliente clica 'Qualificar', débito de créditos, provedor enriquece."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.lead import EnrichmentRequest, Lead
from app.models.tenant import CreditTransaction, Tenant, User
from app.schemas.schemas import EnrichRequestIn, EnrichRequestOut
from app.services.enrichment import get_provider
from app.services.scoring import refresh_lead_score

router = APIRouter(prefix="/enrichment", tags=["Enriquecimento"])

CREDIT_FIELD = {"enrichment": "credits_enrichment", "reactivation": "credits_reactivation"}


@router.post("/requests", response_model=EnrichRequestOut, status_code=201)
async def request_enrichment(
    body: EnrichRequestIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.service not in CREDIT_FIELD:
        raise HTTPException(422, "service deve ser enrichment ou reactivation")

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    leads = (
        db.query(Lead)
        .filter(Lead.id.in_(body.lead_ids), Lead.tenant_id == tenant.id)
        .all()
    )
    if not leads:
        raise HTTPException(404, "Nenhum lead encontrado")

    cost = len(leads)  # 1 crédito por lead
    field = CREDIT_FIELD[body.service]
    if getattr(tenant, field) < cost:
        raise HTTPException(402, f"Créditos insuficientes: precisa de {cost}, tem {getattr(tenant, field)}")

    req = EnrichmentRequest(
        tenant_id=tenant.id, service=body.service,
        provider=get_provider().__class__.__name__.replace("Provider", "").lower(),
        status="processing", records_sent=len(leads), credits_charged=cost,
    )
    db.add(req)

    # Débito + extrato
    setattr(tenant, field, getattr(tenant, field) - cost)
    db.add(CreditTransaction(
        tenant_id=tenant.id, service=body.service, amount=-cost,
        description=f"Qualificação de {cost} lead(s)",
    ))
    db.flush()

    # v1 síncrono. Quando o volume crescer: fila (Celery/RQ) e status intermediários.
    provider = get_provider()
    results = {}
    for lead in leads:
        data = await provider.enrich({
            "name": lead.name, "email": lead.email, "phone": lead.phone,
            "cpf_cnpj": lead.cpf_cnpj, "company": lead.company,
        })
        lead.enrichment_data = data
        lead.enrichment_status = "done"
        if data.get("propensao"):
            lead.propensity = data["propensao"]
        refresh_lead_score(db, lead)
        results[str(lead.id)] = data

    req.status = "done"
    req.result = {"leads": results}
    req.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return req


@router.get("/requests", response_model=list[EnrichRequestOut])
def list_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(EnrichmentRequest)
        .filter(EnrichmentRequest.tenant_id == user.tenant_id)
        .order_by(EnrichmentRequest.created_at.desc())
        .all()
    )


@router.get("/credits")
def credits(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    txs = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.tenant_id == t.id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "enrichment": t.credits_enrichment,
        "reactivation": t.credits_reactivation,
        "history": [
            {"service": x.service, "amount": x.amount, "description": x.description, "at": x.created_at}
            for x in txs
        ],
    }
