"""6.5 -- the override: any hard-fail rule fired, and the sentence that says so.

`tasks.md` asks for two things and they are the two halves of this file.
:attr:`~app.pipeline.tier0.runner.TierResult.hard_failed` is true when a
hard-fail rule fired, and the reason is a string an officer reads.  The
verify names the pair too: a checksum failure hard-fails and a soft flag does
not.

**The severities are read out of the runner's own tables, not typed here.**
Every id this file expects to override is named beside the sentence and the
field that go with it in
:data:`~app.pipeline.tier0.runner._CHECK_DIGIT_FLAG` or
:data:`~app.pipeline.tier0.runner._WATCHLIST_FLAG`, and the tests below
recompute them rather than repeating them, so a rule that became a hard fail
or stopped being one is one edit in the pipeline and a failing test here.

**The pages are drawn and read back off the pixels**, the way 6.2's and 6.4's
are, so a checksum failure is a document whose printed digit really does not
agree with the characters beside it rather than a hand-built
:class:`~app.pipeline.tier0.mrz.CheckDigitResult`.

**What is pinned hardest is that the weight band is not the answer.**  A
stolen-document hit and a failed check digit are both ``high`` and only one
of them overrides, so a runner that reached for the band would look right on
half this file and wrong on the other half of the same assertion.
"""

import datetime

import pytest

from app.pipeline.tier0 import document, runner, td1, td2, td3
from app.risk import flag_ids, watchlist as watchlist_seam
from tests.fixtures import mrz_images

run_tier0 = runner.run_tier0

BLACKLIST = watchlist_seam.BLACKLIST
STOLEN = watchlist_seam.STOLEN_DOCUMENT
IDENTITY = watchlist_seam.IDENTITY_SEEN

#: The three layouts, by the name Part 3 dispatches on, so a field's position
#: is read out of the table rather than counted out longhand in this file.
LAYOUTS = {"TD1": td1.TD1, "TD2": td2.TD2, "TD3": td3.TD3}

#: The three formats, as names read out of Part 3's own table.
FORMATS = sorted(document.MRZ_SHAPES.values())

#: The reference 5.8's own suite measures against.  6.5 reads no day itself,
#: and the value is here so the argument is shown being passed through
#: unchanged beside a finding and beside no finding.
REFERENCE = datetime.date(2026, 9, 30)


def printed_at(name, field):
    """The ``(line number, position)`` of ``field`` in ``name``'s layout.

    **Read out of the layout rather than counted**, because a position typed
    longhand here is a second copy of the table the pipeline already holds: a
    TD1's composite digit is on its second line and not its last.
    """
    for line_name, fields in LAYOUTS[name].items():
        if field in fields:
            return int(line_name.rsplit("_", 1)[1]), fields[field][0]
    raise KeyError(f"{name} prints no field called {field}")


def zone_with(name, line_number, position, character):
    """The specimen of ``name`` with one printed character replaced."""
    zone = list(mrz_images.SPECIMENS[name])
    line = zone[line_number - 1]
    assert line[position - 1] != character, "the mutation must change something"
    zone[line_number - 1] = line[: position - 1] + character + line[position:]
    return tuple(zone)


def digit_broken(name, label):
    """``name``'s specimen with the printed digit ``label``'s row names broken.

    **The printed digit is what is changed**, because that is the only way to
    fail one digit without failing the characters it covers -- and 6.5's
    answer is about a *rule* firing, so a page failing two digits is a page
    with two hard fails rather than a mistake in the fixture.

    **The replacement is read off the character already printed rather than
    written here**, because an expiry date's digit is a 9 on all three
    specimens and a fixed replacement would leave those cases asserting
    nothing at all.
    """
    line_number, position = printed_at(
        name, runner._CHECK_DIGIT_FLAG[label][2]
    )
    printed = mrz_images.SPECIMENS[name][line_number - 1][position - 1]
    return zone_with(
        name, line_number, position, "0" if printed != "0" else "1"
    )


