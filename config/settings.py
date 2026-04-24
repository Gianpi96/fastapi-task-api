from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    SECRET_KEY: str
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENV: str = "production"

    # FIX: ALGORITHM hardcoded come Literal — non configurabile da .env
    # Impedisce algorithm confusion attack (es. "none" o RS256→HS256)
    ALGORITHM: Literal["HS256"] = "HS256"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        # FIX: validazione entropia minima — impedisce chiavi deboli come "super-secret-key"
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY deve essere almeno 32 caratteri. "
                'Generala con: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return v


settings = Settings()
