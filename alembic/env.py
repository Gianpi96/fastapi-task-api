from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

from config.settings import settings
from database import Base
from models.user import User  # noqa: F401
from models.tasks import Task  # noqa: F401

config = context.config

# Sovrascrive sqlalchemy.url con il valore reale dal .env
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Usa create_engine direttamente invece di engine_from_config
    # per evitare il KeyError 'url' quando sqlalchemy.url non è nel .ini
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
