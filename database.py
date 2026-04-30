import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)


def _build_engine(url: str):
    if url.startswith("sqlite"):
        logger.info("DB: SQLite — %s", url)
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
        )

    if url.startswith(("postgresql", "postgres")):
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
            logger.warning("DATABASE_URL corretta da postgres:// a postgresql://")

        logger.info("DB: PostgreSQL")
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
        )

    raise ValueError(f"DATABASE_URL non supportata: {url!r}")


# Importa settings QUI — pydantic-settings legge il .env correttamente
from config.settings import settings  # noqa: E402

DATABASE_URL = settings.DATABASE_URL
engine = _build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
