from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    SECRET_KEY: str
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENV: str = "production"
    ALGORITHM: Literal["HS256"] = "HS256"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY deve essere almeno 32 caratteri. "
                'Generala con: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        allowed = ("sqlite", "postgresql", "postgres")
        if not any(v.startswith(prefix) for prefix in allowed):
            raise ValueError(
                f"DATABASE_URL non valida: '{v}'. "
                "Deve iniziare con sqlite:// o postgresql://"
            )
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith(("postgresql", "postgres"))


settings = Settings()
