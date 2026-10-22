import numpy as np

from app.quality_checker import engine


def test_a_failed_module_does_not_leak_its_exception_message(monkeypatch):
    class BrokenModule:
        __name__ = "broken_check"

        @staticmethod
        def assess(_image, mode="photo"):
            raise RuntimeError("internal detail that should not be returned")

    monkeypatch.setattr(engine, "MODULES", ((BrokenModule, "Broken check"),))

    results = engine.run_all(np.zeros((8, 8, 3), dtype=np.uint8))

    assert results == [
        {
            "module": "BrokenModule",
            "label": "Broken check",
            "score": None,
            "unit": "",
            "passed": False,
            "mode": "photo",
            "rule": "",
            "reasons": ["module_error"],
            "details": {},
        }
    ]
