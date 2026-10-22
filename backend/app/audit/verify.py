"""What one walk of the log found, said in the words an officer reads.

18.7's read: the three answers beside the root the walk reached and the length
of the path it walked, plus one plain sentence per check that completed, so a
reader can tell a clearance from an answer that stopped before it compared
anything.  The walk is :func:`app.ledger.verification.verification_of` and the
names of its steps are that module's constants, so neither the three answers
nor the steps behind them are spelled twice.  Rationale in
``docs/DECISIONS.md`` D149.
"""

import uuid
from dataclasses import dataclass
from types import MappingProxyType

from sqlalchemy.orm import Session, sessionmaker

from app.audit.trail import event_by_id
from app.ledger.store import Ledger
from app.ledger.verification import (
    CHECK_PROOF,
    CHECK_RECORD,
    CHECK_ROOT,
    UNKNOWN,
    Verification,
    verification_of,
)

__all__ = [
    "CHECK_SENTENCES",
    "AuditVerification",
    "ExplainError",
    "explain",
    "verify_audit_event",
]


#: One sentence per check 9.17 can complete, keyed by its own constant, so a
#: step is never retyped here and none is named twice.  Read-only, because the
#: table is the record.
CHECK_SENTENCES = MappingProxyType(
    {
        CHECK_ROOT: (
            "The root of the batch this record belongs to was read back from "
            "the log, which is never amended."
        ),
        CHECK_RECORD: (
            "The stored record was hashed again from its own row and compared "
            "with the digest stored beside it."
        ),
        CHECK_PROOF: (
            "The path from this record's own place in its batch was walked up "
            "to that root, and the two were compared."
        ),
    }
)


class ExplainError(ValueError):
    """Raised when a check 9.17 reports is one this table cannot name.

    A ``ValueError``, on :class:`~app.ledger.verification.VerifyError`'s
    reasoning: what is unusable is what the caller passed in, and a step added
    to the walk without a sentence here is a fault in this service rather
    than anything a row carried.
    """


@dataclass(frozen=True)
class AuditVerification:
    """One event's standing, and the proof of it an officer can read.

    ``batch_root`` is the log's own spelling of the entry's root (D57) and
    ``proof_length`` is how many siblings the walked path carried; both are
    ``None`` when the walk did not reach them.  ``checked`` is prose rather
    than a check name, so nothing here needs a reader who knows the trail.
    """

    audit_id: uuid.UUID
    status: str
    batch_id: uuid.UUID | None
    batch_root: str | None
    proof_length: int | None
    checked: tuple[str, ...]


def explain(walked: Verification) -> tuple[str, ...]:
    """The walk's own check names as one sentence each, in the walk's order.

    :param walked: what one walk of the log found.
    :returns: a sentence per check that completed, in the order they ran.
    :raises ExplainError: when a check name has no sentence here.
    """
    return tuple(_sentence_of(check) for check in walked.checked)


def verify_audit_event(
    audit_id: uuid.UUID, *, sessions: sessionmaker[Session], ledger: Ledger
) -> AuditVerification:
    """Walk one stored event to its anchored root and say what was checked.

    :param audit_id: the event id ``POST /api/screenings`` answered with.
    :param sessions: the factory the row is read through, required and never
        the module-level one (``D62``'s reasoning).
    :param ledger: the log the anchored root is read back from.
    :returns: the answer, whose ``status`` is 9.17's own word and whose
        ``checked`` names no step that did not complete.
    """
    stored = event_by_id(sessions, audit_id)
    if stored is None:
        return AuditVerification(audit_id, UNKNOWN, None, None, None, ())
    walked = verification_of(stored, sessions=sessions, ledger=ledger)
    return AuditVerification(
        audit_id=audit_id,
        status=walked.status,
        batch_id=walked.batch_id,
        batch_root=walked.batch_root,
        proof_length=walked.proof_length,
        checked=explain(walked),
    )


def _sentence_of(check: str) -> str:
    """``check``'s sentence, refusing a step this table cannot name.

    :param check: one of 9.17's own check names.
    :returns: the sentence written for it.
    :raises ExplainError: naming the check, which is a constant in this
        service's own source rather than anything a row carried.
    """
    try:
        return CHECK_SENTENCES[check]
    except KeyError:
        raise ExplainError(
            f"{check!r} is a check app.ledger.verification reports and "
            f"app.audit.verify cannot name in a sentence: no value is shown"
        ) from None
