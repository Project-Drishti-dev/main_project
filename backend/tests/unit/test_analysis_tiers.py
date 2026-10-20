from app import analysis
from app.pipeline.tier_checks import TIER_NOTICE, TierCheck


def test_analysis_includes_tier_summaries_without_retaining_the_frame(monkeypatch):
    frame = object()
    expected_check = TierCheck(
        tier=2,
        module="tamper_ela",
        label="Error-level analysis",
        status="stub",
        value=0.2,
        is_stub=True,
        model_version="heuristic-v0",
        detail="Synthetic heuristic output.",
    )
    monkeypatch.setattr(analysis, "read_uploaded_image", lambda *_args: frame)
    monkeypatch.setattr(
        analysis,
        "analyze_image",
        lambda image, requested_mode: {
            "mode": "scan",
            "image": {"width": 2, "height": 2},
            "trim_box": None,
            "overall_pass": True,
            "modules": [],
        },
    )
    monkeypatch.setattr(
        analysis,
        "run_tier_checks",
        lambda image: (expected_check,) if image is frame else (),
    )

    result = analysis.analyze_uploaded_image(b"image", "image/png", "scan")

    assert result["tier_checks"] == [expected_check.to_wire()]
    assert result["tier_notice"] == TIER_NOTICE
    assert "frame" not in result
    assert "ocr" not in result
