"""10.5: the screening flow -- one row, the cascade, and the events it left.

The flow is the only caller of :func:`app.audit.emit.emit`: it writes the row
the upload arrived as, emits ``screening_created`` before the cascade has run
anything, runs the tiers in :data:`CASCADE` -- one ``tier_completed`` per tier
that ran, and a hard fail ends the cascade -- scores what came back, stores it
on the row, and emits ``analysis_completed`` carrying that row's own columns.
Rationale for the events and for the versions beside them:
``docs/DECISIONS.md`` D66, D67, D68 and D69.

**What the run cost, and how the run ended, are metrics rather than events
(26.8).**  :mod:`app.metrics` writes one line per tier the cascade ran and
one naming how the whole of it ended, off a monotonic clock the flow reads
itself; none of it reaches the trail, for the reason a score is scaled there
(D48).  The same run stamps the request's correlation id on the row, read off
the ambient binding rather than off the inbound header, so the row a reader
finds in the database and the lines the same run wrote share one value.

**The upload is stored, and only its address is kept.** 19.6 hands
:func:`run_screening` the bytes an officer uploaded and the
:class:`~app.storage.blob_store.EvidenceStore` to store them in; the flow
writes the blob and puts the one token
:meth:`~app.storage.blob_store.BlobRef.to_wire` spells on the row, so no row in
this service holds the document.  A caller that wires no store stores nothing
and the row carries ``None`` -- the flow never keeps a copy of its own.

**The reader sits beside the writer, and that is the point.**
:func:`screening_contributions` is the one place a stored row is asked what it
scored, so the spelling of the ``flags`` column is written down once, by
:func:`_store_result` and by the reader that consumes it.  A reader in a
second module would be a second answer to "what does this row hold", and the
two could disagree about the score without either noticing.
"""

import dataclasses
import datetime
import time
import uuid
from collections.abc import Callable
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app import metrics
from app.audit.emit import emit
from app.audit.event_types import (
    ANALYSIS_COMPLETED,
    SCREENING_CREATED,
    TIER_COMPLETED,
)
from app.logging_config import current_request_id
from app.pipeline.tier0 import document, runner
from app.risk.engine import RiskResult, compute_risk
from app.risk.flags import FlagValueError
from app.risk.scoring import Contribution, weighted_breakdown
from app.risk.watchlist import Watchlist
from app.risk.weightsets.loader import (
    DEFAULT_WEIGHTSET,
    Weightset,
    WeightsetError,
    load_weightset,
)
from app.storage.blob_store import BlobRef, EvidenceStore
from app.storage.models import SCREENING_STATUSES, Screening
from app.storage.repository import ScreeningRepository

__all__ = [
    "CASCADE",
    "COMPLETED_STATUS",
    "HARD_FAIL_IDS",
    "SCORE_BP_KEY",
    "TIER_KEY",
    "TIERS_RUN_KEY",
    "run_screening",
    "screening_contributions",
]

#: What each tier is called by, and the function that runs it.  **This table
#: is the cascade's plan**: :data:`CASCADE` is its own keys, so a tier the
#: plan names and a tier the trail records cannot drift apart, and Parts 12
#: and 15 add a name and its runner here and change nothing else.
_TIER_RUNNERS: dict[str, Callable[..., runner.TierResult]] = {
    runner.TIER_NAME: runner.run_tier0,
}

#: The tiers the cascade runs, in the order it runs them.  A tier that hard
#: fails ends it -- 6.5's "exits directly to High Risk" -- so this is the
#: longest a trail's per-tier events can ever be.
CASCADE = tuple(_TIER_RUNNERS)

#: 6.5's answer -- which findings override the score -- read off the runner's
#: own union rather than written down here.  ``app.risk`` may not hold it
#: (``D6``'s one-way dependency), so the composition layer is where it is
#: asked for, and 7.15's required keyword is what it is handed through.
HARD_FAIL_IDS = frozenset(runner._HARD_FAIL_IDS)

#: The payload key a score is written under: whole basis points on the 0-100
#: scale, because ``D48`` refuses a float in a payload and ``D66`` says a
#: score goes into one as text or as a scaled integer.
SCORE_BP_KEY = "score_bp"

#: The payload key a ``tier_completed`` event names its tier under, so the
#: spelling 18.10's progress stream reads is written down once here rather
#: than guessed at by every reader of that event.
TIER_KEY = "tier"

