"""Conector Meta Lead Ads (Facebook/Instagram).

Fluxo:
1. GET  /webhooks/meta — verificação do webhook (hub.challenge) ao configurar no Meta
2. POST /webhooks/meta — Meta envia leadgen_id quando alguém preenche o formulário
3. Buscamos os dados completos na Graph API e salvamos com o tenant correto

Mapeamento tenant ↔ página: o cliente conecta a página dele e guardamos page_id
no campo extra de configuração (v1: query param ?tenant_token= na URL do webhook).
"""
import hashlib
import hmac

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.tenant import Tenant

router = APIRouter(prefix="/webhooks", tags=["Conectores"])

GRAPH = "https://graph.facebook.com/v21.0"


@router.get("/meta")
def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(403, "Verificação falhou")


def _valid_signature(body: bytes, signature: str | None) -> bool:
    if not settings.META_APP_SECRET:
        return True  # dev — em produção SEMPRE configurar META_APP_SECRET
    if not signature:
        return False
    expected = "sha256=" + hmac.new(
        settings.META_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _fetch_lead_data(leadgen_id: str) -> dict:
    """Busca os campos preenchidos no formulário via Graph API."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{GRAPH}/{leadgen_id}",
            params={"access_token": settings.META_PAGE_ACCESS_TOKEN},
        )
        r.raise_for_status()
        return r.json()


def _parse_field_data(field_data: list[dict]) -> dict:
    """Converte field_data do Meta em campos do Lead."""
    mapping = {
        "full_name": "name", "nome": "name", "name": "name",
        "email": "email", "e-mail": "email",
        "phone_number": "phone", "telefone": "phone", "celular": "phone",
        "company_name": "company", "empresa": "company",
        "city": "city", "cidade": "city",
    }
    out, extra = {}, {}
    for f in field_data:
        key = f.get("name", "").lower()
        val = (f.get("values") or [None])[0]
        if key in mapping:
            out[mapping[key]] = val
        else:
            extra[key] = val
    if extra:
        out["extra"] = extra
    return out


@router.post("/meta")
async def receive_lead(
    request: Request,
    tenant_token: str = Query(..., description="tracking_token do tenant"),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if not _valid_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "Assinatura inválida")

    tenant = db.query(Tenant).filter(Tenant.tracking_token == tenant_token).first()
    if not tenant:
        raise HTTPException(404, "Tenant não encontrado")

    payload = await request.json()
    created = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "leadgen":
                continue
            leadgen_id = change["value"].get("leadgen_id")
            form_id = change["value"].get("form_id")
            try:
                data = await _fetch_lead_data(leadgen_id)
                fields = _parse_field_data(data.get("field_data", []))
            except Exception:
                # Sem access token (dev) — registra o mínimo, não perde o lead
                fields = {"extra": {"leadgen_id": leadgen_id, "pending_fetch": True}}

            fields["source"] = "meta_ads"
            fields["source_detail"] = f"form:{form_id}"

            from app.api.leads import create_or_merge_lead
            lead = create_or_merge_lead(db, tenant.id, fields)
            created.append(lead.id)

    return {"ok": True, "leads_created": created}
