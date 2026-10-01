"""6.4 -- a list hit, one flag, and the two severities the task names.

`tasks.md` 6.4 asks for two things and they are the two halves of this file:
every watchlist hit becomes a flag, and the three kinds do not come out the
same.  A blacklist hit is a hard fail, a stolen-document hit is heavy and is
not, and an identity_seen hit is neither of those things at all.

**The two severities are read off the seed, not typed here.**  The named tests
below drive 5.11's own :class:`~app.seed.mock_watchlist.MockWatchlist` with a
page whose document number is one the seed carries, so a finding that fired
for the wrong reason would have to be the seed's rows being wrong.

**What is pinned hardest is what does not reach the flag.**  ``D13`` says a
hit names an entry and never the value that matched it, and this is the last
place in the pipeline where a match is in hand -- so a flag carrying the
document number, the name or the entry id would be putting identity data on
the dashboard, in the log and on the officer's screen at once.

**The runner does not import the connector.**  It is handed one, and that is
asserted by walking its imports, because a runner that knew about the seed
could not be given a live feed without an edit.
"""

import ast
import datetime
import importlib.resources
import json
import pathlib

import pytest

from app.pipeline.tier0 import (
    dates,
    document,
    mrz,
    mrz_region,
    runner,
    td1,
    td2,
    td3,
)
from app.pipeline.tier0.mrz import MrzValueError
from app.risk import flag_ids, watchlist as watchlist_seam
from app.seed import mock_watchlist
from tests.fixtures import mrz_images

run_tier0 = runner.run_tier0
MockWatchlist = mock_watchlist.MockWatchlist

#: The three layouts, read out of Part 3's own table rather than counted out
#: longhand here, because a field name typed into this file is a second copy
#: of the table the pipeline already holds.
LAYOUTS = {"TD1": td1.TD1, "TD2": td2.TD2, "TD3": td3.TD3}

#: The reference 5.8's own suite measures against.  The specimen's date of
#: birth is ``740812``, which this day reads as 1974-08-12 -- 5.6's reading
#: and not a constant this file wrote.
REFERENCE = datetime.date(2026, 9, 30)


def seed_number(entry_id):
    """The document number the seed's one entry of ``entry_id`` is found by."""
    text = (
        importlib.resources.files(mock_watchlist.SEED_PACKAGE)
        .joinpath(mock_watchlist.SEED_RESOURCE)
        .read_text(encoding="utf-8")
    )
    for row in json.loads(text)["entries"]:
        if row["entry_id"] == entry_id:
            return row["document_number"]
    raise KeyError(entry_id)


def a_hit(kind, entry_id="ENTRY-0001"):
    """A :class:`WatchlistHit` of ``kind``, with the ``matched_on`` it must carry."""
    return watchlist_seam.WatchlistHit(
        kind, entry_id, watchlist_seam.KEY_EACH_KIND_IS_FOUND_BY[kind]
    )


def parsed_page(name="TD3", zone=None):
    """A drawn page, and the parse a caller would hand over.

    **The zone is read back off the pixels before it is parsed**, so the
    document under test is the one the frame holds rather than the one this
    file typed.
    """
    zone = mrz_images.SPECIMENS[name] if zone is None else zone
    page = mrz_images.render_format(name, lines=tuple(zone))
    read = mrz_images.read_zone(page)
    assert read == tuple(zone)
    return page, document.parse_mrz(read)


def page_with_number(entry_id):
    """The TD3 specimen carrying the document number the seed's row holds.

    **The number is changed on the drawn page, read back off the pixels, and
    the two digits the change invalidates are recomputed.**  This used to
    leave them broken, which was harmless while nothing but a blacklist
    answered for ``hard_failed``; 6.5 makes a failed printed check digit a
    hard fail in its own right, so a page with two broken digits on it would
    have turned every test below that says *a stolen hit does not override*
    into a claim about a document with three hard fails rather than about the
    hit.  **The digits are recomputed with Part 1's arithmetic over Part 3's
    own spans**, and the outcome is asserted, so a page this returns is one
    where the list is the only thing wrong with the document.
    """
    number = seed_number(entry_id)
    zone = list(mrz_images.SPECIMENS["TD3"])
    assert zone[1][0] != number, "the substitution must change something"
    zone[1] = number + zone[1][len(number) :]
    zone[1] = _agreeing_digits(zone[1])
    page, parsed = parsed_page("TD3", tuple(zone))
    assert all(row.passed for row in parsed.check_digit_results), (
        "the substituted number must leave every printed digit agreeing"
    )
    return page, parsed


