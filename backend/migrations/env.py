from logging.config import fileConfig
import os
import sys
import re
from pathlib import Path

# Add the backend directory to sys.path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import engine_from_config, pool, MetaData
from alembic import context

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / "app" / ".env"
load_dotenv(dotenv_path=env_path)

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from environment (same as app.database)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    # Remove any quotes or whitespace
    DATABASE_URL = DATABASE_URL.strip().strip("'").strip('"')
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    # Ensure sslmode=require for external PostgreSQL
    _is_local = bool(re.search(r'(localhost|127\.0\.0\.1|::1)', DATABASE_URL))
    if not _is_local:
        if re.search(r'sslmode=', DATABASE_URL):
            DATABASE_URL = re.sub(r'sslmode=[\w-]+', 'sslmode=require', DATABASE_URL)
        else:
            separator = "&" if "?" in DATABASE_URL else "?"
            DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

# Override sqlalchemy.url with environment variable
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Import models for autogenerate support
# We need to import all models so their metadata is registered
target_metadata = None

# For autogenerate, we need to import the SQLAlchemy declarative base
# Since this project uses raw psycopg2, we'll create a minimal metadata
# for autogenerate to work with the existing tables
target_metadata = MetaData()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set. Cannot run migrations offline.")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set. Cannot run migrations.")
    
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Reflect existing tables for autogenerate
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()