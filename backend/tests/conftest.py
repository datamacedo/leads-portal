"""Fixtures: banco isolado por teste + 2 tenants para provar isolamento."""
import os
import secrets
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tenant, User  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # mesma conexão em memória para toda a sessão de teste
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_tenant(db, slug: str, credits: int = 100) -> tuple[Tenant, User]:
    t = Tenant(
        name=f"Empresa {slug}", slug=slug,
        tracking_token=secrets.token_urlsafe(16),
        credits_enrichment=credits, credits_reactivation=credits,
    )
    db.add(t)
    db.flush()
    u = User(
        tenant_id=t.id, name=f"Admin {slug}",
        email=f"admin@{slug}.com",
        password_hash=hash_password("senha123"), role="admin",
    )
    db.add(u)
    db.commit()
    return t, u


@pytest.fixture()
def tenant_a(db):
    return make_tenant(db, "alpha")


@pytest.fixture()
def tenant_b(db):
    return make_tenant(db, "beta")


def login(client, email: str) -> dict:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": "senha123"})
    assert r.status_code == 200, r.text
    return {"Authorizatio