def _agreeing_digits(line_2):
    """Return ``line_2`` with its number's own digit and its composite fixed.

    **Both positions are read out of :data:`td3.TD3_LINE_2` rather than
    counted**, because a position typed longhand here is a second copy of the
    table the pipeline already holds, and **the document number's digit is
    repaired before the composite is computed** because position 10 sits
    inside the composite's own span.
    """
    line_2 = _with_digit(
        line_2, "document_number_check_digit", _span(line_2, "document_number")
    )
    return _with_digit(
        line_2, "composite_check_digit", td3.td3_composite_input(line_2)
    )


def _span(line_2, field):
    """Return the characters ``line_2`` prints for ``field``."""
    start, end = td3.TD3_LINE_2[field]
    return line_2[start - 1 : end]


def _with_digit(line_2, field, text):
    """Return ``line_2`` with ``field``'s printed digit set to ``text``'s."""
    start, end = td3.TD3_LINE_2[field]
    return line_2[: start - 1] + str(mrz.check_digit(text)) + line_2[end:]


def only(flags, flag_id):
    """The one flag in ``flags`` carrying ``flag_id``."""
    found = [flag for flag in flags if flag.id == flag_id]
    assert len(found) == 1, f"expected one {flag_id}, found {len(found)}"
    return found[0]


def said(result, flag):
    """Every string one result says about a document: the flag and the reason."""
    return (
        flag.id,
        flag.label,
        flag.expected or "",
        flag.found or "",
        flag.reason,
        flag.source_module,
        flag.field or "",
        result.hard_fail_reason or "",
    )


class RecordingWatchlist(watchlist_seam.Watchlist):
    """A connector that records what it was asked and answers what it is given.

    **The three keys are recorded as they arrive, by keyword**, because the
    seam makes them keyword-only and a test that read them positionally would
    be testing a call the runner cannot make.
    """

    def __init__(self, hits=()):
        """Keep the answer and forget everything else, and return ``None``."""
        self.asked = []
        self.answer = list(hits)

    def lookup(self, *, document_number, name, dob):
        """Record the three keys, and answer with what this connector was built with."""
        self.asked.append(
            {"document_number": document_number, "name": name, "dob": dob}
        )
        return self.answer


# --- the named behaviour: the two severities --------------------------------


def test_a_blacklist_hit_is_a_hard_fail_with_the_document_number_highlighted():
    """`tasks.md` 6.4's own verify, on the seed's own blacklist row.

    **The abstract names a blacklist match beside a broken checksum** as the
    finding that exits straight to High Risk with the reason recorded, and
    names the offending field as highlighted -- so the override and the box
    over the document number are one claim here rather than two.
    """
    page, parsed = page_with_number("BLACKLIST-0001")

    result = run_tier0(page.image, None, REFERENCE, parsed, MockWatchlist())
    flag = only(result.flags, flag_ids.WATCHLIST_HIT)

    assert result.hard_failed is True
    assert result.hard_fail_reason == flag.label
    assert flag.field == "document_number"
    assert flag.weight_band == "high"
    assert flag.region == mrz_region.field_regions(
        parsed, mrz_region.detect_mrz(page.image).lines
    )["document_number"]


def test_a_stolen_document_hit_is_heavy_and_is_not_a_hard_fail():
    """The second half of 6.4's verify, on the seed's own stolen row.

    **A stolen document is a fact about a document rather than about the
    person holding it**, which is the seam's own reason the kind exists beside
    the blacklist: the same ``high`` band, because the finding is as certain
    as the other, and no override, because what a stolen document means is the
    officer's call and not this module's.
    """
    page, parsed = page_with_number("STOLEN-0001")

    result = run_tier0(page.image, None, REFERENCE, parsed, MockWatchlist())
    flag = only(result.flags, flag_ids.WATCHLIST_STOLEN_DOCUMENT)

    assert flag.weight_band == "high"
    assert flag.field == "document_number"
    assert flag.region is not None
    assert result.hard_failed is False
    assert result.hard_fail_reason is None


