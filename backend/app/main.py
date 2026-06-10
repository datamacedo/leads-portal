from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api import auth, leads, tracking, enrichment, apikeys, bi
from app.connectors import meta

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Plataforma de Inteligência de Base — captura, rastreamento, "
        "score e qualificação de leads. Multi-tenant.\n\n"
        "**Painel**: JWT via /api/v1/auth/login · **BI/Integrações**: header X-API-Key"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
app.include_router(auth.router, prefix=API)
app.include_router(leads.router, prefix=API)
app.include_router(tracking.router, prefix=API)
app.include_router(enrichment.router, prefix=API)
app.include_router(apikeys.router, prefix=API)
app.include_router(bi.router, prefix=API)
app.include_router(meta.router, prefix=API)


@app.get("/health", tags=["Infra"])
def health():
    return {"status": "ok", "env": settings.ENV}


@app.on_event("startup")
def startup():
    # Dev: cria tabelas direto. Produção: usar Alembic (alembic upgrade head).
    if settings.ENV == "dev":
        Base.metadata.create_all(bind=engine)
