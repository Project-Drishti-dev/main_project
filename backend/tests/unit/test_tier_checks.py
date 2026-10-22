from __future__ import annotations

import json
from types import SimpleNamespace

from app.pipeline import tier_checks
from app.pipeline.tier0.runner import TierResult as Tier0Result
from app.pipeline.tier1.ocr import NO_WORDS, OcrResult, OcrWord
from app.pipeline.tier1.runner import Tier1Result
from app.pipeline.tier2 import base, ela


class StubModule(base.DeepModule):
    name = ela.MODULE_NAME

    def run(self, context):
        return base.DeepResult(
            module=self.name,
            score=0.2,
            is_stub=True,
            model_version="heuristic-v0",
            detail="Synthetic heuristic output.",
        )


def test_run_tier_checks_returns_only_safe_summaries_and_marks_stubs():
    image = object()

    def run_tier0(frame, **_kwargs):
        assert frame is image
        return Tier0Result(detected_format="TD3")

    def run_tier1(frame, *, preference):
        assert frame is image
        assert preference == tier_checks.TESSERACT_PREFERENCE
        return Tier1Result(ocr=NO_WORDS, ocr_available=True)

    checks = tier_checks.run_tier_checks(
        image,
        tier0_runner=run_tier0,
        tier1_runner=run_tier1,
        tier2_modules={ela.MODULE_NAME: StubModule()},
        anomaly_scorer=None,
    )

    assert [(check.tier, check.module) for check in checks] == [
        (0, "mrz_detection"),
        (1, "ocr"),
        (2, ela.MODULE_NAME),
    ]
    assert checks[0].status == "completed"
    assert checks[1].status == "completed"
    assert checks[1].recognized_text is None
    assert checks[2].status == "stub"
    assert checks[2].is_stub is True
    assert checks[2].model_version == "heuristic-v0"
    assert "words" not in json.dumps([check.to_wire() for check in checks])


def test_hard_fail_stops_later_tiers():
    called = []

    def run_tier0(_image, **_kwargs):
        return Tier0Result(hard_failed=True, hard_fail_reason="checksum mismatch")

    def run_tier1(_image, *, preference):
        called.append(preference)
        return Tier1Result(ocr=NO_WORDS, ocr_available=False)

    checks = tier_checks.run_tier_checks(
        object(),
        tier0_runner=run_tier0,
        tier1_runner=run_tier1,
        tier2_modules={ela.MODULE_NAME: StubModule()},
    )

    assert len(checks) == 1
    assert checks[0].status == "hard_fail"
    assert called == []


def test_tier1_summary_includes_detected_text_for_the_prototype():
    words = (
        OcrWord(text="SYNTHETIC", bbox=(0, 0, 50, 10), confidence=0.9),
        OcrWord(text="DOCUMENT", bbox=(55, 0, 100, 10), confidence=0.9),
    )

    checks = tier_checks.run_tier_checks(
        object(),
        tier0_runner=lambda _image, **_kwargs: Tier0Result(detected_format="TD3"),
        tier1_runner=lambda _image, *, preference: Tier1Result(
            ocr=OcrResult(words=words, mean_confidence=0.9),
            ocr_available=True,
        ),
        tier2_modules={},
        anomaly_scorer=None,
    )

    ocr_check = next(check for check in checks if check.module == "ocr")
    assert ocr_check.recognized_text == "SYNTHETIC DOCUMENT"
    assert ocr_check.to_wire()["recognized_text"] == "SYNTHETIC DOCUMENT"


def test_tier2_summaries_use_plain_language_and_keep_the_prototype_caveat(
    monkeypatch,
):
    class NamedStubModule(base.DeepModule):
        def __init__(self, name):
            self.name = name

        def run(self, _context):
            return base.DeepResult(
                module=self.name,
                score=0.2,
                is_stub=True,
                model_version="heuristic-v0",
                detail="Internal implementation detail.",
            )

    class AnomalyStub:
        model_version = "synthetic-v0"

        def rank(self, _vector):
            return 0.3

    monkeypatch.setattr(tier_checks.anomaly, "feature_vector", lambda _image: ())
    modules = {
        name: NamedStubModule(name) for name in tier_checks.DEFAULT_TIER2_MODULES
    }
    checks = tier_checks.run_tier_checks(
        object(),
        tier0_runner=lambda _image, **_kwargs: Tier0Result(detected_format="TD3"),
        tier1_runner=lambda _image, *, preference: Tier1Result(
            ocr=NO_WORDS, ocr_available=False
        ),
        tier2_modules=modules,
        anomaly_scorer=AnomalyStub(),
    )

    tier2 = [check for check in checks if check.tier == 2]
    assert len(tier2) == 7
    assert all(
        check.label
        and len(check.label.split()) <= 4
        and "found" not in check.label.lower()
        and len(check.detail.split()) <= 20
        for check in tier2
    )
    assert "re-compresses unlike the page around it" not in tier2[0].label
    assert "not proof" in tier_checks.TIER_NOTICE
    assert "trained or validated authenticity models" not in tier_checks.TIER_NOTICE


def test_one_deep_module_failure_does_not_skip_the_next():
    called = []

    class BrokenModule(base.DeepModule):
        name = "tamper_broken"

        def run(self, context):
            raise RuntimeError("details are intentionally not surfaced")

    class FollowingModule(StubModule):
        name = ela.MODULE_NAME

        def run(self, context):
            called.append(context.image)
            return super().run(context)

    checks = tier_checks.run_tier_checks(
        object(),
        tier0_runner=lambda _image, **_kwargs: Tier0Result(),
        tier1_runner=lambda _image, *, preference: Tier1Result(
            ocr=NO_WORDS, ocr_available=False
        ),
        tier2_modules={
            "tamper_broken": BrokenModule(),
            ela.MODULE_NAME: FollowingModule(),
        },
        anomaly_scorer=None,
    )

    assert checks[-2].status == "failed"
    assert checks[-2].detail == "This check could not run."
    assert checks[-1].status == "stub"
    assert called
    assert "details are intentionally not surfaced" not in json.dumps(
        [check.to_wire() for check in checks]
    )
