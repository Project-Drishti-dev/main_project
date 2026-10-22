"""The six names an audit event may carry, spelled in one place.

``AuditEvent.event_type`` is a plain text column, so these are ``str`` and
not enum members.  This module states names only -- refusing one is 10.2's
writer.  Rationale: ``docs/DECISIONS.md`` D65.
"""

#: A screening row exists; the first event of every trail.
SCREENING_CREATED = "screening_created"

#: The cascade finished and produced a result, or stopped early.
ANALYSIS_COMPLETED = "analysis_completed"

#: One tier finished -- one event per tier that actually ran (10.5).
TIER_COMPLETED = "tier_completed"

#: An officer recorded an allow / further-inspection / reject choice.
DECISION_RECORDED = "decision_recorded"

#: That choice contradicted the band (10.6's own event, beside the result).
OVERRIDE_RECORDED = "override_recorded"

#: The screening row was soft-deleted; its events survive it.
SCREENING_DELETED = "screening_deleted"

#: The six names, closed, in the order a reader meets a trail.  A tuple, so
#: that a duplicate is representable and "no duplicates" is a real claim.
EVENT_TYPES = (
    SCREENING_CREATED,
    ANALYSIS_COMPLETED,
    TIER_COMPLETED,
    DECISION_RECORDED,
    OVERRIDE_RECORDED,
    SCREENING_DELETED,
)

__all__ = [
    "ANALYSIS_COMPLETED",
    "DECISION_RECORDED",
    "EVENT_TYPES",
    "OVERRIDE_RECORDED",
    "SCREENING_CREATED",
    "SCREENING_DELETED",
    "TIER_COMPLETED",
]
