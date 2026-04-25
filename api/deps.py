from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models.user import User as UserModel
from auth.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserModel:
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Token non valido o scaduto")

    username: str = payload.get("sub")

    if username is None:
        raise HTTPException(status_code=401, detail="Token non valido")

    user = db.query(UserModel).filter(UserModel.username == username).first()

    if user is None:
        raise HTTPException(status_code=401, detail="Utente non trovato")

    return user
