from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# URL database SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./tasks.db"

# Engine (connessione DB)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # necessario per SQLite
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# Base class (SQLAlchemy 2.0 style)
class Base(DeclarativeBase):
    pass


# 🔥 Dependency Injection (QUI la spostiamo)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
