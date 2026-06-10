import hashlib
import hmac
import json

from app.core.config import settings
from tests.conftest import login

PAYLOAD = {
    "entry": [{
        "changes": [{
            "field": "leadgen",
            "value": {"leadgen_id": "lg-1", "form_id": "f-1"},
        }]
    }]
}


def test_verificacao_do_webhook(client, tenant_a):
    r = client.get("/api/v1/webhooks/meta", params={
        "hub.mode": "subscribe",
        "hub.verify_token": settings.META_VERIFY_TOKEN,
        "hub.challenge": "12345",
    })
    assert r.status_code == 200 and r.json() == 12345

    r = client.get("/api/v1/webhooks/meta", params={
        "hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1",
    })
    assert r.status_code == 403


def test_recebe_lead_e_cria_no_tenant_certo(client, tenant_a):
    t, user = tenant_a
    r = client.post(f"/api/v1/webhooks/meta?tenant_token={t.tracking_token}", json=PAYLOAD)
    assert r.status_code == 200
    assert len(r.json()["leads_created"]) == 1
    h = login(client, user.email)
    leads = client.get("/api/v1/leads?source=meta_ads", headers=h).json()
    assert leads["total"] == 1
    assert leads["items"][0]["source_detail"] == "form:f-1"


def test_tenant_token_invalido(client, tenant_a):
    r = client.post("/api/v1/webhooks/meta?tenant_token=nao-existe", json=PAYLOAD)
    assert r.status_code == 404


def test_assinatura_invalida_rejeitada(client, tenant_a, monkeypatch):
    """Com META_APP_SECRET configurado, payload sem assinatura válida é rejeitado."""
    monkeypatch.setattr(settings, "META_APP_SECRET", "segredo-teste")
    t, _ = tenant_a
    body = json.dumps(PAYLOAD).encode()

    # sem assinatura
    r = client.post(f"/api/v1/webhooks/meta?tenant_token={t.tracking_token}",
                    content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 403

    # assinatura correta passa
    sig = "sha256=" + hmac.new(b"segredo-teste", body, hashlib.sha256).hexdigest()
    r = client.post(f"/api/v1/webhooks/meta?tenant_token={t.tracking_token}",
                    content=body,
                    headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})
    assert r.status_code == 200
