"""15.9 -- a registry holding no template says ``not_configured``, not clean.

The claim pinned first is the verification the task names: a missing stamp
template is reported as ``not_configured`` rather than as a page with nothing
on it, and the two answers cannot be confused even though both hold no match.
The rest holds that the distinction survives into the record the module
answers, and that nothing is reported without a template behind it -- D121.

The page is synthetic and carries the entry mark this repository drew, pasted at
the size it was authored at rather than rescaled, so no test here depends on a
figure a probe never measured.
"""

import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import stamp

SCREENING_ID = uuid.UUID("5b1d0c47-2a86-4f31-9e07-6c4a8d2f1b93")
WIDTH, HEIGHT = 640, 480
PAGE_QUALITY = 95
ENTRY = "demo_entry_stamp"
MARK_AT = (430, 300)


def _page(with_mark):
    """Return a text page carrying the entry mark, written at quality 95."""
    gray = np.full((HEIGHT, WIDTH), 236, np.uint8)
    for row in range(70, 430, 12):
        for column in range(30, 400, 14):
            cv2.line(gray, (column, row), (column + 9, row), 60, 1, cv2.LINE_AA)
    page = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if with_mark:
        art = stamp.STAMP_TEMPLATES[ENTRY].image
        x, y = MARK_AT
        page[y : y + art.shape[0], x : x + art.shape[1]] = art
    encoded, buffer = cv2.imencode(
        ".jpg", page, [int(cv2.IMWRITE_JPEG_QUALITY), PAGE_QUALITY]
    )
    assert encoded, "the test's own JPEG encoder refused its page"
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


CLEAN = _page(False)
MARKED = _page(True)


