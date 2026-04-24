import uuid
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from jwt import ExpiredSignatureError, InvalidTokenError

from config.settings import settings

# FIX: whitelist algoritmi hardcoded nel codice, mai da configurazione esterna.
# Previene algorithm confusion attack (algo=none, RS256→HS256, ecc.)
_ALLOWED_ALGORITHMS = ["HS256"]

# FIX: hash dummy usato per prevenire user enumeration via timing attack.
# verify_password viene eseguito sempre, anche quando l'utente non esiste.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-never-used", bcrypt.gensalt()).decode("utf-8")


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    # FIX: aggiunge jti (JWT ID) univoco — necessario per revoca token (blacklist/logout)
    to_encode.update(
        {
            "exp": expire,
            "jti": str(uuid.uuid4()),
        }
    )
    # FIX: usa _ALLOWED_ALGORITHMS[0] — algoritmo hardcoded, non da settings
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=_ALLOWED_ALGORITHMS[0])


def decode_token(token: str) -> dict | None:
    try:
        # FIX: algorithms= usa la whitelist hardcoded, non settings.ALGORITHM
        # Anche se settings.ALGORITHM fosse compromesso, questo non cambia
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=_ALLOWED_ALGORITHMS,
        )
    except (ExpiredSignatureError, InvalidTokenError):
        return None


def get_dummy_hash() -> str:
    """Restituisce l'hash dummy per prevenire timing attack nel login."""
    return _DUMMY_HASH
