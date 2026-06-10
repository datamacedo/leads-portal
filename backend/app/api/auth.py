from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, verify_password
from app.models.tenant import User
from app.schemas.schemas import Token, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "E-mail ou senha incorretos")
    return Token(access_token=create_access_token(user.email, user.tenant_id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
