from tests.conftest import login, make_tenant


def _lead(client, h, email="q@x.com"):
    return client.post("/api/v1/leads", json={"name": "Q", "email": email}, headers=h).json()


def test_qualificacao_debita_creditos(client, tenant_a):
    _, user = tenant_a
    h = login(client, user.email)
    lead = _lead(client, h)
    r = client.post("/api/v1/enrichment/requests",
                    json={"lead_ids": [lead["id"]], "service": "enrichment"}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "done"
    assert body["credits_charged"] == 1

    c = client.get("/api/v1/enrichment/credits", headers=h).json()
    assert c["enrichment"] == 99  # começou com 100
    assert c["history"][0]["amount"] == -1

    # lead atualizado
    updated = client.get(f"/api/v1/leads/{lead['id']}", headers=h).json()
    assert updated["enrichment_status"] == "done"
    assert updated["enrichment_data"]["provider"] == "mock"


def test_creditos_insuficientes(client, db):
    t, user = make_tenant(db, "semcredito", credits=0)
    h = login(client, user.email)
    lead = _lead(client, h)
    r = client.post("/api/v1/enrichment/requests",
                    json={"lead_ids": [lead["id"]], "service": "enrichment"}, headers=h)
    assert r.status_code == 402  # Payment Required


def test_nao_qualifica_lead_de_outro_tenant(client, tenant_a, tenant_b):
    _, ua = tenant_a
    _, ub = tenant_b
    ha, hb = login(client, ua.email), login(client, ub.email)
    lead = _lead(client, ha)
    r = client.post("/api/v1/enrichment/requests",
                    json={"lead_ids": [lead["id"]], "service": "enrichment"}, headers=hb)
    assert r.status_code == 404