#: The payload key naming which tiers ran, on ``analysis_completed`` -- so a
#: reader who comes to the trail at its end can tell a cascade that stopped
#: early from a cascade that was never more than one tier deep.
TIERS_RUN_KEY = "tiers_run"

#: The status a row carries once the cascade has answered, read out of the
#: vocabulary the model holds rather than spelled beside it.
COMPLETED_STATUS = SCREENING_STATUSES[1]


def run_screening(
    *,
    sessions: sessionmaker[Session],
    image: Any,
    document_type: str,
    filename: str,
    document: bytes | None = None,
    evidence_store: EvidenceStore | None = None,
    reference_date: datetime.date | None = None,
    parsed_document: document.MrzDocument | None = None,
    watchlist: Watchlist | None = None,
    weightset: str = DEFAULT_WEIGHTSET,
    model_versions: dict[str, str] | None = None,
) -> Screening:
    """Screen one upload and leave a row and its events behind it.

    :param sessions: the factory every write below goes through, required and
        never the module-level one (``D62``'s reasoning).
    :param image: the working frame Tier 0 measures -- height, width and
        channels -- which is where the row's two size columns come from.
    :param document_type: the caller's claim about the document, stored on the
        row and handed to the runner as a claim (``D16``).
    :param filename: the name the upload arrived under.  **Stored on the row
        and carried into no event and no payload.**
    :param document: the uploaded bytes, as they arrived.  Stored as an
        encrypted blob and not kept anywhere else; ``None`` for a caller that
        wired no store (19.6).
    :param evidence_store: where ``document`` is stored, or ``None`` to store
        nothing.  **A document with no store beside it is refused rather than
        dropped**, so a caller cannot ask for a screening and lose the page
        it was screened from.
    :param reference_date: the day Tier 0's date rules are measured against,
        or ``None`` for a caller that injected none.
    :param parsed_document: the caller's parse of this same page, which is
        how 6.2 gets its characters.
    :param watchlist: the connector Tier 0 asks, or ``None`` for none wired.
    :param weightset: the weightset name the findings are scored against; the
        version it carries is what the row and the event are stamped with.
    :param model_versions: module name to version for the modules that
        answered, written on the row and handed to the final event, or
        ``None`` while no model has answered.
    :returns: the committed row, carrying the score, band, ruleset version,
        flags and ``completed`` status the cascade produced.
    :raises WeightsetError: when ``weightset`` names no readable file.  The
        ``screening_created`` and ``tier_completed`` events are already in the
        trail by then, which is what "written before the score" means.
    :raises ValueError: when ``document`` is given without ``evidence_store``,
        whatever the runner, the weightset loader or the engine refuse,
        propagated rather than swallowed.
    """
    height, width = image.shape[:2]
    columns = {"image_width": int(width), "image_height": int(height)}
    reference = _stored_reference(evidence_store, document)
    created = ScreeningRepository(sessions).create(
        document_type=document_type,
        filename=filename,
        image_blob_ref=None if reference is None else reference.to_wire(),
        request_id=current_request_id(),
        **columns,
    )
    emit(
        SCREENING_CREATED,
        created.id,
        {"document_type": document_type, **columns},
        sessions=sessions,
    )
    tier, ran = _run_cascade(
        created.id,
        sessions=sessions,
        image=image,
        document_type=document_type,
        reference_date=reference_date,
        parsed_document=parsed_document,
        watchlist=watchlist,
    )
    risk = compute_risk(tier.flags, load_weightset(weightset), hard_fail_ids=HARD_FAIL_IDS)
    row = _store_result(sessions, created, tier, risk, model_versions)
    emit(
        ANALYSIS_COMPLETED,
        row.id,
        _completed_payload(tier, risk, ran),
        sessions=sessions,
        ruleset_version=row.ruleset_version,
        model_versions=row.model_versions,
    )
    return row


def _stored_reference(
    evidence_store: EvidenceStore | None, document: bytes | None
) -> BlobRef | None:
    """The document stored as an encrypted blob, and the address it answers.

    :param evidence_store: where the document is stored, or ``None``.
    :param document: the uploaded bytes, or ``None``.
    :returns: the :class:`~app.storage.blob_store.BlobRef` the document was
        written under, or ``None`` when neither was given.
    :raises ValueError: when one was given without the other.  A document no
        store was given would be discarded while the row claimed a screening,
        and a store with no document has nothing to write -- so the pair is
        required together rather than half-honoured.
    """
    if (evidence_store is None) != (document is None):
        raise ValueError(
            "a screening is given the uploaded document and the store to "
            "write it in together, or neither: storing nothing while "
            "answering with a screening id would lose the document"
        )
    if evidence_store is None:
        return None
    return evidence_store.put(document)