def composite_broken(name):
    """``name``'s specimen with its composite's printed digit broken."""
    return digit_broken(name, "composite")


def parsed_page(name="TD3", zone=None):
    """A drawn page and the parse a caller would hand over.

    **The zone is read back off the pixels before it is parsed**, so the
    document under test is the one the frame holds rather than the one this
    file typed.
    """
    zone = mrz_images.SPECIMENS[name] if zone is None else zone
    page = mrz_images.render_format(name, lines=tuple(zone))
    read = mrz_images.read_zone(page)
    assert read == tuple(zone)
    return page, document.parse_mrz(read)


def a_hit(kind, entry_id="ENTRY-0001"):
    """A hit of ``kind``, carrying the ``matched_on`` that kind is found by."""
    return watchlist_seam.WatchlistHit(
        kind, entry_id, watchlist_seam.KEY_EACH_KIND_IS_FOUND_BY[kind]
    )


def only(flags, flag_id):
    """The one flag in ``flags`` carrying ``flag_id``."""
    found = [flag for flag in flags if flag.id == flag_id]
    assert len(found) == 1, f"expected one {flag_id}, found {len(found)}"
    return found[0]


class StubWatchlist(watchlist_seam.Watchlist):
    """The seam, answered with whatever kinds this test built it with.

    **The runner is handed one and never imports it**, and this is the same
    shape 6.4 drives: 5.11's seed is what proves the severities against real
    rows, and a stub is what lets this file ask about a *kind* rather than
    about a number it would then have to invent.
    """

    def __init__(self, kinds=()):
        """Keep the answer and forget everything else, and return ``None``."""
        self.asked = []
        self.answer = [a_hit(kind) for kind in kinds]

    def lookup(self, *, document_number, name, dob):
        """Record the three keys, and answer with what this connector holds."""
        self.asked.append(
            {"document_number": document_number, "name": name, "dob": dob}
        )
        return self.answer


# --- the named behaviour: a checksum overrides, a soft flag does not -------


@pytest.mark.parametrize("name", FORMATS)
def test_a_broken_checksum_is_a_hard_fail(name):
    """`tasks.md` 6.5's own verify, on each of the three formats.

    **The abstract names a broken checksum beside a blacklist match** as the
    finding that exits straight to High Risk, and the composite is the one
    digit a document cannot pass by accident: every character inside a
    composite span also sits inside some other printed digit's field, so a
    page that fails it alone has had its composite and nothing else touched.
    """
    page, parsed = parsed_page(name, composite_broken(name))

    result = run_tier0(page.image, parsed_document=parsed)
    flag = only(result.flags, flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH)

    assert result.hard_failed is True
    assert result.hard_fail_reason == flag.label
    assert flag.tier == 0


def test_the_reason_is_the_digits_own_sentence_and_not_a_second_string():
    """Two sentences about one event are one of them able to disagree."""
    page, parsed = parsed_page("TD3", composite_broken("TD3"))

    result = run_tier0(page.image, parsed_document=parsed)

    assert result.hard_fail_reason == result.flags[0].label
    assert result.hard_fail_reason in dict(
        (row[0], row[1]) for row in runner._CHECK_DIGIT_FLAG.values()
    ).values()


def test_a_character_changed_inside_a_field_breaks_the_digits_that_cover_it():
    """The realistic tampering rather than a doctored printed digit.

    **The document number's first character is the one changed**, because that
    is how a rebuilt MRZ looks, and the digit the number's own check digit
    covers cannot then agree.  **The composite covers the same characters**,
    so two rules fire and both are named: an officer is owed each of them
    separately, and a hard-fail reason that mentioned only one of the two
    would be a reason that read differently depending on which rule answered
    first.
    """
    page, parsed = parsed_page("TD3", zone_with("TD3", 2, 1, "0"))

    result = run_tier0(page.image, parsed_document=parsed)
    ids = {flag.id for flag in result.flags}

    assert ids == {
        flag_ids.MRZ_DOCUMENT_NUMBER_CHECK_DIGIT_MISMATCH,
        flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH,
    }
    assert result.hard_failed is True
    assert set(result.hard_fail_reason.split("; ")) == {
        flag.label for flag in result.flags
    }


