"""The one read of the trail: the event 11.1's answer names.

Writing is :func:`app.audit.emit.emit` and nothing else; this is where a
caller asks the trail a question.  It holds no vocabulary of its own -- the
name it filters on is imported from :mod:`app.audit.event_types` -- and it
adds nothing to a session.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.audit.event_types import ANALYSIS_COMPLETED
from app.storage.models import AuditEvent

__all__ = ["completed_event_id"]


def completed_event_id(
    screening_id: uuid.UUID, *, sessions: sessionmaker[Session]
) -> uuid.UUID | None:
    """The id of the one ``analysis_completed`` event for this screening.

    :param screening_id: the screening whose trail is being read.  A
        :class:`uuid.UUID`, not coerced from a string.
    :param sessions: the factory the row is read through, required and never
        the module-level one (``D62``'s reasoning).
    :returns: the event's id, or ``None`` when no such event exists -- a
        cascade that raised leaves none, and that is an answer rather than a
        fault, on ``ScreeningRepository.get``'s reasoning.
    """
    with sessions() as session:
        return session.execute(
            select(AuditEvent.id).where(
                AuditEvent.screening_id == screening_id,
                AuditEvent.event_type == ANALYSIS_COMPLETED,
            )
        ).scalar_one_or_none()
