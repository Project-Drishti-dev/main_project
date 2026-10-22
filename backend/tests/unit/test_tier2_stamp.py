"""15.8 -- a stamp on the document is found, and the right template is named.

The claim pinned first is the verification the task names: a mark printed on a
page is located by the detector, compared against the committed registry, and
the template it matches is named.  The rest holds that detection proposes and
matching disposes, that the comparison is independent of the size the stamp was
printed at, that the registry is read-only, and that the module ships labelled
and unregistered -- D120.

The capture is synthetic on purpose: a text page written once at quality 95,
with a mark from the registry pasted onto it and the file written again.  Its
every constant was measured against it, and the mark is one this repository
draws -- no authority's stamp is committed, so nothing here claims to have
recognised one.
"""

import dataclasses
import uuid

import cv2
import numpy as np
import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base, stamp

SCREENING_ID = uuid.UUID("2f7b6d31-9c4a-4e15-9b72-1d4c8af60e35")
WIDTH, HEIGHT = 640, 480
SEED = 20261008
PAGE_QUALITY = 95
ENTRY = "demo_entry_stamp"
EXIT = "demo_exit_stamp"
#: The name every mark this repository ships carries, so no test can pass
#: against a template somebody else's stamp was quietly committed under.
DEMO_PREFIX = "demo_"
#: Where the photograph and each mark sit, clear of one another so the
#: detector's closing kernel is never handed a stamp it bridged to the photo.
PHOTO_AT = (30, 80, 190, 150)
FIRST_AT = (420, 300, 140, 140)
SECOND_AT = (300, 40, 140, 140)


def _page():
    """A page carrying text and scattered marks, so it has texture."""
    rng = np.random.default_rng(SEED)
    gray = np.full((HEIGHT, WIDTH), 236, np.uint8)
    gray[0:44, :] = np.linspace(202, 248, WIDTH, dtype=np.uint8)
    y = 70
    while y < 430:
        x = 30
        while x < 400:
            length = int(rng.integers(8, 34))
            cv2.line(gray, (x, y), (x + length, y), int(rng.integers(15, 90)),
                     int(rng.integers(1, 3)), cv2.LINE_AA)
            x += length + int(rng.integers(5, 11))
        y += 12
    for _ in range(200):
        centre = (int(rng.integers(420, 610)), int(rng.integers(74, 330)))
        cv2.circle(gray, centre, int(rng.integers(2, 14)), int(rng.integers(30, 230)), -1)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _written(frame):
    """Return ``frame`` as a codec wrote it and read it back."""
    encoded, buffer = cv2.imencode(
        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), PAGE_QUALITY]
    )
    assert encoded, "the test's own JPEG encoder refused its frame"
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _with_photo(page):
    """Return ``page`` carrying a colour photograph, which is chromatic too."""
    x, y, width, height = PHOTO_AT
    rng = np.random.default_rng(7)
    page[y : y + height, x : x + width] = rng.integers(40, 220, (height, width, 3)).astype(
        np.uint8
    )
    return page


def _at(page, template_name, at):
    """Return ``page`` with ``template_name``'s mark printed at ``at``."""
    art = stamp.STAMP_TEMPLATES[template_name].image
    x, y, width, height = at
    scaled = cv2.resize(art, (width, height), interpolation=cv2.INTER_AREA)
    page[y : y + height, x : x + width] = scaled
    return page


#: A gray page with no ink at all, one with a colour photograph on it, and the
#: two marks on their own pages and together on one.
CLEAN = _written(_page())
PHOTO_ONLY = _written(_with_photo(_page().copy()))
ENTRY_PAGE = _written(_at(_page(), ENTRY, FIRST_AT))
EXIT_PAGE = _written(_at(_page(), EXIT, SECOND_AT))
BOTH_PAGE = _written(_at(_at(_page(), ENTRY, FIRST_AT), EXIT, SECOND_AT))

#: The same mark printed small and large, which is what :data:`stamp.CANONICAL`
#: is for.  Both pages carry the entry mark and nothing else.
ENTRY_SMALL = _written(_at(_page(), ENTRY, (420, 300, 98, 98)))
ENTRY_LARGE = _written(_at(_page(), ENTRY, (420, 280, 182, 182)))


