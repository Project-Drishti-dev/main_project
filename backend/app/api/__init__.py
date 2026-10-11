"""The HTTP surface as a package of routers, and the seams they share.

``app.main`` holds the app and the error envelope; this package holds the
routers, one per resource, and the session-factory dependency every route that
writes reaches through -- so a test points the service at a temporary
database by overriding one name rather than by patching a module global.
18.7's log is reached through that same factory, so one override points both.
19.6's evidence store is the second such seam: one override points the whole
service at a temporary directory and a temporary key.
"""

import functools

from fastapi import Depends

from sqlalchemy.orm import Session, sessionmaker

from app.config import (
    get_app_env,
    get_evidence_encryption_key,
    get_evidence_store_root,
)
from app.ledger.store import Ledger, SqliteLedger
from app.storage.blob_store import EvidenceStore
from app.storage.db import SessionLocal
from app.storage.master_key import MasterKeyError, load_master_key

__all__ = ["get_evidence_store", "get_ledger", "get_sessions"]


def get_sessions() -> sessionmaker[Session]:
    """The session factory the routes write through.

    :returns: :data:`app.storage.db.SessionLocal` -- bound to whatever
        ``DATABASE_URL`` said when that module was first imported, which is
        why this is an overridable dependency and not a module-level
        reference each route closes over.
    """
    return SessionLocal

def get_ledger(
    sessions: sessionmaker[Session] = Depends(get_sessions),
) -> Ledger:
    """The log an anchored root is read back from.

    :param sessions: the factory :func:`get_sessions` answered with, so one
        override points the rows and the log at the same database.
    :returns: a :class:`~app.ledger.store.SqliteLedger` over it -- a log owns
        no session of its own, on :class:`~app.ledger.store.Ledger`'s
        reasoning.
    """
    return SqliteLedger(sessions)


@functools.lru_cache(maxsize=1)
def get_evidence_store() -> EvidenceStore:
    """The one store this process writes evidence into, under one master key.

    Cached rather than built per request, so a blob this process wrote is a
    blob the next request in it can read: D154 draws a development key per
    call, so a store built each time would write every upload under a key
    that exists for that one request and no other.  A configured key makes
    the cache invisible -- both answers are the same bytes either way.

    :returns: an :class:`~app.storage.blob_store.EvidenceStore` over
        :func:`app.config.get_evidence_store_root`, under the key
        :func:`app.storage.master_key.load_master_key` answers for the
        configured secret and the mode.
    :raises MasterKeyError: when the mode names neither published name, or
        when production has no key configured.  The refusal lands on the
        first request that needs a store rather than at start-up, which is
        where D154 left it.
    """
    return EvidenceStore(
        get_evidence_store_root(),
        load_master_key(get_evidence_encryption_key(), get_app_env()),
    )
