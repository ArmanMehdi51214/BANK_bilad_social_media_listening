from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, engine_from_config, pool
from alembic import context

from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def run_migrations_offline() -> None:
    database_url = get_database_url() or config.get_main_option("sqlalchemy.url")

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url = get_database_url()

    if database_url:
        safe_host = database_url.split("@")[-1] if "@" in database_url else database_url[:30]
        print(f"ALEMBIC_USING_ENV_DATABASE_URL=True host={safe_host}")
        connectable = create_engine(database_url, poolclass=pool.NullPool)
    else:
        print("ALEMBIC_USING_ENV_DATABASE_URL=False using alembic.ini")
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