def _context(image):
    """A context carrying the working frame the seam hands a module."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=image,
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


def _holds(at, candidate_box, slack=8):
    """Whether ``candidate_box`` is where ``at`` says the mark was printed."""
    x, y, width, height = candidate_box
    return (
        abs(x - at[0]) <= slack
        and abs(y - at[1]) <= slack
        and abs(width - at[2]) <= slack
        and abs(height - at[3]) <= slack
    )


# ---------------------------------------------------------------------------
# The task's own claim: the mark is found and its template is named
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "page, named",
    [
        pytest.param(ENTRY_PAGE, ENTRY, id="entry_mark"),
        pytest.param(EXIT_PAGE, EXIT, id="exit_mark"),
    ],
)
def test_a_stamp_on_the_page_is_found_and_its_own_template_is_named(page, named):
    """15.8's verification, once per mark: located, and named as itself.

    The exit mark is on the page here, so a matcher that answered with
    whichever template it held first would name the entry one and fail.
    """
    detection = stamp.detect_stamps(page)

    assert [match.template for match in detection.matches] == [named]
    assert detection.matches[0].score >= stamp.MATCH_LEVEL


def test_the_mark_is_located_where_it_was_printed():
    """A named mark nobody could point at on the document locates nothing."""
    matches = stamp.detect_stamps(ENTRY_PAGE).matches

    assert _holds(FIRST_AT, matches[0].box)


def test_both_marks_on_one_page_are_both_found_and_named_apart():
    """Two marks are two findings, and neither is allowed to stand for the other."""
    matches = stamp.detect_stamps(BOTH_PAGE).matches

    assert sorted(match.template for match in matches) == sorted([ENTRY, EXIT])
    assert _holds(FIRST_AT, next(m.box for m in matches if m.template == ENTRY))
    assert _holds(SECOND_AT, next(m.box for m in matches if m.template == EXIT))


def test_a_candidate_scores_its_own_template_above_the_one_it_is_not():
    """The score is what separates the marks, so the margin is the claim."""
    candidate = stamp.find_stamps(ENTRY_PAGE)[0]

    scores = {
        name: stamp.match_score(ENTRY_PAGE, candidate, template)
        for name, template in stamp.STAMP_TEMPLATES.items()
    }

    assert scores[ENTRY] >= stamp.MATCH_LEVEL
    assert scores[EXIT] < stamp.MATCH_LEVEL


@pytest.mark.parametrize(
    "page, named",
    [
        pytest.param(ENTRY_SMALL, ENTRY, id="printed_small"),
        pytest.param(ENTRY_LARGE, ENTRY, id="printed_large"),
    ],
)
def test_the_same_mark_is_named_whatever_size_it_was_printed_at(page, named):
    """:data:`stamp.CANONICAL` is what makes the size the stamp was printed at
    irrelevant, and a matcher that did not resample would read one of these two
    as the wrong mark."""
    detection = stamp.detect_stamps(page)

    assert [match.template for match in detection.matches] == [named]


def test_a_print_that_is_too_small_to_mean_anything_is_not_offered():
    """A candidate below :data:`stamp.MIN_SIDE` has too few pixels for the grid.

    Offering it would hand a caller a match computed from a stamp smaller than
    the comparison it was made on.
    """
    tiny = _written(_at(_page(), ENTRY, (420, 300, 30, 30)))

    assert stamp.find_stamps(tiny) == ()


# ---------------------------------------------------------------------------
# Detection proposes, matching disposes
# ---------------------------------------------------------------------------


def test_a_gray_page_holds_no_ink_and_nothing_is_proposed():
    """Ink is chromatic, so a page with none carries no candidate at all."""
    assert stamp.chroma(CLEAN).max() == 0.0
    assert stamp.find_stamps(CLEAN) == ()
    assert stamp.detect_stamps(CLEAN).matches == ()


def test_a_colour_photograph_is_proposed_and_then_declined():
    """The realistic false positive is proposed and refused by the comparison.

    Both halves matter: a detector that never proposed the photograph would be
    one that cannot find a stamp beside it, and a registry that reported every
    proposal would report this one.
    """
    candidates = stamp.find_stamps(PHOTO_ONLY)
    matches = stamp.detect_stamps(PHOTO_ONLY).matches

    assert candidates != ()
    assert matches == ()


def test_a_proposal_is_refused_when_the_registry_is_one_the_page_cannot_match():
    """The registry decides what a mark is, so a page outranks nothing.

    With no templates at all there is nothing to compare a candidate against,
    and 15.9 reports that absence as ``not_configured`` rather than as a page
    with nothing on it (D121); what it must not do is report the candidate as
    matched.
    """
    detection = stamp.detect_stamps(ENTRY_PAGE, templates={})

    assert detection.matches == ()
    assert stamp.find_stamps(ENTRY_PAGE) != ()


# ---------------------------------------------------------------------------
# The registry: read-only, and every mark in it drawn here
# ---------------------------------------------------------------------------


def test_the_registry_is_read_only():
    """A set a screening draws from cannot be widened after import, as
    :data:`~app.pipeline.tier2.base.DEEP_MODULES` cannot be."""
    with pytest.raises(TypeError):
        stamp.STAMP_TEMPLATES["another"] = stamp.STAMP_TEMPLATES[ENTRY]


def test_the_registry_holds_both_marks_and_names_them_in_order():
    """The names are what a result is reported under, so they are pinned."""
    assert stamp.TEMPLATE_NAMES == (ENTRY, EXIT)
    assert set(stamp.STAMP_TEMPLATES) == set(stamp.TEMPLATE_NAMES)


def test_every_shipped_mark_is_one_this_repository_drew():
    """The honesty claim, held mechanically rather than in prose.

    No authority's stamp is committed, so every name a real one would have been
    registered under is absent; a template added later under a real name fails
    this rather than being quietly believed.
    """
    assert all(name.startswith(DEMO_PREFIX) for name in stamp.STAMP_TEMPLATES)


def test_a_template_is_cropped_to_its_own_ink_and_not_to_the_sheet_it_was_drawn_on():
    """The regression this task found by reading its own module back.

    A template cropped to the closed mask carries a border the candidate it is
    compared against does not, and the two then sit on the canonical grid
    differently -- which the score shows and the size pins first.
    """
    drawn = np.full((200, 200, 3), 255, np.uint8)
    cv2.circle(drawn, (100, 100), 40, (190, 60, 40), 3)

    template = stamp.make_template("a_mark", drawn)
    left, top, width, height = stamp.ink_extent(drawn)

    assert template.size == (width, height)
    assert 0 < max(template.size) < 200


def test_a_template_is_frozen_and_its_arrays_are_read_only():
    """A registry nobody may edit is the whole of a registry, arrays included."""
    template = stamp.STAMP_TEMPLATES[ENTRY]

    with pytest.raises(dataclasses.FrozenInstanceError):
        template.name = "another"
    with pytest.raises(ValueError):
        template.image[0, 0, 0] = 0
    with pytest.raises(ValueError):
        template.canonical[0, 0] = 0.0


@pytest.mark.parametrize(
    "draw",
    [
        pytest.param(lambda art: None, id="blank"),
        pytest.param(lambda art: cv2.line(art, (10, 10), (180, 180), (60, 60, 60), 2),
                     id="gray_ink"),
    ],
)
def test_a_sheet_with_no_findable_ink_is_not_a_template(draw):
    """A template carrying no ink would match nothing by construction."""
    art = np.full((200, 200, 3), 255, np.uint8)
    draw(art)

    with pytest.raises(stamp.StampError, match="no ink"):
        stamp.make_template("a_mark", art)


# ---------------------------------------------------------------------------
# What the module is refused, and what it answers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "image",
    [
        pytest.param("not an array", id="not_an_array"),
        pytest.param(np.zeros((10, 10), np.uint8), id="gray_plane"),
        pytest.param(np.zeros((10, 10, 2), np.uint8), id="two_channels"),
        pytest.param(np.zeros((10, 10, 3), np.float64), id="not_8_bit"),
        pytest.param(np.zeros((0, 10, 3), np.uint8), id="no_rows"),
    ],
)
def test_a_frame_this_cannot_measure_is_refused(image):
    """A frame this module cannot read is not answered as a page with no stamp.

    A grayscale plane is the sharpest case: it holds no chromatic ink by
    construction, so answering ``clean`` would be a claim about the module
    rather than about the document.
    """
    with pytest.raises(stamp.StampError):
        stamp.find_stamps(image)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        pytest.param({"level": -1}, "level must sit", id="level_below_zero"),
        pytest.param({"level": 256}, "level must sit", id="level_above_255"),
        pytest.param({"level": True}, "level must be a real number", id="level_is_a_bool"),
        pytest.param({"close": 0}, "odd number", id="close_is_zero"),
        pytest.param({"close": 16}, "odd number", id="close_is_even"),
        pytest.param({"close": 1.5}, "whole number", id="close_is_a_fraction"),
    ],
)
def test_a_mask_that_cannot_be_drawn_is_refused(kwargs, message):
    """Every threshold is checked rather than clamped, as OpenCV would."""
    with pytest.raises(stamp.StampError, match=message):
        stamp.ink_mask(ENTRY_PAGE, **kwargs)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        pytest.param({"min_ink": 0}, "min_ink must be at least", id="no_ink_wanted"),
        pytest.param({"min_side": True}, "min_side must be a whole number", id="side_is_a_bool"),
    ],
)
def test_a_detector_that_cannot_be_asked_is_refused(kwargs, message):
    with pytest.raises(stamp.StampError, match=message):
        stamp.find_stamps(ENTRY_PAGE, **kwargs)


@pytest.mark.parametrize(
    "box, ink",
    [
        pytest.param((0, 0, 10), 5, id="three_numbers"),
        pytest.param((0, 0, 10.5, 10), 5, id="a_fractional_pixel"),
        pytest.param((0, 0, 0, 10), 5, id="no_width"),
        pytest.param((-1, 0, 10, 10), 5, id="off_the_left"),
        pytest.param((0, 0, 10, 10), -1, id="negative_ink"),
    ],
)
def test_a_candidate_that_is_not_a_whole_pixel_box_is_refused(box, ink):
    with pytest.raises(stamp.StampError):
        stamp.StampCandidate(box=box, ink=ink)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        pytest.param({"template": " ", "score": 0.9}, "must name its template",
                      id="no_template_named"),
        pytest.param({"template": ENTRY, "score": 1.5}, "score must sit", id="score_above_one"),
        pytest.param({"template": ENTRY, "score": True}, "score must be a real number",
                      id="score_is_a_bool"),
    ],
)
def test_a_match_that_is_not_a_measured_one_is_refused(kwargs, message):
    with pytest.raises(stamp.StampError, match=message):
        stamp.StampMatch(box=(0, 0, 10, 10), **kwargs)


@pytest.mark.parametrize(
    "templates, message",
    [
        pytest.param([], "must be a mapping", id="a_list"),
        pytest.param({ENTRY: object()}, "is not a StampTemplate", id="not_a_template"),
        pytest.param({ENTRY: stamp.STAMP_TEMPLATES[EXIT]}, "registered under a different name",
                     id="registered_under_another_name"),
    ],
)
def test_a_registry_that_is_not_one_is_refused(templates, message):
    with pytest.raises(stamp.StampError, match=message):
        stamp.detect_stamps(ENTRY_PAGE, templates=templates)


def test_a_score_computed_off_something_other_than_a_record_is_refused():
    """Neither half of the comparison may be handed a loose value."""
    candidate = stamp.find_stamps(ENTRY_PAGE)[0]

    with pytest.raises(stamp.StampError, match="must be a StampCandidate"):
        stamp.match_score(ENTRY_PAGE, (0, 0, 10, 10), stamp.STAMP_TEMPLATES[ENTRY])
    with pytest.raises(stamp.StampError, match="must be a StampTemplate"):
        stamp.match_score(ENTRY_PAGE, candidate, "demo_entry_stamp")


# ---------------------------------------------------------------------------
# The record the module answers with
# ---------------------------------------------------------------------------


def test_the_regions_are_whole_pixel_boxes_in_the_corner_order_copy_move_promised():
    """D119 stated the corner order once; this module states it again and holds."""
    matches = stamp.detect_stamps(ENTRY_PAGE).matches
    polygon = stamp.region_polygons(matches)[0]
    x, y, width, height = matches[0].box

    assert polygon == ((x, y), (x + width, y), (x + width, y + height), (x, y + height))
    assert all(
        isinstance(corner, int)
        for point in polygon
        for corner in point
    )


def test_regions_that_are_not_matches_are_refused():
    with pytest.raises(stamp.StampError, match="tuple of StampMatch"):
        stamp.region_polygons([stamp.detect_stamps(ENTRY_PAGE).matches[0].box])


def test_the_module_answers_the_deep_result_the_seam_froze():
    """The claim 15.1's seam makes and 15.2 froze, held over this module."""
    result = stamp.StampModule().run(_context(ENTRY_PAGE))

    assert isinstance(result, base.DeepResult)
    assert result.module == stamp.MODULE_NAME
    assert result.score >= stamp.MATCH_LEVEL
    assert len(result.regions) == 1
    assert result.regions == stamp.region_polygons(stamp.detect_stamps(ENTRY_PAGE).matches)


def test_the_module_ships_labelled_and_says_what_the_registry_is():
    """A name for a mark this repository drew is not authentication, and the
    detail an officer reads is where that has to be said."""
    result = stamp.StampModule().run(_context(ENTRY_PAGE))

    assert result.is_stub is True
    assert result.model_version == stamp.MODEL_VERSION
    assert ENTRY in result.detail
    assert "not an authentication" in result.detail


def test_a_page_with_nothing_on_it_answers_zero_and_says_it_measured():
    """Zero here is a measurement and not a pass, so the detail says so.

    D115's rule one tier up: an absent capability stays visible rather than
    being read as a clean document.
    """
    result = stamp.StampModule().run(_context(PHOTO_ONLY))

    assert result.score == 0.0
    assert result.regions == ()
    assert "not a clean page" in result.detail


def test_the_module_is_shipped_and_is_not_registered():
    """D115 and D119's reason hold for this module too: a five-of-five registry
    would let ``ran`` claim the tier stood behind all of it."""
    assert stamp.MODULE_NAME not in base.MODULE_NAMES
    assert base.MODULE_NAMES == ()
    assert base.DEEP_MODULES == {}
