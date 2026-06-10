"""Autenticação: JWT para usuários do painel, API key para integrações/BI."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(sub: str, tenant_id: int) -> str:
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


# ---------- API keys (formato: ifl_<token>) ----------

def generate_api_key() -> tuple[str, str]:
    """Retorna (chave_em_claro, hash). Só o hash vai pro banco."""
    raw = "ifl_" + secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------- Dependencies ----------

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.models.tenant import User

    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise cred_exc
    return user


def get_tenant_from_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    """Autentica integrações externas (BI, track.js server-side, etc.)."""
    from app.models.tenant import ApiKey

    key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == hash_api_key(x_api_key), ApiKey.is_active.is_(True))
        .first()
    )
    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida")
    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return key.tenant
