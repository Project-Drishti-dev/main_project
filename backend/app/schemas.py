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
