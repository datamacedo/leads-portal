from tests.conftest import login


def test_login_ok(client, tenant_a):
    _, user = tenant_a
    h = login(client, user.email)
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 200
    assert r.json()["email"] == user.email


def test_login_senha_errada(client, tenant_a):
    r = client.post("/api/v1/auth/login",
                    data={"username": "admin@alpha.com", "password": "errada"})
    assert r.status_code == 401


def test_rota_protegida_sem_token(client, tenant_a):
    assert client.get("/api/v1/leads").status_code == 401


def test_token_invalido(client, tenant_a):
    r = client.get("/api/v1/leads", headers={"Authorization": "Bearer lixo"})
    assert r.status_code == 401