def _run_cascade(
    screening_id: uuid.UUID,
    *,
    sessions: sessionmaker[Session],
    image: Any,
    document_type: str,
    reference_date: datetime.date | None,
    parsed_document: document.MrzDocument | None,
    watchlist: Watchlist | None,
) -> tuple[runner.TierResult, tuple[str, ...]]:
    """Run the plan, recording one ``tier_completed`` for each tier that ran.

    A hard fail ends the cascade, so the names answered back are the tiers
    that ran and no others, and a cascade that raises part-way leaves the
    trail naming exactly how far it got.

    26.8's two metrics are written around that run and from a ``finally``, so
    a cascade that raised is measured as well as one that answered.
    """
    ran: list[str] = []
    tier: runner.TierResult | None = None
    outcome = metrics.OUTCOME_COMPLETED
    started = _now()
    try:
        for name in CASCADE:
            mark = _now()
            tier = _TIER_RUNNERS[name](
                image,
                document_type=document_type,
                reference_date=reference_date,
                parsed_document=parsed_document,
                watchlist=watchlist,
            )
            ran.append(name)
            metrics.emit_tier_latency(
                screening_id=screening_id,
                tier=name,
                elapsed_ms=_elapsed_ms(mark),
                flags_found=len(tier.flags),
                hard_failed=tier.hard_failed,
            )
            emit(
                TIER_COMPLETED,
                screening_id,
                _tier_payload(name, tier),
                sessions=sessions,
            )
            if tier.hard_failed:
                outcome = metrics.OUTCOME_HARD_FAILED
                break
    except Exception:
        outcome = metrics.OUTCOME_FAILED
        raise
    finally:
        metrics.emit_cascade_outcome(
            screening_id=screening_id,
            outcome=outcome,
            tiers_run=tuple(ran),
            elapsed_ms=_elapsed_ms(started),
            flags_found=0 if tier is None else len(tier.flags),
        )
    if tier is None:
        raise ValueError(
            "the cascade ran no tier, and a screening with no tier result "
            "has nothing to score: CASCADE is empty, which is a constant in "
            "this module rather than anything a screening carried"
        )
    return tier, tuple(ran)


def _now() -> float:
    """:returns: the monotonic counter's own reading, in seconds.

    A stopwatch and not a calendar, on ``app.pipeline.tier0.runner``'s
    reasoning: a latency is a duration, and the wall clock moves when the
    host's time is corrected.
    """
    return time.perf_counter()


def _elapsed_ms(started: float) -> float:
    """:returns: milliseconds since a :func:`_now` reading, to 3 places.

    Rounded the way ``app.api.request_logging`` rounds its own, so the
    request line and the tier lines beside it share one spelling of a
    duration.
    """
    return round((_now() - started) * 1000, 3)


def _store_result(
    sessions: sessionmaker[Session],
    created: Screening,
    tier: runner.TierResult,
    risk: RiskResult,
    model_versions: dict[str, str] | None,
) -> Screening:
    """Write what the cascade measured onto the row, and answer that row.

    The result columns are written here and not by
    :class:`~app.storage.repository.ScreeningRepository`, which is the one
    way in to the table and says it writes no result at all.

    :returns: the same row, merged back into a session and committed, so the
        versions the second event is handed are the row's own columns.
    """
    with sessions() as session:
        row = session.merge(created)
        row.status = COMPLETED_STATUS
        row.score = risk.score
        row.band = risk.band
        row.ruleset_version = risk.ruleset_version
        row.model_versions = model_versions
        row.flags = [dataclasses.asdict(flag) for flag in tier.flags]
        session.commit()
    return row


def _tier_payload(name: str, tier: runner.TierResult) -> dict[str, Any]:
    """What one tier found, under the tier's own name.

    Both version keys are attached as the unknowns they are: a tier event is
    written before anything has been scored, and Tier 0 runs no model, so
    handing it the screening's model versions would claim a model answered
    that did not.  The 6.6 stage timings stay off the trail for the same
    reason a score arrives scaled (``D48``).
    """
    return {TIER_KEY: name, **_tier_facts(tier)}


