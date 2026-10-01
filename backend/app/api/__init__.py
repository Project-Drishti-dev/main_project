"""The HTTP surface as a package of routers, and the seams they share.

``app.main`` holds the app and the error envelope; this package holds the
routers, one per resource, and the session-factory dependency every route that
writes reaches through -- so a test points the service at a temporary
database by overriding one name rather than by patching a module global.
"""

from sqlalchemy.orm import Session, sessionmaker

from app.storage.db import SessionLocal

__all__ = ["get_sessions"]


def get_sessions() -> sessionmaker[Session]:
    """The session factory the routes write through.

    :returns: :data:`app.storage.db.SessionLocal` -- bound to whatever
        ``DATABASE_URL`` said when that module was first imported, which is
        why this is an overridable dependency and not a module-level
        reference each route closes over.
    """
    return SessionLocal
