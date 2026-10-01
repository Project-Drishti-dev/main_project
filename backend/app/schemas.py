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


class ScreeningResultResponse(BaseModel):
    """The whole of a stored screening, as 11.2's endpoint answers it.

    ``score``, ``band`` and ``ruleset_version`` are the row's own columns and
    are ``None`` for a row no stage has scored.  ``flags`` is the stored
    evidence; ``contributions`` is its per-flag ``weight x value`` breakdown.
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