def _context(image):
    """A context carrying the working frame the seam hands a module."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _match():
    """One match off the marked page, for the records that must refuse one."""
    return stamp.detect_stamps(MARKED).matches[0]


# ---------------------------------------------------------------------------
# The task's own claim: a missing template is reported, not silently empty
# ---------------------------------------------------------------------------


def test_a_registry_holding_no_template_is_answered_not_configured():
    """The verification the task names, on a page that plainly carries a mark."""
    detection = stamp.detect_stamps(MARKED, templates={})

    assert detection.status == stamp.NOT_CONFIGURED


def test_the_unconfigured_answer_is_not_the_one_a_page_with_nothing_on_it_gets():
    """The distinction itself: two answers, one shape, and no way to confuse them.

    Both hold no match, which is why a bare match list could not carry this
    rule; the status is what separates an absent capability from a measurement.
    """
    unconfigured = stamp.detect_stamps(MARKED, templates={})
    measured = stamp.detect_stamps(CLEAN)

    assert unconfigured.matches == measured.matches == ()
    assert unconfigured.status != measured.status
    assert measured.status == stamp.NO_MATCH


def test_an_unconfigured_answer_still_reports_the_ink_it_had_no_template_for():
    """Without this the answer is indistinguishable from a page with nothing on it."""
    detection = stamp.detect_stamps(MARKED, templates={})

    assert detection.proposed > 0


def test_the_status_is_about_the_registry_and_not_about_the_page():
    """A page with nothing on it and no template is still ``not_configured``.

    The status says what the module was able to do, so a blank page does not
    turn an absent capability into a measurement nobody made.
    """
    detection = stamp.detect_stamps(CLEAN, templates={})

    assert detection.status == stamp.NOT_CONFIGURED
    assert detection.proposed == 0


def test_a_registry_holding_the_mark_names_it_and_says_so():
    """The third status, so the record has one answer per situation, not two."""
    detection = stamp.detect_stamps(MARKED)

    assert detection.status == stamp.MATCHED
    assert [match.template for match in detection.matches] == [ENTRY]
    assert detection.proposed >= len(detection.matches)


def test_no_status_is_named_clean():
    """The vocabulary the task asks for excludes the reading it is stopping.

    ``clean`` would be this module's silence read as a verdict on the document,
    and a status a caller can pass by mistyping is worse than no status at all.
    """
    assert "clean" not in stamp.STATUSES
    assert stamp.STATUSES == (stamp.MATCHED, stamp.NO_MATCH, stamp.NOT_CONFIGURED)


# ---------------------------------------------------------------------------
# What the record refuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        pytest.param("clean", id="the_answer_being_stopped"),
        pytest.param("MATCHED", id="the_wrong_case"),
        pytest.param("", id="empty"),
        pytest.param(None, id="not_a_string"),
    ],
)
def test_a_status_outside_the_three_is_refused(status):
    """A record may only say one of the three things this module can mean."""
    with pytest.raises(stamp.StampError, match="status must be one of"):
        stamp.StampDetection(status=status)


def test_a_matched_answer_that_named_nothing_is_refused():
    """:data:`stamp.MATCHED` with no match in it is the claim being made twice."""
    with pytest.raises(stamp.StampError, match="must name at least one mark"):
        stamp.StampDetection(status=stamp.MATCHED)


@pytest.mark.parametrize(
    "status", [stamp.NO_MATCH, stamp.NOT_CONFIGURED], ids=["measured", "unconfigured"]
)
def test_an_answer_that_named_a_mark_may_not_carry_one_unless_it_is_matched(status):
    """A match under either of the other two statuses is a measurement undone."""
    with pytest.raises(stamp.StampError, match="may not carry a match"):
        stamp.StampDetection(status=status, matches=(_match(),), proposed=1)


def test_a_match_cannot_be_reported_where_no_proposal_was_made():
    """Every match is one proposal, so more matches than proposals is arithmetic
    nobody performed."""
    with pytest.raises(stamp.StampError, match="there cannot be more"):
        stamp.StampDetection(status=stamp.MATCHED, matches=(_match(),), proposed=0)


@pytest.mark.parametrize(
    "matches, proposed, message",
    [
        pytest.param([_match()], 1, "must be a tuple of StampMatch", id="a_list"),
        pytest.param((_match().box,), 1, "must be a tuple of StampMatch", id="a_box"),
        pytest.param((_match(),), True, "whole number of candidates", id="a_bool"),
        pytest.param((_match(),), 1.5, "whole number of candidates", id="a_fraction"),
    ],
)
def test_a_detection_that_is_not_a_measurement_is_refused(matches, proposed, message):
    with pytest.raises(stamp.StampError, match=message):
        stamp.StampDetection(
            status=stamp.MATCHED, matches=matches, proposed=proposed
        )


# ---------------------------------------------------------------------------
# The record the module answers with
# ---------------------------------------------------------------------------


def test_the_module_holding_no_template_says_not_configured_and_not_a_clean_page():
    """The reporting surface is D116's detail, and it must carry the answer.

    A zero here is an absent capability, so the sentence an officer reads is
    the only place left to say so.
    """
    result = stamp.StampModule(templates={}).run(_context(MARKED))

    assert stamp.NOT_CONFIGURED in result.detail
    assert "not a clean page" not in result.detail
    assert result.score == 0.0
    assert result.is_stub is True


def test_the_module_holding_no_template_reports_no_region_for_ink_it_could_not_name():
    """D120's rule holds under the new status: nothing is reported without a
    template behind it, and a proposal is not a finding."""
    result = stamp.StampModule(templates={}).run(_context(MARKED))

    assert result.regions == ()


def test_the_module_holding_the_shipped_registry_is_never_unconfigured():
    """The shipped registry holds marks, so the shipped module is configured."""
    assert stamp.STAMP_TEMPLATES != {}

    result = stamp.StampModule().run(_context(MARKED))

    assert stamp.NOT_CONFIGURED not in result.detail
    assert result.regions != ()


def test_a_registry_that_is_not_one_is_refused_when_the_module_is_built():
    """Construction is where a miswired module is caught, not once per document."""
    with pytest.raises(stamp.StampError, match="must be a mapping"):
        stamp.StampModule(templates=[stamp.STAMP_TEMPLATES[ENTRY]])
