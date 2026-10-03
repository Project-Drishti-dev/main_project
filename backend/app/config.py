import os
import pathlib
from urllib.parse import urlsplit

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

#: The variable holding the level the service logs at (11.6).  Named here for
#: the same reason as :data:`LEDGER_SIGNING_KEY_ENV_VAR`: this module is the
#: only reader of the environment, so the name is spelled once and
#: :mod:`app.logging_config` imports the reader rather than ``os.getenv``.
LOG_LEVEL_ENV_VAR = "LOG_LEVEL"

#: The level used when the variable is unset or blank.  ``INFO``, so a
#: deployment logs one line per request -- which is 11.6's point -- without
#: the module-level detail the request line already summarises.
DEFAULT_LOG_LEVEL = "INFO"

#: The levels a level name may be, the same set :mod:`logging` defines.  An
#: unknown name is refused while the configuration is read rather than
#: becoming a silent no-op: :func:`logging.Logger.setLevel` answers an
#: unrecognised string by doing nothing at all, so a typo would leave the
#: level at whatever it was while looking as though it had been applied.
LOG_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")
#: The variable holding the ledger's Ed25519 private key (9.13).  Named here
#: because this module is the only reader of the environment, and the name is
#: spelled once: :mod:`app.ledger.signing` imports it to name the variable in
#: its refusals rather than holding a second copy of the string.
LEDGER_SIGNING_KEY_ENV_VAR = "LEDGER_SIGNING_KEY"

#: The variable naming the mode this service is running in (19.1).  Named
#: here for the same reason as :data:`LEDGER_SIGNING_KEY_ENV_VAR`: this
#: module is the only reader of the environment, so the name is spelled once
#: and :mod:`app.storage.master_key` imports the two mode names rather than
#: holding a second copy of either.
APP_ENV_ENV_VAR = "APP_ENV"

#: The two mode names, and the only two :func:`get_app_env` answers.  A mode
#: rather than a flag, because 19.1 has exactly two answers to give and a
#: third setting would only ever be a spelling of one of them.
ENV_DEVELOPMENT = "development"
ENV_PRODUCTION = "production"
ENVIRONMENTS = (ENV_DEVELOPMENT, ENV_PRODUCTION)

#: The mode used when the variable is unset or blank.  ``development``,
#: because the zero-setup demo must start with nothing configured, on
#: :func:`get_ledger_signing_key`'s reasoning.  An operator who wants a
#: missing key refused rather than generated sets the variable.
DEFAULT_APP_ENV = ENV_DEVELOPMENT

#: The variable holding the AES-256 master key every evidence blob is
#: wrapped under (19.1).  Named for the same reason as the two above: the
#: name is spelled once, and :mod:`app.storage.master_key` reads what this
#: module answers rather than the variable itself.
EVIDENCE_ENCRYPTION_KEY_ENV_VAR = "EVIDENCE_ENCRYPTION_KEY"

#: The variable holding how many analysis requests one address may make per
#: minute (11.8).  Named here for the same reason as
#: :data:`LOG_LEVEL_ENV_VAR`: this module is the only reader of the
#: environment, so the name is spelled once and
#: :mod:`app.api.rate_limit` imports the answer rather than reading the
#: variable itself.
RATE_LIMIT_ENV_VAR = "RATE_LIMIT_PER_MINUTE"

#: The limit used when the variable is unset or blank.  Sixty a minute is
#: about one request a second: more than an officer working one document at a
#: time reaches, and few enough that an open endpoint cannot be run flat by
#: one address.  It is a per-process count, so a deployment behind a proxy
#: sees one bucket for every address the proxy forwards for.
DEFAULT_RATE_LIMIT_PER_MINUTE = 60

#: The variable holding the address of the local Ollama / llama.cpp HTTP API
#: (17.7).  Named for the same reason as :data:`RATE_LIMIT_ENV_VAR`: this
#: module is the only reader of the environment, so the name is spelled once
#: and :mod:`app.explain.summarizer` imports the answer rather than reading
#: the variable itself.
LOCAL_LLM_BASE_URL_ENV_VAR = "LOCAL_LLM_BASE_URL"

#: The address used when the variable is unset or blank.  Loopback, because
#: 17.7 ships no external fallback: a default naming a public API would be a
#: host the operator never configured and flag data could reach anyway.
DEFAULT_LOCAL_LLM_BASE_URL = "http://127.0.0.1:11434"

#: The URL schemes a local server may be addressed with.  Two, and both are
#: served by Ollama and by llama.cpp's server alike; a third would be a
#: scheme neither of them answers.
SUPPORTED_LOCAL_LLM_SCHEMES = ("http", "https")

