from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import generate_api_key, get_current_user
from app.models.tenant import ApiKey, User
from app.schemas.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
def create_key(body: ApiKeyCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Apenas administradores criam API keys")
    raw, key_hash = generate_api_key()
    key = ApiKey(tenant_id=user.tenant_id, name=body.name, key_hash=key_hash, prefix=raw[:12])
    db.add(key)
    db.commit()
    db.refresh(key)
    out = ApiKeyCreated.model_validate({**key.__dict__, "key": raw})
    return out  # a chave em claro aparece SÓ aqui


@router.get("", response_model=list[ApiKeyOut])
def list_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(ApiKey).filter(ApiKey.tenant_id == user.tenant_id).all()


@router.delete("/{key_id}", status_code=204)
def revoke_key(key_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Apenas administradores revogam API keys")
    key = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.tenant_id == user.tenant_id).first()
    if not key:
        raise HTTPException(404, "Key não encontrada")
    key.is_active = False
    db.commit()
