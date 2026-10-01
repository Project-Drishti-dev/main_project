import os
import pathlib

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000

LOCAL_CORS_ORIGINS = (
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5501",
    "http://127.0.0.1:5501",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

#: The backend package directory, resolved rather than spelled relative to the
#: current working directory, so the default database below is the same file
#: whichever directory the process was started from.
BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]

#: The SQLite file used when ``DATABASE_URL`` is unset. A file, not
#: ``:memory:``, because the schema is migrated by alembic in one process and
#: read by the service in another (8.8), and an in-memory database is not
#: shared between them.
DEFAULT_DATABASE_FILENAME = "drishti.db"
DEFAULT_DATABASE_PATH = BACKEND_DIR / DEFAULT_DATABASE_FILENAME

#: ``sqlite:///`` plus the absolute path, in posix form, so the URL is the
#: same shape on every platform: four slashes on a POSIX path, and a drive
#: letter on a Windows one.
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"

#: The URL schemes the service can be configured with.  Two, and they are the
#: two backends the project ships (ROADMAP D3): SQLite for the zero-setup demo
#: and PostgreSQL for a deployment, which is a ``DATABASE_URL`` change.  A third
#: scheme is refused while the configuration is being read rather than at the
#: first connection, where SQLAlchemy's own failure is a driver lookup that
#: names nothing about the variable that asked for it.
SUPPORTED_DATABASE_SCHEMES = ("postgresql", "sqlite")

#: The variable holding the ledger's Ed25519 private key (9.13).  Named here
#: because this module is the only reader of the environment, and the name is
#: spelled once: :mod:`app.ledger.signing` imports it to name the variable in
#: its refusals rather than holding a second copy of the string.
LEDGER_SIGNING_KEY_ENV_VAR = "LEDGER_SIGNING_KEY"


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS")
    if configured_origins is None:
        return list(LOCAL_CORS_ORIGINS)

    origins = list(
        dict.fromkeys(
            origin.strip().rstrip("/")
            for origin in configured_origins.split(",")
            if origin.strip()
        )
    )
    if "*" in origins:
        raise ValueError("CORS_ORIGINS must list exact origins; '*' is not allowed.")
    return origins


def get_ledger_signing_key() -> str | None:
    """``LEDGER_SIGNING_KEY`` as written, or ``None`` when none is set.

    :returns: the configured PEM exactly as the operator wrote it, or
        ``None`` when the variable is unset *or* blank -- a blank value is
        what ``.env.example`` ships, and the zero-setup demo must start
        without it.  Nothing is trimmed, decoded or parsed here: the
        spelling belongs to :func:`app.ledger.signing.load_signing_key`, and
        so does every refusal of a malformed one, so a bad key is refused by
        the module that knows what a key is.
    """
    configured = os.getenv(LEDGER_SIGNING_KEY_ENV_VAR)
    if configured is None or not configured.strip():
        return None
    return configured


def get_database_url() -> str:
    """The SQLAlchemy URL the service is configured to use.

    :returns: ``DATABASE_URL`` when it is set to a non-blank, acceptable URL,
        and :data:`DEFAULT_DATABASE_URL` -- a local SQLite file inside the
        backend directory -- otherwise.  The configured string is returned as
        written, not re-serialised out of a parsed URL.
    :raises ValueError: when ``DATABASE_URL`` is set to something that is not a
        URL, names a backend this service does not ship, or is a PostgreSQL URL
        that names no database.

    **Accepting a URL is not connecting to it.**  The gate is
    :func:`~sqlalchemy.engine.make_url`, which parses a string and returns
    nothing else -- no DBAPI is imported, no socket is opened, no host is
    resolved.  So a ``postgresql://`` URL is answered here in an environment
    where ``psycopg`` is not installed; it is
    :func:`~app.storage.db.build_engine`, not this answer, that needs the
    driver.  Measured in this environment: ``create_engine`` on a PostgreSQL
    URL raises ``ModuleNotFoundError: No module named 'psycopg'``, having
    parsed the URL and dialled nothing.
    """
    configured_url = os.getenv("DATABASE_URL")
    if configured_url is None or not configured_url.strip():
        return DEFAULT_DATABASE_URL
    return _validated_database_url(configured_url.strip())


def _validated_database_url(url: str) -> str:
    """``url``, unchanged, when the service can be configured with it.

    :param url: a non-blank SQLAlchemy URL.
    :returns: the string it was handed.  A parsed URL is not returned, because
        re-serialising one is a second spelling of it -- the answer
        :func:`get_database_url` promises is the one the operator configured.
    :raises ValueError: when ``url`` is not a URL at all, when its scheme is
        not in :data:`SUPPORTED_DATABASE_SCHEMES`, or when it is a PostgreSQL
        URL naming no database.  Every message names the variable and none of
        them echoes the value: a configured database URL carries a password,
        and this refusal can reach a log.
    """
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError) as error:
        # SQLAlchemy raises ArgumentError for a string it cannot read as a
        # URL at all, and a bare ValueError when a component it has read is
        # itself malformed -- a port of "not-a-port" is the second.
        raise ValueError(
            "DATABASE_URL must be a SQLAlchemy URL naming one of "
            f"{', '.join(SUPPORTED_DATABASE_SCHEMES)}, such as "
            "'sqlite:///drishti.db' or 'postgresql://user@host/drishti'."
        ) from error

    scheme = parsed.drivername.split("+", 1)[0]
    if scheme not in SUPPORTED_DATABASE_SCHEMES:
        raise ValueError(
            "DATABASE_URL must name one of "
            f"{', '.join(SUPPORTED_DATABASE_SCHEMES)}; {scheme!r} is not one."
        )
    if scheme == "postgresql" and not parsed.database:
        raise ValueError(
            "A PostgreSQL DATABASE_URL must name the database it is for, as in "
            "'postgresql://user@host/drishti'."
        )
    return url