def test_the_two_severities_are_the_two_ids_and_nothing_else():
    """The whole severity claim, held in one assertion.

    **Read out of the runner's own table rather than a copy of it**, so a kind
    that became a hard fail, or stopped being one, is one edit there and a
    failing test here.  A stolen hit and a blacklist hit sit in the same band
    on purpose: the band names how heavy a finding is and is not the question.
    """
    severity = {}
    for kind, row in runner._WATCHLIST_FLAG.items():
        severity[kind] = (row[0], row[2], row[4])

    assert runner._WATCHLIST_HARD_FAIL_IDS == {flag_ids.WATCHLIST_HIT}
    assert severity == {
        watchlist_seam.BLACKLIST: (flag_ids.WATCHLIST_HIT, "high", True),
        watchlist_seam.STOLEN_DOCUMENT: (
            flag_ids.WATCHLIST_STOLEN_DOCUMENT,
            "high",
            False,
        ),
        watchlist_seam.IDENTITY_SEEN: (
            flag_ids.WATCHLIST_IDENTITY_SEEN,
            "review",
            False,
        ),
    }


def test_an_identity_hit_is_a_review_about_no_one_field():
    """The third kind is a lookup and not a verdict, and it says so three ways.

    **``review`` is the band ``tasks.md`` reserves for a case that goes to a
    person rather than being rejected automatically**, which is what a
    previous screening is: a lead.  It names no field because it is about a
    name and a date of birth together, and 4.12 has no box for a pair of
    fields, so 23.6 is what lists such a finding honestly.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist([a_hit(watchlist_seam.IDENTITY_SEEN)])

    flag = only(
        run_tier0(page.image, None, REFERENCE, parsed, connector).flags,
        flag_ids.WATCHLIST_IDENTITY_SEEN,
    )

    assert flag.weight_band == "review"
    assert flag.value == 1.0
    assert flag.confidence == 1.0
    assert flag.field is None
    assert flag.region is None


# --- nothing about the person holding the document reaches the flag ---------


def test_nothing_the_document_printed_reaches_the_flag_or_the_reason():
    """`D13` at the last place a match is in hand.

    **The document number, the printed name, the surname, the given names and
    the date of birth are each checked against every string the result says**
    -- the flag's own fields and the hard-fail reason.
    """
    page, parsed = page_with_number("BLACKLIST-0001")
    result = run_tier0(page.image, None, REFERENCE, parsed, MockWatchlist())
    flag = only(result.flags, flag_ids.WATCHLIST_HIT)

    secrets = (
        parsed.document_number,
        parsed.name,
        parsed.surname,
        parsed.date_of_birth,
    ) + tuple(parsed.given_names)

    assert secrets
    assert not [
        (secret, text)
        for secret in secrets
        if secret
        for text in said(result, flag)
        if secret in text
    ]


def test_an_entry_id_that_reads_as_a_name_still_never_reaches_the_flag():
    """The half of `D13` that is a field set rather than a character check.

    **``entry_id``'s charset is a guard and not a guarantee** -- 5.9's own test
    admits a one-word name passes it -- so a connector whose rows name people
    in the one field it is given must not put those names on a flag.  The row
    reference belongs to the hit; the prose belongs to this project.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist([a_hit(watchlist_seam.BLACKLIST, "MALHOTRA")])

    result = run_tier0(page.image, None, REFERENCE, parsed, connector)
    flag = only(result.flags, flag_ids.WATCHLIST_HIT)

    assert not [text for text in said(result, flag) if "MALHOTRA" in text]


