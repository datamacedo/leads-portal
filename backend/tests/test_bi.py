from tests.conftest import login


def _apikey(client, h, name="Power BI"):
    r = client.post("/api/v1/api-keys", json={"name": name}, headers=h)
    assert r.status_code == 201
    return r.json()["key"]


def test_api_key_acessa_so_o_proprio_tenant(client, tenant_a, tenant_b):
    _, ua = tenant_a
    _, ub = tenant_b
    ha, hb = login(client, ua.email), login(client, ub.email)
    client.post("/api/v1/leads", json={"name": "A", "email": "a@a.com"}, headers=ha)
    key_b = _apikey(client, hb)
    r = client.get("/api/v1/bi/leads", headers={"X-API-Key": key_b})
    assert r.status_code == 200
    assert r.json()["total"] == 0  # B não vê o lead de A


def test_api_key_invalida(client, tenant_a):
    assert client.get("/api/v1/bi/leads", headers={"X-API-Key": "ifl_falsa"}).status_code == 401


def test_api_key_revogada_para_de_funcionar(client, tenant_a):
    _, user = tenant_a
    h = login(client, user.email)
    key = _apikey(client, h)
    assert client.get("/api/v1/bi/metrics", headers={"X-API-Key": key}).status_code == 200
    key_id = client.get("/api/v1/api-keys", headers=h).json()[0]["id"]
    client.delete(f"/api/v1/api-keys/{key_id}", headers=h)
    assert client.get("/api/v1/bi/metrics", headers={"X-API-Key": key}).status_code == 401


def test_metrics_e_csv(client, tenant_a):
    _, user = tenant_a
    h = login(client, user.email)
    client.post("/api/v1/leads", json={"name": "M", "email": "m@m.com", "source": "meta_ads"}, headers=h)
    key = _apikey(client, h)
    m = client.get("/api/v1/bi/metrics", headers={"X-API-Key": key}).json()
    assert m["total_leads"] == 1 and m["by_source"] == {"meta_ads": 1}
    csv = client.get("/api/v1/bi/leads.csv", headers={"X-API-Key": key})
    assert csv.status_code == 200 and "m@m.com" in csv.text