def test_every_printed_digit_this_project_knows_is_a_hard_fail():
    """The family claim in full, which is a fact about the table and not a page.

    **All seven rows are named here rather than driven one at a time**, and
    the reason is on the arithmetic: 6.2 fires on ``passed is False`` and
    nothing else, so what a *page* can be made to show is that one of these
    ids hard-fails, while whether **every** one of them does is a property of
    :data:`~app.pipeline.tier0.runner._CHECK_DIGIT_HARD_FAIL_IDS`.  A digit
    needing an exception would have to say so against the abstract rather
    than be quietly left out of this set.
    """
    rows = runner._CHECK_DIGIT_FLAG
    ids = {row[0] for row in rows.values()}

    # Seven rows and five ids, because 6.2's table gives the three printed
    # optional-data and personal-number digits one id between them.  Both
    # counts are held so a fourth kind of row cannot join unnoticed.
    assert len(rows) == 7
    assert len(ids) == 5
    assert ids <= runner._CHECK_DIGIT_HARD_FAIL_IDS
    assert ids <= runner._HARD_FAIL_IDS
    assert runner._CHECK_DIGIT_HARD_FAIL_IDS == ids


def test_a_digit_this_project_could_not_read_is_never_an_override():
    """The direction that would cost a document if it broke.

    **A TD1's optional data prints filler for the field and for its own
    digit**, so there is no arithmetic whose answer could disagree and 2.14
    leaves the row at ``None``.  6.5's answer has to leave it alone too,
    because an override owed to an absence is a document refused for
    something nobody read -- and this is the one row on an otherwise honest
    specimen that would otherwise be indistinguishable from a failure.
    """
    page, parsed = parsed_page("TD1")
    unreadable = [
        row for row in parsed.check_digit_results if row.passed is None
    ]

    result = run_tier0(page.image, parsed_document=parsed)

    assert [row.field for row in unreadable] == ["optional_data_1"]
    assert flag_ids.MRZ_OPTIONAL_DATA_CHECK_DIGIT_MISMATCH in (
        runner._CHECK_DIGIT_HARD_FAIL_IDS
    ), "the id is a hard fail when it fires, which is not the same question"
    assert result.flags == ()
    assert result.hard_failed is False
    assert result.hard_fail_reason is None


def test_a_stolen_document_hit_is_heavy_and_does_not_override():
    """A soft flag is the other half of 6.5's verify, on its own.

    **The page is an honest one**, so the only finding is the hit: nothing
    here is a hard fail, and a result that said otherwise would be answering
    about a document the tests did not damage.
    """
    page, parsed = parsed_page()
    connector = StubWatchlist([STOLEN])

    result = run_tier0(page.image, None, REFERENCE, parsed, connector)
    flag = only(result.flags, flag_ids.WATCHLIST_STOLEN_DOCUMENT)

    assert len(connector.asked) == 1
    assert flag.weight_band == "high"
    assert result.hard_failed is False
    assert result.hard_fail_reason is None


def test_an_identity_hit_does_not_override_either():
    """The third kind is a lookup and not a verdict, so it is two of the same."""
    page, parsed = parsed_page()

    result = run_tier0(
        page.image, None, REFERENCE, parsed, StubWatchlist([IDENTITY])
    )

    assert only(result.flags, flag_ids.WATCHLIST_IDENTITY_SEEN).weight_band == (
        "review"
    )
    assert result.hard_failed is False
    assert result.hard_fail_reason is None