@pytest.mark.parametrize("kind", sorted(watchlist_seam.HIT_KINDS))
def test_the_reason_is_written_here_from_the_hit_s_own_two_halves(kind):
    """The prose is this project's, and it names the two closed vocabularies.

    **A live feed's own free text is where identity data would ride in**, so
    the reason is built from :attr:`WatchlistHit.kind` and
    :attr:`WatchlistHit.matched_on` and from nothing else -- one of three kind
    names and one of two key names, neither of which is a value a document
    printed.
    """
    hit = a_hit(kind)

    assert runner._watchlist_reason(hit) == (
        f"an entry of kind {hit.kind} matched on {hit.matched_on}"
    )


def test_the_found_half_is_the_kind_and_the_expected_half_is_nothing():
    """The two halves of a comparison whose expected state is an empty flag.

    **A clean document produces no flag at all**, so there is no expected
    string to print against: ``None`` says the flag was not expected to
    exist, and the kind is the whole of what the list answered with.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist([a_hit(watchlist_seam.IDENTITY_SEEN)])

    flag = only(
        run_tier0(page.image, None, REFERENCE, parsed, connector).flags,
        flag_ids.WATCHLIST_IDENTITY_SEEN,
    )

    assert flag.expected is None
    assert flag.found == watchlist_seam.IDENTITY_SEEN


def test_a_finding_names_the_seam_that_defined_it_and_not_the_connector():
    """``source_module`` is the module that says what a hit is.

    **Which list answered is a deployment concern and not part of the
    finding**: the seed, a stolen-document feed and a blacklist service are
    three implementations of one seam, and the claim is "a list answered with
    an entry of this kind" rather than a vendor name.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist([a_hit(watchlist_seam.STOLEN_DOCUMENT)])

    flag = only(
        run_tier0(page.image, None, REFERENCE, parsed, connector).flags,
        flag_ids.WATCHLIST_STOLEN_DOCUMENT,
    )

    assert flag.source_module == "app.risk.watchlist"
    assert flag.tier == 0


# --- one flag per hit, and nothing read into the order ----------------------


def test_two_entries_are_two_flags_in_the_order_they_were_answered():
    """A document on two lists owes an officer both findings, separately.

    **The order is kept and nothing is read into it**: 5.9 promises no order,
    so the flags come back as the connector gave them and each severity is
    read off its own hit's kind.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist(
        [
            a_hit(watchlist_seam.STOLEN_DOCUMENT, "STOLEN-0002"),
            a_hit(watchlist_seam.IDENTITY_SEEN, "IDENTITY-0001"),
        ]
    )

    flags = run_tier0(page.image, None, REFERENCE, parsed, connector).flags

    assert [flag.id for flag in flags] == [
        flag_ids.WATCHLIST_STOLEN_DOCUMENT,
        flag_ids.WATCHLIST_IDENTITY_SEEN,
    ]
    assert [flag.found for flag in flags] == [
        watchlist_seam.STOLEN_DOCUMENT,
        watchlist_seam.IDENTITY_SEEN,
    ]


def test_a_stolen_hit_answered_first_does_not_become_the_hard_fail():
    """The accident 5.9's "no order is promised" is written to prevent.

    **A rule that read the first hit as the serious one would report a
    document on a stolen list as blacklisted**, because a connector is free to
    answer in either order.  Here the heavy non-hard hit comes first and the
    override still comes from the blacklist entry two places down.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist(
        [
            a_hit(watchlist_seam.STOLEN_DOCUMENT, "STOLEN-0001"),
            a_hit(watchlist_seam.BLACKLIST, "BLACKLIST-0001"),
        ]
    )

    result = run_tier0(page.image, None, REFERENCE, parsed, connector)

    assert [flag.id for flag in result.flags] == [
        flag_ids.WATCHLIST_STOLEN_DOCUMENT,
        flag_ids.WATCHLIST_HIT,
    ]
    assert result.hard_failed is True
    assert result.hard_fail_reason == "The document number is on the blacklist."


