"""Configuração central — lê variáveis de ambiente (Railway injeta DATABASE_URL)."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "InForge Leads API"
    ENV: str = "dev"  # dev | prod

    # Railway injeta DATABASE_URL automaticamente ao provisionar o Postgres
    DATABASE_URL: str = "sqlite:///./inforge_dev.db"

    # JWT para usuários do painel
    SECRET_KEY: str = "troque-em-producao"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Meta Lead Ads
    META_VERIFY_TOKEN: str = "inforge-meta-verify"
    META_APP_SECRET: str = ""
    META_PAGE_ACCESS_TOKEN: str = ""

    # Provedores de enriquecimento (plugáveis)
    ENRICHMENT_PROVIDER: str = "mock"  # mock | speedio | econodata
    SPEEDIO_API_KEY: str = ""
    ECONODATA_API_KEY: str = ""

    # CORS — domínios que podem chamar a API / enviar eventos do track.js
    CORS_ORIGINS: str = "*"

    class Config:
        env_file = ".env"


settings = Settings()