def test_two_high_band_findings_and_only_one_of_them_overrides():
    """The whole claim of this task, in one result.

    **Both findings are ``high``, so the band cannot be the test**, and the
    soft one is answered about nowhere: the reason is the checksum's sentence
    alone, because naming the stolen hit beside the override would say the
    runner treats the two as the same kind of thing.
    """
    page, parsed = parsed_page("TD3", composite_broken("TD3"))

    result = run_tier0(
        page.image, None, REFERENCE, parsed, StubWatchlist([STOLEN])
    )
    hard = {f.id for f in result.flags if f.id in runner._HARD_FAIL_IDS}
    soft = {f.id for f in result.flags if f.id not in runner._HARD_FAIL_IDS}

    assert {flag.weight_band for flag in result.flags} == {"high"}
    assert hard == {flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH}
    assert soft == {flag_ids.WATCHLIST_STOLEN_DOCUMENT}
    assert result.hard_failed is True
    assert result.hard_fail_reason == only(
        result.flags, flag_ids.MRZ_COMPOSITE_CHECK_DIGIT_MISMATCH
    ).label


def test_a_clean_document_overrides_nothing():
    """The quiet case, with a list actually asked and a parse actually read.

    **The connector is asked and finds nothing**, which is the only quiet case
    that says something: a list that answered would have answered, and a
    blacklist answer is 6.4's hard fail rather than a silence.
    """
    page, parsed = parsed_page()

    result = run_tier0(page.image, None, REFERENCE, parsed, StubWatchlist())

    assert result.flags == ()
    assert result.detected_format == "TD3"
    assert result.hard_failed is False
    assert result.hard_fail_reason is None


def test_a_page_nobody_handed_a_parse_for_overrides_nothing():
    """The override is a fact about findings and not about what was wired.

    **A connector holding a blacklist hit is standing right there**, and no
    parse means nothing was asked and therefore nothing fired.  A runner that
    read the override off the wiring rather than off the flags would pass
    every test above and fail this one.
    """
    page = mrz_images.draw_page(("B" * 44,)).image

    result = run_tier0(
        page, None, REFERENCE, None, StubWatchlist([BLACKLIST])
    )

    assert result.flags == ()
    assert result.hard_failed is False
    assert result.hard_fail_reason is None


# --- the reason, as a string an officer reads ------------------------------


def test_every_hard_fail_is_named_and_nothing_else_is():
    """Two families firing at once, and the reason is exactly their labels.

    **A reason naming a finding the result does not carry would be an officer
    reading about a document finding nobody reported**, and a reason leaving
    one out would be an override with nothing said about it -- so the set is
    held in both directions rather than by counting.
    """
    page, parsed = parsed_page("TD3", digit_broken("TD3", "document_number"))

    result = run_tier0(
        page.image, None, REFERENCE, parsed, StubWatchlist([BLACKLIST])
    )
    clauses = set(result.hard_fail_reason.split("; "))
    labels = {flag.label for flag in result.flags}

    assert len(clauses) > 1, "this page must break more than one digit"
    assert flag_ids.WATCHLIST_HIT in {f.id for f in result.flags}
    assert clauses == {
        flag.label
        for flag in result.flags
        if flag.id in runner._HARD_FAIL_IDS
    }
    assert clauses <= labels


def test_the_reason_is_the_hard_fail_labels_sorted_and_joined():
    """The string's shape, so two runs over one document read identically."""
    page, parsed = parsed_page("TD3", digit_broken("TD3", "document_number"))

    result = run_tier0(page.image, parsed_document=parsed)
    hard = [flag.label for flag in result.flags if flag.id in runner._HARD_FAIL_IDS]

    assert result.hard_fail_reason == "; ".join(sorted(hard))
    assert all(clause.endswith(".") for clause in result.hard_fail_reason.split("; "))
    assert result.hard_fail_reason == result.hard_fail_reason.strip()


def test_the_reason_does_not_depend_on_the_order_the_flags_arrive_in():
    """Two tuples of the same findings, one string.

    **The families do not promise an order** -- a connector may answer in
    either, and 6.3's dates will join in the middle -- so a reason built by
    walking the flags in the order they came would read differently on two
    runs over one document, and an audit reads the reason.
    """
    page, parsed = parsed_page("TD3", composite_broken("TD3"))
    findings = run_tier0(
        page.image,
        None,
        REFERENCE,
        parsed,
        StubWatchlist([STOLEN, BLACKLIST]),
    ).flags

    assert len(findings) == 3
    assert runner._hard_fail_reason(findings) == runner._hard_fail_reason(
        tuple(reversed(findings))
    )
    assert runner._hard_fail_reason(()) is None