def test_the_hard_fail_reason_does_not_depend_on_which_list_answered_first():
    """Two runs over one document, two answers, one identical reason.

    **An audit reads the reason and not the order**, so a reason that came out
    differently depending on a connector's internal ordering would be a reason
    nobody could rely on.
    """
    page, parsed = parsed_page()
    reasons = set()
    orders = (
        [
            a_hit(watchlist_seam.BLACKLIST, "BLACKLIST-0001"),
            a_hit(watchlist_seam.STOLEN_DOCUMENT, "STOLEN-0001"),
        ],
        [
            a_hit(watchlist_seam.STOLEN_DOCUMENT, "STOLEN-0001"),
            a_hit(watchlist_seam.BLACKLIST, "BLACKLIST-0001"),
        ],
    )
    for hits in orders:
        connector = RecordingWatchlist(hits)
        result = run_tier0(page.image, None, REFERENCE, parsed, connector)
        reasons.add(result.hard_fail_reason)

    assert reasons == {"The document number is on the blacklist."}


# --- the three keys, and what was not read ---------------------------------


def test_the_three_keys_are_asked_by_name_with_the_values_as_printed():
    """The lookup's whole interface, shown being called.

    **Nothing is tidied, folded or stripped of filler**, on 5.11's own ground:
    the runner asks about what the document printed, and a connector that
    spells names differently answers about itself.  **The name is the printed
    field with its padding**, which is the honest half of a seam no list can
    yet be asked by identity until a tidied single-string spelling exists -- a
    gap recorded in `HANDOVER.md` rather than papered over with a join invented
    here.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist()

    run_tier0(page.image, None, REFERENCE, parsed, connector)

    assert len(connector.asked) == 1
    asked = connector.asked[0]
    assert set(asked) == {"document_number", "name", "dob"}
    assert asked["document_number"] == parsed.document_number
    assert asked["name"] == parsed.name
    assert parsed.name.endswith("<")
    assert asked["dob"] == dates.dob_result(parsed.date_of_birth, REFERENCE).birth
    assert asked["dob"] == datetime.date(1974, 8, 12)


def test_a_date_of_birth_is_the_injected_reference_s_reading_and_not_the_clock():
    """Two references, two centuries, and no day read from anywhere else.

    **``740812`` read in 2026 is 1974 and read in 1950 is 1874**, so the day a
    list is asked about is 5.6's reading of the day the caller injected.  A
    screening whose date of birth differed depending on when it ran would not
    be a finding.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist()

    run_tier0(page.image, None, REFERENCE, parsed, connector)
    run_tier0(page.image, None, datetime.date(1950, 9, 30), parsed, connector)

    assert [asked["dob"] for asked in connector.asked] == [
        datetime.date(1974, 8, 12),
        datetime.date(1874, 8, 12),
    ]


