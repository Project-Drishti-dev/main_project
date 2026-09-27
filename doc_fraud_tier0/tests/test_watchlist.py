import json

import pytest

from tier0.watchlist import lookup, check_watchlist


@pytest.fixture
def watchlist_file(tmp_path):
    data = {
        "entries": [
            {"document_number": "L898902C3", "issuing_country": "UTO", "reason": "Reported stolen"},
            {"document_number": "AB1234567", "reason": "Previously flagged as fraudulent"},
        ]
    }
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_lookup_hit_with_matching_country(watchlist_file):
    hit = lookup("L898902C3", watchlist_file, issuing_country="UTO")
    assert hit is not None
    assert hit.reason == "Reported stolen"


def test_lookup_miss_with_wrong_country(watchlist_file):
    hit = lookup("L898902C3", watchlist_file, issuing_country="USA")
    assert hit is None


def test_lookup_hit_ignores_country_when_entry_has_none(watchlist_file):
    hit = lookup("AB1234567", watchlist_file, issuing_country="ANYTHING")
    assert hit is not None


def test_lookup_normalizes_padding(watchlist_file):
    hit = lookup("L898902C3<<<", watchlist_file, issuing_country="UTO")
    assert hit is not None


def test_lookup_miss_for_clean_document(watchlist_file):
    hit = lookup("ZZ0000000", watchlist_file, issuing_country="UTO")
    assert hit is None


def test_check_watchlist_missing_file_skips_gracefully():
    outcome = check_watchlist("L898902C3", "/nonexistent/path.json")
    assert outcome.passed is True
    assert "not found" in outcome.detail.lower()


def test_check_watchlist_reflects_hit(watchlist_file):
    outcome = check_watchlist("L898902C3", watchlist_file, issuing_country="UTO")
    assert outcome.passed is False


def test_watchlist_cache_invalidates_on_file_change(tmp_path):
    path = tmp_path / "wl.json"
    path.write_text(json.dumps({"entries": []}))
    assert lookup("L898902C3", str(path)) is None

    import time
    time.sleep(0.01)
    path.write_text(json.dumps({"entries": [{"document_number": "L898902C3"}]}))
    assert lookup("L898902C3", str(path)) is not None