#: The variable naming the model to ask the local server for (17.7).  Blank
#: is what ``.env.example`` ships, and it is not a refusal: no model named is
#: no model asked, and the client answers ``None`` to everything.
LOCAL_LLM_MODEL_ENV_VAR = "LOCAL_LLM_MODEL"

#: The variable holding how many seconds the summariser may spend on one
#: request (17.7), named for the same reason as the two above.
LOCAL_LLM_TIMEOUT_ENV_VAR = "LOCAL_LLM_TIMEOUT_SECONDS"

#: The budget used when the variable is unset or blank.  Thirty seconds is
#: what a local model on CPU takes to narrate a document; past it the officer
#: is better served by the template summary than by a slower answer.
DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS = 30

#: The variable holding the master switch for the summariser (17.8), named
#: for the same reason as the three above.
LOCAL_LLM_ENABLED_ENV_VAR = "LOCAL_LLM_ENABLED"

#: The answer when the variable is unset or blank.  ``False``, which is the
#: safe one: 17.5's template summary is a complete answer, so a switch nobody
#: has turned on must leave the client uncalled.
DEFAULT_LOCAL_LLM_ENABLED = False

#: The spellings that mean the switch is on.  Everything else is off --
#: unset, blank, ``false``, and a spelling that is not one -- because both
#: answers this switch can give are ordinary operating states, and only one of
#: them is safe to reach for when the value is not understood.
LOCAL_LLM_ENABLED_ON_VALUES = ("1", "on", "true", "yes")


def get_log_level() -> str:
    """The level name the service logs at.

    :returns: ``LOG_LEVEL`` upper-cased when it is set to a known level name,
        and :data:`DEFAULT_LOG_LEVEL` when the variable is unset or blank --
        a blank value is what ``.env.example`` ships.
    :raises ValueError: when the variable is set to something that is not a
        level name.  The message names the variable and lists the levels, and
        echoes no part of the value.
    """
    configured = os.getenv(LOG_LEVEL_ENV_VAR)
    if configured is None or not configured.strip():
        return DEFAULT_LOG_LEVEL

    level = configured.strip().upper()
    if level not in LOG_LEVELS:
        raise ValueError(
            f"{LOG_LEVEL_ENV_VAR} must be one of {', '.join(LOG_LEVELS)}; "
            f"{configured!r} is not one."
        )
    return level


def get_rate_limit_per_minute() -> int:
    """How many analysis requests one address may make in a minute.

    :returns: ``RATE_LIMIT_PER_MINUTE`` when it is set to a whole number of
        requests, and :data:`DEFAULT_RATE_LIMIT_PER_MINUTE` when the variable
        is unset or blank -- a blank value is what ``.env.example`` ships.
    :raises ValueError: when the variable is set to something that is not a
        count of requests.  ``0`` and a negative number are refused along
        with the rest: a limit of zero would answer every request with a
        refusal, and reading it as "no limit" would turn a typo into an
        endpoint with none.  The message names the variable.
    """
    configured = os.getenv(RATE_LIMIT_ENV_VAR)
    if configured is None or not configured.strip():
        return DEFAULT_RATE_LIMIT_PER_MINUTE

    try:
        limit = int(configured.strip())
    except ValueError:
        raise ValueError(
            f"{RATE_LIMIT_ENV_VAR} must be a whole number of requests per "
            f"minute; {configured!r} is not one."
        ) from None
    if limit < 1:
        raise ValueError(
            f"{RATE_LIMIT_ENV_VAR} must be at least 1; {configured!r} is not."
        )
    return limit


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


def get_app_env() -> str:
    """The mode this process is running in.

    :returns: ``APP_ENV`` folded to lower case when it is set to one of
        :data:`ENVIRONMENTS`, and :data:`DEFAULT_APP_ENV` when the variable
        is unset or blank -- which is what ``.env.example`` ships.
    :raises ValueError: when the variable is set to a name this service does
        not publish.  The message names the variable and lists the two
        names, and this is deliberately not
        :func:`get_local_llm_enabled`'s "off is safe": this is the one
        variable that decides whether 19.1 generates a master key or
        refuses, so an unrecognised spelling stops
        the start-up rather than choosing on the operator`'s behalf.
    """
    configured = os.getenv(APP_ENV_ENV_VAR)
    if configured is None or not configured.strip():
        return DEFAULT_APP_ENV

    environment = configured.strip().lower()
    if environment not in ENVIRONMENTS:
        raise ValueError(
            f"{APP_ENV_ENV_VAR} must be one of {', '.join(ENVIRONMENTS)}; "
            f"{configured!r} is not one."
        )
    return environment


