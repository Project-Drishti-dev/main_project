"""18.9: the report is a page an officer can print with nothing else around.

Reached through the real app, the real flow behind it and one temporary
database under it, so what is asserted is the bytes that get printed rather
than a route's return value.  The task names four things on the page -- the
band, the findings, the reason each rule wrote and the audit id -- and the
claim beside them is that the page is standalone: it fetches nothing, so it
prints on a machine with no network and reads the same in ten years.

**The findings under the report are a real cascade's.**  A page with no
machine-readable zone produces none, so a blank upload could only prove that
an empty table prints.  A drawn TD3 whose printed composite digit is wrong is
screened through app.screening.run_screening with its own parse, which is how
a rule gets its characters, and 6.2 then boxes the failing digit on the page.

**The last two groups of cases are what the page must not carry**, on the
ground 11.2's read is held to: a filename is caller-supplied text and a field
value is read off the document, and a record that is filed carries neither.
The reason floor in app.explain.reasons is not reached here either -- 23.8
is where a screen wires it -- so every reason on the page is the one its own
rule wrote.

**The ban is held against a page that really does reference an asset**, so a
checker that matched nothing could not pass the cases above for the wrong
reason.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import get_sessions
from app.audit.trail import completed_event_id
from app.main import app
from app.pipeline.tier0 import document
from app.reporting import NOT_RECORDED
from app.screening import run_screening
from app.storage import db
from app.storage.models import Base, Screening
from app.storage.repository import ScreeningRepository
from tests.fixtures import mrz_images


#: Every spelling of a reference the page must not make, lowercased and
#: matched as a substring: the elements that fetch, the attributes that
#: name something to fetch, and the URL forms that would be one.  A styles
#:heet is the half that is easy to forget and prints worst.
FORBIDDEN_REFERENCES = (
    "<link",
    "<script",
    "<img",
    "<iframe",
    "<object",
    "<embed",
    "<base",
    "<audio",
    "<video",
    "<source",
    "<form",
    "src=",
    "href=",
    "srcset=",
    "poster=",
    "action=",
    "@import",
    "@font-face",
    "url(",
    "http://",
    "https://",
    "ftp://",
    "data:",
    "file:",
)

#: Markup written into a stored finding, to be read back as text.
STORED_MARKUP = '<b>bold</b> & "quoted"'

#: What that markup prints as, so the case asserts the escaping rather than
#: the browser's idea of it.
STORED_MARKUP_PRINTED = (
    "&lt;b&gt;bold&lt;/b&gt; &amp; &quot;quoted&quot;"
)


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema, and a factory over it."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        factory = db.build_session_factory(engine)
        app.dependency_overrides[get_sessions] = lambda: factory
        yield factory
    finally:
        app.dependency_overrides.pop(get_sessions, None)
        engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _screened(sessions: sessionmaker[Session]) -> Screening:
    """One real screening, so the report is asked about a row with a result.

    The page is parsed back off its own pixels rather than handed over as
    text, and 6.2 boxes the failing digit, so the row carries a finding, a
    reason and a band for the report to print.
    """
    zone = list(mrz_images.SPECIMENS["TD3"])
    printed = zone[1][43]
    zone[1] = zone[1][:43] + ("0" if printed != "0" else "1") + zone[1][44:]
    page = mrz_images.render_format("TD3", lines=tuple(zone))
    return run_screening(
        sessions=sessions,
        image=page.image,
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        parsed_document=document.parse_mrz(mrz_images.read_zone(page)),
    )


def _pending(sessions: sessionmaker[Session]) -> Screening:
    """One row 11.1 wrote before any stage ran, carrying no result at all."""
    return ScreeningRepository(sessions).create(
        document_type="passport",
        filename="a-name-that-must-not-travel.jpg",
        image_width=320,
        image_height=90,
    )


def _printed(client: TestClient, row: Screening) -> str:
    """The page the report endpoint prints for ``row``."""
    response = client.get(f"/api/screenings/{row.id}/report")
    assert response.status_code == 200
    return response.text


def _external_references(page: str) -> list[str]:
    """The names of the external references ``page`` makes."""
    folded = page.casefold()
    return [name for name in FORBIDDEN_REFERENCES if name in folded]


# --- the page itself ------------------------------------------------------


def test_the_page_is_one_html_document_and_nothing_else(client, sessions):
    """The task's own shape: printable, and complete on its own."""
    row = _screened(sessions)

    response = client.get(f"/api/screenings/{row.id}/report")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    page = response.text
    assert page.startswith("<!DOCTYPE html>")
    assert page.rstrip().endswith("</html>")
    assert page.count("<style>") == 1
    assert "<body>" in page and "</body>" in page


def test_the_page_references_no_external_asset(client, sessions):
    """The task's own claim: nothing on it has to be fetched to be read."""
    row = _screened(sessions)

    page = _printed(client, row)

    assert _external_references(page) == []


def test_the_ban_is_held_against_a_page_that_really_references_one():
    """A checker that matched nothing would pass the case above for the wrong
    reason, so the spellings are checked against a page that makes them."""
    planted = (
        "<!DOCTYPE html><html><head>"
        + '<link rel="stylesheet" href="https://example.test/drishti.css">'
        + '<script src="/static/report.js"></script>'
        + "</head><body></body></html>"
    )

    assert set(_external_references(planted)) == {
        "<link",
        "href=",
        "https://",
        "<script",
        "src=",
    }