def _tier_facts(tier: runner.TierResult) -> dict[str, Any]:
    """What a tier run measured, in the shape a payload can be hashed in.

    A finding goes in as its id and a hard fail as its boolean and its
    reason, which is the sentence 6.5 exits with.
    """
    return {
        "detected_format": tier.detected_format,
        "flag_ids": [flag.id for flag in tier.flags],
        "hard_failed": tier.hard_failed,
        "hard_fail_reason": tier.hard_fail_reason,
    }


def _completed_payload(
    tier: runner.TierResult, risk: RiskResult, ran: tuple[str, ...]
) -> dict[str, Any]:
    """What the cascade answered, spelled so 9.3 can hash it.

    A finding goes in as its id and the score as whole basis points, because
    a payload carrying a ``float`` is refused before a row is written
    (``D48``) and a flag object would carry the measured values a ledger has
    no column for.  The stage timings 6.6 measured stay off the trail for the
    same reason.  :data:`TIERS_RUN_KEY` is the cascade's own answer about
    itself: the tier events beside this one are the same names.
    """
    return {
        **_tier_facts(tier),
        "band": risk.band,
        SCORE_BP_KEY: _score_bp(risk.score),
        TIERS_RUN_KEY: list(ran),
    }


def _score_bp(score: float) -> int:
    """``score`` as whole basis points on the 0-100 scale (``D66``)."""
    return int(round(score * 100))


@dataclasses.dataclass(frozen=True)
class _Term:
    """One stored finding as the sum reads it: an id and a measured value.

    **The two fields the arithmetic needs, and no others.**  The row stores
    each finding as the object
    :func:`_store_result` wrote with
    :func:`dataclasses.asdict`, so reading a contribution back out of it is
    not a second parsing of the record -- it is the same two values the
    original :class:`~app.risk.flags.EvidenceFlag` carried, handed to the
    same :func:`~app.risk.scoring.weighted_breakdown` that summed them the
    first time.  Rebuilding the full record to reach those two fields would
    add a refusal this read does not need.
    """

    id: object
    value: object


def _term(record: object) -> _Term:
    """One stored finding, as the record the sum reads.

    :param record: one object of the row's ``flags`` column, as JSON read it
        back: a mapping carrying the finding's own fields.
    :returns: the finding's ``id`` and ``value``, unexamined.
    :raises FlagValueError: when ``record`` is not a mapping at all.  A
        stored column no writer here can produce, and a reader that indexed
        it would answer ``AttributeError`` instead.
    """
    if not isinstance(record, Mapping):
        raise FlagValueError(
            "a stored finding must be a mapping, not "
            f"{type(record).__name__}"
        )
    return _Term(id=record.get("id"), value=record.get("value"))


def screening_contributions(
    row: Screening, weightset: Weightset
) -> tuple[Contribution, ...]:
    """The terms ``row``'s score was summed from, read back off the row.

    **The breakdown is recomputed rather than stored, and the ruleset it is
    recomputed against must be the one the row names.**  ``screenings`` holds
    sixteen columns and none of them is a contribution, so a term -- a
    ``weightset`` weight times a stored ``value`` -- is a pure function of the
    two things the row does hold, and the same
    :func:`~app.risk.scoring.weighted_breakdown` that produced it produces it
    again.  Recomputing against *another* weightset would put numbers beside
    a score they cannot add up to, so a version that is not the row's own is
    refused rather than answered.

    :param row: the stored screening, read through
        :class:`~app.storage.repository.ScreeningRepository`.
    :param weightset: the weightset to weigh the findings against, which must
        carry the ``ruleset_version`` the row does.
    :returns: one :class:`~app.risk.scoring.Contribution` per stored finding,
        in the order the column holds them, or the empty tuple for a row no
        stage has scored.
    :raises WeightsetError: when ``weightset`` is not the ruleset the row was
        scored under, when the file itself cannot be read, or when a finding
        carries an id it weighs no row for.
    :raises FlagValueError: when a stored finding is not a mapping, or
        carries no ``id`` or no measured ``value`` -- from
        :func:`_term` and from 7.3/7.4's own gates.
    """
    if row.ruleset_version is None:
        return ()
    if weightset.ruleset_version != row.ruleset_version:
        raise WeightsetError(
            f"the {weightset.ruleset_version!r} weightset is not the "
            f"{row.ruleset_version!r} ruleset this screening was scored "
            "under, so its contributions cannot be recomputed"
        )
    return weighted_breakdown(
        tuple(_term(record) for record in (row.flags or ())), weightset
    ).contributions
