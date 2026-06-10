from tests.conftest import login


def _create(client, h, **kw):
    body = {"name": "Carlos", "email": "carlos@x.com", "source": "manual"} | kw
    r = client.post("/api/v1/leads", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def test_criar_e_listar(client, tenant_a):
    _, user = tenant_a
    h = login(client, user.email)
    lead = _create(client, h)
    assert lead["score"] > 0
    assert lead["propensity"] in ("alta", "media", "baixa")
    r = client.get("/api/v1/leads", headers=h)
    assert r.json()["total"] == 1


def test_deduplicacao_por_email(client, tenant_a):
    """Mesmo email = atualiza, não duplica."""
    _, user = tenant_a
    h = login(client, user.email)
    a = _create(client, h, email="dup@x.com", phone=None)
    b = _create(client, h, email="dup@x.com", phone="+5511999998888", name=None)
    assert a["id"] == b["id"]
    assert b["phone"] == "+5511999998888"  # merge preencheu o que faltava
    assert client.get("/api/v1/leads", headers=h).json()["total"] == 1


def test_isolamento_entre_tenants(client, tenant_a, tenant_b):
    """CRÍTICO: tenant B nunca vê leads do tenant A."""
    _, ua = tenant_a
    _, ub = tenant_b
    ha, hb = login(client, ua.email), login(client, ub.email)
    lead = _create(client, ha)
    # B não lista
    assert client.get("/api/v1/leads", headers=hb).json()["total"] == 0
    # B não acessa direto
    assert client.get(f"/api/v1/leads/{lead['id']}", headers=hb).status_code == 404
    # B não edita
    assert client.patch(f"/api/v1/leads/{lead['id']}",
                        json={"status": "won"}, headers=hb).status_code == 404


def test_filtros_e_paginacao(client, tenant_a):
    _, user = tenant_a
    h = login(client, user.email)
    for i in range(5):
        _create(client, h, email=f"l{i}@x.com")
    r = client.get("/api/v1/leads?per_page=2&page=2", headers=h)
    body = r.json()
    assert body["total"] == 5 and len(body["items"]) == 2
    r = client.get("/api/v1/leads?search=l3", headers=h)
    assert r.json()["total"] == 1