def get_evidence_encryption_key() -> str | None:
    """``EVIDENCE_ENCRYPTION_KEY`` as written, or ``None`` when none is set.

    :returns: the configured base64 exactly as the operator wrote it, or
        ``None`` when the variable is unset *or* blank -- the value
        ``.env.example`` ships.  Nothing is trimmed, decoded or width-checked
        here: the spelling belongs to
        :func:`app.storage.master_key.load_master_key`, and so does every
        refusal of a malformed one, so a bad key is refused by the module
        that knows what a key is.
    """
    configured = os.getenv(EVIDENCE_ENCRYPTION_KEY_ENV_VAR)
    if configured is None or not configured.strip():
        return None
    return configured


def get_local_llm_base_url() -> str:
    """The address of the local model server, without a trailing slash.

    :returns: ``LOCAL_LLM_BASE_URL`` when it is set to an address a local
        server is reachable on, and :data:`DEFAULT_LOCAL_LLM_BASE_URL`
        otherwise.  A trailing slash is trimmed rather than refused: an
        address written with one names the same server.
    :raises ValueError: when the variable is set to something that is not an
        HTTP URL, names a scheme no local server speaks, or carries no host.
        The message names the variable and echoes none of the value.
    """
    configured = os.getenv(LOCAL_LLM_BASE_URL_ENV_VAR)
    if configured is None or not configured.strip():
        return DEFAULT_LOCAL_LLM_BASE_URL
    return _validated_local_llm_base_url(configured.strip())


def _validated_local_llm_base_url(url: str) -> str:
    """``url`` with no trailing slash, when it addresses a local HTTP server."""
    refusal = (
        f"{LOCAL_LLM_BASE_URL_ENV_VAR} must be an http or https URL naming a local "
        f"model server, such as {DEFAULT_LOCAL_LLM_BASE_URL!r}."
    )
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        # A port that is not a number and a malformed authority both raise
        # here, and neither is readable as the host an operator wrote.
        raise ValueError(refusal) from None
    if parts.scheme not in SUPPORTED_LOCAL_LLM_SCHEMES or not parts.hostname:
        raise ValueError(refusal)
    if port is not None and not 0 < port < 65_536:
        raise ValueError(
            f"{LOCAL_LLM_BASE_URL_ENV_VAR} must name a port between 1 and 65535."
        )
    return url.rstrip("/")


def get_local_llm_model() -> str | None:
    """The model to ask the local server for, or ``None`` when none is named.

    :returns: ``LOCAL_LLM_MODEL`` trimmed, or ``None`` when the variable is
        unset or blank -- the value ``.env.example`` ships.  Nothing here is
        a refusal: a model that is not configured is a client that answers
        ``None``, which is the shape 17.7 asks a failure to take anyway.
    """
    configured = os.getenv(LOCAL_LLM_MODEL_ENV_VAR)
    if configured is None or not configured.strip():
        return None
    return configured.strip()


def get_local_llm_timeout_seconds() -> int:
    """How many seconds the summariser may spend on one request.

    :returns: ``LOCAL_LLM_TIMEOUT_SECONDS`` when it is a whole number of
        seconds, and :data:`DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS` when the
        variable is unset or blank.
    :raises ValueError: when the variable is not a whole number of seconds, or
        names a budget of zero or less.  Zero is refused rather than read as
        "no budget", which would be a client that gives up before it dials.
    """
    configured = os.getenv(LOCAL_LLM_TIMEOUT_ENV_VAR)
    if configured is None or not configured.strip():
        return DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS

    try:
        seconds = int(configured.strip())
    except ValueError:
        raise ValueError(
            f"{LOCAL_LLM_TIMEOUT_ENV_VAR} must be a whole number of seconds; "
            f"{configured!r} is not one."
        ) from None
    if seconds < 1:
        raise ValueError(
            f"{LOCAL_LLM_TIMEOUT_ENV_VAR} must be at least 1 second; "
            f"{configured!r} is not."
        )
    return seconds


def get_local_llm_enabled() -> bool:
    """Whether the summariser may ask the local model anything at all (17.8).

    :returns: ``True`` when ``LOCAL_LLM_ENABLED`` is set to one of
        :data:`LOCAL_LLM_ENABLED_ON_VALUES` -- case and surrounding space
        folded, so a shell's ``True `` is the same answer -- and ``False`` in
        every other case, unset and blank included.  Nothing here is a
        refusal: both answers are ordinary, and the one a misspelling has to
        be read as is the safe one, the way a blank model name is.
    """
    configured = os.getenv(LOCAL_LLM_ENABLED_ENV_VAR)
    if configured is None:
        return DEFAULT_LOCAL_LLM_ENABLED
    return configured.strip().lower() in LOCAL_LLM_ENABLED_ON_VALUES


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