# --- what the task names on the page --------------------------------------


def test_the_page_carries_the_row_s_own_columns(client, sessions):
    """The columns a stage wrote, not a fresh reading beside them."""
    row = _screened(sessions)

    page = _printed(client, row)

    assert f"<td>{row.id}</td>" in page
    assert f"<td>{row.document_type}</td>" in page
    assert row.band is not None
    assert f"<td>{row.band}</td>" in page
    assert f"<td>{row.score}</td>" in page
    assert f"<td>{row.ruleset_version}</td>" in page
    assert f"<td>{row.status}</td>" in page


def test_every_stored_finding_is_listed_with_the_reason_its_rule_wrote(
    client, sessions
):
    """One row per stored finding, and the reason off that finding."""
    row = _screened(sessions)

    page = _printed(client, row)

    assert page.count('<tr class="finding">') == len(row.flags)
    for finding in row.flags:
        assert f"<td>{finding['id']}</td>" in page
        assert f"<td>{finding['label']}</td>" in page
        assert f"<td>{finding['reason']}</td>" in page


def test_every_finding_column_the_report_prints_is_one_a_case_reads_back(
    client, sessions
):
    """A dropped column is a shorter table rather than a failing one, so the
    five columns no other case names are named here.

    **The two numbers are read as an ordered run, not searched for.**  This
    fixture's findings score value and confidence alike, so a case asserting
    that one number appears would be answered by the other's cell and pass
    against a table with a column missing.
    """
    row = _screened(sessions)
    finding = row.flags[0]

    page = _printed(client, row)
    numbers = [
        cell.split("<", 1)[0].strip()
        for cell in page.split('<td class="number">')[1:]
    ]

    assert f"<td>{finding['tier']}</td>" in page
    assert f"<td>{finding['source_module']}</td>" in page
    assert f"<td>{finding['weight_band']}</td>" in page
    assert numbers == [
        text
        for stored in row.flags
        for text in (str(stored["value"]), str(stored["confidence"]))
    ]


def test_the_audit_id_on_the_page_is_the_one_the_trail_holds(client, sessions):
    """The event 11.1 answered with, and the one 18.7's verify endpoint takes."""
    row = _screened(sessions)

    page = _printed(client, row)

    audit_id = completed_event_id(row.id, sessions=sessions)
    assert audit_id is not None
    assert page.count(f"<td>{audit_id}</td>") == 1
    assert client.get(f"/api/audit/{audit_id}/verify").status_code == 200


def test_a_row_nobody_scored_prints_a_sentence_where_a_value_would_be(
    client, sessions
):
    """A value nothing wrote is named, so an empty cell is never a blank
    answer an officer could read as one."""
    row = _pending(sessions)

    page = _printed(client, row)

    assert page.count(NOT_RECORDED) == 4
    assert "<p>No findings were recorded for this screening.</p>" in page
    assert f"<td>{row.status}</td>" in page
    assert row.created_at.strftime("%Y-%m-%d") in page


def test_a_stored_angle_bracket_prints_as_a_character_and_runs_as_nothing(
    client, sessions
):
    """A label and a reason are text a rule wrote; the page escapes them."""
    row = _screened(sessions)
    with sessions() as session:
        stored = session.merge(row)
        stored.flags = [
            {**finding, "label": STORED_MARKUP, "reason": STORED_MARKUP}
            for finding in (row.flags or [])
        ]
        session.commit()

    page = _printed(client, row)

    assert STORED_MARKUP_PRINTED in page
    assert "<b>bold</b>" not in page
    assert "<script" not in page


# --- what the page must not carry -----------------------------------------


def test_neither_the_upload_s_own_name_nor_a_value_off_the_page_is_printed(
    client, sessions
):
    """The upload's name is the caller's text and the field values are read
    off the document; a record that is filed carries neither."""
    row = _screened(sessions)
    off_the_page = "A-VALUE-READ-OFF-THE-PAGE-" + row.flags[0]["id"]
    with sessions() as session:
        stored = session.merge(row)
        stored.flags = [
            {**finding, "expected": off_the_page, "found": off_the_page}
            for finding in (row.flags or [])
        ]
        session.commit()

    page = _printed(client, row)

    assert "a-name-that-must-not-travel" not in page
    assert off_the_page not in page
    assert f"<td>{row.flags[0]['reason']}</td>" in page


def test_an_id_no_row_carries_is_a_404_in_the_shared_envelope(client, sessions):
    """11.4 holds this body to the shape every other refusal uses."""
    response = client.get(f"/api/screenings/{uuid.uuid4()}/report")

    assert response.status_code == 404
    assert set(response.json()["error"]) == {"code", "message"}
    assert response.json()["error"]["code"] == "SCREENING_NOT_FOUND"


def test_an_id_that_is_not_one_is_refused_before_the_table_is_read(
    client, sessions
):
    """A string that is not a uuid is 11.4's question, and the envelope's."""
    response = client.get("/api/screenings/not-a-uuid/report")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_a_deleted_screening_is_absent_rather_than_reported(client, sessions):
    """8.15's rule reaches this read through ScreeningRepository.get."""
    row = _screened(sessions)
    ScreeningRepository(sessions).soft_delete(
        row.id, deleted_at=datetime.now(timezone.utc)
    )

    response = client.get(f"/api/screenings/{row.id}/report")

    assert response.status_code == 404