def test_no_injected_reference_date_asks_no_list_about_a_date_of_birth():
    """``None`` is a key that is not checked, and the other two still are.

    **5.6's century is resolved against a day this module is not allowed to
    read**, so a screening that injected none asks about the document number
    and the name and leaves the third key alone -- which is the half a
    blacklist hit comes from, and is not a reason to skip the list.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist()

    run_tier0(page.image, None, None, parsed, connector)

    assert connector.asked[0]["dob"] is None
    assert connector.asked[0]["document_number"] == parsed.document_number


def test_a_field_a_format_does_not_print_is_passed_as_none():
    """A TD1 prints no name, and the key is asked with nothing.

    **A ``None`` is a key that is not checked and is never a hit**, so a TD1
    is screened against the document-number lists and is simply not asked
    about the identity one.  Dropping the key instead would be a question
    nobody asked, and 5.9 makes all three required so the two cannot be
    confused.
    """
    page, parsed = parsed_page("TD1")
    connector = RecordingWatchlist()

    run_tier0(page.image, None, REFERENCE, parsed, connector)

    assert parsed.name is None
    assert set(connector.asked[0]) == {"document_number", "name", "dob"}
    assert connector.asked[0]["name"] is None
    assert connector.asked[0]["document_number"] == parsed.document_number


def test_a_date_of_birth_no_rule_can_read_is_asked_about_as_nothing():
    """A date that is not six digits is a key that is not checked.

    **``parse_date`` answers ``None`` for characters that are not digits**, so
    5.6's answer is ``UNDETERMINED`` and the day is ``None``.  The document is
    still asked about by its document number, which is where a blacklist hit
    comes from -- an identity the document cannot express is not a reason to
    skip the lists it can be found on.
    """
    zone = list(mrz_images.SPECIMENS["TD3"])
    zone[1] = zone[1][:13] + "AAAAAA" + zone[1][19:]
    page, parsed = parsed_page("TD3", tuple(zone))
    connector = RecordingWatchlist()

    unreadable = dates.dob_result(parsed.date_of_birth, REFERENCE)
    run_tier0(page.image, None, REFERENCE, parsed, connector)

    assert unreadable.status == dates.UNDETERMINED
    assert connector.asked[0]["dob"] is None
    assert connector.asked[0]["document_number"] == parsed.document_number


# --- no list, and no parse: two silences that are not passes ---------------


def test_a_screening_with_no_list_wired_reports_no_watchlist_findings():
    """The same document, the same seed rows, and a list nobody passed.

    **A list that was not asked is not a list that cleared the document**, and
    from here the two look identical: the measurement stands, and there is no
    watchlist finding.  Whether a list is wired is a deployment question, and
    this test says the runner does not invent an answer to it.
    """
    page, parsed = page_with_number("BLACKLIST-0001")

    result = run_tier0(page.image, None, REFERENCE, parsed)

    assert not [flag for flag in result.flags if flag.id.startswith("WATCHLIST_")]
    assert result.hard_failed is False
    assert result.detected_format == "TD3"


def test_a_page_nobody_handed_a_parse_for_asks_no_list_at_all():
    """No parse means no keys, and no keys means no question worth paying for.

    **The three keys are the three values a document prints** and nothing in
    Part 4 reads a character out of a cell, so a parse nobody handed in leaves
    nothing to ask about.  The connector is asserted *not called*, because a
    lookup of three ``None`` values answers ``[]`` and a live feed's round trip
    would have been spent on a silence.
    """
    page = mrz_images.render_format("TD3")
    connector = RecordingWatchlist([a_hit(watchlist_seam.BLACKLIST, "BLACKLIST-0001")])

    result = run_tier0(page.image, None, REFERENCE, None, connector)

    assert connector.asked == []
    assert result.flags == ()
    assert result.detected_format == "TD3"


def test_a_clean_document_on_no_list_reports_nothing_and_is_not_a_hard_fail():
    """The quiet case, with a list actually asked."""
    page, parsed = parsed_page()
    connector = RecordingWatchlist()

    result = run_tier0(page.image, None, REFERENCE, parsed, connector)

    assert len(connector.asked) == 1
    assert result.flags == ()
    assert result.hard_failed is False
    assert result.hard_fail_reason is None


# --- the seam: what may be handed in, and what may come back ---------------


@pytest.mark.parametrize(
    "not_a_watchlist",
    [
        pytest.param("app.seed.mock_watchlist", id="a-module-path"),
        pytest.param({"lookup": lambda **keys: []}, id="a-dict-with-lookup"),
        pytest.param(3, id="an-int"),
        pytest.param(MockWatchlist.lookup, id="the-unbound-method"),
    ],
)
def test_only_a_watchlist_or_nothing_is_a_watchlist(not_a_watchlist):
    """5.9 made the seam an ABC, and the other end of that is checked here.

    **A duck-typed object is refused rather than asked**, so a connector that
    forgot ``lookup`` fails at the wiring rather than at the first document.
    """
    page = mrz_images.render_format("TD3")

    with pytest.raises(MrzValueError):
        run_tier0(page.image, None, REFERENCE, None, not_a_watchlist)


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(None, id="none"),
        pytest.param((1, 2), id="a-tuple"),
        pytest.param({"kind": "blacklist"}, id="a-dict"),
        pytest.param("blacklist", id="a-string"),
        pytest.param(a_hit(watchlist_seam.BLACKLIST), id="one-hit-not-a-list"),
    ],
)
def test_a_connector_that_answers_with_the_wrong_shape_is_refused(answer):
    """A connector's own bug is refused here rather than half-read.

    **Each of these would otherwise become an ``AttributeError`` on the first
    hit's ``kind``**, several lines into a screening and naming this module
    rather than the connector that answered wrongly.
    """
    page, parsed = parsed_page()
    connector = RecordingWatchlist()
    connector.lookup = lambda **keys: answer

    with pytest.raises(MrzValueError):
        run_tier0(page.image, None, REFERENCE, parsed, connector)


def test_a_kind_the_table_lacks_is_refused_rather_than_skipped():
    """1.9's rule: the package raises one error type and never a bare KeyError."""
    with pytest.raises(MrzValueError):
        runner._watchlist_row("no_such_kind")


