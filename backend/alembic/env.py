"""Alembic environment: the one place a migration reads its URL and metadata.

:returns: nothing.  Applies or emits the migration scripts in
    ``alembic/versions`` against ``app.config.get_database_url()``.
:raises ValueError: when ``DATABASE_URL`` is not an acceptable URL, refusing
    it at the configuration rather than at the first connection.

The URL is asked of :mod:`app.config` and never written here or in
``alembic.ini``, so the migrated database and the served one cannot be
different databases.  The metadata is :data:`app.storage.models.Base`'s, so
``--autogenerate`` diffs against the models 8.4 to 8.7 wrote.
"""

from logging.config import fileConfig

from alembic import context

from app.config import get_database_url
from app.storage.db import build_engine
from app.storage.models import Base

config = context.config

# ``disable_existing_loggers`` is off so that configuring alembic's loggers
# from inside a process (a test, a deploy script) does not silence the loggers
# that process already had.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit the migrations as SQL, connecting to nothing.

    :returns: nothing; the script is written to alembic's output stream.
    """
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply the migrations to the configured database.

    :returns: nothing.
    :raises ValueError: when ``DATABASE_URL`` is not an acceptable URL.
    """
    connectable = build_engine(get_database_url())
    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