@pytest.mark.parametrize(
    ("name", "zone", "kinds"),
    [
        pytest.param("TD3", mrz_images.SPECIMENS["TD3"], (), id="clean"),
        pytest.param("TD3", composite_broken("TD3"), (), id="a-broken-digit"),
        pytest.param("TD1", composite_broken("TD1"), (), id="td1-composite"),
        pytest.param("TD3", mrz_images.SPECIMENS["TD3"], (STOLEN,), id="stolen"),
        pytest.param("TD3", mrz_images.SPECIMENS["TD3"], (IDENTITY,), id="identity"),
        pytest.param("TD3", mrz_images.SPECIMENS["TD3"], (BLACKLIST,), id="black"),
        pytest.param(
            "TD3",
            composite_broken("TD3"),
            (STOLEN, BLACKLIST),
            id="broken-and-listed",
        ),
    ],
)
def test_hard_failed_is_exactly_whether_a_hard_fail_rule_fired(
    name, zone, kinds
):
    """The definitional claim, over every combination this module can produce.

    **The answer is computed from the flags here rather than compared against
    a list of expected pairs**, so this is not a second copy of the severities
    to keep in step with the tables: it is the one line that would be wrong if
    :attr:`TierResult.hard_failed` were set anywhere but from the reason.
    """
    page, parsed = parsed_page(name, zone)

    result = run_tier0(
        page.image, None, REFERENCE, parsed, StubWatchlist(kinds)
    )
    reasons = {
        flag.label for flag in result.flags if flag.id in runner._HARD_FAIL_IDS
    }

    assert result.hard_failed is bool(reasons)
    assert result.hard_fail_reason == (
        "; ".join(sorted(reasons)) if reasons else None
    )


# --- the tables the answer is read out of ----------------------------------


def test_the_hard_fail_ids_are_the_union_of_the_families_own_tables():
    """One source of truth, and a family joins by adding its own table."""
    from_check_digits = {row[0] for row in runner._CHECK_DIGIT_FLAG.values()}
    from_watchlist = {
        row[0] for row in runner._WATCHLIST_FLAG.values() if row[4]
    }

    assert runner._HARD_FAIL_IDS == from_check_digits | from_watchlist
    assert runner._HARD_FAIL_IDS == (
        runner._CHECK_DIGIT_HARD_FAIL_IDS | runner._WATCHLIST_HARD_FAIL_IDS
    )
    assert from_check_digits and from_watchlist


def test_the_only_findings_that_do_not_override_are_the_two_named_ones():
    """Every check digit overrides; two list kinds do not, and they are named.

    **The soft half is written out rather than left as "whatever is left"**,
    because a third kind joining the seam must be asked the question and not
    inherit an answer from a rule that has not had one.
    """
    every = {row[0] for row in runner._CHECK_DIGIT_FLAG.values()} | {
        row[0] for row in runner._WATCHLIST_FLAG.values()
    }

    assert every - runner._HARD_FAIL_IDS == {
        flag_ids.WATCHLIST_STOLEN_DOCUMENT,
        flag_ids.WATCHLIST_IDENTITY_SEEN,
    }
    assert runner._HARD_FAIL_IDS <= every


def test_no_hard_fail_id_is_invented_beside_the_tables_that_name_one():
    """Every id the answer is keyed on is an id some rule table produced."""
    every = {row[0] for row in runner._CHECK_DIGIT_FLAG.values()} | {
        row[0] for row in runner._WATCHLIST_FLAG.values()
    }

    assert set(runner._HARD_FAIL_IDS) <= every
    assert set(runner._HARD_FAIL_IDS) <= set(flag_ids.FLAG_IDS)