def test_the_table_is_exactly_the_three_kinds_and_their_three_ids():
    """Held both ways round, so a fourth kind or a fourth id is a loud failure."""
    kinds = set(runner._WATCHLIST_FLAG)
    ids = set()
    for row in runner._WATCHLIST_FLAG.values():
        ids.add(row[0])

    assert kinds == set(watchlist_seam.HIT_KINDS)
    assert ids == {i for i in flag_ids.FLAG_IDS if i.startswith("WATCHLIST_")}
    assert ids <= set(flag_ids.FLAG_IDS)


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_every_field_a_watchlist_row_names_is_a_field_the_layout_prints(name):
    """The field column is read out of the layouts, so a typo cannot hide.

    **A row naming a field no layout prints would box nothing on every
    document of that format**, and a highlight that never lands is the quiet
    version of a highlight drawn over the wrong words.  The identity row is
    held to the opposite claim: it is about two fields at once and names
    neither.
    """
    fields = set()
    for line in LAYOUTS[name].values():
        fields |= set(line)

    for kind, row in runner._WATCHLIST_FLAG.items():
        if row[3] is None:
            assert kind == watchlist_seam.IDENTITY_SEEN
            continue
        assert row[3] in fields
        assert (
            watchlist_seam.KEY_EACH_KIND_IS_FOUND_BY[kind]
            == watchlist_seam.DOCUMENT_NUMBER
        )


# --- the runner does not become a connector's friend -----------------------


def _runner_tree():
    """The runner's own syntax tree, parsed from its file."""
    return ast.parse(pathlib.Path(runner.__file__).read_text(encoding="utf-8"))


def _called_names(module):
    """Every function name ``module`` calls, however it is reached."""
    names = set()
    for node in ast.walk(ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
        elif isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def test_the_runner_imports_the_seam_and_never_the_connector():
    """A runner that knew the seed could not be given a live feed.

    **The connector arrives as an argument**, so swapping 5.11's mock for a
    stolen-document feed or a blacklist service changes no caller -- which is
    B1.8's own claim about an ``InterpolWatchlist``.
    """
    imported = set()
    for node in ast.walk(_runner_tree()):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            for alias in node.names:
                imported.add(f"{node.module or ''}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
    source = pathlib.Path(runner.__file__).read_text(encoding="utf-8")

    assert "app.risk.watchlist" in imported
    assert not [name for name in imported if name.startswith("app.seed")]
    assert "mock_watchlist" not in source


def test_the_runner_asks_five_sixies_rule_and_not_half_of_it():
    """5.6 is one rule, and the plausibility half is 6.3's to flag.

    **:func:`~app.pipeline.tier0.mrz.infer_birth_year` is the century
    function inside 5.6** rather than the rule, and calling it here would skip
    the half that reads a holder over the maximum age.  A module that cannot
    say a document is too old to be real, and can still ask a list about the
    day it prints, is the honest arrangement rather than a gap.
    """
    called = _called_names(runner)

    assert "dob_result" in called
    assert "infer_birth_year" not in called


def test_nothing_in_the_runner_reached_the_clock_on_the_way():
    """6.2's walk is repeated here, and it matters more than it did.

    **6.4 asks a list about a date of birth**, so a runner that could reach
    the clock would resolve a century against the day the screening happened,
    and which identities a list was asked about would move with the calendar.
    5.8's named dependency exists to make that impossible and this is the
    walk that says it still is.
    """
    assert [
        node.func.attr
        for node in ast.walk(_runner_tree())
        if isinstance(node, ast.Call)
        if isinstance(node.func, ast.Attribute)
        if node.func.attr in {"now", "utcnow", "today", "fromtimestamp"}
    ] == []
