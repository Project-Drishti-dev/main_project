import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ImageDimensions(BaseModel):
    width: int
    height: int


class ModuleResult(BaseModel):
    module: str
    label: str
    score: int | float | None
    unit: str
    passed: bool | None
    rule: str
    reasons: list[str]
    details: dict[str, Any]
    mode: Literal["photo", "scan"]


class AnalysisResponse(BaseModel):
    mode: Literal["photo", "scan"]
    image: ImageDimensions
    trim_box: list[int] | None
    overall_pass: bool
    modules: list[ModuleResult]


class ScreeningCreatedResponse(BaseModel):
    """The two ids 11.1's endpoint answers with, and nothing else.

    ``screening_id`` names the row and ``audit_id`` the one
    ``analysis_completed`` event beside it, which is the event 18.7 verifies
    and the one whose payload says what the system answered.
    """

    screening_id: uuid.UUID
    audit_id: uuid.UUID


class ScreeningFlagResponse(BaseModel):
    """One stored finding, with the polygon an officer's screen highlights.

    ``region`` is the flag's own :attr:`~app.risk.flags.EvidenceFlag.region`
    as a list of ``[x, y]`` corners, or ``None`` for a finding that cannot be
    located on this image -- a claim rather than a gap.
    """

    id: str
    tier: int | str
    label: str
    weight_band: str
    value: float
    confidence: float
    region: list[list[int]] | None
    expected: str | None
    found: str | None
    reason: str
    source_module: str
    field: str | None


class ScreeningContributionResponse(BaseModel):
    """One finding's term in the sum: the two numbers and their product."""

    id: str
    weight: float
    value: float
    contribution: float


class ScreeningStageTimingResponse(BaseModel):
    """One stage's window: which stage, when it was recorded, what it cost.

    ``elapsed_ms`` is ``None`` where the run recorded no instant to measure the
    window from -- an absence rather than a zero (18.12, D153).
    """

    tier: str
    recorded_at: datetime
    elapsed_ms: int | None


class ScreeningStageTraceResponse(BaseModel):
    """Where one run's time went: its stages in order, and the whole of it.

    ``total_ms`` is the run from its first recorded event to the instant it
    answered, which is more than the stages beside it add up to, because
    the scoring after the last tier is charged to no stage.  A row nothing
    ran on carries no stage and no total (18.12, D153).
    """

    total_ms: int | None
    stages: list[ScreeningStageTimingResponse]


class ScreeningResultResponse(BaseModel):
    """The whole of a stored screening, as 11.2's endpoint answers it.

    ``score``, ``band`` and ``ruleset_version`` are the row's own columns and
    are ``None`` for a row no stage has scored.  ``flags`` is the stored
    evidence; ``contributions`` is its per-flag ``weight x value`` breakdown.
    ``stage_trace`` is what each stage cost, as the run recorded it (18.12).
    """

    screening_id: uuid.UUID
    status: str
    document_type: str
    created_at: datetime
    image: ImageDimensions
    score: float | None
    band: str | None
    ruleset_version: str | None
    model_versions: dict[str, str] | None
    summary: str | None
    flags: list[ScreeningFlagResponse]
    contributions: list[ScreeningContributionResponse]
    stage_trace: ScreeningStageTraceResponse


class ScreeningListItemResponse(BaseModel):
    """One row of a screening list: enough for a table, and nothing more.

    The columns a stored row carries: ``score`` and ``band`` are ``None``
    for a row no stage has scored, and the findings, the narrative and the
    upload's filename are 11.2's answer rather than a page's.
    """

    screening_id: uuid.UUID
    status: str
    document_type: str
    created_at: datetime
    score: float | None
    band: str | None


class ScreeningListResponse(BaseModel):
    """One page of rows, the number that matched, and the bounds it took.

    ``total`` counts the rows every given filter matched rather than the
    rows on this page, so 24.3's table needs no second request for it.
    """

    items: list[ScreeningListItemResponse]
    total: int
    offset: int
    limit: int


class ScreeningDeletedResponse(BaseModel):
    """The row a delete stamped, named by the id it was found through.

    ``deleted_at`` is the instant the request was handled, and it is the only
    change the row carries -- 8.15's soft delete removes nothing, so nothing
    read off the document belongs here.
    """

    screening_id: uuid.UUID
    deleted_at: datetime


class DecisionRequest(BaseModel):
    """What an officer sends with a decision: the choice, a remark, and
    whether the choice is being made against the band shown beside it."""

    action: str
    remark: str = ""
    override: bool = False


class DecisionResponse(BaseModel):
    """The choice as it was accepted, and the record it was written to.

    The first four are what the request named and none of them has moved
    since 18.1 (D143).  ``decision_id`` is the ``decision_recorded`` event
    this choice was written to, ``status`` is where that record stands on the
    trail, and ``supersedes`` names the choice it was taken over from -- so a
    second decision answers with the record it wrote and the one it replaced
    rather than overwriting either (18.4, D146).  Nothing read off a document
    is here.
    """

    screening_id: uuid.UUID
    action: str
    remark: str
    override: bool
    decision_id: uuid.UUID
    status: str
    supersedes: str | None


class AuditVerificationResponse(BaseModel):
    """Whether one stored event still stands, and what was checked to say so.

    ``status`` is 9.17's three words and ``checked`` is one plain sentence per
    check that completed, so a caller reading a 200 can tell a clearance from
    an answer that stopped before it compared anything.  ``batch_root`` and
    ``proof_length`` are ``None`` whenever the walk did not reach them, and
    ``batch_id`` is ``None`` for an event no batch has claimed.
    """

    audit_id: uuid.UUID
    status: Literal["verified", "altered", "unknown"]
    batch_id: uuid.UUID | None
    batch_root: str | None
    proof_length: int | None
    checked: list[str]

class VersionResponse(BaseModel):
    """The four versions this deployment answers with, and nothing else.

    ``model_versions`` is spelled and shaped as the column and the trail spell
    it -- module to version -- so a caller reads one shape for "which models"
    wherever it meets one (``D79``).
    """

    app_version: str
    ruleset_version: str
    model_versions: dict[str, str]
    prompt_version: str

class HealthResponse(BaseModel):
    """The liveness answer: the process answers, and nothing else was asked.

    ``Literal`` rather than ``str`` so the model pins the one value the
    endpoint may answer.  A caller asking whether this process can serve reads
    ``/ready``; a caller asking whether it is up reads this and never waits
    on a database to find out.
    """

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    """The readiness answer: the process can serve, and this is what it proved.

    ``checks`` names every check that ran, so a caller reading a 200 can tell
    a full answer from one that quietly skipped a step -- the difference
    between "verified" and "assumed", which is the difference a supervisor
    acts on.
    """

    status: Literal["ready"]
    checks: list[str]


class ProgressStepResponse(BaseModel):
    """One recorded step, spelled the one way both routes spell it.

    ``unit``, ``state`` and ``tier`` are plain text rather than ``Literal``:
    the vocabulary is owned by ``app.progress`` and pinned to these
    spellings by its own cases, so a second copy of it in a schema would be a
    second place to change rather than a second check on the one that owns it.
    """

    screening_id: uuid.UUID
    unit: str
    state: str
    tier: str
    module: str | None


class ScreeningProgressResponse(BaseModel):
    """The whole sequence in one document, for a caller that cannot stream.

    ``events`` is the list of ``progress`` frames 18.10's route carries, under
    the same keys and in the same order, and ``units`` is what its ``done``
    frame reports -- so a caller polling and a caller streaming read one
    state rather than two (D152).
    """

    screening_id: uuid.UUID
    units: int
    events: list[ProgressStepResponse]
