from tests.conftest import login


def _event(client, token, vid="v1", sess="s1", type="pageview", **data):
    return client.post("/api/v1/track/event", json={
        "token": token, "visitor_id": vid, "session_key": sess,
        "type": type, "url": "https://cliente.com/planos",
        "data": data or None,
        "device": {"type": "desktop", "os": "Windows 10/11", "browser": "Chrome", "screen": "1920x1080"},
    })


def test_evento_token_invalido(client, tenant_a):
    r = _event(client, "token-falso")
    assert r.status_code == 401


def test_eventos_e_sessao(client, tenant_a):
    t, _ = tenant_a
    assert _event(client, t.tracking_token, time_on_page=60).status_code == 202
    assert _event(client, t.tracking_token, type="click", text="Comprar").status_code == 202
    assert _event(client, t.tracking_token, type="scroll", depth_pct=75).status_code == 202


def test_identity_stitching(client, tenant_a):
    """Anônimo navega → identifica → histórico inteiro vinculado ao lead."""
    t, user = tenant_a
    # 2 sessões anônimas
    _event(client, t.tracking_token, sess="s1", time_on_page=120)
    _event(client, t.tracking_token, sess="s2", time_on_page=300)
    # identifica
    r = client.post("/api/v1/track/identify", json={
        "token": t.tracking_token, "visitor_id": "v1",
        "email": "ana@empresa.com", "name": "Ana",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["sessions_linked"] == 2
    assert body["score"] > 30  # comportamento elevou o score

    # jornada completa na ficha
    h = login(client, user.email)
    j = client.get(f"/api/v1/leads/{body['lead_id']}/journey", headers=h).json()
    assert len(j["sessions"]) == 2
    assert j["sessions"][0]["device"]["type"] == "desktop"
    assert j["first_seen_at"] is not None


def test_identify_sem_contato(client, tenant_a):
    t, _ = tenant_a
    r = client.post("/api/v1/track/identify", json={
        "token": t.tracking_token, "visitor_id": "v1", "name": "Sem Contato",
    })
    assert r.status_code == 422


def test_identify_deduplica_com_lead_existente(client, tenant_a):
    """Lead criado manualmente + identify com mesmo email = mesmo registro."""
    t, user = tenant_a
    h = login(client, user.email)
    created = client.post("/api/v1/leads", json={"email": "x@y.com", "name": "X"}, headers=h).json()
    _event(client, t.tracking_token)
    r = client.post("/api/v1/track/identify", json={
        "token": t.tracking_token, "visitor_id": "v1", "email": "x@y.com",
    })
    assert r.json()["lead_id"] == created["id"]
