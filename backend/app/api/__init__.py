"""The HTTP surface as a package of routers, and the seams they share.

``app.main`` holds the app and the error envelope; this package holds the
routers, one per resource, and the session-factory dependency every route that
writes reaches through -- so a test points the service at a temporary
database by overriding one name rather than by patching a module global.
18.7's log is reached through that same factory, so one override points both.
"""

from fastapi import Depends

from sqlalchemy.orm import Session, sessionmaker

from app.ledger.store import Ledger, SqliteLedger
from app.storage.db import SessionLocal

__all__ = ["get_ledger", "get_sessions"]


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
