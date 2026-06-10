"""Cria tenant demo + usuário admin + créditos. Rodar: python seed.py"""
import secrets

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import Tenant, User

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if not db.query(Tenant).filter(Tenant.slug == "empresa-exemplo").first():
    t = Tenant(
        name="Empresa Exemplo Ltda",
        slug="empresa-exemplo",
        plan="volume",
        tracking_token=secrets.token_urlsafe(24),
        credits_enrichment=25000,
        credits_reactivation=3000,
    )
    db.add(t)
    db.flush()
    db.add(User(
        tenant_id=t.id,
        name="Ricardo Costa",
        email="ricardo.costa@empresa.com.br",
        password_hash=hash_password("demo123"),
        role="admin",
    ))
    db.commit()
    print(f"Tenant criado — tracking_token: {t.tracking_token}")
    print("Login: ricardo.costa@empresa.com.br / demo123")
else:
    print("Tenant demo já existe")
db.close()
