"""The TD3 layout constants: the positions, and the coverage they claim.

Part 2 of ``tasks.md`` requires every TD3 position to live in a named
constant rather than an inline magic number in a parser, so the constants
become the single place a field position is stated.  That is only worth
anything if the table is right, and a test that reads the module's own
constants back to itself proves nothing -- so the table is written out a
second time here from the standard, and then checked against a real MRZ.

Two independent kinds of evidence, because they fail differently:

* the longhand tables below are the ICAO 9303 Part 4 field list, so a field
  that moved, was renamed, or was given the wrong width is caught by name;
* the specimen passport is sliced with the constants, so an index that is
  self-consistent but off by one is caught by the text it produces.  The
  printed check digits are the strongest part of that: a shifted boundary
  changes the field, and then the digit no longer matches the field it sits
  next to.

Below the constants sit the field readers, each in its own section.  They are
held to the same rule as the tables: a reader that slices a line does it with
the constant, a check that can fail raises the one error type the package
raises, and a message carries the value being judged without carrying the
identity data around it.
"""

import collections
import collections.abc
import dataclasses
import inspect
import string

import pytest

from app.pipeline.tier0 import mrz, td3

# Written out longhand from the standard rather than read back from the module.
EXPECTED_LINE_1 = {
    "document_code": (1, 2),
    "issuing_state": (3, 5),
    "name": (6, 44),
}

EXPECTED_LINE_2 = {
    "document_number": (1, 9),
    "document_number_check_digit": (10, 10),
    "nationality": (11, 13),
    "date_of_birth": (14, 19),
    "date_of_birth_check_digit": (20, 20),
    "sex": (21, 21),
    "date_of_expiry": (22, 27),
    "date_of_expiry_check_digit": (28, 28),
    "personal_number": (29, 42),
    "personal_number_check_digit": (43, 43),
    "composite_check_digit": (44, 44),
}

EXPECTED = {"line_1": EXPECTED_LINE_1, "line_2": EXPECTED_LINE_2}

LAYOUTS = [("line_1", td3.TD3_LINE_1), ("line_2", td3.TD3_LINE_2)]

# The ICAO 9303 Part 4 specimen passport.  Line 2's document number, date of
# birth and date of expiry are the three fields 1.6 already verified against the
# standard, with the digits 3, 2 and 9 printed in the line itself, so those
# three are quoted from the standard here too.
#
# The line-level *composite* digit is the exception.  1.6 recorded that it
# could not be confirmed from a source in reach and declined to quote a
# remembered value, and this task does not obtain a new source, so SPECIMEN_LINE_2
# is built from the quoted fields plus the digits mrz.check_digit derives.  The
# test below therefore pins the composite *position* and the 39 characters it
# covers, not a published value for the character at position 44.
SPECIMEN_LINE_1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
SPECIMEN_LINE_2 = (
    "L898902C<3"  # 1-10  document number + its published check digit
    "UTO"  # 11-13 nationality
    "7408122"  # 14-20 date of birth + its published check digit
    "F"  # 21     sex
    "1204159"  # 22-28 date of expiry + its published check digit
    "ZE184226B<<<<<1"  # 29-43 personal number + its check digit
    "6"  # 44     composite check digit
)


def field(line, layout, name):
    """Slice ``name`` out of ``line`` the way a Part 2 parser will."""
    start, end = layout[name]
    return line[start - 1 : end]


# --- the constants are the standard's field list ---------------------------


@pytest.mark.parametrize("line_name", sorted(EXPECTED))
def test_the_layout_holds_the_fields_the_standard_lists(line_name):
    assert td3.TD3[line_name] == EXPECTED[line_name]


def test_the_line_is_44_characters():
    # Not "the table happens to add up to 44": the two specimen lines are real
    # printed MRZs, so if the length were wrong they would not be 44 either.
    assert td3.TD3_LINE_LENGTH == 44
    assert len(SPECIMEN_LINE_1) == td3.TD3_LINE_LENGTH
    assert len(SPECIMEN_LINE_2) == td3.TD3_LINE_LENGTH


def test_a_td3_zone_is_two_lines():
    assert td3.TD3_LINE_COUNT == 2
    assert len(td3.TD3) == td3.TD3_LINE_COUNT


def test_the_aggregate_holds_the_line_tables_rather_than_copies():
    # A copy would be a second table to drift, which is the failure this module
    # exists to prevent, so the identity is the assertion.
    assert td3.TD3["line_1"] is td3.TD3_LINE_1
    assert td3.TD3["line_2"] is td3.TD3_LINE_2
    assert set(td3.TD3) == {"line_1", "line_2"}


# --- the coverage this task asks for ---------------------------------------


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_a_line_covers_positions_1_to_44_with_no_gap_or_overlap(line_name, layout):
    claimed = []
    for field_name, (start, end) in sorted(layout.items(), key=lambda item: item[1]):
        assert isinstance(start, int), f"{line_name}.{field_name} start is not an int"
        assert isinstance(end, int), f"{line_name}.{field_name} end is not an int"
        assert 1 <= start <= end, f"{line_name}.{field_name} is an empty or inverted range"
        assert end <= td3.TD3_LINE_LENGTH, f"{line_name}.{field_name} runs past the line"
        claimed.extend(range(start, end + 1))

    # One sorted comparison carries the whole claim.  A gap drops a position, an
    # overlap repeats one, and an out-of-range index puts a value in the list
    # that is not in 1-44; whichever it is, the two lists first differ at the
    # position that broke.  Counting to 44 would not do: a gap and an overlap
    # can cancel out in the total.
    assert sorted(claimed) == list(range(1, td3.TD3_LINE_LENGTH + 1))


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_the_fields_are_adjacent_and_ordered(line_name, layout):
    # The same claim as above, reported per boundary, so a failure says which
    # field broke the line rather than only that 44 integers did not appear.
    expected_start = 1
    for field_name, (start, end) in sorted(layout.items(), key=lambda item: item[1]):
        assert start == expected_start, f"{line_name}.{field_name} starts at {start}, not {expected_start}"
        expected_start = end + 1

    assert expected_start == td3.TD3_LINE_LENGTH + 1


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_every_field_is_readable_from_a_printed_line(line_name, layout):
    # A layout whose positions are all inside the line but land in the wrong
    # place still passes both coverage tests above, so the positions are
    # checked against a real MRZ here.
    line = SPECIMEN_LINE_1 if line_name == "line_1" else SPECIMEN_LINE_2
    for field_name, (start, end) in layout.items():
        assert len(field(line, layout, field_name)) == end - start + 1


# --- the positions against the specimen passport ---------------------------


@pytest.mark.parametrize(
    "line_name, field_name, expected",
    [
        ("line_1", "document_code", "P<"),
        ("line_1", "issuing_state", "UTO"),
        ("line_1", "name", "ERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"),
        ("line_2", "document_number", "L898902C<"),
        ("line_2", "nationality", "UTO"),
        ("line_2", "date_of_birth", "740812"),
        ("line_2", "sex", "F"),
        ("line_2", "date_of_expiry", "120415"),
        ("line_2", "personal_number", "ZE184226B<<<<<"),
    ],
)
def test_a_field_slices_the_text_the_specimen_prints(line_name, field_name, expected):
    layout = td3.TD3[line_name]
    line = SPECIMEN_LINE_1 if line_name == "line_1" else SPECIMEN_LINE_2

    assert field(line, layout, field_name) == expected


@pytest.mark.parametrize(
    "field_name",
    [
        "document_number",
        "date_of_birth",
        "date_of_expiry",
        "personal_number",
    ],
)
def test_a_check_digit_field_sits_next_to_the_digit_it_checks(field_name):
    # The load-bearing position test.  The check digit for a field is only
    # correct for that exact field over that exact span, so if a boundary moves
    # by one the sliced digit no longer matches -- which is what catches a table
    # that is internally consistent and still wrong.
    layout = td3.TD3_LINE_2
    value = field(SPECIMEN_LINE_2, layout, field_name)
    printed = field(SPECIMEN_LINE_2, layout, f"{field_name}_check_digit")

    assert printed == str(mrz.check_digit(value))


def test_the_composite_digit_covers_1_to_10_14_to_20_and_22_to_43():
    # Built from the constants, so this also states the three spans as ranges.
    layout = td3.TD3_LINE_2
    spans = [
        (layout["document_number"][0], layout["document_number_check_digit"][1]),
        (layout["date_of_birth"][0], layout["date_of_birth_check_digit"][1]),
        (layout["date_of_expiry"][0], layout["personal_number_check_digit"][1]),
    ]
    covered = [(1, 10), (14, 20), (22, 43)]
    composite = "".join(SPECIMEN_LINE_2[start - 1 : end] for start, end in spans)

    assert spans == covered
    assert len(composite) == 39
    assert field(SPECIMEN_LINE_2, layout, "composite_check_digit") == str(
        mrz.check_digit(composite)
    )


# --- the shape check: two lines of exactly 44 characters ------------------

VALID_TD3_LINES = [SPECIMEN_LINE_1, SPECIMEN_LINE_2]


def test_validate_td3_lines_is_exported():
    assert "validate_td3_lines" in td3.__all__


def test_a_valid_td3_zone_is_accepted_and_handed_back_in_order():
    # The three rejection tests below all pass against a validator that raises
    # unconditionally, so the accepted case is asserted too: it does not raise,
    # and it returns the two lines in printed order for the parser to slice.
    line_1, line_2 = td3.validate_td3_lines(VALID_TD3_LINES)

    assert (line_1, line_2) == (SPECIMEN_LINE_1, SPECIMEN_LINE_2)


def test_the_lines_may_be_a_tuple_rather_than_a_list():
    # What the OCR step hands over is a sequence, not a list specifically.
    assert td3.validate_td3_lines(tuple(VALID_TD3_LINES)) == tuple(VALID_TD3_LINES)


def test_no_lines_at_all_is_rejected():
    # The zone that found nothing has to say so here, rather than passing on an
    # empty sequence for a parser to index into.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_td3_lines([])

    assert f"{td3.TD3_LINE_COUNT} lines, not 0" in str(excinfo.value)


def test_one_line_is_not_a_td3_zone():
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_td3_lines([SPECIMEN_LINE_1])

    assert f"{td3.TD3_LINE_COUNT} lines, not 1" in str(excinfo.value)


def test_three_lines_are_not_a_td3_zone():
    # Every line here is a full 44 characters, so this is a rejection on the
    # count alone -- which is the part a "trim the extra line" fix could lose.
    third = SPECIMEN_LINE_1
    assert len(third) == td3.TD3_LINE_LENGTH

    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2, third])

    assert f"{td3.TD3_LINE_COUNT} lines, not 3" in str(excinfo.value)


@pytest.mark.parametrize("delta", [-1, 1], ids=["short", "long"])
def test_a_line_of_the_wrong_length_is_rejected(delta):
    # A 43-character line is the truncated-OCR case the task names; a
    # 45-character one is the same check from the other side, and the two must
    # not be confused with a bad character count.
    wrong = SPECIMEN_LINE_2[:-1] if delta < 0 else SPECIMEN_LINE_2 + "<"
    assert len(wrong) == td3.TD3_LINE_LENGTH + delta

    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_td3_lines([SPECIMEN_LINE_1, wrong])

    message = str(excinfo.value)
    assert f"line 2 is {td3.TD3_LINE_LENGTH + delta} characters" in message
    assert f"not {td3.TD3_LINE_LENGTH}" in message
    # Only the offending line is named: line 1 is the right length here, and a
    # message that pointed at both would send a reader to the wrong one.
    assert "line 1" not in message


def test_one_string_rather_than_two_lines_is_rejected():
    # The likeliest caller mistake is passing the text of the whole zone as a
    # single string.  Iterated as a sequence that is 44 one-character "lines",
    # so the message has to name the mistake rather than report a count of 44.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_td3_lines(SPECIMEN_LINE_1)

    message = str(excinfo.value)
    assert f"{td3.TD3_LINE_COUNT} lines" in message
    assert f"not one string of {td3.TD3_LINE_LENGTH} characters" in message


def test_something_that_is_not_a_sequence_of_lines_is_rejected():
    # len()/iteration on None would escape as a bare TypeError, and a caller
    # catching MrzValueError (the package's one error type) would miss it.
    with pytest.raises(mrz.MrzValueError):
        td3.validate_td3_lines(None)


def test_a_line_that_is_not_a_string_is_rejected():
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_td3_lines([SPECIMEN_LINE_1, None])

    assert "line 2 must be a string" in str(excinfo.value)


def test_the_error_does_not_echo_the_line_contents():
    # The lines are the identity data the screening is about, and an exception
    # message is the most likely thing to reach a log, so a rejected zone is
    # reported by shape only -- counts and lengths, never characters.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2[:20]])

    message = str(excinfo.value)
    assert "ERIKSSON" not in message
    assert "L898902C" not in message


# --- the document code: the first thing a character can say ----------------


def line_1_with_document_code(code):
    """A full-length TD3 line 1 whose positions 1-2 read ``code``."""
    end = td3.TD3_LINE_1["document_code"][1]

    return code + SPECIMEN_LINE_1[end:]


def test_the_slicing_helper_is_exported():
    assert "td3_field" in td3.__all__


@pytest.mark.parametrize(
    "line, layout, name, expected",
    [
        (SPECIMEN_LINE_1, td3.TD3_LINE_1, "document_code", "P<"),
        (SPECIMEN_LINE_1, td3.TD3_LINE_1, "issuing_state", "UTO"),
        (SPECIMEN_LINE_1, td3.TD3_LINE_1, "name", "ERIKSSON<<ANNA<MARIA" + "<" * 19),
        (SPECIMEN_LINE_2, td3.TD3_LINE_2, "document_number", "L898902C<"),
        (SPECIMEN_LINE_2, td3.TD3_LINE_2, "composite_check_digit", "6"),
    ],
    ids=["code", "state", "name", "number", "composite"],
)
def test_the_helper_slices_the_field_the_layout_names(line, layout, name, expected):
    # The module's own helper, checked against the longhand table above rather
    # than against the test file's `field()` -- two implementations of the same
    # slice, agreeing.  Line 2 is here so the helper is not quietly hardwired
    # to line 1, and the two-character code and the 39-character name are here
    # because they are the widest and narrowest spans in the layout.
    assert td3.td3_field(line, layout, name) == expected


def test_the_helper_stops_at_the_end_of_its_field():
    # The -1 and the inclusive end are the whole conversion, so both edges of
    # it are pinned: the code must not run on past position 2 and the name must
    # not start one character early.  The two are separated by the issuing
    # state, so an off-by-one in either direction pulls a field into it.
    start, end = td3.TD3_LINE_1["document_code"]
    name_start, name_end = td3.TD3_LINE_1["name"]
    code = td3.td3_field(SPECIMEN_LINE_1, td3.TD3_LINE_1, "document_code")
    name = td3.td3_field(SPECIMEN_LINE_1, td3.TD3_LINE_1, "name")

    assert (start, end) == (1, 2)
    assert code == "P<"
    assert name.startswith("ERIKSSON")
    assert len(name) == name_end - name_start + 1 == 39
    assert td3.TD3_LINE_1["issuing_state"] == (end + 1, name_start - 1)
    assert SPECIMEN_LINE_1[end : name_start - 1] == "UTO"


def test_a_field_name_the_layout_does_not_have_is_rejected():
    # A bare KeyError out of the lookup is the kind of built-in error 1.9
    # forbids: a caller catching MrzValueError would never see it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.td3_field(SPECIMEN_LINE_1, td3.TD3_LINE_1, "nationality")

    assert repr("nationality") in str(excinfo.value)


def test_a_layout_from_the_wrong_line_is_rejected_by_its_field_names():
    # line_1 has no document_number and line_2 has no name, so handing the
    # wrong table is a mistake the helper can name rather than pass on.
    with pytest.raises(mrz.MrzValueError):
        td3.td3_field(SPECIMEN_LINE_2, td3.TD3_LINE_1, "document_number")


def test_a_line_that_is_not_a_string_is_rejected_by_the_helper():
    # Slicing None raises a bare TypeError that a caller catching
    # MrzValueError would never see.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.td3_field(None, td3.TD3_LINE_1, "document_code")

    assert "NoneType" in str(excinfo.value)


@pytest.mark.parametrize("code", ["P<", "P"], ids=["P<", "P"])
def test_a_passport_document_code_is_accepted(code):
    assert td3.validate_document_code(code) == code


@pytest.mark.parametrize("code", ["V<", "X<"], ids=["V<", "X<"])
def test_a_document_code_that_is_not_a_passport_is_rejected(code):
    # V< is a visa and X< is no document at all.  Both are well-formed MRZ
    # codes -- neither is a misspelling -- and a TD3 passport line is neither
    # of them, so the answer is to refuse the line rather than parse it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_document_code(code)

    assert repr(code) in str(excinfo.value)


def test_the_accepted_document_codes_are_p_and_p_with_filler_exactly():
    # Pinned rather than read back into use: widening this set is a change to
    # what DRISHTI will accept as a passport, so it has to be a deliberate edit
    # of the module and not a side effect of something else.  A frozenset, so
    # no caller can widen it at runtime either.
    assert td3.TD3_DOCUMENT_CODES == {"P<", "P"}
    assert isinstance(td3.TD3_DOCUMENT_CODES, frozenset)


@pytest.mark.parametrize("code", ["PA", "PP"], ids=["PA", "PP"])
def test_a_code_that_starts_with_p_but_is_not_one_of_the_two_is_rejected(code):
    # This is what pins the *behaviour* of the set, and not only its contents:
    # an implementation that checked `code.startswith("P")` would pass every
    # test above and accept both of these.  PP is the plausible real spelling
    # -- a passport type letter where the filler usually is -- so this states
    # the decision plainly: this task admits only the two codes it names, and
    # a line carrying a type letter is refused for a person to look at rather
    # than parsed on the assumption that the letter was filler.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_document_code(code)

    assert repr(code) in str(excinfo.value)


def test_the_document_code_names_are_exported():
    assert {
        "TD3_DOCUMENT_CODES",
        "parse_document_code",
        "validate_document_code",
    } <= set(td3.__all__)


def test_the_document_code_is_read_from_positions_1_and_2():
    start, end = td3.TD3_LINE_1["document_code"]
    code = td3.parse_document_code(SPECIMEN_LINE_1)

    assert (start, end) == (1, 2)
    assert code == "P<"
    assert len(code) == end - start + 1
    # The two neighbouring slices are different text, so a reader that is off
    # by one in either direction cannot pass this.
    assert code not in (SPECIMEN_LINE_1[:1], SPECIMEN_LINE_1[:3], SPECIMEN_LINE_1[2:5])


@pytest.mark.parametrize("code", ["V<", "X<"], ids=["V<", "X<"])
def test_a_line_whose_code_is_not_a_passport_is_rejected_end_to_end(code):
    # The path 2.13 will actually take: slice positions 1-2 off a real 44
    # character line, then judge it.  The two tests above only ever hand the
    # validator a bare two-character code, which proves nothing about whether
    # the reader calls it.
    line = line_1_with_document_code(code)
    assert len(line) == td3.TD3_LINE_LENGTH

    with pytest.raises(mrz.MrzValueError):
        td3.parse_document_code(line)


def test_a_one_character_line_reads_as_the_bare_p():
    # Why "P" is in the accepted set at all.  The second character of a
    # passport's document code is filler -- it says "no variant" -- so a code
    # that lost it is the same document, not a different one, and nothing
    # downstream of this field reads position 2.  This is the only way a bare
    # "P" can arrive: 2.2's validate_td3_lines is what guarantees 44
    # characters, and 2.13 is where the two are composed.
    assert td3.parse_document_code("P") == "P"


def test_a_line_with_no_characters_at_all_is_rejected():
    # The other end of the same slice: a line too short to hold a code must
    # not be read as an empty one and waved through.
    with pytest.raises(mrz.MrzValueError):
        td3.parse_document_code("")


def test_a_document_code_line_that_is_not_a_string_is_rejected():
    # Slicing None raises a bare TypeError, which a caller catching
    # MrzValueError -- the one error type 1.9 pinned -- would never see.  The
    # same leak 1.9 found in weights().
    with pytest.raises(mrz.MrzValueError):
        td3.parse_document_code(None)


def test_the_rejection_names_the_code_it_found_and_the_ones_it_wants():
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_document_code("V<")

    message = str(excinfo.value)
    assert repr("V<") in message
    assert repr("P<") in message
    assert repr("P") in message


def test_a_rejected_document_code_is_the_packages_one_error_type():
    # The exact type, not a subclass: 1.9 pinned this so that a second error
    # type cannot hide underneath this one unnoticed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_document_code(line_1_with_document_code("X<"))

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_rejection_does_not_echo_the_line():
    # The document code is two characters naming the *type* of document, and
    # naming it is what makes the message useful.  Everything after it is
    # identity data, so 2.2's rule still holds for the rest of the line.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_document_code(line_1_with_document_code("V<"))

    message = str(excinfo.value)
    assert "UTO" not in message
    assert "ERIKSSON" not in message


# --- the issuing state: the second thing a character can say ---------------


def line_1_with_issuing_state(code):
    """A full-length TD3 line 1 whose positions 3-5 read ``code``.

    Only a three-character code can sit at positions 3-5 of a 44-character
    line, so the width is asserted here instead of being discovered later: a
    short code is what a *short line* produces, not what a well-formed line
    prints, and that case is tested on its own below.
    """
    start, end = td3.TD3_LINE_1["issuing_state"]
    assert len(code) == end - start + 1

    return SPECIMEN_LINE_1[: start - 1] + code + SPECIMEN_LINE_1[end:]


def test_the_issuing_state_names_are_exported():
    assert {"parse_issuing_state", "validate_issuing_state"} <= set(td3.__all__)


def test_the_issuing_state_is_three_positions_wide_in_the_layout():
    # The width is read out of the table rather than typed into the check, so
    # the standard's positions stay the only place a position is stated and a
    # message cannot disagree with the layout it is describing.
    start, end = td3.TD3_LINE_1["issuing_state"]

    assert (start, end) == (3, 5)
    assert end - start + 1 == 3
    assert SPECIMEN_LINE_1[start - 1 : end] == "UTO"


@pytest.mark.parametrize(
    "code", ["UTO", "IND", "AAA", "ZZZ"], ids=["UTO", "IND", "AAA", "ZZZ"]
)
def test_a_three_uppercase_letter_issuing_state_is_accepted(code):
    # Three uppercase letters is the whole of the rule the standard states for
    # positions 3-5, and these are only that: strings.  No list of real codes
    # is consulted -- see the IND test below for why that is deliberate.
    assert td3.validate_issuing_state(code) == code


@pytest.mark.parametrize(
    "code",
    [
        "",
        "UT",
        "UTOX",
        "UTO ",
        "UT0",
        "1TO",
        "uto",
        "UtO",
        "U O",
        "U<O",
        "UT-",
        "ÜTO",
    ],
    ids=[
        "empty",
        "two letters",
        "four letters",
        "trailing space",
        "a digit for the O",
        "a leading digit",
        "lower case",
        "mixed case",
        "an inner space",
        "filler where a letter is",
        "punctuation",
        "a non-ASCII letter",
    ],
)
def test_an_issuing_state_that_is_not_three_uppercase_letters_is_rejected(code):
    # The cases that matter are the ones OCR produces: a zero read for an O, a
    # lower-case or mixed-case read, a filler or a space where a letter should
    # be, and a diacritic carried over from the printed name.  "ÜTO" is the
    # load-bearing one -- it is three characters, `isalpha()` is True and
    # `isupper()` is True, so an implementation written from those two methods
    # would wave it through and read Ü as a country.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_issuing_state(code)

    assert repr(code) in str(excinfo.value)


@pytest.mark.parametrize(
    "code", [None, 123, b"UTO"], ids=["None", "an int", "bytes"]
)
def test_an_issuing_state_that_is_not_a_string_is_rejected(code):
    # Iterating or measuring a non-string raises the bare TypeError 1.9 forbids,
    # which a caller catching MrzValueError would never see.  bytes is the
    # subtle one: `b"UTO".isalpha()` is True, so a validator that asked the
    # value rather than the type would accept a byte string as a code.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_issuing_state(code)

    assert type(code).__name__ in str(excinfo.value)


def test_the_rejection_names_the_code_and_the_width_the_layout_gives():
    # The width in the message is the layout's, so the two cannot drift: if the
    # field ever moves or changes width, this message changes with it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_issuing_state("UT")

    message = str(excinfo.value)
    width = td3.TD3_LINE_1["issuing_state"][1] - td3.TD3_LINE_1["issuing_state"][0]
    assert repr("UT") in message
    assert str(width + 1) in message


def test_a_real_country_code_such_as_ind_is_accepted_although_the_task_says_otherwise():
    # tasks.md 2.4 asks for "a test rejecting IND".  IND cannot be rejected by
    # the rule the same sentence states -- "3 uppercase letters" -- because
    # IND is three uppercase letters.  The two clauses of the task contradict
    # each other, and this test says which one this module implements.
    #
    # A membership rule does not rescue the other clause either: ISO 3166-1
    # alpha-3 assigns IND to India, so every conforming list of issuing states
    # -- ICAO Doc 9303's included -- contains IND.  The only implementations
    # that reject it hold a list with India missing, and that parser refuses
    # every genuine Indian passport: a 100% false-alert rate on the field most
    # likely to be correct.  2.3 took the same direction with `PP`, refusing a
    # well-formed code rather than parsing it on an assumption.
    #
    # So the field reader decides well-formedness, and recognising a state is a
    # Tier 0 policy question: a code list that has to be sourced rather than
    # remembered (the rule 1.6 applied to the composite check digit) and
    # belongs to the rules engine, not to a field reader.
    assert td3.validate_issuing_state("IND") == "IND"
    assert td3.parse_issuing_state(line_1_with_issuing_state("IND")) == "IND"


def test_the_issuing_state_is_read_from_positions_3_to_5():
    start, end = td3.TD3_LINE_1["issuing_state"]
    state = td3.parse_issuing_state(SPECIMEN_LINE_1)

    assert state == "UTO"
    assert len(state) == end - start + 1
    # The neighbouring slices are different text, so a reader that is off by
    # one in either direction cannot pass this: position 2 is the document
    # code's filler and position 6 is the surname.
    assert state not in (SPECIMEN_LINE_1[:3], SPECIMEN_LINE_1[1:4], SPECIMEN_LINE_1[3:6])


@pytest.mark.parametrize("code", ["uto", "U<O", "UT0"], ids=["lower", "filler", "digit"])
def test_a_line_whose_issuing_state_is_malformed_is_rejected_end_to_end(code):
    # The path 2.13 will take: slice positions 3-5 off a real 44-character
    # line, then judge it.  A validator test alone would not prove the reader
    # calls it.
    line = line_1_with_issuing_state(code)
    assert len(line) == td3.TD3_LINE_LENGTH

    with pytest.raises(mrz.MrzValueError):
        td3.parse_issuing_state(line)


@pytest.mark.parametrize("line", ["", "P<"], ids=["empty", "too short to hold one"])
def test_a_line_too_short_to_hold_an_issuing_state_is_rejected(line):
    # A line that stops before position 5 slices to a short or empty string.
    # That is not a well-formed code and must not be waved through as one.
    with pytest.raises(mrz.MrzValueError):
        td3.parse_issuing_state(line)


def test_an_issuing_state_line_that_is_not_a_string_is_rejected():
    # Slicing None raises a bare TypeError, which a caller catching
    # MrzValueError -- the one error type 1.9 pinned -- would never see.  Named
    # apart from 2.3's identically-shaped document-code test so this one does
    # not shadow it out of the suite.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_issuing_state(None)

    assert "NoneType" in str(excinfo.value)


def test_a_rejected_issuing_state_is_the_packages_one_error_type():
    # The exact type, not a subclass: 1.9 pinned this so a second error type
    # cannot hide underneath this one unnoticed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_issuing_state(line_1_with_issuing_state("UT0"))

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_rejection_names_the_state_but_not_the_name_after_it():
    # Three characters naming a *state* is what makes the message useful, on
    # the same reasoning 2.3 used for the document code.  The surname behind it
    # is identity data, so 2.2's rule still holds.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_issuing_state(line_1_with_issuing_state("UT0"))

    message = str(excinfo.value)
    assert repr("UT0") in message
    assert "ERIKSSON" not in message


# --- the raw name: extracted here, judged nowhere ------------------------


# The name field as the specimen passport prints it, written out in full
# rather than sliced from the line it is supposed to have come from: a test
# that expected ``SPECIMEN_LINE_1[5:]`` would pass against a reader whose
# positions were wrong, which is the mistake 2.1's longhand tables exist to
# catch.
SPECIMEN_NAME = "ERIKSSON<<ANNA<MARIA" + "<" * 19


def test_the_name_reader_is_exported():
    assert "parse_name" in td3.__all__


def test_the_name_is_the_last_field_of_line_1():
    # Positions 6-44 as 2.5 states them, read out of the table rather than
    # typed into the test, and 44 *is* TD3_LINE_LENGTH: the name field runs to
    # the end of the line.  A reader that sliced to the end of the string
    # instead of to position 44 is caught below rather than by this.
    start, end = td3.TD3_LINE_1["name"]

    assert (start, end) == (6, 44)
    assert end == td3.TD3_LINE_LENGTH
    assert end - start + 1 == len(SPECIMEN_NAME)
    assert SPECIMEN_LINE_1[start - 1 : end] == SPECIMEN_NAME


def test_the_raw_name_of_a_known_mrz_is_read():
    # The test 2.5 asks for, on the one MRZ in this file that is a real printed
    # passport rather than something built to fit.  The value is *raw*: filler
    # intact, nothing split off it, no case changed.  2.6, 2.7 and 2.8 are the
    # tasks that do those three things, and each of them starts from this.
    raw = td3.parse_name(SPECIMEN_LINE_1)

    assert raw == SPECIMEN_NAME
    assert len(raw) == 39
    assert SPECIMEN_LINE_1.endswith(raw)


def test_the_raw_name_is_read_from_a_validated_zone():
    # The path 2.13 will take: the zone is gated by validate_td3_lines first,
    # then line 1 is handed to the reader.  Tested on a hand-passed line only,
    # the two would never be shown to work together.
    line_1, line_2 = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])

    assert td3.parse_name(line_1) == SPECIMEN_NAME
    assert line_2.startswith("L898902C<3")


def test_the_raw_name_keeps_its_filler():
    # 2.8 is the task that strips filler and normalises case, so this pins
    # that neither has happened yet.  A reader that quietly returned
    # "ERIKSSON<<ANNA<MARIA" would make 2.8 untestable and would throw away
    # the field width, which is evidence in its own right.
    raw = td3.parse_name(SPECIMEN_LINE_1)

    assert raw.endswith("<<<<<<<<<<<<<<<<<<<")
    # Three separators ("<<" after the surname, "<" between the given names)
    # plus 19 padding characters, against the 17 letters the name is printed
    # in.  39 in total, which is the width the layout claims.
    assert raw.count(mrz.FILLER) == 3 + 19
    assert raw.replace(mrz.FILLER, "") == "ERIKSSONANNAMARIA"


def test_the_raw_name_is_one_unsplit_string():
    # 2.6 splits on "<<" and 2.7 splits the given names on "<".  Neither has
    # happened: what comes back is the single string the line printed, and the
    # separators are still in it.
    raw = td3.parse_name(SPECIMEN_LINE_1)

    assert isinstance(raw, str)
    assert "<<" in raw
    assert "ERIKSSON" in raw
    assert "ANNA" in raw
    assert "MARIA" in raw
    assert raw == raw.upper()


def test_the_name_reader_starts_where_the_layout_says_and_no_earlier():
    # The two fields before the name are the ones most likely to be swept into
    # it, so the neighbouring slices are named explicitly: a reader off by one
    # in either direction prints different text and fails here.
    raw = td3.parse_name(SPECIMEN_LINE_1)

    assert raw != SPECIMEN_LINE_1[:5]  # the document code and the state
    assert raw != SPECIMEN_LINE_1[4:]  # one character early
    assert raw != SPECIMEN_LINE_1[6:]  # one character late
    assert "UTO" not in raw
    assert "P<" not in raw


def test_the_name_is_read_by_position_not_by_the_end_of_the_string():
    # The name field ends at position 44 and the line is 44 characters, so
    # "position 44" and "the end of the line" are the same thing on a
    # well-formed zone and the two implementations cannot be told apart by it.
    # An over-long line tells them apart, and the layout is what decides which
    # one is right: the surplus characters are not the name.
    over_read = SPECIMEN_LINE_1 + "TRAILING"

    assert len(over_read) > td3.TD3_LINE_LENGTH
    assert td3.parse_name(over_read) == SPECIMEN_NAME


@pytest.mark.parametrize(
    "line",
    [
        "P<UTO\u015eRIKSSON<<ANNA<MARIA",
        "P<UTOERIKSSON<<anna maria",
        "P<UTOERIKSSON<<ANNA<MAR",
    ],
    ids=[
        "a diacritic in the surname",
        "a lower-case read with a space for a filler",
        "a lower-case read of a few given names",
    ],
)
def test_a_name_that_is_not_cleanly_printed_is_still_extracted_verbatim(line):
    # Each of these is something a character-set rule would refuse, and each
    # of them is something 2.8 exists to clean up.  A diacritic is what 2.4
    # rejected in an issuing state, and here it is carried straight through:
    # the difference between the two fields is deliberate, because 2.8 is the
    # task that normalises the name.  A reader that refused these would leave
    # 2.8 nothing to normalise -- a misread arriving as UTF-8 from a real OCR
    # engine is a rules-engine flag, not a reason to drop the document.
    raw = td3.parse_name(line + "<" * (td3.TD3_LINE_LENGTH - len(line)))

    assert len(raw) == td3.TD3_LINE_LENGTH - td3.TD3_LINE_1["name"][0] + 1
    # Whatever the line printed in positions 6-44 is what comes back, uncut and
    # unaltered, so 2.6/2.7/2.8 each start from the same raw string.
    start, end = td3.TD3_LINE_1["name"]
    assert raw == (line + "<" * td3.TD3_LINE_LENGTH)[start - 1 : end]
    assert raw != SPECIMEN_NAME


def test_a_name_field_of_nothing_but_filler_is_extracted_rather_than_judged():
    # An empty name is an anomaly, but it is not this task's to refuse.  2.4
    # took the same position on `IND` and for the same reason: whether a
    # well-formed field is *acceptable* is a Tier 0 policy question answered by
    # the rules engine, and a reader that refused this would refuse the
    # document instead of flagging it.  2.6 is where the consequence becomes
    # visible -- splitting 39 fillers yields an empty surname -- so this test
    # is here to make 2.6 decide that deliberately rather than inherit it.
    blank = "P<UTO" + "<" * 39
    raw = td3.parse_name(blank)

    assert raw == "<" * 39
    assert not raw.strip(mrz.FILLER)


@pytest.mark.parametrize("line", [None, b"P<UTOERIKSSON<<ANNA<MARIA"])
def test_a_name_line_that_is_not_a_string_is_rejected(line):
    # Slicing a non-string raises the bare TypeError 1.9 forbids, which a
    # caller catching MrzValueError would never see.  bytes is the subtle one:
    # indexing it gives integers, so a reader without td3_field's guard would
    # compare ints against the layout's width and report a length rather than
    # a type.  Named apart from 2.3's and 2.4's identically-shaped tests so
    # this one does not shadow either out of the suite.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_name(line)

    assert type(line).__name__ in str(excinfo.value)


@pytest.mark.parametrize(
    "line",
    ["", "P<", "P<UTO", "P<UTOERIKSSON<<ANNA<MAR"],
    ids=["empty", "the document code alone", "up to the state", "part-way through"],
)
def test_a_line_that_stops_before_the_name_ends_is_rejected(line):
    # The one misread this field has, and the reason it needs a judgement at
    # all.  Every other reader in this module rejects a short line as a side
    # effect of checking its contents; the name has no content rule until 2.6,
    # so without this the reader would slice to whatever arrived and hand back
    # "" -- which reads downstream as a document that printed no name, rather
    # than a line that was cut off.  "Parsing must not silently fix it" is
    # 2.14's rule and this is where it starts.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_name(line)

    # The message reports how much of the *field* arrived, not the line's
    # length: a line that stops before position 6 slices to nothing at all
    # rather than to a negative count.
    start = td3.TD3_LINE_1["name"][0]
    assert str(max(0, len(line) - start + 1)) in str(excinfo.value)


def test_the_truncation_message_carries_the_layout_positions_and_lengths():
    # The width and the positions are read out of the layout, so the message
    # cannot describe a field the table does not have: move the name field and
    # this text moves with it.  No characters, either -- the name is the
    # identity data 2.2's rule protects, and it is the field where breaking
    # that rule would have been easiest.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_name("P<UTOERIKSSON<<ANNA<MAR")

    start, end = td3.TD3_LINE_1["name"]
    message = str(excinfo.value)
    assert f"{start}" in message
    assert f"{end}" in message
    assert str(end - start + 1) in message
    assert "ERIKSSON" not in message
    assert "ANNA" not in message


def test_a_rejected_name_is_the_packages_one_error_type():
    # The exact type, not a subclass: 1.9 pinned this so a second error type
    # cannot hide underneath this one unnoticed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_name("P<UTO")

    assert type(excinfo.value) is mrz.MrzValueError


# --- the name, split on the separator into surname and given names --------


def test_the_name_splitter_is_exported():
    assert "split_name" in td3.__all__


def test_a_name_carrying_the_separator_is_split_into_surname_and_given_names():
    # The first case 2.6 asks for.  The given names are written with a space
    # where the MRZ prints a filler, because that is the misread a real OCR
    # engine produces and it is 2.8's to clean.  The split has to survive it
    # rather than refuse it, or 2.8 would never be handed the name it exists
    # to normalise.
    surname, given_names = td3.split_name("ERIKSSON<<ANNA MARIA")

    assert surname == "ERIKSSON"
    assert given_names == "ANNA MARIA"


def test_the_specimen_name_is_split_into_surname_and_given_names():
    # The same split on the real printed field, where the given names are
    # separated by single fillers and the whole name is padded to 39
    # characters.  The expected halves are written out in full rather than
    # sliced from SPECIMEN_NAME: a test that expected
    # SPECIMEN_NAME.split("<<") would pass against a splitter that did
    # nothing but call the stdlib's.
    surname, given_names = td3.split_name(SPECIMEN_NAME)

    assert surname == "ERIKSSON"
    assert given_names == "ANNA<MARIA" + "<" * 19


def test_the_specimen_name_is_split_out_of_a_validated_zone():
    # The path 2.13 will take, composed end to end: gate the zone, read the
    # name, split it.  Each step has its own test, and none of them shows that
    # the three fit together.
    line_1, _line_2 = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])

    assert td3.split_name(td3.parse_name(line_1)) == (
        "ERIKSSON",
        "ANNA<MARIA" + "<" * 19,
    )


def test_a_mononym_with_no_separator_is_all_surname_and_no_given_names():
    # The second case 2.6 asks for, and the decision in it.  A field with no
    # "<<" in it -- a holder who has one name, or a "<<" misread as "<" --
    # has no boundary to find, and the split hands back the whole field as the
    # surname with nothing on the given-names side.  The alternative, treating
    # the single name as the given names, is not distinguishable from this at
    # the parse level and would be a guess 2.14's "parsing must not silently
    # fix it" rules out.
    #
    # So the cost is a labelled one: a mononym's given-names list is empty and
    # every consumer downstream has to live with that.  Refusing instead would
    # drop a document over a shape 2.5 deliberately extracted, and a mononym is
    # an anomaly to flag, not a document to discard.
    surname, given_names = td3.split_name("NGUYEN")

    assert surname == "NGUYEN"
    assert given_names == ""


def test_a_padded_mononym_carries_its_separator_in_the_padding():
    # The consequence of the field being filler-padded, found by writing the
    # mononym test down at its real width: "NGUYEN" followed by 32 fillers does
    # contain "<<", in the padding, so the separator is found and the surname
    # comes back without the padding rather than with it.  Nothing is lost by
    # that -- the padding is filler, and 2.8 strips it -- and it means a
    # mononym and a surname with no given names are the *same string*, so this
    # task does not have to tell them apart and no test below can either.  A
    # splitter that special-cased "no given names" would be guessing.
    surname, given_names = td3.split_name("NGUYEN" + "<" * 32)

    assert surname == "NGUYEN"
    # 32 fillers, less the two that became the separator: the given-names half
    # is nothing but filler, which 2.7's split-and-drop-empty turns into no
    # names at all and 2.8's strip turns into "".
    assert given_names == mrz.FILLER * 30
    assert not given_names.strip(mrz.FILLER)


def test_a_name_of_nothing_but_filler_is_split_rather_than_refused():
    # 2.5 said explicitly that this case is 2.6's to decide rather than
    # inherit: 39 fillers split to an empty surname, and the choice was
    # between returning the empty halves and refusing the document.  It
    # returns them, on 2.4's IND reasoning -- whether a well-formed field is
    # *acceptable* is a Tier 0 policy question for the rules engine, and a
    # splitter that raised here would turn a flaggable name into a dropped
    # document.  The given-names half still carries its filler because
    # stripping is 2.8's job, not this one's.
    surname, given_names = td3.split_name(mrz.FILLER * 39)

    assert surname == ""
    assert given_names == mrz.FILLER * 37


def test_only_the_first_separator_splits_the_name():
    # The field carries one "<<", so a second is a misread -- most likely a
    # single filler doubled.  Splitting once keeps the surname intact and hands
    # the extra separator to 2.7, whose "<" split reads it as the empty entry
    # between two given names and drops it.  Splitting on every "<<" would put
    # a piece of the given names in the surname, and refusing would drop the
    # document over a misread.
    assert td3.split_name("A<<B<<C") == ("A", "B<<C")
    assert td3.split_name("A<<") == ("A", "")


def test_a_single_filler_is_not_the_separator():
    # Only "<<" separates, so a field whose separators are all single fillers
    # arrives as one primary identifier with no given names.  Reinterpreting
    # the first single filler as the separator would be 2.14's "silently fix
    # it", and the flag costs less than the guess.
    surname, given_names = td3.split_name("ERIKSSON<ANNA<MARIA")

    assert surname == "ERIKSSON<ANNA<MARIA"
    assert given_names == ""


@pytest.mark.parametrize(
    "name",
    [
        "ERIKSSON<<ANNA<MARIA" + "<" * 19,
        "ERIKSSON<<ANNA MARIA",
        "NGUYEN",
        "A<<B<<C",
        "A<<",
        "ERIKSSON<ANNA<MARIA",
        "<" * 39,
        "",
    ],
    ids=[
        "the specimen",
        "a space for a filler",
        "a mononym",
        "two separators",
        "nothing after the separator",
        "single fillers only",
        "nothing but filler",
        "empty",
    ],
)
def test_the_two_halves_are_exactly_what_the_field_holds(name):
    # The split is lossless and this says so, for every shape above: put the
    # halves back together with the separator between them and the field is
    # what it was.  A splitter that trimmed a half, or that dropped the
    # separator on a field that had none, breaks this.
    surname, given_names = td3.split_name(name)

    if mrz.FILLER * 2 in name:
        assert surname + mrz.FILLER * 2 + given_names == name
    else:
        assert surname == name
        assert given_names == ""


def test_the_split_does_not_clean_what_2_7_and_2_8_own():
    # The given names come back as ONE string, still carrying the single
    # filler between them and the 19 that pad the field: 2.7 splits them into
    # a list and 2.8 strips filler and case, and each has to start from
    # exactly this.  A splitter that split or stripped here would leave 2.7
    # nothing to do and make its tests unfalsifiable.
    surname, given_names = td3.split_name(SPECIMEN_NAME)

    assert isinstance(given_names, str)
    assert given_names.count(mrz.FILLER) == 1 + 19
    assert surname == surname.upper()
    assert given_names == given_names.upper()


@pytest.mark.parametrize("name", [None, b"ERIKSSON<<ANNA<MARIA", 42])
def test_a_name_that_is_not_a_string_is_rejected(name):
    # str.partition raises AttributeError on None and TypeError on bytes, and
    # neither is in the package's one error type, so a caller's
    # `except MrzValueError` would miss both.  The message names the type it
    # was given and not the name: this is the identity field, and 2.5 is why
    # that rule is stated here rather than assumed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.split_name(name)

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(name).__name__ in str(excinfo.value)
    assert "ERIKSSON" not in str(excinfo.value)


# --- the given names, split on the single filler into a list --------------


def test_the_given_names_splitter_is_exported():
    assert "split_given_names" in td3.__all__


def test_given_names_separated_by_a_space_stay_one_entry():
    # The first case 2.7 asks for, and the misread it is written in.  A space
    # where the MRZ prints a filler is what an OCR engine actually produces --
    # 2.6 wrote its own named case that way for the same reason -- and the
    # filler is not there to be found.  This function splits on the filler and
    # on nothing else, so "ANNA MARIA" is ONE name carrying a space, not two
    # names.  Merging them here would be 2.14's "parsing must not silently fix
    # it", and 2.8 is the task that strips a space, so a splitter that did it
    # would leave 2.8 nothing to clean up.
    assert td3.split_given_names("ANNA MARIA") == ["ANNA MARIA"]


def test_given_names_separated_by_a_filler_are_two_entries():
    # The second case 2.7 asks for, and the shape the standard actually
    # prints: a single filler between the secondary identifiers, so the
    # specimen's own given names are this with 19 fillers of padding on the
    # end.  Unlike the case above, the filler really is in the string here,
    # which is the whole difference between the two.
    assert td3.split_given_names("ANNA<MARIA") == ["ANNA", "MARIA"]


def test_the_specimen_given_names_are_split_and_the_padding_is_dropped():
    # End to end over 2.5 and 2.6's work: the real printed field, read, split
    # at the "<<" and now split again at the single fillers.  The expected
    # list is written out literally, because an expectation of
    # SPECIMEN_NAME.split("<<")[1].split("<") would pass against a function
    # that did nothing but call the stdlib's -- which is the one thing this
    # has to be more than, given the empty-entry rule below.
    _surname, given_names = td3.split_name(SPECIMEN_NAME)

    assert td3.split_given_names(given_names) == ["ANNA", "MARIA"]


def test_the_specimen_given_names_are_split_out_of_a_validated_zone():
    # The whole path 2.13 will take, composed: gate the zone, read the name,
    # split it at the "<<", split the given names at the single fillers.  Each
    # step has its own test and none of them shows that the four fit together.
    line_1, _line_2 = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])
    _surname, given_names = td3.split_name(td3.parse_name(line_1))

    assert td3.split_given_names(given_names) == ["ANNA", "MARIA"]


def test_no_given_names_is_an_empty_list_and_not_a_list_holding_an_empty_string():
    # 2.6 hands back "" for a mononym's given-names half, and the honest
    # reading of that is *no given names* -- so the list is empty.  This is
    # the one case where the empty-entry rule has to do real work rather than
    # restate what str.split already does: splitting "" on any separator
    # returns [""] -- a one-element list naming a person who has no name --
    # and only an explicit drop turns it back into [].  A consumer downstream
    # cannot tell that apart from a real name, which is the whole cost.
    assert td3.split_given_names("") == []


def test_given_names_of_nothing_but_filler_are_an_empty_list():
    # The other half of 2.6's labelled cost.  A field of nothing but filler
    # splits to 37 fillers, and every one of them is an empty entry between
    # two separators, so the list is empty -- the same answer the mononym
    # gets, for the same reason: there is no given name to name.  2.8's strip
    # would also arrive at "", so this is the case the two tasks agree on
    # rather than one the second contradicts.
    assert td3.split_given_names(mrz.FILLER * 37) == []
    assert td3.split_given_names(mrz.FILLER * 30) == []


def test_a_doubled_filler_in_the_given_names_is_an_empty_entry():
    # 2.6 kept a second "<<" in the given-names half on purpose, saying that
    # 2.7 would read it as the empty entry between two names and drop it --
    # and here it is.  This is the promise being kept: it is not a second
    # separator to honour, because the field carries only one.
    assert td3.split_given_names("B<<C") == ["B", "C"]


@pytest.mark.parametrize(
    "given_names, expected",
    [
        pytest.param("ANNA MARIA", ["ANNA MARIA"], id="a space for a filler"),
        pytest.param("ANNA<MARIA", ["ANNA", "MARIA"], id="the printed form"),
        pytest.param("ANNA<MARIA<<" + "<" * 19, ["ANNA", "MARIA"], id="the specimen"),
        pytest.param("B<<C", ["B", "C"], id="a doubled separator"),
        pytest.param("A<B<C", ["A", "B", "C"], id="three given names"),
        pytest.param("<<ANNA<<MARIA<<", ["ANNA", "MARIA"], id="empties at both ends"),
        pytest.param("ANNA<<MARIA", ["ANNA", "MARIA"], id="an interior empty"),
        pytest.param("ANNA", ["ANNA"], id="a single given name"),
        pytest.param("", [], id="no given names"),
        pytest.param(mrz.FILLER * 37, [], id="nothing but filler"),
    ],
)
def test_the_given_names_split_into_the_names_the_field_printed(given_names, expected):
    # One table over the shapes, so the rule is stated once and every shape is
    # a row: split on the single filler, keep what is between the fillers, and
    # drop every entry that is nothing.  The rows a splitter written from
    # `str.split()` with no argument would fail are the first and the second --
    # whitespace is not a separator -- and the row a splitter written from
    # `str.split(FILLER)` alone would fail is the empty one.
    assert td3.split_given_names(given_names) == expected


def test_the_names_come_back_in_the_order_the_field_printed_them():
    # The given names are a list rather than a set or a dict for this reason:
    # the order on the document is part of what the document says, and a
    # screening that compares them across documents (12.15) has to be able to
    # see that the first one differs from the first one.
    assert td3.split_given_names("ZULU<ALPHA<MIKE") == ["ZULU", "ALPHA", "MIKE"]


def test_the_entries_are_not_stripped_folded_or_otherwise_cleaned():
    # 2.8 strips filler and normalises case, and each has to start from
    # exactly what this returns, so nothing here may clean an entry.  The
    # padding below survives: a splitter that trimmed would hand 2.8 nothing
    # to strip, and a splitter that split on whitespace as well would split a
    # two-word name in half.  A whitespace-only entry is kept for the same
    # reason -- it is not a name, but saying so is 2.8's judgement to make
    # over the whole list, not this one's to make per entry.
    assert td3.split_given_names("  anna  maria  ") == ["  anna  maria  "]
    assert td3.split_given_names("   ") == ["   "]


def test_the_result_is_a_list_of_strings():
    # A list, not a tuple and not a generator: 2.13 is going to iterate it, and
    # a generator would be exhausted by the first consumer, so the type is
    # part of the contract rather than an accident of how it was built.
    names = td3.split_given_names("ANNA<MARIA")

    assert isinstance(names, list)
    assert all(isinstance(name, str) for name in names)


def test_the_given_names_half_needs_no_width_of_its_own():
    # 2.5 checks the width of the field and 2.6 checks for the separator;
    # this one has neither a length nor a content rule to enforce, so a short
    # value is answered rather than refused.  Refusing would turn a
    # flaggable name into a dropped document for no gain -- there is no
    # reading of "ANNA" that this function could not hand on to 2.8.
    assert td3.split_given_names("ANNA") == ["ANNA"]


@pytest.mark.parametrize(
    "given_names", [None, b"ANNA<MARIA", 42], ids=["none", "bytes", "int"]
)
def test_given_names_that_is_not_a_string_is_rejected(given_names):
    # str.split raises AttributeError on None and TypeError on bytes, and
    # neither is in the package's one error type, so a caller's
    # `except MrzValueError` would miss both.  The message names the type it
    # was given and not the value: this is still the name field, and 2.5 is
    # why that rule stops here rather than being assumed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.split_given_names(given_names)

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(given_names).__name__ in str(excinfo.value)
    assert "ANNA" not in str(excinfo.value)


# --- the names, cleaned of filler, whitespace and lower case ---------------


# The line 2.8 names, padded out to the width the standard prints so it can go
# through the whole real path instead of being handed straight to the cleaner.
# It is a misread: the printed name field is "LIE<<SOPHIE" and what arrived
# carries a space where a filler belongs, which is the shape both 2.6 and 2.7
# wrote their own named cases in for the same reason.  Written out longhand
# rather than sliced from anything, for the reason 2.1's longhand tables exist.
MISREAD_SPECIMEN_LINE_1 = "P<UTO LIE<SOPHIE" + mrz.FILLER * 28


def parsed_names(line_1):
    """The path 2.8 completes: gate, read, split, split, clean."""
    gated, _line_2 = td3.validate_td3_lines([line_1, SPECIMEN_LINE_2])
    surname, given_names = td3.split_name(td3.parse_name(gated))
    return td3.normalise_names(surname, td3.split_given_names(given_names))


def test_the_name_cleaner_is_exported():
    assert "normalise_names" in td3.__all__


def test_a_name_misread_with_a_space_where_a_filler_belongs_loses_the_space():
    # The test 2.8 asks for, on the line it names.  A space is not in the ICAO
    # MRZ alphabet, so one in a name field is always an OCR misread, and the
    # shape this task is about is a *filler* read as a space.  2.6 and 2.7
    # each refused to guess at it -- one splits on "<<" only, the other on "<"
    # only, and neither merges on a space -- so this is the first function in
    # the chain that touches it, and the space goes here or nowhere.
    surname, given_names = parsed_names(MISREAD_SPECIMEN_LINE_1)

    assert " " not in surname
    assert " " not in "".join(given_names)


def test_the_space_is_gone_and_the_filler_with_it():
    # The whole of what the specimen is worth, written out.  The printed field
    # is "LIE<<SOPHIE": surname LIE, then "<<", then the one given name SOPHIE.
    # What arrived has a space and a single filler where the "<<" was, so
    # 2.6's mononym branch takes the whole thing as the surname -- the
    # `<` misread-as-`<` case its docstring names -- and this strips the space
    # and the leftover filler out of it.  The name the misread destroyed is NOT
    # recovered: inventing a "<<" would be 2.14's "parsing must not silently
    # fix it", so the cost is labelled here rather than hidden.
    surname, given_names = parsed_names(MISREAD_SPECIMEN_LINE_1)

    assert (surname, given_names) == ("LIESOPHIE", [])


def test_the_misread_line_really_is_a_td3_line():
    # Guard on the fixture rather than on the parser: if the padding above
    # were wrong the test would pass for the wrong reason, through
    # validate_td3_lines rejecting the line or through parse_name truncating
    # it.  5 + 1 + 10 + 28 is the 44 the standard prints, and the name field is
    # the 39 characters after position 5.
    assert len(MISREAD_SPECIMEN_LINE_1) == 44
    assert MISREAD_SPECIMEN_LINE_1[:5] == "P<UTO"
    assert len(MISREAD_SPECIMEN_LINE_1[5:]) == 39
    assert td3.parse_document_code(MISREAD_SPECIMEN_LINE_1) == "P<"
    assert td3.parse_issuing_state(MISREAD_SPECIMEN_LINE_1) == "UTO"


def test_the_specimen_names_survive_the_cleaning_unchanged():
    # The other direction, and the one that proves the cleaner is not simply
    # eating characters.  A correctly printed passport has no filler inside a
    # name, no whitespace and no lower case, so the specimen comes back
    # exactly as 2.6 and 2.7 produced it.
    assert parsed_names(SPECIMEN_LINE_1) == ("ERIKSSON", ["ANNA", "MARIA"])


def test_a_lower_case_read_is_normalised_to_upper_case():
    # The second half of the task, which the specimen cannot demonstrate: every
    # character in the line 2.8 names is already upper case, so a suite with
    # only that case would pass against a function that removed the space and
    # nothing else.  An MRZ is printed in capitals and a lower-case letter is a
    # misread, so the name comes back the way the document claims to print it.
    assert td3.normalise_names("eriksson", ["anna", "maria"]) == (
        "ERIKSSON",
        ["ANNA", "MARIA"],
    )


def test_a_mixed_case_read_is_normalised_to_upper_case():
    # Case, not just full lower case: a real OCR read is as likely to give
    # "Eriksson" as "eriksson", and a cleaner written from str.lower()
    # somewhere in the chain would catch only one of the two.
    assert td3.normalise_names("Eriksson", ["Anna", "MaRia"]) == (
        "ERIKSSON",
        ["ANNA", "MARIA"],
    )


def test_the_cleaning_reaches_every_character_and_not_just_the_ends():
    # str.strip() removes whitespace at the ends only, and the interior is
    # where the misread actually lives: 2.7's own test holds
    # "  anna  maria  " as a single entry, and this is the function that has to
    # deal with it.  It is *stripped*, not split -- the entry stays one name,
    # because 2.7 already decided that a space is not a separator and 2.14
    # rules out splitting it here.
    assert td3.normalise_names("  Eriksson  ", ["  anna  maria  "]) == (
        "ERIKSSON",
        ["ANNAMARIA"],
    )


@pytest.mark.parametrize(
    "whitespace", [" ", "\t", "\n", "\r"], ids=["space", "tab", "newline", "return"]
)
def test_every_kind_of_whitespace_a_read_can_produce_is_removed(whitespace):
    # A space is the one a real engine produces, but a tab or a newline read
    # out of a misaligned row is the same mistake with a different character,
    # and a cleaner written as name.replace(" ", "") would leave them in as
    # un-MRZ characters no consumer could do anything with.
    assert td3.normalise_names(
        f"ERIKSSON{whitespace}", [f"ANNA{whitespace}MARIA"]
    ) == ("ERIKSSON", ["ANNAMARIA"])


@pytest.mark.parametrize(
    "surname, given_names, expected",
    [
        pytest.param("ERIKSSON", ["ANNA", "MARIA"], ("ERIKSSON", ["ANNA", "MARIA"]), id="clean"),
        pytest.param("eriksson", ["anna"], ("ERIKSSON", ["ANNA"]), id="lower case"),
        pytest.param("ERIKSSON", ["ANNA MARIA"], ("ERIKSSON", ["ANNAMARIA"]), id="a space for a filler"),
        pytest.param("ERIKSSON", ["A<B"], ("ERIKSSON", ["AB"]), id="a filler inside a given name"),
        pytest.param("ERIKSSON<ANNA", [], ("ERIKSSONANNA", []), id="the surname misread case"),
        pytest.param("   ", [], ("", []), id="a surname that is only whitespace"),
        pytest.param("ERIKSSON", ["   "], ("ERIKSSON", []), id="a given name that is only whitespace"),
        pytest.param("", [], ("", []), id="no names at all"),
        pytest.param("ERIKSSON", [], ("ERIKSSON", []), id="no given names"),
    ],
)
def test_names_are_cleaned_on_one_rule_over_every_shape(surname, given_names, expected):
    # The rule stated once: take out the filler, take out the whitespace, put
    # the case up, and drop a given name that is nothing once that is done.
    # The rows a cleaner that forgot the filler would fail is the fourth and
    # the fifth -- the fifth is the one 2.6's docstring promised would arrive
    # here -- and the row a cleaner that only stripped the ends would fail is
    # the third.
    assert td3.normalise_names(surname, given_names) == expected


def test_a_given_name_that_is_nothing_but_whitespace_is_dropped():
    # The judgement 2.7 explicitly deferred: "a whitespace-only entry is kept
    # here -- it is not a name, but saying so is a judgement about the whole
    # list and it is 2.8's to make over it."  This is it.  Stripped, "   " is
    # "", and a list holding "" names a person who has no name -- the same
    # argument 2.7 used for the empty entry, one step later.
    assert td3.split_given_names("   ") == ["   "]
    assert td3.normalise_names("ERIKSSON", ["   "]) == ("ERIKSSON", [])


def test_the_empty_string_never_survives_the_cleaning():
    # The invariant behind the drop, over both ways a name can arrive empty.
    # 2.7 already removed the "" entries a filler produces; this removes the
    # ones a space produces, and after it no entry in the list is "".
    cleaned = td3.normalise_names("  ", ["", " ", "\t", "ANNA", "  "])

    assert cleaned == ("", ["ANNA"])
    assert all(name for name in cleaned[1])


def test_a_surname_that_cleans_to_nothing_is_kept_as_the_empty_string():
    # The list is judged; the surname is not.  2.6 already hands back "" for a
    # name field of nothing but filler, and dropping it here as well would
    # mean a caller could no longer tell "no surname" from "not parsed", and
    # would give 2.13 a tuple of a different shape depending on the document.
    assert td3.normalise_names(mrz.FILLER * 37, []) == ("", [])


def test_the_order_the_field_printed_survives_the_cleaning():
    # 2.7 made the order part of the contract so 12.15 can see that the first
    # name differs from the first name on another document.  A cleaner that
    # deduplicated, sorted or dropped duplicates on the way past would take
    # that back, and 12.15 would compare the wrong pair.
    assert td3.normalise_names("ZULU", ["alfa", "mike", "alfa"]) == (
        "ZULU",
        ["ALFA", "MIKE", "ALFA"],
    )


def test_a_cleaned_name_holds_no_mrz_punctuation():
    # What the cleaning is *for*, said as an invariant over all three of the
    # things it takes out at once: what comes back is something a person can be
    # called, not something a misread engine produced.
    surname, given_names = parsed_names(MISREAD_SPECIMEN_LINE_1)

    for name in (surname, *given_names):
        assert mrz.FILLER not in name
        assert name == name.strip()
        assert name == name.upper()
        assert not any(character.isspace() for character in name)


def test_nothing_is_transliterated_here():
    # 2.9's job, and the line that keeps it a job: MÜLLER is already upper case
    # and carries no filler and no space, so it comes back untouched.  A
    # cleaner that reached for unidecode or an ASCII fold here would make 2.9
    # look already done, and the transliteration map would have nothing to add
    # and no reason to exist.
    assert td3.normalise_names("MÜLLER", ["ØYVIND"]) == ("MÜLLER", ["ØYVIND"])


def test_a_diacritic_is_upper_cased_but_not_folded_away():
    # The companion to the test above, and the reason it cannot pass by
    # accident.  A cleaner that folded to the ASCII alphabet -- which is what
    # ``str.encode("ascii", "ignore")`` or a hand-rolled ASCII table does --
    # would return "MULLER" for a *lower-case* diacritic while still returning
    # "MÜLLER" for an upper-case one, because the fold has nothing to do to a
    # character outside A-Z.  str.upper is the whole of the case rule here, so
    # the diacritic is carried and changed and 2.9 still has a character to
    # map.
    assert td3.normalise_names("müller", ["øyvind"]) == ("MÜLLER", ["ØYVIND"])


def test_the_cleaning_is_its_own_inverse_on_an_already_clean_name():
    # A cleaner applied twice has to be the same as a cleaner applied once,
    # because 2.9 and whatever comes after it will call into this path and
    # nobody should have to track how many times a name went through it.
    once = td3.normalise_names(" eriksson ", [" anna ", " maria "])

    assert td3.normalise_names(*once) == once


def test_the_result_is_a_surname_and_a_list_of_names():
    # The shape 2.13 assembles, pinned: a string and a list, not a list of
    # lists and not a generator.  2.7's argument applies unchanged -- the
    # caller iterates these more than once -- and the surname stays beside the
    # given names because the printed field put them side by side.
    cleaned = td3.normalise_names("eriksson", ["anna", "maria"])

    assert isinstance(cleaned, tuple)
    assert len(cleaned) == 2
    assert isinstance(cleaned[0], str)
    assert isinstance(cleaned[1], list)
    assert all(isinstance(name, str) for name in cleaned[1])


@pytest.mark.parametrize("surname", [None, b"ERIKSSON", 42], ids=["none", "bytes", "int"])
def test_a_surname_that_is_not_a_string_is_rejected(surname):
    # str.replace raises AttributeError on None and TypeError on bytes, and
    # neither is the package's one error type, so a caller's
    # `except MrzValueError` would miss both.  The message names the type and
    # never the name: 2.5 is why that rule is stated rather than assumed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.normalise_names(surname, ["ANNA"])

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(surname).__name__ in str(excinfo.value)
    assert "ANNA" not in str(excinfo.value)


@pytest.mark.parametrize(
    "given_names", [None, 42], ids=["none", "int"]
)
def test_given_names_that_are_not_a_sequence_are_rejected(given_names):
    # Iterating a non-iterable raises TypeError, which is not the package's
    # one error type.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.normalise_names("ERIKSSON", given_names)

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(given_names).__name__ in str(excinfo.value)


@pytest.mark.parametrize("given_names", ["ANNA<MARIA", b"ANNA"], ids=["str", "bytes"])
def test_a_bare_string_is_not_a_sequence_of_names(given_names):
    # The trap validate_td3_lines already documents for a zone: a string is a
    # sequence, so iterating "ANNA" would hand back four names called A, N, N
    # and A, and b"ANNA" would iterate as integers.  A caller passing the
    # given-names *string* instead of 2.7's list is a mistake worth naming, not
    # a name to invent.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.normalise_names("ERIKSSON", given_names)

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(given_names).__name__ in str(excinfo.value)


@pytest.mark.parametrize("entry", [None, b"ANNA", 7], ids=["none", "bytes", "int"])
def test_a_given_name_that_is_not_a_string_is_rejected(entry):
    # The list is checked element by element rather than trusted, because the
    # same mistake arrives through it: a comprehension over a list holding one
    # bad entry would raise TypeError from inside the loop, still not
    # MrzValueError, and still carrying the value in the traceback's locals.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.normalise_names("ERIKSSON", ["ANNA", entry])

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(entry).__name__ in str(excinfo.value)
    assert "ANNA" not in str(excinfo.value)


def test_a_rejected_name_is_the_packages_one_error_type():
    # 1.9's rule, checked on this function rather than assumed: every way in
    # out of here is MrzValueError, and MrzValueError is a ValueError so an
    # `except ValueError` caller keeps working.
    for bad in [(None, []), (b"ERIKSSON", []), ("ERIKSSON", None), ("ERIKSSON", 42), ("ERIKSSON", "ANNA"), ("ERIKSSON", [7])]:
        with pytest.raises(mrz.MrzValueError) as excinfo:
            td3.normalise_names(*bad)
        assert type(excinfo.value) is mrz.MrzValueError
        assert isinstance(excinfo.value, ValueError)


# --- the names, transliterated to the MRZ alphabet --------------------------


# A name field that is a valid MRZ field except that the OCR engine read two
# characters the visible zone prints with a diacritic: the MÜLLER of the task,
# and the Ø of the second named case.  Padded longhand and not sliced from
# anything, for the reason 2.1's longhand tables exist; the field is 39 wide
# and the printed name is 14 characters, so 25 fillers pad it out.
TRANSLITERATED_SPECIMEN_LINE_1 = "P<UTOMÜLLER<<ØYVIND" + mrz.FILLER * 25


def parsed_and_transliterated(line_1):
    """The path 2.9 completes: 2.5-2.8's, then transliterate."""
    return td3.transliterate_names(*parsed_names(line_1))


def test_the_transliterator_is_exported():
    assert "transliterate_names" in td3.__all__


def test_the_map_is_exported_so_a_caller_knows_what_was_tried():
    # The map is the one place a transliterated-to value is stated, exactly as
    # the layout tables are the one place a position is stated.  A rules engine
    # that wants to flag a name it could not transliterate has to be able to
    # read the list of what was attempted rather than guess at it.
    assert "TRANSLITERATIONS" in td3.__all__


def test_the_transliterated_line_is_really_a_td3_line():
    # The fixture guard, so neither named case below can pass for the wrong
    # reason: a line that is 43 characters would have its name field cut short
    # and would raise in 2.5 before the transliteration was ever reached.
    assert len(TRANSLITERATED_SPECIMEN_LINE_1) == td3.TD3_LINE_LENGTH
    assert len(td3.parse_name(TRANSLITERATED_SPECIMEN_LINE_1)) == 39


def test_a_diacritic_becomes_the_base_letter_the_document_meant():
    # The test 2.9 asks for, on a whole printed line.  MÜLLER reaches the
    # transliterator already upper case with no filler and no space, so what
    # comes out differs from what went in in exactly one way: the mark is off
    # the U and the letter underneath it is still there.
    surname, given_names = parsed_and_transliterated(TRANSLITERATED_SPECIMEN_LINE_1)

    assert (surname, given_names) == ("MULLER", ["OYVIND"])


def test_the_letter_with_a_stroke_through_it_becomes_the_letter_without_one():
    # The task's second named case.  Ø is the one that cannot be derived: it
    # is a letter in its own right in Danish and Norwegian, Unicode gives it
    # no decomposition, and so nothing mechanical can take the stroke off it.
    # The MRZ has one O, and O is the letter the document meant.
    assert td3.transliterate_names("Ø", []) == ("O", [])
    assert td3.transliterate_names("ØYVIND", []) == ("OYVIND", [])


def test_the_map_holds_exactly_the_letters_the_task_names():
    # Pinned as a set, so a map that gained or lost an entry would be a
    # decision somebody made and wrote down rather than an accident.  It is
    # four entries and not two hundred, and that is deliberate: every other
    # accented letter in the Latin ranges is handled by a rule rather than
    # quoted (see the test below), and the letters Unicode will not decompose
    # -- AE ligature, OE ligature, thorn, eth, eng, h-stroke, ij ligature,
    # middle-dot L, t-stroke -- are deliberately *not* here, because no source
    # for their ICAO values was in reach and 1.6's rule is not to quote a
    # remembered one.  The cost of leaving them out is named in its own test.
    assert td3.TRANSLITERATIONS == {
        "ß": "SS",
        "Ø": "O",
        "Ł": "L",
        "Đ": "D",
    }


@pytest.mark.parametrize(
    "accented, base",
    [
        pytest.param("ÀÁÂÃÄÅĀĂĄ", "AAAAAAAAA", id="A with every mark"),
        pytest.param("ÇĆĈĊČ", "CCCCC", id="C cedilla and caron"),
        pytest.param("ÉÈÊËĒĔĖĘĚ", "EEEEEEEEE", id="E acute grave circumflex diaeresis"),
        pytest.param("ÍÌÎÏĨĪĬĮİ", "IIIIIIIII", id="I with every mark, Turkish dotted included"),
        pytest.param("ÑŃŇŅ", "NNNN", id="N tilde and accents"),
        pytest.param("ÓÒÔÕÖŐŌ", "OOOOOOO", id="O with every mark"),
        pytest.param("ŠŚŜŞ", "SSSS", id="S caron and accents"),
        pytest.param("ÚÙÛÜŨŪŬŮŰŲ", "UUUUUUUUUU", id="U with every mark"),
        pytest.param("ÝŶŸ", "YYY", id="Y with diaeresis"),
        pytest.param("ŽŹŻ", "ZZZ", id="Z with caron and accents"),
    ],
)
def test_a_diacritic_becomes_its_base_letter(accented, base):
    # The rule that covers the map's other three quarters of the alphabet, and
    # it is a *rule* rather than a table because a table of two hundred
    # characters would be two hundred remembered values, which 1.6 forbids.
    # Every one of these letters decomposes canonically into its base plus a
    # combining mark, and taking the marks off leaves the base: the accented
    # string and the plain string are the same length, one letter each.
    assert len(accented) == len(base)
    assert td3.transliterate_names(accented, []) == (base, [])


def test_the_letter_under_the_diacritic_is_kept_and_not_just_removed():
    # The failure a strip written as a deletion rather than a decomposition
    # would have: "ANGSTROM" instead of "ANGSTROM", one letter short, a
    # surname that no longer matches the document by more than an accent.
    surname, _ = td3.transliterate_names("ÅNGSTRÖM", [])

    assert surname == "ANGSTROM"
    assert len(surname) == 8


def test_a_name_already_in_the_mrz_alphabet_comes_back_unchanged():
    # What has to be true of most names, on the real specimen: the ICAO
    # specimen passport prints its name in capitals with no diacritic, so the
    # whole path runs and the last step changes nothing.
    assert parsed_and_transliterated(SPECIMEN_LINE_1) == ("ERIKSSON", ["ANNA", "MARIA"])


def test_it_does_not_re_case_strip_or_split():
    # The three things the handover says this must not do, because they are
    # 2.8's and 2.7's and doing them here would make those unfalsifiable.  The
    # name handed over is padded, mixed case and carries a space, and all
    # three survive: str.upper is not repeated, the whitespace table is not
    # reapplied, and "ANNA MARIA" stays one name rather than becoming two.
    surname, given_names = td3.transliterate_names(" eRiKSSon ", [" anna maria "])

    assert (surname, given_names) == (" eRiKSSon ", [" anna maria "])


def test_every_given_name_is_transliterated_and_not_only_the_first():
    # A comprehensions that stopped after the first entry, or a transliterator
    # that only looked at the surname, would pass every other test in this
    # section.
    assert td3.transliterate_names("Ø", ["Ł", "Đ", "Ü"]) == (
        "O",
        ["L", "D", "U"],
    )


def test_the_surname_and_the_given_names_go_through_the_same_rule():
    # 2.8 wrote one private helper so the two halves could not be cleaned
    # differently; the way to check that here is to hand both halves the same
    # character and require the same answer from each.
    assert td3.transliterate_names("Ø", ["Ø"]) == ("O", ["O"])
    assert td3.transliterate_names("Ü", ["Ø", "Ł", "Đ"]) == ("U", ["O", "L", "D"])


@pytest.mark.parametrize(
    "letter",
    ["Æ", "Œ", "Þ", "Ð", "Ŋ", "Ħ", "Ĳ", "Ŀ", "Ŧ", "Ǆ", "Ж", "①"],
    ids=[
        "AE ligature",
        "OE ligature",
        "thorn",
        "eth",
        "eng",
        "H with stroke",
        "IJ ligature",
        "L with middle dot",
        "T with stroke",
        "DZ digraph",
        "cyrillic",
        "circled digit",
    ],
)
def test_a_character_the_map_does_not_name_is_carried_through_unchanged(letter):
    # 2.14's rule is "parsing must not silently fix it", and a *dropped*
    # character is the worst kind of silent fix: it changes a name and leaves
    # no mark that anything downstream could see.  So anything this cannot map
    # is carried, whole, in both halves.  An AE ligature is the honest example
    # -- AE is what the standard would want and it is not in the map, so it
    # stays AE rather than becoming a guess.
    assert td3.transliterate_names(letter, [letter]) == (letter, [letter])


def test_a_name_the_map_cannot_reach_is_still_outside_the_mrz_alphabet():
    # The cost of the rule above, stated rather than hidden: carrying the
    # character through is right, and it does not make the name readable by the
    # arithmetic.  Nothing in Tier 0 turns AE into AE; that is a rules-engine
    # flag, and the evidence it needs is a name the transliterator could not
    # finish.
    surname, _ = td3.transliterate_names("Æ", [])

    assert surname == "Æ"
    with pytest.raises(mrz.MrzValueError):
        mrz.char_value(surname)


def test_a_compatibility_form_is_not_a_diacritic():
    # The decomposition is canonical (NFD) and not compatibility (NFKD), and
    # this is the difference: NFKD would also expand the DZ digraph to D plus Z
    # with a caron, which is a rewrite of the name rather than the taking off
    # of an accent, and it would do it to a name that has no accent on it at
    # all.  So the digraph is carried through, and is flagged downstream.
    assert td3.transliterate_names("Ǆ", []) == ("Ǆ", [])


def test_the_upper_case_step_already_takes_the_lower_case_ones():
    # A fact about the previous task, found by running the characters, and it
    # changes what the map is for.  str.upper -- which is the whole of 2.8's
    # case rule -- already maps the lower case of all four: "weiß" is WEISS,
    # "øyvind" is ØYVIND, "łukasz" is ŁUKASZ, "đorđe" is ĐORĐE.  So through the
    # real path the map's four entries only ever see the upper-case
    # characters, and ß in particular can never reach it: the S-S in WEISS was
    # written by str.upper, not by the map.  The map's es-sharp-s entry is
    # still worth having for a caller that hands this function a name directly.
    cleaned = td3.normalise_names("weiß", ["øyvind", "łukasz", "đorđe"])

    assert cleaned == ("WEISS", ["ØYVIND", "ŁUKASZ", "ĐORĐE"])
    assert td3.transliterate_names(*cleaned) == (
        "WEISS",
        ["OYVIND", "LUKASZ", "DORDE"],
    )


def test_the_escaped_s_is_the_only_letter_the_map_makes_longer():
    # Every other entry is one character for one character; the sharp s is two,
    # and that is the standard's own value rather than this function's choice.
    assert len(td3.transliterate_names("STRAßE", [])[0]) == 7
    assert len(td3.transliterate_names("Ø", [])[0]) == 1


def test_a_name_that_grows_is_not_truncated_to_the_field_width():
    # The 39-character width is a property of the *field* and 2.5 already
    # checked it, so a name that has been through the whole path is free to be
    # longer than the field it came from.  A transliterator that padded or cut
    # to keep the width would silently change a name here.
    surname, _ = td3.transliterate_names("STRAßE" * 10, [])

    assert surname == "STRASSE" * 10
    assert len(surname) == 70


def test_the_transliteration_is_its_own_inverse_on_a_finished_name():
    # 2.8 pinned that its cleaner is, so a name can go through this more than
    # once -- 2.13 assembles from these pieces and a later comparison may hand
    # a name back through -- without anyone tracking how many times.
    once = parsed_and_transliterated(TRANSLITERATED_SPECIMEN_LINE_1)

    assert td3.transliterate_names(*once) == once


def test_a_transliterated_name_can_be_read_by_the_mrz_arithmetic():
    # The reason the map exists at all, as an assertion rather than a claim:
    # char_value raises for a diacritic and does not for the base letter, so
    # this is the difference the map makes to anything downstream of it.
    surname, _given_names = parsed_names(TRANSLITERATED_SPECIMEN_LINE_1)

    with pytest.raises(mrz.MrzValueError):
        mrz.char_value(surname)
    transliterated = parsed_and_transliterated(TRANSLITERATED_SPECIMEN_LINE_1)
    for name in (transliterated[0], *transliterated[1]):
        assert [mrz.char_value(character) for character in name]


def test_a_transliterated_name_holds_only_characters_the_alphabet_has():
    # The invariant, over the two halves and over a name that went through the
    # whole printed path rather than being handed to the function directly.
    cleaned = parsed_and_transliterated(TRANSLITERATED_SPECIMEN_LINE_1)

    for name in (cleaned[0], *cleaned[1]):
        assert set(name) <= set(mrz.CHAR_VALUES)


def test_no_entry_in_the_list_is_left_empty():
    # 2.7 dropped the empty entries a filler produces and 2.8 dropped the ones
    # a space produces, so "no entry in the list is ''" is an invariant those
    # two established.  Transliterating is the one step that can empty a name
    # -- a name of nothing but combining marks loses all of them -- and
    # letting that through would quietly reintroduce what they removed.
    cleaned = td3.transliterate_names("ERIKSSON", ["̈", "ANNA"])

    assert cleaned == ("ERIKSSON", ["ANNA"])
    assert all(name for name in cleaned[1])


def test_the_surname_is_not_judged_even_here():
    # 2.8's rule, unchanged: the list is judged and the surname is not, because
    # 2.6 already hands back "" for a name field of nothing but filler and a
    # caller has to be able to tell "no surname" from "not parsed".  The
    # second half is the part a mutation of the return statement gets wrong: a
    # surname that transliterates to nothing must not take the given names
    # with it, because "no surname" is still a holder with given names.
    assert td3.transliterate_names("̈", []) == ("", [])
    assert td3.transliterate_names("̈", ["ANNA"]) == ("", ["ANNA"])


def test_the_order_the_field_printed_still_survives():
    # 2.7 made the order part of the contract so 12.15 can see that the first
    # name differs from the first name on another document, and nothing in this
    # step may reorder or deduplicate.
    assert td3.transliterate_names("Ø", ["Ü", "Ø", "Ü"]) == (
        "O",
        ["U", "O", "U"],
    )


def test_the_transliterated_result_is_a_surname_and_a_list_of_names():
    # The shape 2.13 assembles, pinned again at the end of the chain: a string
    # and a list, not a list of lists and not a generator, because the caller
    # iterates these more than once.
    transliterated = td3.transliterate_names("Ø", ["Ł", "Đ"])

    assert isinstance(transliterated, tuple)
    assert len(transliterated) == 2
    assert isinstance(transliterated[0], str)
    assert isinstance(transliterated[1], list)
    assert all(isinstance(name, str) for name in transliterated[1])


@pytest.mark.parametrize("surname", [None, b"ERVIND", 42], ids=["none", "bytes", "int"])
def test_the_transliterator_refuses_a_surname_that_is_not_a_string(surname):
    # The same guard 2.8 makes, and for the same reason: this function is
    # reachable from a caller, and translate raises TypeError on bytes and
    # AttributeError on None, neither of which is the package's one error type.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.transliterate_names(surname, ["ANNA"])

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(surname).__name__ in str(excinfo.value)
    assert "ANNA" not in str(excinfo.value)


@pytest.mark.parametrize("given_names", [None, 42], ids=["none", "int"])
def test_the_transliterator_refuses_given_names_that_are_not_a_sequence(
    given_names,
):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.transliterate_names("Ø", given_names)

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(given_names).__name__ in str(excinfo.value)


@pytest.mark.parametrize("given_names", ["ANNA<MARIA", b"ANNA"], ids=["str", "bytes"])
def test_the_transliterator_refuses_a_bare_string_as_a_sequence_of_names(
    given_names,
):
    # A caller passing the given-names *string* instead of 2.7's list is the
    # same mistake 2.8 documents, and it is worth naming rather than
    # transliterating one character at a time and reporting nothing wrong.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.transliterate_names("Ø", given_names)

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(given_names).__name__ in str(excinfo.value)


@pytest.mark.parametrize("entry", [None, b"ANNA", 7], ids=["none", "bytes", "int"])
def test_the_transliterator_refuses_a_given_name_that_is_not_a_string(entry):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.transliterate_names("Ø", [entry])

    assert type(excinfo.value) is mrz.MrzValueError
    assert type(entry).__name__ in str(excinfo.value)
    assert "Ø" not in str(excinfo.value)


def test_a_name_the_transliterator_refuses_is_the_packages_one_error_type():
    # 1.9's rule, checked here as well: every way in and out of this function
    # is MrzValueError, and it is a ValueError so an `except ValueError`
    # caller keeps working.
    for bad in [(None, []), (b"O", []), ("Ø", None), ("Ø", 42), ("Ø", "ANNA"), ("Ø", [7])]:
        with pytest.raises(mrz.MrzValueError) as excinfo:
            td3.transliterate_names(*bad)
        assert type(excinfo.value) is mrz.MrzValueError
        assert isinstance(excinfo.value, ValueError)


# --- the document number: the first field of line 2 -----------------------


def line_2_with_document_number(number):
    """A full-length TD3 line 2 whose positions 1-9 read ``number``.

    Nine characters is the only width that fits at positions 1-9 of a
    44-character line, so the width is asserted here rather than discovered
    later: a short number is what a *short line* produces, not what a
    well-formed line prints, and that case is tested on its own below.
    """
    start, end = td3.TD3_LINE_2["document_number"]
    assert len(number) == end - start + 1

    return SPECIMEN_LINE_2[: start - 1] + number + SPECIMEN_LINE_2[end:]


def test_the_document_number_names_are_exported():
    assert {"parse_document_number", "validate_document_number"} <= set(td3.__all__)


def test_the_document_number_is_nine_positions_wide_in_the_layout():
    # The width is read out of the table rather than typed into the check, so
    # the standard's positions stay the only place a position is stated and a
    # message cannot disagree with the layout it is describing.
    start, end = td3.TD3_LINE_2["document_number"]

    assert (start, end) == (1, 9)
    assert end - start + 1 == 9
    assert SPECIMEN_LINE_2[start - 1 : end] == "L898902C<"


def test_a_normal_document_number_is_read_from_positions_1_to_9():
    # The task's first named case, end to end: the shape gate, the slice and
    # the judgement, over the ICAO specimen passport.
    zone = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])
    line_1, line_2 = zone
    start, end = td3.TD3_LINE_2["document_number"]
    number = td3.parse_document_number(line_2)

    assert zone == (SPECIMEN_LINE_1, SPECIMEN_LINE_2)
    assert number == "L898902C<"
    assert len(number) == end - start + 1
    # The neighbouring slices are different text, so a reader off by one in
    # either direction cannot pass: position 10 is the check digit this task
    # does not read, and nothing is printed before position 1.
    assert number not in (SPECIMEN_LINE_2[1:10], SPECIMEN_LINE_2[0:8])


def test_a_document_number_of_nothing_but_filler_is_rejected():
    # The task's second named case, and the reason the rule is "non-empty"
    # rather than "not an empty string": the field is nine characters wide and
    # filler-padded, so `if not number` accepts a document that printed no
    # number at all.  A field of nine fillers is what that looks like.
    line = line_2_with_document_number("<" * 9)
    assert len(line) == td3.TD3_LINE_LENGTH

    with pytest.raises(mrz.MrzValueError):
        td3.parse_document_number(line)

    with pytest.raises(mrz.MrzValueError):
        td3.validate_document_number("<" * 9)


@pytest.mark.parametrize(
    "number", ["", "<", "<" * 9, "<<<<<<<<"], ids=["empty", "one", "nine", "eight"]
)
def test_a_document_number_with_nothing_in_it_is_rejected(number):
    # Every field that prints no character but the padding, whatever its
    # width.  The filler is the only character the standard itself uses to
    # mean "no value here", which is why it is the one that is removed before
    # the emptiness is judged.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_document_number(number)

    # The message says what was wrong without saying what was read, and still
    # says enough to act on: 2.2's rule is why the value is absent, and
    # "nothing but the filler" is the whole of the diagnosis.
    assert "filler" in str(excinfo.value)


@pytest.mark.parametrize(
    "number",
    [
        "L898902C<",
        "L898902C3",
        "123456789",
        "A<<<<<<<<",
        "AB1234567",
        "9<8<7<6<<",
    ],
    ids=[
        "the specimen",
        "nine characters, no padding",
        "all digits",
        "one letter and eight fillers",
        "letters and digits",
        "filler between the digits",
    ],
)
def test_a_document_number_with_something_in_it_is_accepted(number):
    assert td3.validate_document_number(number) == number


def test_padding_with_filler_is_not_emptiness():
    # The mirror of the task's second named case, and the boundary between the
    # two.  Eight fillers pad a one-character number and are not emptiness;
    # only a field with *no* character that is not the padding is.
    assert td3.validate_document_number("A<<<<<<<<") == "A<<<<<<<<"

    with pytest.raises(mrz.MrzValueError):
        td3.validate_document_number("<" * 9)


def test_the_number_comes_back_exactly_as_printed_with_its_padding():
    # Nothing is stripped, and the padding in particular is load-bearing: the
    # check digit at position 10 is computed over positions 1-9 *as printed*,
    # and `char_value(FILLER) == 0` exists so the filler is a character that
    # digit covers rather than tidying.  `L898902C<` checks to the 3 the
    # specimen prints.
    number = td3.parse_document_number(SPECIMEN_LINE_2)
    printed = SPECIMEN_LINE_2[9]

    assert number == "L898902C<"
    assert mrz.check_digit(number) == int(printed)
    # And the agreement a stripping reader would enjoy on this specimen is a
    # trap, not a licence: a *trailing* filler contributes nothing to the sum
    # and shifts no weight, so dropping it cannot change the digit.  Move the
    # filler and the two answers part company, which is why the padding is
    # kept and why the width is a rule of its own.
    assert mrz.check_digit(number.replace("<", "")) == int(printed)
    assert mrz.check_digit("<1234567<") != mrz.check_digit("1234567")


@pytest.mark.parametrize(
    "number",
    ["l898902c<", " L898902C", "L898902C ", "L898902 C", "L898902C\n"],
    ids=[
        "lower case",
        "leading space",
        "trailing space",
        "inner space",
        "a newline where a character should be",
    ],
)
def test_the_number_is_not_stripped_recased_or_otherwise_edited(number):
    # 2.8 removed the filler, the whitespace and the lower case from a *name*
    # and 2.9 transliterated it.  None of that is repeated here, because the
    # filler is what the check digit is computed over and the task asks for a
    # number, not a cleaned string.  What the line printed is what comes back.
    assert td3.validate_document_number(number) == number


def test_a_number_the_standard_cannot_print_is_left_to_the_check_digit():
    # There is no space in the ICAO alphabet, so a field carrying one is a
    # misread rather than a number, and the rule this task states -- "non-empty"
    # -- does not reach it: the field is not empty, it holds a character.  What
    # matters is that the failure is *reported* rather than lost, and 1.6's
    # arithmetic is where it is reported.  An implementation that also rejected
    # characters outside the MRZ alphabet here would be inventing a rule the
    # task does not state, and would put the check in the wrong place: 2.14 is
    # where "parsing must not silently fix it" lives.
    number = "  <<<<<<<"

    assert td3.validate_document_number(number) == number
    with pytest.raises(mrz.MrzValueError):
        mrz.check_digit(number)


@pytest.mark.parametrize(
    "number",
    ["L898902", "L898902C<3", "L898902C<X"],
    ids=["eight", "ten", "ten with a filler"],
)
def test_a_document_number_of_the_wrong_width_is_rejected(number):
    # A field of the right width is what the layout says positions 1-9 hold.
    # A short one is a line that stopped early, and a long one is a reader that
    # reached into position 10 -- the check digit -- which is a different field
    # entirely.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_document_number(number)

    message = str(excinfo.value)
    start, end = td3.TD3_LINE_2["document_number"]
    assert str(end - start + 1) in message
    assert str(len(number)) in message


def test_the_rejection_does_not_echo_the_number():
    # 2.3 named the document *code* and 2.4 named the *state*: neither names a
    # person.  A document number is the identifier the screening is about, and
    # it is unique to one holder's document, so the value is absent from every
    # message here.  The width, which says what was expected, is present -- and
    # the check digit printed after the number is inside this rejected value,
    # so an echo would leak both.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_document_number("L898902C<3")

    message = str(excinfo.value)
    assert "L898902C" not in message
    assert repr("L898902C<3") not in message
    assert "9" in message


@pytest.mark.parametrize(
    "number", [None, 42, b"L898902C<"], ids=["None", "an int", "bytes"]
)
def test_a_document_number_that_is_not_a_string_is_rejected(number):
    # Iterating or measuring a non-string raises the bare TypeError 1.9
    # forbids, which a caller catching MrzValueError would never see.  bytes is
    # the subtle one: `len(b"<<<<<<<<<")` is 9, so a validator that measured
    # before checking the type would wave a byte string through as a number
    # with nothing in it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_document_number(number)

    assert type(number).__name__ in str(excinfo.value)


def test_the_document_number_is_read_from_line_2_and_not_line_1():
    # Line 1's positions 1-9 are the document code and the issuing state, so a
    # reader pointed at the wrong table hands back different text and cannot
    # pass by accident.
    number = td3.parse_document_number(SPECIMEN_LINE_2)

    assert number == "L898902C<"
    assert number != SPECIMEN_LINE_1[0:9]
    assert SPECIMEN_LINE_1[0:9] == "P<UTOERIK"
    # And the cost, stated rather than hidden: "P<UTOERIK" is not empty either,
    # so a caller that hands this function line 1 by mistake gets a plausible
    # nine-character answer.  Only the check digit at position 10 of the real
    # line 2 disagrees, and 2.14 is the task that says so.
    assert td3.parse_document_number(SPECIMEN_LINE_1) == "P<UTOERIK"


@pytest.mark.parametrize("line", ["", "L8", "L898902"], ids=["empty", "two", "eight"])
def test_a_line_too_short_to_hold_a_document_number_is_rejected(line):
    # A line that stops before position 9 slices to a short or empty string.
    # That is not a number of the field's width and must not be waved through
    # as one.
    with pytest.raises(mrz.MrzValueError):
        td3.parse_document_number(line)


def test_a_document_number_line_that_is_not_a_string_is_rejected():
    # Slicing None raises a bare TypeError, which a caller catching
    # MrzValueError -- the one error type 1.9 pinned -- would never see.  Named
    # apart from 2.3's and 2.4's identically-shaped tests so none of the three
    # shadows another out of the suite.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_document_number(None)

    assert "NoneType" in str(excinfo.value)


def test_the_document_number_reader_ignores_the_check_digit_printed_after_it():
    # Position 10 is a field in its own right in the layout and this reader
    # does not touch it: parsing a number is not verifying it, and 1.6's
    # `verify_check_digit` is what reports a mismatch.  A wrong printed digit
    # leaves the number itself readable, which is what makes 2.14's "parsing
    # must not silently fix it" possible to write.
    line = SPECIMEN_LINE_2[:9] + "0" + SPECIMEN_LINE_2[10:]

    assert len(line) == td3.TD3_LINE_LENGTH
    assert td3.parse_document_number(line) == "L898902C<"
    assert mrz.verify_check_digit(td3.parse_document_number(line), line[9]) is False


def test_a_rejected_document_number_is_the_packages_one_error_type():
    # The exact type, not a subclass: 1.9 pinned this so a second error type
    # cannot hide underneath this one unnoticed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_document_number(line_2_with_document_number("<" * 9))

    assert type(excinfo.value) is mrz.MrzValueError


# --- the nationality: the first field that is about the holder -------------


def line_2_with_nationality(code):
    """A full-length TD3 line 2 whose positions 11-13 read ``code``.

    Only a three-character code fits at positions 11-13 of a 44-character
    line, so the width is asserted here rather than discovered later: a short
    code is what a *short line* produces, not what a well-formed line prints,
    and that case is tested on its own below.
    """
    start, end = td3.TD3_LINE_2["nationality"]
    assert len(code) == end - start + 1

    return SPECIMEN_LINE_2[: start - 1] + code + SPECIMEN_LINE_2[end:]


def test_the_nationality_names_are_exported():
    assert {"parse_nationality", "validate_nationality"} <= set(td3.__all__)


def test_the_nationality_is_three_positions_wide_in_the_layout():
    # The width is read out of the table rather than typed into the check, so
    # the standard's positions stay the only place a position is stated and a
    # message cannot disagree with the layout it is describing.
    start, end = td3.TD3_LINE_2["nationality"]

    assert (start, end) == (11, 13)
    assert end - start + 1 == 3
    assert SPECIMEN_LINE_2[start - 1 : end] == "UTO"


def test_a_normal_nationality_is_read_from_positions_11_to_13():
    # The task's named case, end to end: the shape gate, the slice and the
    # judgement, over the ICAO specimen passport.
    zone = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])
    line_1, line_2 = zone
    start, end = td3.TD3_LINE_2["nationality"]
    nationality = td3.parse_nationality(line_2)

    assert zone == (SPECIMEN_LINE_1, SPECIMEN_LINE_2)
    assert nationality == "UTO"
    assert len(nationality) == end - start + 1
    # The neighbouring slices are different text, so a reader off by one in
    # either direction cannot pass: position 10 is the document number's check
    # digit and position 14 is the first character of the date of birth.
    assert nationality not in (SPECIMEN_LINE_2[9:12], SPECIMEN_LINE_2[11:14])


def test_a_real_nationality_code_such_as_ind_is_accepted_although_the_task_says_otherwise():
    # tasks.md 2.11 asks for "a test rejecting IND", and the same sentence asks
    # for "3 uppercase letters".  IND cannot fail that rule: it is three
    # uppercase letters.  This is 2.4's contradiction with the issuing state,
    # carried over rather than re-derived, and it is the same contradiction
    # because it is the same three letters: ISO 3166-1 alpha-3 assigns IND to
    # India, so every conforming list of nationality codes -- ICAO Doc 9303's
    # included -- contains it.  The only implementations that reject it hold a
    # list with India missing, and that parser refuses every genuine Indian
    # passport: a 100% false-alert rate on the field most likely to be right.
    #
    # So the field reader decides well-formedness, and recognising a
    # nationality is a Tier 0 policy question: a code list that has to be
    # sourced rather than remembered (the rule 1.6 applied to the composite
    # check digit) and belongs to the rules engine, not to a field reader.
    assert td3.validate_nationality("IND") == "IND"
    assert td3.parse_nationality(line_2_with_nationality("IND")) == "IND"


@pytest.mark.parametrize(
    "code",
    ["UTO", "IND", "NLD", "BFA", "ZZZ"],
    ids=["UTO", "IND", "NLD", "BFA", "ZZZ"],
)
def test_a_three_uppercase_letter_nationality_is_accepted(code):
    # Three uppercase letters is the whole of the rule the standard states for
    # positions 11-13, and these are only that: strings.  No list of real
    # codes is consulted -- see the IND test above for why that is deliberate.
    assert td3.validate_nationality(code) == code


@pytest.mark.parametrize(
    "code",
    [
        "",
        "UT",
        "UTOX",
        "UTO ",
        "UT0",
        "1TO",
        "uto",
        "UtO",
        "U O",
        "U<O",
        "<<<",
        "UT-",
        "ÜTO",
    ],
    ids=[
        "empty",
        "two letters",
        "four letters",
        "trailing space",
        "a digit for the O",
        "a leading digit",
        "lower case",
        "mixed case",
        "an inner space",
        "filler where a letter is",
        "a field of nothing but filler",
        "punctuation",
        "a non-ASCII letter",
    ],
)
def test_a_nationality_that_is_not_three_uppercase_letters_is_rejected(code):
    # The cases that matter are the ones OCR produces: a zero read for an O, a
    # lower-case or mixed-case read, a filler or a space where a letter should
    # be, and a diacritic carried across from the printed name.  "ÜTO" is the
    # load-bearing one -- it is three characters, `isalpha()` is True and
    # `isupper()` is True, so an implementation written from those two methods
    # would wave it through and read Ü as a nationality.
    with pytest.raises(mrz.MrzValueError):
        td3.validate_nationality(code)


def test_a_nationality_of_nothing_but_filler_is_rejected():
    # The standard gives this field no "unspecified" value, which is what makes
    # `<<<` different from the sex marker's filler in 2.12: there is no such
    # thing as an unknown nationality in a TD3 zone, so a field of three
    # fillers is a misread rather than an honest blank.  It is rejected for
    # the ordinary reason -- the filler is not one of A-Z -- and *not* as an
    # empty field, because 2.10 already decided that "empty" is judged by
    # removing the filler and this field has no emptiness rule at all.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_nationality("<<<")

    assert "A-Z" in str(excinfo.value)


@pytest.mark.parametrize(
    "code", [None, 42, b"UTO"], ids=["None", "an int", "bytes"]
)
def test_a_nationality_that_is_not_a_string_is_rejected(code):
    # Iterating or measuring a non-string raises the bare TypeError 1.9
    # forbids, which a caller catching MrzValueError would never see.  bytes is
    # the subtle one: `b"UTO".isalpha()` is True, so a validator that asked the
    # value rather than the type would accept a byte string as a nationality.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_nationality(code)

    assert type(code).__name__ in str(excinfo.value)


def test_the_rejection_names_the_width_and_positions_but_not_the_nationality():
    # The width in the message is the layout's, so the two cannot drift: if the
    # field ever moves or changes width, this message changes with it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_nationality("UT0")

    message = str(excinfo.value)
    start, end = td3.TD3_LINE_2["nationality"]
    assert str(start) in message
    assert str(end) in message
    # 2.3 named the document *code* and 2.4 named the *state*: each named a
    # document.  A nationality is a property of the holder, not of the
    # document, and 2.10 is where that reasoning began -- a document number is
    # unique to one holder's document and its messages carry the width and the
    # filler instead.  So the rule is named and the value is not.
    assert "UT0" not in message


def test_the_rejection_carries_no_identity_data_from_the_line_around_it():
    # The same rule through the reader rather than the validator, where the
    # value being judged sits inside a line holding the document number, the
    # date of birth and the personal number.  None of them is echoed, and
    # neither is the nationality itself.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_nationality(line_2_with_nationality("UT0"))

    message = str(excinfo.value)
    assert "UT0" not in message
    assert "L898902C" not in message
    assert "740812" not in message


@pytest.mark.parametrize("code", ["UT0", "uTO", "U<O"], ids=["digit", "lower", "filler"])
def test_a_line_whose_nationality_is_malformed_is_rejected_end_to_end(code):
    # The path 2.13 will take: slice positions 11-13 off a real 44-character
    # line, then judge it.  A validator test alone would not prove the reader
    # calls it.
    line = line_2_with_nationality(code)
    assert len(line) == td3.TD3_LINE_LENGTH

    with pytest.raises(mrz.MrzValueError):
        td3.parse_nationality(line)


@pytest.mark.parametrize(
    "line", ["", "L898902C<3", "L898902C<3U"], ids=["empty", "ten", "twelve"]
)
def test_a_line_too_short_to_hold_a_nationality_is_rejected(line):
    # A line that stops before position 13 slices to a short or empty string.
    # That is not three uppercase letters and must not be waved through as one.
    with pytest.raises(mrz.MrzValueError):
        td3.parse_nationality(line)


def test_a_nationality_line_that_is_not_a_string_is_rejected():
    # Slicing None raises a bare TypeError, which a caller catching
    # MrzValueError -- the one error type 1.9 pinned -- would never see.  Named
    # apart from 2.3's, 2.4's and 2.10's identically-shaped tests so none of
    # the four shadows another out of the suite.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_nationality(None)

    assert "NoneType" in str(excinfo.value)


def test_the_nationality_is_read_by_position_and_not_by_the_end_of_the_line():
    # The field ends at position 13 whatever follows it, so a surplus
    # character past the zone is not part of the nationality -- the same rule
    # 2.5 stated for the name field, and here it is load-bearing: a reader that
    # sliced to the end of the string would return the date of birth with it.
    line = SPECIMEN_LINE_2 + "SURPLUS"

    assert len(line) > td3.TD3_LINE_LENGTH
    assert td3.parse_nationality(line) == "UTO"


def test_the_reader_takes_its_positions_from_the_layout_rather_than_its_own(
    monkeypatch,
):
    # The module's central claim -- that no parser carries an index of its own,
    # because :func:`td3_field` is the one place a line is sliced -- is
    # otherwise unfalsifiable for this reader: the layout and a hand-written
    # `line[10:13]` agree on the specimen, so both pass every other test here.
    # Moving the field in the table, and giving the line different letters at
    # positions 11-13 and 12-14, is what tells them apart.  The table is
    # restored by the fixture.
    line = SPECIMEN_LINE_2[:10] + "UNDI" + SPECIMEN_LINE_2[14:]
    assert td3.TD3_LINE_2["nationality"] == (11, 13)
    assert field(line, td3.TD3_LINE_2, "nationality") == "UND"
    assert td3.parse_nationality(line) == "UND"

    monkeypatch.setitem(td3.TD3_LINE_2, "nationality", (12, 14))

    assert td3.parse_nationality(line) == "NDI"


def test_the_nationality_is_read_from_line_2_and_not_line_1():
    # The cost of getting this wrong is worse here than it was for the document
    # number, and it is worth stating plainly.  Line 1's positions 11-13 are the
    # middle of the surname ERIKSSON, so the wrong line reads "SON" -- which is
    # three uppercase letters, and so is *not* caught by this task's rule at
    # all.  Unlike the document number, whose wrong-line answer the check digit
    # at position 10 contradicts, nothing below catches this one: see the next
    # test.
    assert td3.parse_nationality(SPECIMEN_LINE_2) == "UTO"
    assert SPECIMEN_LINE_1[10:13] == "SON"
    assert td3.parse_nationality(SPECIMEN_LINE_1) == "SON"


def test_no_check_digit_covers_the_nationality():
    # Why the wrong-line read above is silent, built from the layout rather
    # than stated: the composite digit covers positions 1-10, 14-20 and 22-43,
    # and this field sits in the gap between the first two spans.  The
    # nationality is therefore the one identity field with no arithmetic of its
    # own at all -- which is why the rules engine (Part 12) rather than 1.6's
    # arithmetic is what will have to say whether it is plausible.
    layout = td3.TD3_LINE_2
    spans = [
        (layout["document_number"][0], layout["document_number_check_digit"][1]),
        (layout["date_of_birth"][0], layout["date_of_birth_check_digit"][1]),
        (layout["date_of_expiry"][0], layout["personal_number_check_digit"][1]),
    ]
    covered = {
        position for start, end in spans for position in range(start, end + 1)
    }
    start, end = layout["nationality"]

    assert [span for span in spans] == [(1, 10), (14, 20), (22, 43)]
    assert not any(start <= position <= end for position in covered)


def test_a_rejected_nationality_is_the_packages_one_error_type():
    # The exact type, not a subclass: 1.9 pinned this so a second error type
    # cannot hide underneath this one unnoticed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_nationality(line_2_with_nationality("UT0"))

    assert type(excinfo.value) is mrz.MrzValueError


# --- the dates and the sex marker: the rest of the identity fields ---------


def line_2_with_field(line, name, value):
    """A TD3 line whose ``name`` field reads ``value``.

    The width is asserted here rather than discovered later, for 2.11's
    reason: a value of the wrong length is what a *short line* produces, not
    what a well-formed line prints, and that case is tested on its own below.
    """
    start, end = td3.TD3_LINE_2[name]
    assert len(value) == end - start + 1

    return line[: start - 1] + value + line[end:]


def accepts(check, value):
    """Whether ``check`` returns ``value`` rather than raising.

    A shorthand the closed-set tests below need: "does this value raise?",
    asked of thirty-seven MRZ characters, is thirty-seven near-identical try
    blocks.
    """
    try:
        return check(value) == value
    except mrz.MrzValueError:
        return False


def test_the_date_and_sex_field_names_are_exported():
    assert {
        "TD3_SEX_MARKERS",
        "parse_date_of_birth",
        "parse_date_of_expiry",
        "parse_sex",
        "validate_date_of_birth",
        "validate_date_of_expiry",
        "validate_sex",
    } <= set(td3.__all__)


def test_the_dates_and_the_sex_marker_sit_where_the_layout_says():
    # The positions come out of the table and the specimen is sliced with it,
    # rather than typed in beside the text, so an off-by-one fails here instead
    # of in a reader three sections down.
    layout = td3.TD3_LINE_2

    assert layout["date_of_birth"] == (14, 19)
    assert layout["sex"] == (21, 21)
    assert layout["date_of_expiry"] == (22, 27)

    assert field(SPECIMEN_LINE_2, layout, "date_of_birth") == "740812"
    assert field(SPECIMEN_LINE_2, layout, "sex") == "F"
    assert field(SPECIMEN_LINE_2, layout, "date_of_expiry") == "120415"


@pytest.mark.parametrize(
    "name, width",
    [("date_of_birth", 6), ("sex", 1), ("date_of_expiry", 6)],
    ids=["date_of_birth", "sex", "date_of_expiry"],
)
def test_each_field_is_exactly_as_wide_as_the_standard_prints_it(name, width):
    # The width is the whole of what the two date validators judge, so it is
    # pinned rather than assumed: 3.11 adds the YYMMDD content rule on top of
    # it, and this is the boundary between the two tasks.
    start, end = td3.TD3_LINE_2[name]

    assert end - start + 1 == width
    assert len(field(SPECIMEN_LINE_2, td3.TD3_LINE_2, name)) == width


def test_a_date_of_birth_is_read_from_positions_14_to_19():
    # The task's first named field, end to end over the ICAO specimen: the
    # shape gate, the slice, and the width the validator judges.
    zone = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])
    line_1, line_2 = zone
    date_of_birth = td3.parse_date_of_birth(line_2)

    assert zone == (SPECIMEN_LINE_1, SPECIMEN_LINE_2)
    assert date_of_birth == "740812"
    assert len(date_of_birth) == 6
    # One character out in either direction is different text -- position 13 is
    # the last character of the nationality, position 20 is the date's own
    # check digit -- so a reader off by one cannot pass.
    assert date_of_birth not in (SPECIMEN_LINE_2[12:18], SPECIMEN_LINE_2[14:20])


def test_a_date_of_expiry_is_read_from_positions_22_to_27():
    zone = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])
    line_1, line_2 = zone
    date_of_expiry = td3.parse_date_of_expiry(line_2)

    assert zone == (SPECIMEN_LINE_1, SPECIMEN_LINE_2)
    assert date_of_expiry == "120415"
    assert len(date_of_expiry) == 6
    assert date_of_expiry not in (SPECIMEN_LINE_2[20:26], SPECIMEN_LINE_2[22:28])


def test_a_sex_marker_is_read_from_position_21():
    zone = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])
    line_1, line_2 = zone

    assert td3.parse_sex(line_2) == "F"
    # Positions 20 and 22 hold the date of birth's check digit and the first
    # character of the date of expiry.  Neither is one of the four markers, so
    # a reader off by one in either direction raises instead of returning one.
    assert not accepts(td3.validate_sex, SPECIMEN_LINE_2[19])
    assert not accepts(td3.validate_sex, SPECIMEN_LINE_2[21])


@pytest.mark.parametrize(
    "field_name, reader_name, digit_position",
    [
        ("date_of_birth", "parse_date_of_birth", 20),
        ("date_of_expiry", "parse_date_of_expiry", 28),
    ],
    ids=["date_of_birth", "date_of_expiry"],
)
def test_the_extracted_date_is_the_one_its_printed_check_digit_was_computed_over(
    field_name, reader_name, digit_position
):
    # The strongest evidence available that a date comes back *as printed*: the
    # digit printed beside it in a real MRZ was computed over exactly these six
    # characters, so a stripped date, a re-cased one or a reader off by one
    # gives a different answer.
    date = getattr(td3, reader_name)(SPECIMEN_LINE_2)
    printed = SPECIMEN_LINE_2[digit_position - 1]
    start, end = td3.TD3_LINE_2[field_name]

    assert len(date) == end - start + 1
    assert mrz.check_digit(date) == int(printed)


def test_the_printed_check_digit_alone_cannot_prove_a_date_was_read_correctly():
    # ...and the limit of that evidence, found while writing the test above.
    # The six characters one to the right of the expiry are "204159", and
    # check_digit("204159") is 9 -- the digit the specimen prints at position
    # 28.  So a reader off by one in that direction would agree with the
    # printed digit, which is why the layout tests below move the field in the
    # table instead of trusting the arithmetic.  2.10 recorded the same trap
    # for a trailing filler.
    expiry = td3.parse_date_of_expiry(SPECIMEN_LINE_2)
    shifted = SPECIMEN_LINE_2[22:28]

    assert shifted != expiry
    assert mrz.check_digit(shifted) == mrz.check_digit(expiry) == 9
    assert SPECIMEN_LINE_2[27] == "9"


def test_a_six_character_field_nobody_could_read_is_still_extracted():
    # The half of 2.12's boundary that 3.11 did not move.  It judged the month
    # and the day, and said nothing about characters: "AAAAAA", "<<<<<<" and
    # "abcdef" are six characters that are not a date, which is a different
    # finding from a date that could not exist -- a misread for the check digit
    # printed beside the field to report, and 2.14's unreadable row rather
    # than a refusal.
    for date in ("AAAAAA", "<<<<<<", "abcdef", "74 812", "74/812"):
        assert td3.validate_date_of_birth(date) == date
        assert td3.validate_date_of_expiry(date) == date
        assert (
            td3.parse_date_of_birth(
                line_2_with_field(SPECIMEN_LINE_2, "date_of_birth", date)
            )
            == date
        )
        assert (
            td3.parse_date_of_expiry(
                line_2_with_field(SPECIMEN_LINE_2, "date_of_expiry", date)
            )
            == date
        )


@pytest.mark.parametrize(
    "date, fault",
    [
        pytest.param("993199", "month", id="month-31"),
        pytest.param("013200", "month", id="month-32"),
        pytest.param("740000", "month", id="month-00"),
        pytest.param("749999", "month", id="month-99"),
        pytest.param("740132", "day", id="day-32-in-january"),
        pytest.param("740230", "day", id="day-30-in-february"),
        pytest.param("740432", "day", id="day-32-in-april"),
    ],
)
def test_a_date_whose_month_or_day_could_not_be_a_day_is_refused(date, fault):
    # 3.11's rule, in this format: "993199" and "013200" are the two values
    # the task names and the five beside them are the same rule one step in.
    # **The component name and the positions come back, and the six characters
    # do not** -- a date of birth is identity data and an exception message is
    # the most likely thing in this project to reach a log.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_date_of_birth(date)

    message = str(excinfo.value)
    assert type(excinfo.value) is mrz.MrzValueError
    assert fault in message
    assert "14-19" in message
    assert date not in message
    with pytest.raises(mrz.MrzValueError):
        td3.parse_date_of_birth(
            line_2_with_field(SPECIMEN_LINE_2, "date_of_birth", date)
        )
    with pytest.raises(mrz.MrzValueError) as expiry:
        td3.validate_date_of_expiry(date)

    assert "22-27" in str(expiry.value)


@pytest.mark.parametrize("date", ["000101", "991231", "000229", "020229"])
def test_a_date_is_accepted_without_anybody_having_read_its_century(date):
    # "00" is not refused, and neither is a February 29th.  Both are 3.12's
    # and 3.13's question -- a date of birth and an expiry infer their century
    # by different rules -- and **this task must leave both visibly open**: a
    # range check that needed a century would have to invent one, and a record
    # that carried one could not be asked.
    assert td3.validate_date_of_birth(date) == date
    assert td3.validate_date_of_expiry(date) == date
    assert mrz.date_fault(date) is None


@pytest.mark.parametrize(
    "date",
    ["740812", "120415", "000101", "851001", "991231", "abcdef"],
    ids=[
        "the birth date",
        "the expiry date",
        "new year",
        "an eighties date",
        "new year's eve",
        "lower-case letters",
    ],
)
def test_a_six_character_date_is_extracted_exactly_as_printed(date):
    # "abcdef" is the load-bearing row: 2.8 upper-cases a *name* and 2.9
    # transliterates one, and a reader that carried either habit over to this
    # field would answer a question nobody asked.  Six characters is the whole
    # of the rule here, and "abcdef" is six characters.
    assert td3.validate_date_of_birth(date) == date
    assert td3.validate_date_of_expiry(date) == date
    birth_line = line_2_with_field(SPECIMEN_LINE_2, "date_of_birth", date)
    expiry_line = line_2_with_field(SPECIMEN_LINE_2, "date_of_expiry", date)

    assert td3.parse_date_of_birth(birth_line) == date
    assert td3.parse_date_of_expiry(expiry_line) == date


@pytest.mark.parametrize(
    "date", ["74081 ", " 40812"], ids=["a trailing space", "a leading space"]
)
def test_a_date_holding_whitespace_is_returned_untrimmed(date):
    # 2.10's rule, on a field that has no content rule of its own.  A field
    # carrying a space is a misread, but it is six characters and it is what
    # the document printed, so it comes back as printed rather than tidied --
    # the same reasoning that keeps 2.10's padding on a document number.
    # Whether those six characters are a date is 3.11's question.
    #
    # The misread is reported rather than lost, because there is a space in
    # the six and :func:`mrz.check_digit` raises on one, which is the call
    # 3.2 makes.  A validator that demanded the MRZ alphabet here would put
    # that check on the wrong side of 2.14's "parsing must not silently fix
    # it", so this asserts both halves: returned untouched, and refused below.
    with pytest.raises(mrz.MrzValueError):
        mrz.check_digit(date)

    assert td3.validate_date_of_birth(date) == date
    assert td3.validate_date_of_expiry(date) == date
    assert (
        td3.parse_date_of_birth(
            line_2_with_field(SPECIMEN_LINE_2, "date_of_birth", date)
        )
        == date
    )
    assert (
        td3.parse_date_of_expiry(
            line_2_with_field(SPECIMEN_LINE_2, "date_of_expiry", date)
        )
        == date
    )


@pytest.mark.parametrize(
    "date",
    ["", "74081", "7408122", "740812 ", " 740812", "74081234"],
    ids=[
        "empty",
        "five",
        "seven",
        "a trailing space",
        "a leading space",
        "eight",
    ],
)
def test_a_date_field_of_the_wrong_width_is_rejected(date):
    # Six is a property of the *field*, not of the date, so it is judged from
    # the layout.  It is also the only thing judged here: a six-character value
    # that is not a date at all -- "74081<", "AAAAAA" -- is accepted, which is
    # the 3.11 boundary test above.  A slice that landed one character out is
    # six characters too and is likewise accepted here; the layout test at the
    # end of this section is what catches a reader that does that.
    with pytest.raises(mrz.MrzValueError):
        td3.validate_date_of_birth(date)

    with pytest.raises(mrz.MrzValueError):
        td3.validate_date_of_expiry(date)


def test_the_sex_markers_are_the_four_the_standard_allows():
    # A closed set, and closed for the same reason TD3_DOCUMENT_CODES is: an
    # open one would let a caller widen what a passport may print at run time.
    assert td3.TD3_SEX_MARKERS == frozenset({"M", "F", "X", mrz.FILLER})
    assert isinstance(td3.TD3_SEX_MARKERS, frozenset)


def test_the_sex_marker_m_is_accepted():
    assert td3.validate_sex("M") == "M"
    assert td3.parse_sex(line_2_with_field(SPECIMEN_LINE_2, "sex", "M")) == "M"


def test_the_sex_marker_f_is_accepted():
    # The specimen's own marker, so this is also the end-to-end reading of a
    # real passport's line 2.
    assert td3.validate_sex("F") == "F"
    assert td3.parse_sex(SPECIMEN_LINE_2) == "F"


def test_the_sex_marker_x_is_accepted():
    # X is what a document prints when the holder has not stated a sex, so it
    # is a value the standard allows rather than a marker of "unknown" that
    # the field reader has to invent a meaning for.
    assert td3.validate_sex("X") == "X"
    assert td3.parse_sex(line_2_with_field(SPECIMEN_LINE_2, "sex", "X")) == "X"


def test_the_sex_marker_of_filler_is_accepted():
    # The filler is a *value* here and nowhere else in line 2: ICAO prints "<"
    # to say the sex is unspecified.  This is what 2.11 deferred when it
    # declined an emptiness rule for the nationality -- there is no such thing
    # as an unknown nationality, and there is precisely one unspecified sex.
    assert td3.validate_sex(mrz.FILLER) == mrz.FILLER
    assert (
        td3.parse_sex(line_2_with_field(SPECIMEN_LINE_2, "sex", mrz.FILLER))
        == mrz.FILLER
    )


def test_a_sex_marker_of_z_is_rejected():
    # The task's named rejection.  Z is not a misspelling of a value the
    # standard prints -- no document may print it here at all -- so it is
    # refused on the closed-set ground, exactly like a digit, a space or a
    # lower-case read.
    with pytest.raises(mrz.MrzValueError):
        td3.validate_sex("Z")

    line = line_2_with_field(SPECIMEN_LINE_2, "sex", "Z")
    assert len(line) == td3.TD3_LINE_LENGTH

    with pytest.raises(mrz.MrzValueError):
        td3.parse_sex(line)


def test_the_sex_check_accepts_exactly_the_published_set_and_nothing_else():
    # Exhaustive over the whole MRZ alphabet plus a few characters it does not
    # contain, so the closed set and the check cannot drift apart: a set that
    # gained a value without the check, or a check that quietly stopped
    # accepting the filler, both fail here rather than in the wild.
    candidates = [*mrz.CHAR_VALUES, "", " ", "?", "MM", "< ", "æ"]
    accepted = {value for value in candidates if accepts(td3.validate_sex, value)}

    assert set(td3.TD3_SEX_MARKERS) == {"M", "F", "X", mrz.FILLER}
    assert accepted == set(td3.TD3_SEX_MARKERS)


@pytest.mark.parametrize(
    "marker",
    [
        "",
        "m",
        "f",
        "x",
        "1",
        "?",
        "-",
        " ",
        "N",
        "D",
        "MM",
        "MF",
        "M<",
        "M ",
        " M",
        "< ",
        "æ",
    ],
    ids=[
        "empty",
        "lower-case m",
        "lower-case f",
        "lower-case x",
        "a digit",
        "punctuation",
        "a hyphen",
        "a space",
        "N",
        "D",
        "two markers",
        "two different markers",
        "a marker and the filler",
        "a trailing space",
        "a leading space",
        "a space before the filler",
        "a non-ASCII letter",
    ],
)
def test_a_sex_marker_the_standard_does_not_print_is_rejected(marker):
    # These are the misreads a one-character field actually produces: a digit
    # or a space for the marker, a lower-case read, a diacritic carried across
    # from the printed name -- and the two-character values, which are what a
    # sloppy slice of the neighbouring positions returns.
    with pytest.raises(mrz.MrzValueError):
        td3.validate_sex(marker)


@pytest.mark.parametrize("value", [None, 42, b"M", []], ids=["None", "an int", "bytes", "a list"])
def test_a_sex_marker_that_is_not_a_string_is_rejected(value):
    # The type guard is load-bearing for this field in a way it is not for the
    # dates: the check is a membership test, and `[] in TD3_SEX_MARKERS` raises
    # a bare TypeError that a caller catching MrzValueError would never see.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_sex(value)

    assert type(value).__name__ in str(excinfo.value)


@pytest.mark.parametrize("value", [None, 42, b"740812"], ids=["None", "an int", "bytes"])
def test_a_date_that_is_not_a_string_is_rejected(value):
    # bytes is the subtle one: it has a length, so a validator that measured
    # before it checked the type would accept a byte string as a date.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_date_of_birth(value)

    with pytest.raises(mrz.MrzValueError) as expiry_excinfo:
        td3.validate_date_of_expiry(value)

    assert type(value).__name__ in str(excinfo.value)
    assert type(value).__name__ in str(expiry_excinfo.value)


def test_the_sex_rejection_names_the_four_markers_and_not_the_one_it_found():
    # The set is the standard's, not the holder's, so the message may name what
    # it wanted.  What it must not name is the marker it found: a sex marker is
    # a property of the holder, and 2.10 is where that reasoning started and
    # 2.11 carried it across the line.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_sex("Z")

    message = str(excinfo.value)
    start, end = td3.TD3_LINE_2["sex"]
    assert str(start) in message
    assert str(end) in message
    for marker in td3.TD3_SEX_MARKERS:
        assert repr(marker) in message
    assert "Z" not in message


def test_a_rejected_sex_marker_carries_no_identity_data_from_the_line_around_it():
    # The same rule through the reader, where the rejected character sits
    # inside a line holding the document number, both dates and the personal
    # number.  None of them may reach the message.
    line = line_2_with_field(SPECIMEN_LINE_2, "sex", "Z")

    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.parse_sex(line)

    message = str(excinfo.value)
    for identity in ("L898902C", "UTO", "740812", "120415", "ZE184226"):
        assert identity not in message


def test_the_date_rejections_name_the_width_and_the_positions_and_not_the_date():
    # The width in the message is the layout's, so the two cannot drift: if
    # the field ever moves or changes width, this message changes with it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td3.validate_date_of_birth("74081")

    message = str(excinfo.value)
    start, end = td3.TD3_LINE_2["date_of_birth"]
    assert str(start) in message
    assert str(end) in message
    assert "6" in message
    # A date of birth is the holder's, and a message is the most likely thing
    # to reach a log.
    assert "74081" not in message


@pytest.mark.parametrize(
    "reader_name, stops_before",
    [
        ("parse_date_of_birth", 19),
        ("parse_sex", 21),
        ("parse_date_of_expiry", 27),
    ],
    ids=["date_of_birth", "sex", "date_of_expiry"],
)
def test_a_line_too_short_to_hold_the_field_is_rejected(reader_name, stops_before):
    # A line that stops one position early slices to a short field, and the
    # width rule turns that away: that is a line which stopped early, not a
    # document carrying a five-character date.
    line = SPECIMEN_LINE_2[: stops_before - 1]

    with pytest.raises(mrz.MrzValueError):
        getattr(td3, reader_name)(line)


@pytest.mark.parametrize(
    "reader_name",
    ["parse_date_of_birth", "parse_sex", "parse_date_of_expiry"],
    ids=["date_of_birth", "sex", "date_of_expiry"],
)
def test_a_field_reader_line_that_is_not_a_string_is_rejected(reader_name):
    # Named apart from 2.3's, 2.4's, 2.10's and 2.11's identically-shaped
    # tests so none of the seven shadows another out of the suite.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        getattr(td3, reader_name)(None)

    assert "NoneType" in str(excinfo.value)


def test_each_field_is_read_by_position_and_not_by_the_end_of_the_line():
    # A surplus character past the zone is not part of any of the three fields
    # -- 2.5's rule for the name, and load-bearing for the sex marker, which
    # is a single character: a reader that sliced to the end of the string
    # would return "F" with thirteen characters of expiry behind it.
    line = SPECIMEN_LINE_2 + "SURPLUS"

    assert len(line) > td3.TD3_LINE_LENGTH
    assert td3.parse_date_of_birth(line) == "740812"
    assert td3.parse_sex(line) == "F"
    assert td3.parse_date_of_expiry(line) == "120415"


def test_a_full_length_line_cannot_make_a_date_reader_fail_on_anything_but_its_dates():
    # Worth restating, because it is the reason the two date validators can
    # only ever fire on a value handed to them directly: validate_td3_lines
    # has already promised 44 characters, so the slice is always exactly as
    # wide as the layout says, and a surplus at the end is not the reader's
    # business.  **3.11 narrowed what "cannot fail" means and this is the
    # rewrite**: the only two lines below that now fail are the two carrying a
    # date that could not exist, and they fail by *name* -- the month -- rather
    # than as a line that could not be read.
    for line in (SPECIMEN_LINE_2, SPECIMEN_LINE_2 + "SURPLUS"):
        assert td3.parse_date_of_birth(line) == field(
            line, td3.TD3_LINE_2, "date_of_birth"
        )
        assert td3.parse_date_of_expiry(line) == field(
            line, td3.TD3_LINE_2, "date_of_expiry"
        )

    with pytest.raises(mrz.MrzValueError) as birth:
        td3.parse_date_of_birth(
            line_2_with_field(SPECIMEN_LINE_2, "date_of_birth", "993199")
        )
    with pytest.raises(mrz.MrzValueError) as expiry:
        td3.parse_date_of_expiry(
            line_2_with_field(SPECIMEN_LINE_2, "date_of_expiry", "013200")
        )

    assert "month" in str(birth.value)
    assert "month" in str(expiry.value)


def test_the_three_fields_are_read_from_line_2_and_not_line_1():
    # All three wrong-line answers pass their own validators, and two of the
    # three are caught by nothing underneath either -- which is worth stating
    # plainly, because it is why 2.13's caller has to pass the right line
    # rather than trust the reader.  Line 1's positions 14-19 and 22-27 are
    # inside the name ("<<ANNA" and "ARIA<<"), and position 21 is the "M" of
    # "MARIA", which is one of the four markers -- so the wrong line yields a
    # perfectly valid sex marker rather than an error.
    assert td3.parse_date_of_birth(SPECIMEN_LINE_1) == "<<ANNA"
    assert td3.parse_sex(SPECIMEN_LINE_1) == "M"
    assert td3.parse_date_of_expiry(SPECIMEN_LINE_1) == "ARIA<<"

    # The date of birth's printed digit disagrees with the wrong read, so 3.2's
    # verification would catch that one.  The expiry's does not -- "ARIA<<" and
    # "120415" both come to 9, which is what the specimen prints -- and the sex
    # marker has no digit of its own at all.
    assert mrz.check_digit("<<ANNA") != int(SPECIMEN_LINE_2[19])
    assert mrz.check_digit("ARIA<<") == mrz.check_digit("120415") == 9
    assert int(SPECIMEN_LINE_2[27]) == 9


def test_the_sex_marker_is_the_only_field_here_with_no_check_digit():
    # Built from the layout rather than stated, for 2.11's reason.  Position 21
    # sits in the gap between the date of birth's span (14-20) and the date of
    # expiry's (22-28), and the composite digit covers 1-10, 14-20 and 22-43,
    # so it does not reach position 21 either.  Nothing below this field will
    # object to a marker that is wrong, which is why the set is closed: it is
    # the only guard there is.
    layout = td3.TD3_LINE_2
    spans = [
        (layout["document_number"][0], layout["document_number_check_digit"][1]),
        (layout["date_of_birth"][0], layout["date_of_birth_check_digit"][1]),
        (layout["date_of_expiry"][0], layout["date_of_expiry_check_digit"][1]),
        (layout["personal_number"][0], layout["personal_number_check_digit"][1]),
    ]
    composite = [(1, 10), (14, 20), (22, 43)]
    covered = {position for start, end in spans for position in range(start, end + 1)}
    composite_covered = {
        position for start, end in composite for position in range(start, end + 1)
    }

    assert spans == [(1, 10), (14, 20), (22, 28), (29, 43)]
    assert composite == [(1, 10), (14, 20), (22, 43)]
    assert 21 not in covered
    assert 21 not in composite_covered
    # The nationality is in the same gap, and 2.11 already made that point.
    assert 11 not in covered and 13 not in covered


@pytest.mark.parametrize(
    "field_name, reader_name, line, moved_to, expected_after_move",
    [
        (
            "date_of_birth",
            "parse_date_of_birth",
            SPECIMEN_LINE_2[:12] + "N" + SPECIMEN_LINE_2[13:],
            (13, 17),
            "N7408",
        ),
        (
            "date_of_expiry",
            "parse_date_of_expiry",
            SPECIMEN_LINE_2[:21] + "X" + SPECIMEN_LINE_2[22:],
            (23, 27),
            "20415",
        ),
        (
            "sex",
            "parse_sex",
            SPECIMEN_LINE_2[:21] + "X" + SPECIMEN_LINE_2[22:],
            (22, 22),
            "X",
        ),
    ],
    ids=["date_of_birth", "date_of_expiry", "sex"],
)
def test_each_new_reader_takes_its_positions_from_the_layout_rather_than_its_own(
    monkeypatch, field_name, reader_name, line, moved_to, expected_after_move
):
    # 2.11's test, once per reader, for the same reason: the layout and a
    # hand-written slice agree on the specimen, so nothing else here can tell
    # them apart.  Moving the field in the table, and giving the line a
    # different character at the old and the new position, is what does.
    #
    # **Each date is moved to a field of a different width**, not merely to a
    # different range, so a validator that typed in a 6 rather than reading the
    # layout fails here too -- and that is the same claim 2.4 made about its
    # width and the same reason it was tested.  The table is restored by the
    # fixture.
    reader = getattr(td3, reader_name)
    before = field(line, td3.TD3_LINE_2, field_name)

    assert reader(line) == before
    assert before != expected_after_move

    monkeypatch.setitem(td3.TD3_LINE_2, field_name, moved_to)

    assert reader(line) == expected_after_move
    assert field(line, td3.TD3_LINE_2, field_name) == expected_after_move


def test_a_rejected_field_is_the_packages_one_error_type():
    # The exact type, not a subclass: 1.9 pinned this so a second error type
    # cannot hide underneath this one unnoticed, and these are the three new
    # failures a caller can meet.
    for check, argument in (
        (td3.validate_date_of_birth, "74081"),
        (td3.validate_date_of_expiry, "74081"),
        (td3.validate_sex, "Z"),
    ):
        with pytest.raises(mrz.MrzValueError) as excinfo:
            check(argument)

        assert type(excinfo.value) is mrz.MrzValueError


# --- the whole zone, assembled into one record ------------------------------

# Written out longhand from the specimen rather than sliced out of the line
# under test.  A test expecting `field(SPECIMEN_LINE_2, layout, "sex")` would
# pass against an assembler whose positions were wrong, which is the mistake
# every field reader above is held to.
EXPECTED_DOCUMENT_FIELDS = {
    "document_code": "P<",
    "issuing_state": "UTO",
    "name": "ERIKSSON<<ANNA<MARIA" + "<" * 19,
    "document_number": "L898902C<",
    "document_number_check_digit": "3",
    "nationality": "UTO",
    "date_of_birth": "740812",
    "date_of_birth_check_digit": "2",
    "sex": "F",
    "date_of_expiry": "120415",
    "date_of_expiry_check_digit": "9",
    "personal_number": "ZE184226B<<<<<",
    "personal_number_check_digit": "1",
    "composite_check_digit": "6",
}

SPECIMEN_ZONE = [SPECIMEN_LINE_1, SPECIMEN_LINE_2]

# Every field the two layout tables state, the ones in alphabetical order and
# the ones in the order the document prints them, and the spans they claim.
# The record's attributes, its source slices and these lists are the three
# things the tests below hold against each other.
ALL_FIELD_NAMES = sorted(EXPECTED_LINE_1) + sorted(EXPECTED_LINE_2)
PRINTED_FIELD_NAMES = [
    name
    for layout in (EXPECTED_LINE_1, EXPECTED_LINE_2)
    for name in sorted(layout, key=layout.__getitem__)
]
FIELD_SPANS = {
    name: span
    for layout in (EXPECTED_LINE_1, EXPECTED_LINE_2)
    for name, span in layout.items()
}

# The five printed digits.  Named rather than picked out by pattern, because
# every one of them is a *field of its own right* in the layout and this list
# is what says so.
CHECK_DIGIT_FIELDS = [
    "document_number_check_digit",
    "date_of_birth_check_digit",
    "date_of_expiry_check_digit",
    "personal_number_check_digit",
    "composite_check_digit",
]

# The eight fields Part 2 wrote a reader for, and the six it did not.  Written
# out rather than derived from the module's `__all__`, because the list is a
# claim about the design -- each of the eight is sliced once by its own reader
# and once more for the raw map, each of the six only for the map -- and a
# claim read back from the implementation cannot be that.
FIELDS_WITH_A_READER = [
    "document_code",
    "issuing_state",
    "name",
    "document_number",
    "nationality",
    "date_of_birth",
    "sex",
    "date_of_expiry",
]
FIELDS_WITHOUT_A_READER = [
    name for name in ALL_FIELD_NAMES if name not in FIELDS_WITH_A_READER
]


def line_1_with_name(name):
    """A TD3 line 1 whose name field reads ``name``."""
    start, end = td3.TD3_LINE_1["name"]
    assert len(name) == end - start + 1

    return SPECIMEN_LINE_1[: start - 1] + name + SPECIMEN_LINE_1[end :]


def test_the_record_and_the_assembler_are_exported():
    assert {"MrzDocument", "parse_td3"} <= set(td3.__all__)


def test_the_specimen_mrz_parses_into_every_field():
    # The test this task names, end to end over the ICAO specimen passport: the
    # shape gate, all fourteen fields of both lines, and the two the name field
    # is split into.  Every expected value is written out above rather than read
    # back from the line, so an assembler reading the wrong positions produces a
    # different document instead of a matching one.
    document = td3.parse_td3(SPECIMEN_ZONE)

    assert isinstance(document, td3.MrzDocument)
    assert {
        name: getattr(document, name) for name in ALL_FIELD_NAMES
    } == EXPECTED_DOCUMENT_FIELDS
    assert document.surname == "ERIKSSON"
    assert document.given_names == ("ANNA", "MARIA")


def test_the_record_holds_one_attribute_per_field_the_layout_states():
    # No more and no fewer, in printed order -- so reading the record from top
    # to bottom reads the document top to bottom, and a field added to a layout
    # without a place here fails rather than going missing quietly.
    #
    # 3.3's `check_digit_results` goes immediately after `composite_check_digit`
    # and before the two derived name halves: position 44 is the last position
    # the five verdicts cover, so this is the only place it can go without
    # putting something after it that it is a verdict *about*.
    #
    # 3.14 made this the record for all three formats, so the tail is longer:
    # the five optional-data attributes a TD1 and a TD2 print and a TD3 does
    # not, then the discriminator.  They go after `sources` rather than among
    # the printed fields because no single printed order contains a TD1's
    # optional data 1, its optional data 2 and a TD2's optional data, and
    # putting them among the common twelve would have meant reading all three
    # documents in one format's order.  The fourteen a TD3 prints keep their
    # printed order, so the top of the record is unchanged.
    assert [item.name for item in dataclasses.fields(td3.MrzDocument)] == (
        PRINTED_FIELD_NAMES
        + ["check_digit_results", "surname", "given_names", "sources"]
        + [
            "optional_data_1",
            "optional_data_1_check_digit",
            "optional_data_2",
            "optional_data",
            "optional_data_check_digit",
            "format",
        ]
    )


def test_the_record_is_a_frozen_dataclass():
    # Frozen because this is a parse result: nothing downstream has any business
    # editing the nationality of a document it is screening.  `sources` is a
    # read-only mapping, so the record compares with `==` and is not hashable --
    # which is the ordinary Python behaviour for a record holding a mapping.
    assert dataclasses.is_dataclass(td3.MrzDocument)
    assert td3.MrzDocument.__dataclass_params__.frozen is True

    document = td3.parse_td3(SPECIMEN_ZONE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        document.nationality = "XXX"


@pytest.mark.parametrize("name", PRINTED_FIELD_NAMES)
def test_every_field_of_the_zone_is_populated(name):
    # "Every field is populated" stated the way a caller checks it: a non-empty
    # string, as wide as the layout says.  Nothing here can be None or absent,
    # which is the failure mode a record built with `getattr(..., default)`
    # would have.
    document = td3.parse_td3(SPECIMEN_ZONE)
    value = getattr(document, name)
    start, end = FIELD_SPANS[name]

    assert isinstance(value, str)
    assert value.strip()
    assert len(value) == end - start + 1


def test_every_field_value_is_the_characters_the_line_prints_there():
    # Nothing is edited on the way out.  A name is cleaned into `surname` and
    # `given_names`, but the field itself, and every other field, comes back
    # exactly as printed -- padding, filler and all.
    document = td3.parse_td3(SPECIMEN_ZONE)

    for line, layout in ((SPECIMEN_LINE_1, EXPECTED_LINE_1), (SPECIMEN_LINE_2, EXPECTED_LINE_2)):
        for name, (start, end) in layout.items():
            value = getattr(document, name)

            assert value == line[start - 1 : end], name
            assert value == document.sources[name], name


def test_every_check_digit_is_carried_as_the_character_that_was_printed():
    # A digit, not an `int` and not a verdict.  2.2 verifies the composite,
    # 2.14 states what a mismatch is, and 3.3 reports which field failed; this
    # task only carries the character the document printed, because a record
    # that said "3" where the line says "B" would have silently fixed it.
    document = td3.parse_td3(SPECIMEN_ZONE)

    for name in CHECK_DIGIT_FIELDS:
        value = getattr(document, name)

        assert value == EXPECTED_DOCUMENT_FIELDS[name], name
        assert isinstance(value, str) and len(value) == 1, name


def test_this_module_computes_no_check_digit_of_its_own():
    # The module docstring says it holds no arithmetic, and the assembler is the
    # last thing in it that could break that claim.
    #
    # **3.3 is the first delegation into that claim, and this test is rewritten
    # rather than deleted, because what it now has to say is bigger than what
    # it said.**  It used to assert that `mrz.check_digit` and
    # `mrz.verify_check_digit` were not in the module's namespace, so there was
    # nothing here that could do arithmetic -- a name check, and a true one
    # until `td3_check_digit_results` needed the digit layer.  Those two
    # assertions stay: this module still has no copy of the digit and no
    # single-field verdict of its own.  What is added is the rule those names
    # were standing in for, now that delegating is possible: the *arithmetic*
    # is not here either, which is a claim about the module's code rather than
    # about one import line, and it holds however the function is reached.
    #
    # The last assertion is the one that says delegation and duplication are
    # different things.  `td3.check_digit_results` **is** `mrz`'s function --
    # the same object, not a wrapper and not a re-implementation -- so the sum,
    # the weights and the modulo live in exactly one place in the package and
    # there is no second copy here that could disagree with the first.
    assert "check_digit" not in vars(td3)
    assert "verify_check_digit" not in vars(td3)
    assert "WEIGHT_CYCLE" not in vars(td3)
    assert "CHAR_VALUES" not in vars(td3)
    assert "%" not in inspect.getsource(td3.td3_check_digit_results)
    assert td3.check_digit_results is mrz.check_digit_results


def test_the_source_slices_are_the_characters_each_field_occupies():
    # The raw record, keyed by field name and read by position rather than
    # copied out of a value -- so 3.3 can name the field a failing digit belongs
    # to without re-slicing a line it no longer has.
    document = td3.parse_td3(SPECIMEN_ZONE)

    for line, layout in ((SPECIMEN_LINE_1, EXPECTED_LINE_1), (SPECIMEN_LINE_2, EXPECTED_LINE_2)):
        for name, (start, end) in layout.items():
            assert document.sources[name] == line[start - 1 : end], name


def test_the_source_slices_rebuild_both_lines_in_printed_order():
    # Completeness as well as fidelity: every position of both lines belongs to
    # exactly one field, so concatenating the slices in printed order gives the
    # lines back.  A map missing a field, or holding one twice, fails here even
    # when every slice it does hold is right.
    document = td3.parse_td3(SPECIMEN_ZONE)

    assert len(document.sources) == len(ALL_FIELD_NAMES)
    for line_name, line in (("line_1", SPECIMEN_LINE_1), ("line_2", SPECIMEN_LINE_2)):
        layout = td3.TD3[line_name]

        assert "".join(document.sources[name] for name in sorted(layout, key=layout.__getitem__)) == line


def test_the_field_names_are_unique_across_the_two_lines():
    # `sources` is keyed by field name alone, which is only possible while no
    # name is claimed twice.  2.1's coverage test shows every position belongs
    # to one field; this shows the fourteen fields can be told apart.
    assert len(ALL_FIELD_NAMES) == len(set(ALL_FIELD_NAMES))
    assert set(td3.parse_td3(SPECIMEN_ZONE).sources) == set(ALL_FIELD_NAMES)


def test_the_source_slices_are_read_only():
    # The record is frozen and so is its raw map: a caller that "corrected" a
    # slice would be editing the evidence of what the document printed.
    document = td3.parse_td3(SPECIMEN_ZONE)

    assert isinstance(document.sources, collections.abc.Mapping)
    assert not isinstance(document.sources, dict)
    with pytest.raises(TypeError):
        document.sources["nationality"] = "XXX"


def test_two_parses_do_not_share_one_source_map():
    # A module-level dict reused across calls would let one document's evidence
    # be changed by another, and the equality below would stop meaning anything.
    first = td3.parse_td3(SPECIMEN_ZONE)
    second = td3.parse_td3(SPECIMEN_ZONE)

    assert first == second
    assert first.sources is not second.sources


def test_the_assembler_reads_every_field_through_td3_field(monkeypatch):
    # The rule from 2.5 onwards: this is the one place a TD3 line is sliced, and
    # the assembler slices nothing for itself.  Recording the calls is what makes
    # that checkable -- an assembler with a hand-written `line[28:42]` would pass
    # every value assertion above while reading one field without the table.
    #
    # The *counts* are the load-bearing half.  The set of fields read says only
    # that every field was read once, which a raw map built by slicing the lines
    # for itself would also satisfy, because the readers cover those fields
    # anyway.  Two reads for the eight fields that have a reader and one for
    # the six that have none is what says "and once more, into the raw map".
    #
    # **3.3 adds a third read for the eight fields the composite is built
    # from, and one for nothing else.**  `td3_check_digit_results` assembles
    # the 39 characters through `td3_composite_input`, so every one of
    # `TD3_COMPOSITE_FIELDS` is read once more -- a ninth read, through the
    # same helper, for the same field.  The count is written as the old one
    # plus a read per composite field rather than as a new literal table, so
    # the claim stays "and once more, into the raw map" with the composite's
    # third read stated on top of it.
    assert len(td3.TD3_COMPOSITE_FIELDS) == 8
    expected_reads = collections.Counter(
        {name: 2 for name in FIELDS_WITH_A_READER}
    )
    expected_reads.update({name: 1 for name in FIELDS_WITHOUT_A_READER})
    expected_reads.update({name: 1 for name in td3.TD3_COMPOSITE_FIELDS})
    calls = []
    original = td3.td3_field

    def recording(line, layout, name):
        calls.append((line, id(layout), name))
        return original(line, layout, name)

    monkeypatch.setattr(td3, "td3_field", recording)
    document = td3.parse_td3(SPECIMEN_ZONE)

    assert collections.Counter(name for _, _, name in calls) == expected_reads
    assert {(line, name) for line, _, name in calls} == {
        (line, name)
        for line, layout in ((SPECIMEN_LINE_1, td3.TD3_LINE_1), (SPECIMEN_LINE_2, td3.TD3_LINE_2))
        for name in layout
    }
    assert {table for _, table, _ in calls} == {id(td3.TD3_LINE_1), id(td3.TD3_LINE_2)}
    assert document.nationality == "UTO"


def test_each_field_is_read_from_the_line_the_layout_names():
    # The trap 2.11 and 2.12 handed over: four fields return a *valid* answer
    # when pointed at line 1, and two of those four are wrong in a way no check
    # digit catches.  The assembler takes the two lines from the shape gate in
    # printed order and cannot validate its way out of a swap, so this asserts
    # the right answers rather than trusting the readers to notice.
    document = td3.parse_td3(SPECIMEN_ZONE)
    wrong = {name: field(SPECIMEN_LINE_1, td3.TD3_LINE_2, name) for name in
             ("nationality", "date_of_birth", "sex", "date_of_expiry")}

    assert wrong == {
        "nationality": "SON",
        "date_of_birth": "<<ANNA",
        "sex": "M",
        "date_of_expiry": "ARIA<<",
    }
    for name, wrong_answer in wrong.items():
        assert getattr(document, name) != wrong_answer, name


def test_a_zone_given_the_other_way_round_is_rejected():
    # A caller that reverses the two lines is caught -- but only by the document
    # code, which is the first field read and the only one of the six line-1 and
    # line-2 headers whose wrong-line answer is not MRZ-shaped.  The message is
    # the reader's own, unaltered, which is what the test below pins.
    swapped = [SPECIMEN_LINE_2, SPECIMEN_LINE_1]

    assert field(SPECIMEN_LINE_2, td3.TD3_LINE_1, "document_code") == "L8"
    with pytest.raises(mrz.MrzValueError) as through_assembler:
        td3.parse_td3(swapped)
    with pytest.raises(mrz.MrzValueError) as through_reader:
        td3.parse_document_code(SPECIMEN_LINE_2)

    assert type(through_assembler.value) is mrz.MrzValueError
    assert str(through_assembler.value) == str(through_reader.value)


def test_a_rejected_field_is_reported_by_the_reader_that_rejected_it():
    # The assembler adds no message of its own and swallows nothing: a visa's
    # well-formed code is refused with the document code's own words, so a
    # caller reading the error knows which field the document made a mistake in
    # rather than that the zone as a whole was no good.
    visa = line_1_with_document_code("V<")

    with pytest.raises(mrz.MrzValueError) as through_assembler:
        td3.parse_td3([visa, SPECIMEN_LINE_2])
    with pytest.raises(mrz.MrzValueError) as through_reader:
        td3.parse_document_code(visa)

    assert str(through_assembler.value) == str(through_reader.value)
    assert SPECIMEN_LINE_2 not in str(through_assembler.value)


@pytest.mark.parametrize(
    "label, zone, reader_name, argument",
    [
        pytest.param(
            "document_code",
            [line_1_with_document_code("V<"), SPECIMEN_LINE_2],
            "parse_document_code",
            line_1_with_document_code("V<"),
            id="document_code",
        ),
        pytest.param(
            "issuing_state",
            [line_1_with_issuing_state("UT1"), SPECIMEN_LINE_2],
            "parse_issuing_state",
            line_1_with_issuing_state("UT1"),
            id="issuing_state",
        ),
        pytest.param(
            "document_number",
            [SPECIMEN_LINE_1, line_2_with_document_number("<" * 9)],
            "parse_document_number",
            "<" * 9,
            id="document_number",
        ),
        pytest.param(
            "nationality",
            [SPECIMEN_LINE_1, line_2_with_nationality("UT1")],
            "parse_nationality",
            "UT1",
            id="nationality",
        ),
        pytest.param(
            "sex",
            [SPECIMEN_LINE_1, line_2_with_field(SPECIMEN_LINE_2, "sex", "Z")],
            "parse_sex",
            "Z",
            id="sex",
        ),
    ],
)
def test_every_field_the_assembler_reads_can_refuse_the_zone(label, zone, reader_name, argument):
    # One row per reader, because "the assembler calls every reader and adds
    # nothing" is a claim about each of them: a field the assembler read with
    # `td3_field` alone would parse a document no reader would accept, and the
    # one value assertion above would not notice.
    with pytest.raises(mrz.MrzValueError) as through_assembler:
        td3.parse_td3(zone)
    with pytest.raises(mrz.MrzValueError) as through_reader:
        getattr(td3, reader_name)(argument)

    assert type(through_assembler.value) is mrz.MrzValueError
    assert str(through_assembler.value) == str(through_reader.value), label
    assert SPECIMEN_LINE_2 not in str(through_assembler.value)


@pytest.mark.parametrize(
    "zone",
    [
        pytest.param(None, id="none"),
        pytest.param([SPECIMEN_LINE_1], id="one-line"),
        pytest.param([SPECIMEN_LINE_1] * 3, id="three-lines"),
        pytest.param(SPECIMEN_LINE_1, id="one-string"),
        pytest.param([SPECIMEN_LINE_1, SPECIMEN_LINE_1[:-1]], id="short-line"),
        pytest.param([SPECIMEN_LINE_1, SPECIMEN_LINE_1 + "A"], id="long-line"),
        pytest.param([SPECIMEN_LINE_1, None], id="non-string-line"),
    ],
)
def test_a_zone_that_is_not_two_lines_of_44_is_rejected(zone):
    # The shape gate is the assembler's first act, so every one of 2.2's
    # rejections is this function's rejection too, in the same words and the one
    # error type.
    with pytest.raises(mrz.MrzValueError) as through_assembler:
        td3.parse_td3(zone)

    assert type(through_assembler.value) is mrz.MrzValueError
    with pytest.raises(mrz.MrzValueError) as through_gate:
        td3.validate_td3_lines(zone)

    assert str(through_assembler.value) == str(through_gate.value)


@pytest.mark.parametrize(
    "zone",
    [
        pytest.param(tuple(SPECIMEN_ZONE), id="tuple"),
        pytest.param(list(SPECIMEN_ZONE), id="list"),
        pytest.param(iter(SPECIMEN_ZONE), id="iterator"),
        pytest.param((line for line in SPECIMEN_ZONE), id="generator"),
    ],
)
def test_the_zone_may_be_any_iterable_of_two_lines(zone):
    # The OCR step hands over a list or a tuple and neither is privileged, so
    # the four ways of arriving with the same two lines parse to one document.
    assert td3.parse_td3(zone) == td3.parse_td3(SPECIMEN_ZONE)


def test_the_personal_number_is_carried_as_printed_and_judged_by_nothing():
    # Part 2 asks for no reader on positions 29-42, so the assembler is the one
    # thing that reads it -- through `td3_field`, like every other read, and by
    # nothing else.  A field of nothing but filler and a field carrying a
    # character the MRZ alphabet cannot print both come back as they arrived;
    # judging them is the rules engine's question (2.4's `IND`, 2.10's number).
    for printed in ("<" * 14, "ZE184226 B<<<<"):
        line_2 = line_2_with_field(SPECIMEN_LINE_2, "personal_number", printed)
        document = td3.parse_td3([SPECIMEN_LINE_1, line_2])

        assert document.personal_number == printed
        assert document.sources["personal_number"] == printed
    assert "parse_personal_number" not in dir(td3)


def test_the_personal_number_is_read_through_the_layout(monkeypatch):
    # The one field the assembler reads for itself, so the one field where a
    # hand-written slice would go unnoticed.  Moving it in the table and giving
    # the line a different character at the new position is what tells the two
    # apart.  The table is restored by the fixture.
    reader_free_slice = SPECIMEN_LINE_2[28:36]

    assert reader_free_slice == "ZE184226"
    assert document_personal_number(SPECIMEN_LINE_2) == SPECIMEN_LINE_2[28:42]

    monkeypatch.setitem(td3.TD3_LINE_2, "personal_number", (29, 36))

    assert document_personal_number(SPECIMEN_LINE_2) == reader_free_slice


def document_personal_number(line_2):
    """The personal number the assembler reads out of ``line_2``."""
    return td3.parse_td3([SPECIMEN_LINE_1, line_2]).personal_number


def test_only_the_name_is_cleaned_and_a_date_comes_back_exactly_as_printed():
    # 2.8's upper-casing and 2.9's transliteration belong to names and to
    # nothing else.  A date is six characters of `YYMMDD` and 3.11 owns what it
    # may print, so an assembler that cleaned one would answer a question
    # nobody asked -- and 2.12's tests would not catch it, because they test
    # the readers rather than this.
    zone = [
        line_1_with_name("eriksson<<anna maria" + "<" * 19),
        line_2_with_field(SPECIMEN_LINE_2, "date_of_birth", "7a0812"),
    ]
    document = td3.parse_td3(zone)

    assert document.name == "eriksson<<anna maria" + "<" * 19
    assert document.surname == "ERIKSSON"
    # One name, not two: a space is not a separator (2.7), so 2.8 removes it and
    # does not split on it.
    assert document.given_names == ("ANNAMARIA",)
    assert document.date_of_birth == "7a0812"
    assert document.sources["date_of_birth"] == "7a0812"


def test_a_name_with_no_given_names_still_produces_a_surname_and_an_empty_list():
    # 2.6's mononym and 2.6's field of nothing but filler, both carried into the
    # record: the surname is a string either way and the given names are an
    # empty tuple, so "no surname" and "no given names" stay distinguishable
    # from a field that was never read.
    for printed, surname in (
        ("ERIKSSON" + "<" * 31, "ERIKSSON"),
        ("<" * 39, ""),
    ):
        document = td3.parse_td3([line_1_with_name(printed), SPECIMEN_LINE_2])

        assert document.name == printed
        assert document.surname == surname
        assert document.given_names == ()
        assert isinstance(document.given_names, tuple)


def test_a_name_survives_transliteration_into_the_record():
    # The last step of 2.5-2.9 is the one the record carries, because a name the
    # MRZ alphabet cannot print is a name nothing downstream can read -- while
    # the raw text it came from stays in `sources` and in `name`, so the change
    # leaves evidence behind rather than none.
    document = td3.parse_td3(
        [line_1_with_name("MÜLLER<<SOFIE" + "<" * 26), SPECIMEN_LINE_2]
    )

    assert document.surname == "MULLER"
    assert document.given_names == ("SOFIE",)
    assert document.sources["name"].startswith("MÜLLER<<SOFIE")


def test_the_holder_field_the_assembler_reaches_the_last_step_of():
    # Everything the record carries about the holder arrives through the four
    # readers 2.5-2.9 wrote, in their order.  If the assembler were to skip one
    # the record would be a plausible-looking document that silently lost a
    # step, and every value assertion above would still pass -- the surname
    # would simply be padded with filler and lower case.
    name = "müller<<sofie anna" + "<" * 21
    document = td3.parse_td3([line_1_with_name(name), SPECIMEN_LINE_2])

    assert document.name == name
    assert document.surname == "MULLER"
    assert document.given_names == ("SOFIEANNA",)


# --- one mutated character: the parse stands, the check digit speaks --------

# The verifier 2.14 names is `mrz.check_digit` from Part 1.  The per-field
# verifier over a TD3 zone is 3.3's and the composite input 3.2's, so neither is
# built here: what 2.14 has to say is that the arithmetic a later task wraps in
# a verifier already disagrees with the printed digit, and that the parse hands
# it the character the document printed rather than a repaired one.

# `'C'` at position 8 of the specimen's document number, replaced by `'A'`.
# Written out longhand rather than built by index arithmetic, so the expected
# number in the assertions below can be read straight off this line.
MUTATED_DOCUMENT_NUMBER = "L898902A<"
MUTATED_LINE_2 = line_2_with_document_number(MUTATED_DOCUMENT_NUMBER)

# One digit and one letter for each of the nine positions, with the digit the
# verifier computes over the mutated number.  The specimen prints `3` and every
# row below is a substitution that moves it, so every row is a mismatch the
# verifier has to report.  The two columns agree with each other at every
# position by choice rather than by rule, which is why both are written out
# instead of one being derived from the other.
MUTATIONS_BY_POSITION = [
    # (position, character as printed, digit, letter, digit the verifier gets)
    (1, "L", "0", "A", 6),
    (2, "8", "0", "A", 9),
    (3, "9", "0", "A", 4),
    (4, "8", "0", "A", 7),
    (5, "9", "0", "A", 6),
    (6, "0", "1", "B", 4),
    (7, "2", "0", "A", 9),
    (8, "C", "0", "A", 7),
    (9, "<", "1", "B", 4),
]

MUTATIONS = [
    pytest.param(
        position,
        printed,
        replacement,
        verdict,
        id=f"{position}-{printed}-to-{replacement}",
    )
    for position, printed, digit, letter, verdict in MUTATIONS_BY_POSITION
    for replacement, verdict in ((digit, verdict), (letter, verdict))
]


def test_a_mutated_document_number_still_parses_and_every_field_is_still_populated():
    # The structural half of 2.14, and 2.10's rule doing the work: nothing in
    # the number is judged but its emptiness, so a number one character away
    # from a real one is read exactly as readily as the real one.  Reading a
    # number is not verifying one, and this is the line that has to hold for
    # the verification to be worth anything -- a parser that refused the
    # mutation would be reporting a mismatch it cannot point at.
    document = td3.parse_td3([SPECIMEN_LINE_1, MUTATED_LINE_2])

    assert td3.validate_td3_lines([SPECIMEN_LINE_1, MUTATED_LINE_2]) == (
        SPECIMEN_LINE_1,
        MUTATED_LINE_2,
    )
    assert td3.parse_document_number(MUTATED_LINE_2) == MUTATED_DOCUMENT_NUMBER

    fields = {name: getattr(document, name) for name in EXPECTED_DOCUMENT_FIELDS}
    assert set(fields) == set(EXPECTED_DOCUMENT_FIELDS)
    assert all(fields.values())
    assert fields == {
        **EXPECTED_DOCUMENT_FIELDS,
        "document_number": MUTATED_DOCUMENT_NUMBER,
    }


def test_the_mutation_is_not_corrected_and_the_check_digit_is_what_reports_it():
    # The whole of 2.14 in one test: the parse does not "fix" the character,
    # and the thing that reports the disagreement is the arithmetic rather than
    # the parse.  A parser that repaired the number to agree with its printed
    # digit would satisfy every value assertion elsewhere in this file and
    # fail this one, because the record would no longer say what the document
    # printed.
    document = td3.parse_td3([SPECIMEN_LINE_1, MUTATED_LINE_2])
    number = EXPECTED_DOCUMENT_FIELDS["document_number"]
    printed = EXPECTED_DOCUMENT_FIELDS["document_number_check_digit"]

    # What the document printed is what comes back -- in the field, in the raw
    # evidence, and out of the line itself.
    assert document.document_number == MUTATED_DOCUMENT_NUMBER
    assert document.document_number != number
    assert "C" not in MUTATED_DOCUMENT_NUMBER and "A" in MUTATED_DOCUMENT_NUMBER
    assert document.sources["document_number"] == MUTATED_DOCUMENT_NUMBER
    assert field(MUTATED_LINE_2, td3.TD3_LINE_2, "document_number") == MUTATED_DOCUMENT_NUMBER

    # The verifier is what reports it: `3` for the specimen, and something else
    # for the mutant, out of the same two characters.
    assert mrz.check_digit(number) == int(printed) == 3
    assert mrz.check_digit(document.document_number) == 7
    assert mrz.check_digit(document.document_number) != int(printed)

    # The record carries the digit the document printed, as a character.  **3.3
    # is why there is no `bool` anywhere in it:** until then a caller wanting
    # to know whether the two agree had to do the arithmetic, because the
    # record held no verdict -- and the assertion below is what says a verdict
    # is a *list of named rows*, not a boolean hung off the printed digit.  The
    # printed character is still there, still a character, and the row that
    # disagrees with it is somewhere else on the record.
    assert document.document_number_check_digit == printed
    assert type(document.document_number_check_digit) is str
    assert not any(
        isinstance(getattr(document, name), bool)
        for name in dir(document)
        if not name.startswith("_")
    )

    # Put the character back and they agree again, so the disagreement is the
    # mutation and not a property the specimen always had.
    assert mrz.check_digit(td3.parse_td3(SPECIMEN_ZONE).document_number) == int(printed)


@pytest.mark.parametrize("position, printed, replacement, verdict", MUTATIONS)
def test_every_position_of_the_document_number_can_be_mutated_and_reported(
    position, printed, replacement, verdict
):
    # "A mutated character" is a claim about the whole field, and a test that
    # mutated one position would leave eight untested -- a parser that
    # corrected, say, only the trailing filler would still satisfy it.  Each
    # row lands on a distinct digit, so the nine positions are covered by
    # arithmetic rather than by hope.
    number = EXPECTED_DOCUMENT_FIELDS["document_number"]
    printed_digit = EXPECTED_DOCUMENT_FIELDS["document_number_check_digit"]
    mutated = number[: position - 1] + replacement + number[position:]

    assert number[position - 1] == printed
    assert mutated != number
    document = td3.parse_td3([SPECIMEN_LINE_1, line_2_with_document_number(mutated)])

    assert document.document_number == mutated
    assert document.sources["document_number"] == mutated
    assert mrz.check_digit(mutated) == verdict
    assert mrz.check_digit(mutated) != int(printed_digit)
    assert document.document_number_check_digit == printed_digit


def test_the_mutant_record_differs_from_the_specimen_in_the_document_number_alone():
    # The precise form of "not silently fixed": one character changes, one
    # field changes and one raw slice changes, and the other thirteen of each
    # are exactly what the same parser returned a moment earlier from the
    # unmutated zone.  A repair would show up here as no differing field at
    # all, and a parser that edited some other field on the way would show up
    # as more than one.
    #
    # **3.3 adds a third differing attribute, and it is the point of the
    # task.**  `check_digit_results` differs because the document number no
    # longer comes to the digit printed beside it, and a record that carried
    # the same verdicts for a forged number as for a genuine one would be
    # reporting nothing.  The other four rows are still identical, so the
    # failure is local to the field it belongs to.
    mutant = td3.parse_td3([SPECIMEN_LINE_1, MUTATED_LINE_2])
    specimen = td3.parse_td3(SPECIMEN_ZONE)
    public = [name for name in dir(specimen) if not name.startswith("_")]

    assert {name for name in public if getattr(specimen, name) != getattr(mutant, name)} == {
        "document_number",
        "check_digit_results",
        "sources",
    }
    assert {
        name for name in specimen.sources if specimen.sources[name] != mutant.sources[name]
    } == {"document_number"}
    assert mutant.document_number == MUTATED_DOCUMENT_NUMBER
    assert sum(
        printed != changed
        for printed, changed in zip(
            EXPECTED_DOCUMENT_FIELDS["document_number"], mutant.document_number
        )
    ) == 1


def test_the_mutation_does_not_disturb_the_three_other_field_digits():
    # The evidence 3.3 needs to name the field that failed rather than just
    # the zone: the three digits covering the other fields still agree, so a
    # mismatch is local to the document number.  The composite is the second
    # witness and is 3.2's to build, so it is not built here.
    document = td3.parse_td3([SPECIMEN_LINE_1, MUTATED_LINE_2])

    assert document.document_number == MUTATED_DOCUMENT_NUMBER
    for name in ("date_of_birth", "date_of_expiry", "personal_number"):
        printed = EXPECTED_DOCUMENT_FIELDS[name + "_check_digit"]
        assert getattr(document, name + "_check_digit") == printed, name
        assert mrz.check_digit(getattr(document, name)) == int(printed), name


def test_the_check_digit_is_blind_to_a_substitution_inside_one_character_value_class():
    # The limit of what 2.14 can promise, written down before 3.3 builds on it.
    # A character contributes its ICAO value times a weight of 7, 3 or 1, and
    # the digit is that sum modulo 10 -- so two characters whose values are
    # congruent modulo 10 are the same character as far as the arithmetic is
    # concerned.  `0`, `<` and `A` are one class and `1`/`B`/`L`/`V` another,
    # and a substitution inside a class produces a number the verifier agrees
    # with.  Exhaustive: every position, every character in the alphabet.
    number = EXPECTED_DOCUMENT_FIELDS["document_number"]
    printed = int(EXPECTED_DOCUMENT_FIELDS["document_number_check_digit"])
    alphabet = "".join(mrz.CHAR_VALUES)

    assert len(alphabet) == 37
    assert mrz.check_digit(number) == printed
    for position, character in enumerate(number, start=1):
        for replacement in alphabet:
            if replacement == character:
                continue
            mutated = number[: position - 1] + replacement + number[position:]
            same_class = mrz.char_value(replacement) % 10 == mrz.char_value(character) % 10

            assert (mrz.check_digit(mutated) == printed) is same_class, (position, replacement)
            if same_class:
                # And the parse does not repair even the substitutions the
                # arithmetic cannot see.  That is the whole of what 2.14 can
                # promise about them: no mismatch is reported, and none is
                # invented either.
                document = td3.parse_td3(
                    [SPECIMEN_LINE_1, line_2_with_document_number(mutated)]
                )
                assert document.document_number == mutated, (position, replacement)


def test_a_mutation_the_check_digit_cannot_see_is_still_parsed_and_still_returned_as_printed():
    # So 2.14's guarantee is "parsing does not fix it", not "the check digit
    # always catches it".  A substitution inside a value class is parsed like
    # any other, comes back as printed, and leaves the verifier agreeing --
    # there is no mismatch to report, and the record does not invent one.  The
    # 25 is the count the class rule above produces, so a change to
    # `char_value` or to the weights would have to be made deliberately.
    number = EXPECTED_DOCUMENT_FIELDS["document_number"]
    printed = EXPECTED_DOCUMENT_FIELDS["document_number_check_digit"]
    invisible = [
        (position, replacement)
        for position, character in enumerate(number, start=1)
        for replacement in "".join(mrz.CHAR_VALUES)
        if replacement != character
        and mrz.char_value(replacement) % 10 == mrz.char_value(character) % 10
    ]

    assert len(invisible) == 25
    for position, replacement in invisible:
        mutated = number[: position - 1] + replacement + number[position:]
        document = td3.parse_td3([SPECIMEN_LINE_1, line_2_with_document_number(mutated)])

        assert document.document_number == mutated
        assert document.sources["document_number"] == mutated
        assert mrz.check_digit(mutated) == int(printed)
        assert document.document_number_check_digit == printed


# --- the composite input: the characters the final digit is computed over ----

# The three spans, written out longhand from ICAO 9303 Part 4 rather than read
# back from the module, and the three fields they skip.
COMPOSITE_SPANS = [(1, 10), (14, 20), (22, 43)]
COMPOSITE_SKIPS = ("nationality", "sex", "composite_check_digit")

# The 39 characters the specimen prints, sliced by those spans alone.
EXPECTED_COMPOSITE = (
    SPECIMEN_LINE_2[0:10] + SPECIMEN_LINE_2[13:20] + SPECIMEN_LINE_2[21:43]
)


def line_2_with(replacements):
    """``SPECIMEN_LINE_2`` with ``replacements`` applied at their positions."""
    line = SPECIMEN_LINE_2
    for name, value in replacements.items():
        start, end = td3.TD3_LINE_2[name]
        assert len(value) == end - start + 1, name
        line = line[: start - 1] + value + line[end:]
    return line


def test_the_composite_assembler_and_its_field_list_are_exported():
    assert "td3_composite_input" in td3.__all__
    assert "TD3_COMPOSITE_FIELDS" in td3.__all__


def test_the_composite_fields_are_the_three_spans_and_nothing_else():
    # The constant is a list of *names*, so the load-bearing question is what
    # those names mean.  Both halves are derived from the layout: the fields
    # that are left out are exactly the three the composite does not cover, and
    # the eight that are left in are adjacent and in printed order, so they
    # collapse into the standard's three ranges and cover 39 positions between
    # them.  A constant that dropped the nationality by accident, or named the
    # sex marker, fails here rather than producing a plausible string.
    layout = td3.TD3_LINE_2
    ordered = sorted(layout, key=layout.__getitem__)
    spans = []
    for name in td3.TD3_COMPOSITE_FIELDS:
        start, end = layout[name]
        if spans and spans[-1][1] + 1 == start:
            spans[-1] = (spans[-1][0], end)
        else:
            spans.append((start, end))

    assert list(td3.TD3_COMPOSITE_FIELDS) == [
        name for name in ordered if name not in COMPOSITE_SKIPS
    ]
    assert spans == COMPOSITE_SPANS
    assert sum(end - start + 1 for start, end in spans) == 39


def test_the_assembled_composite_input_is_39_characters():
    # 3.1's own assertion, and the text as well as the count: the 39 characters
    # are built here from the standard's three spans and nowhere else, so a
    # builder that read 39 characters out of the wrong place fails on the value
    # even though the length would be right.
    composite = td3.td3_composite_input(SPECIMEN_LINE_2)

    assert len(EXPECTED_COMPOSITE) == 39
    assert len(composite) == 39
    assert composite == EXPECTED_COMPOSITE
    assert composite == "L898902C<3" "7408122" "1204159" "ZE184226B<<<<<1"


def test_the_composite_input_is_read_through_td3_field(monkeypatch):
    # The rule from 2.5 onwards, applied to the one function that reads eight
    # fields at once.  The count and the table are the load-bearing half: eight
    # reads, all of them the eight names, all of them the line-2 table, and all
    # of them through the single place a line is sliced.  An assembler with a
    # hand-written `line[28:42]` would pass every value assertion above while
    # never consulting the layout.
    calls = []
    original = td3.td3_field

    def recording(line, layout, name):
        calls.append((line, id(layout), name))
        return original(line, layout, name)

    monkeypatch.setattr(td3, "td3_field", recording)
    composite = td3.td3_composite_input(SPECIMEN_LINE_2)

    assert composite == EXPECTED_COMPOSITE
    assert [name for _, _, name in calls] == list(td3.TD3_COMPOSITE_FIELDS)
    assert {line for line, _, _ in calls} == {SPECIMEN_LINE_2}
    assert {table for _, table, _ in calls} == {id(td3.TD3_LINE_2)}


def test_the_composite_input_covers_neither_the_nationality_nor_the_sex():
    # The gap 2.11 and 2.12 recorded, now measured instead of remembered.
    # Positions 11-13 and 21 are outside the composite, so a line whose
    # nationality and sex are both wrong produces byte-identical input -- which
    # is what 3.2 will see, and why those two fields need the rules engine
    # rather than a check digit.  The contrast is the other half: a field the
    # composite *does* cover moves the string.
    changed = line_2_with({"nationality": "ZZZ", "sex": "M"})
    also_changed = line_2_with({"date_of_birth": "740813"})

    assert td3.td3_composite_input(changed) == EXPECTED_COMPOSITE
    assert len(td3.td3_composite_input(changed)) == 39
    assert td3.td3_composite_input(also_changed) != EXPECTED_COMPOSITE
    assert len(td3.td3_composite_input(also_changed)) == 39


def test_a_mutated_document_number_reaches_the_composite_as_printed():
    # 2.14's second witness, and the reason this is a concatenation rather than
    # a cleverer thing.  The printed check digit sits at position 10, *inside*
    # the span, so a number that no longer agrees with its own digit hands the
    # verifier both halves of the disagreement and nothing here repairs either:
    # the mutation is the first nine characters and the digit it contradicts is
    # the tenth.
    composite = td3.td3_composite_input(
        line_2_with_document_number(MUTATED_DOCUMENT_NUMBER)
    )
    printed = EXPECTED_DOCUMENT_FIELDS["document_number_check_digit"]

    assert len(composite) == 39
    assert composite[:9] == MUTATED_DOCUMENT_NUMBER
    assert composite[9] == printed
    assert mrz.check_digit(composite[:10]) != int(printed)


def test_a_short_line_produces_a_short_composite_and_is_not_rejected_here():
    # The cost of this task judging nothing, written down rather than left to
    # be found by 3.2.  Shape belongs to `validate_td3_lines` and this is not
    # that function, so a caller who skipped the gate gets a composite input of
    # the wrong length and no error.
    #
    # It is *shorter than the line*, which is the part worth writing down: a
    # read of a field that starts past the end of the line returns nothing
    # rather than objecting, so the four spans after position 20 all come back
    # empty and 20 characters of line yield 17.  A composite input that short
    # is arithmetically valid -- `check_digit` would return a digit -- so
    # nothing downstream could tell it from a real one.  The 39 in the test
    # above is the width of a line that passed the gate; nothing here defends
    # it, and 3.2 should read a line that came out of that gate.
    composite = td3.td3_composite_input(SPECIMEN_LINE_2[:20])

    assert len(composite) == 17
    assert composite == SPECIMEN_LINE_2[0:10] + SPECIMEN_LINE_2[13:20]


def test_a_line_that_is_not_a_string_is_rejected_by_td3_field_itself():
    # No new error type and no new message: `td3_field` raises on the first
    # read and the assembler lets it through, so a caller still writes one
    # `except MrzValueError` and 1.9's rule holds.  The message is compared
    # rather than read, so this pins that it is *not* the assembler's.
    with pytest.raises(mrz.MrzValueError) as assembled:
        td3.td3_composite_input(None)
    with pytest.raises(mrz.MrzValueError) as single:
        td3.td3_field(None, td3.TD3_LINE_2, "document_number")

    assert str(assembled.value) == str(single.value)


# --- the composite digit: checked against the one the line printed ----------

# The digit the specimen prints at position 44, read with the longhand table
# rather than by index, so what is compared below is the standard's field and
# not a character of a string.  The 39 characters come from the module, so the
# two halves of the comparison are independent: one is the standard's field
# list, the other is the layout and the assembler 3.1 built over it.
PRINTED_COMPOSITE_DIGIT = field(SPECIMEN_LINE_2, EXPECTED_LINE_2, "composite_check_digit")


def composite_agrees(line_2):
    """Whether the line's own 39 characters come to the digit it printed.

    The verification 3.2 is about, written here rather than in
    `app.pipeline.tier0.td3`: the assembler supplies the characters, `mrz`
    supplies the arithmetic, and the two are compared against the character
    the line printed.  2.2's `test_this_module_computes_no_check_digit_of_its_own`
    is why it is written here -- that digit is not in `td3`'s namespace and
    this task did not put it there, so a verdict has nowhere to live in the
    layout module and 3.3 is what gives it a home on the record.
    """
    return mrz.verify_check_digit(
        td3.td3_composite_input(line_2),
        field(line_2, EXPECTED_LINE_2, "composite_check_digit"),
    )


def test_the_specimen_s_composite_digit_agrees_with_its_own_39_characters():
    # 3.2's own assertion, and 3.1's handover instruction discharged: the line
    # verified is the one that came out of the shape gate, which is where a
    # caller gets one.
    #
    # **What this cannot do is confirm the value, and the test says so rather
    # than letting a green run imply it.**  The specimen's position 44 was
    # derived by `mrz.check_digit` and not quoted from the standard, because
    # 1.6 could not reach a source that publishes it.  So the agreement below
    # is the fixture against the arithmetic: it proves the 39 characters the
    # layout names, the digit the line prints and the verdict over them are
    # one story, and it says nothing about whether 6 is the character the ICAO
    # document carries.
    line_1, line_2 = td3.validate_td3_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2])
    composite = td3.td3_composite_input(line_2)

    assert line_1 == SPECIMEN_LINE_1 and line_2 == SPECIMEN_LINE_2
    assert PRINTED_COMPOSITE_DIGIT == "6"
    assert len(composite) == 39
    assert mrz.check_digit(composite) == int(PRINTED_COMPOSITE_DIGIT)
    assert composite_agrees(line_2) is True


def test_a_deliberately_wrong_final_digit_is_detected():
    # ROADMAP B1.5's "a forged final digit is detected", over all nine wrong
    # digits rather than the one chosen digit, so no digit of the ten can be
    # special.  Only position 44 moves: the 39 characters the composite is
    # computed over are byte-identical and the arithmetic still comes to the
    # same 6 for every one of the nine.  That is what makes the disagreement
    # the printed digit and nothing else -- an input read from anywhere else,
    # or a digit recomputed from the line, would have nothing to disagree with.
    wrong_digits = [d for d in string.digits if d != PRINTED_COMPOSITE_DIGIT]

    assert len(wrong_digits) == 9
    for digit in wrong_digits:
        forged = line_2_with({"composite_check_digit": digit})

        assert forged[:43] == SPECIMEN_LINE_2[:43], digit
        assert forged[43] == digit
        assert td3.td3_composite_input(forged) == EXPECTED_COMPOSITE, digit
        assert mrz.check_digit(td3.td3_composite_input(forged)) == 6, digit
        assert composite_agrees(forged) is False, digit


def test_a_wrong_nationality_and_a_wrong_sex_still_agree():
    # The gap 2.11 and 2.12 recorded, carried into the verdict rather than left
    # as a fact about the assembler: positions 11-13 and 21 are outside the
    # composite, so the two fields with no arithmetic under them produce a
    # document that agrees with itself.  The contrast is what keeps the test
    # honest -- a field the composite *does* cover moves the string and is
    # caught, so the `True` below is the spans' blind spot and not a check that
    # passes everything.
    changed = line_2_with({"nationality": "ZZZ", "sex": "M"})
    covered = line_2_with({"date_of_birth": "740813"})

    assert td3.td3_composite_input(changed) == EXPECTED_COMPOSITE
    assert composite_agrees(changed) is True
    assert td3.td3_composite_input(covered) != EXPECTED_COMPOSITE
    assert len(td3.td3_composite_input(covered)) == 39
    assert composite_agrees(covered) is False


def test_a_character_at_position_44_that_is_not_a_digit_is_refused():
    # Position 44 is read as a character, so an OCR slip that puts a letter
    # there is a claim about the document rather than a mismatch in its
    # arithmetic, and `verify_check_digit` refuses to call it either way.  The
    # distinction is 2.14's and it is the reason a `False` is not invented
    # here: a misread last character is not evidence of a forged digit, and a
    # truncated or garbled line must not reach an officer as tampering.
    for character in (mrz.FILLER, "A", "B"):
        garbled = line_2_with({"composite_check_digit": character})

        with pytest.raises(mrz.MrzValueError):
            composite_agrees(garbled)

        assert len(td3.td3_composite_input(garbled)) == 39
        assert mrz.check_digit(td3.td3_composite_input(garbled)) == 6


def test_a_line_that_never_passed_the_gate_offers_no_digit_to_check():
    # 3.1's boundary, reached from this side: a line that stops at 20
    # characters has a composite input of 17 and nothing printed at position
    # 44, so the check has no claim to compare and the answer is mrz's refusal
    # rather than a `False`.  This is why the line verified above is the one
    # `validate_td3_lines` returned, and why no width check was added to
    # either function to cover it.
    short = SPECIMEN_LINE_2[:20]
    composite = td3.td3_composite_input(short)

    assert len(composite) == 17
    with pytest.raises(mrz.MrzValueError):
        composite_agrees(short)


# --- 3.3: the per-field check-digit verdicts, on the record -----------------

# The five rows the record reports, named as a verdict is named.  Four are
# fields of the layout under their own names; the fifth is the composite,
# which is the one whose characters are not printed anywhere in the zone.
EXPECTED_CHECK_DIGIT_FIELDS = [
    "document_number",
    "date_of_birth",
    "date_of_expiry",
    "personal_number",
    "composite",
]


def results_by_field(document):
    """The record's verdicts, keyed by the field each one is about."""
    return {result.field: result for result in document.check_digit_results}


def failed_fields(document):
    """The fields whose printed digit and computed digit disagree."""
    return [result.field for result in document.check_digit_results if result.passed is False]


def unchecked_fields(document):
    """The fields the arithmetic could not be attempted on at all."""
    return [result.field for result in document.check_digit_results if result.passed is None]


def test_the_result_record_and_the_td3_pairings_are_exported():
    assert {"CheckDigitResult", "check_digit_results"} <= set(mrz.__all__)
    assert {"TD3_CHECK_DIGIT_FIELDS", "td3_check_digit_results"} <= set(td3.__all__)


def test_a_correct_mrz_yields_five_results_and_every_one_of_them_passes():
    # 3.3's first half, and the whole of it: a document that agrees with itself
    # produces one row per printed digit, in printed order, and every row says
    # the two halves are the same number.
    #
    # **What this is not, in the same spirit as 3.2's caveat.**  The specimen's
    # five digits were checked by 2.14 and 3.2 against the arithmetic rather
    # than quoted from a source that publishes them, and 1.6's limit on
    # position 44 is unchanged by moving the comparison here.  So this is the
    # fixture agreeing with the arithmetic, and a caller must not read a green
    # row as "this passport is genuine" -- it is "this line agrees with itself
    # over the characters it printed", which is what a check digit can ever be.
    document = td3.parse_td3(SPECIMEN_ZONE)
    results = document.check_digit_results

    assert [result.field for result in results] == EXPECTED_CHECK_DIGIT_FIELDS
    assert len(results) == 5
    assert [result.passed for result in results] == [True] * 5
    assert failed_fields(document) == []
    assert unchecked_fields(document) == []
    assert all(result.readable for result in results)


def test_each_result_carries_both_digits_and_the_specimen_s_are_its_own():
    # A verdict that could only say pass or fail would leave a flag with no
    # `expected` and no `found`, which is the half of the finding
    # `verify_check_digit` throws away.  Both are here, and they are read from
    # the longhand table of what the specimen prints -- so a result that
    # reported the right digits for the wrong reasons still fails, and a
    # result that recomputed its `expected` from its own `found` would make
    # every row pass forever.
    document = td3.parse_td3(SPECIMEN_ZONE)
    results = results_by_field(document)

    for label in EXPECTED_CHECK_DIGIT_FIELDS:
        printed = EXPECTED_DOCUMENT_FIELDS[f"{label}_check_digit"]
        result = results[label]

        assert type(result.expected) is int, label
        assert type(result.found) is int, label
        assert result.expected == int(printed), label
        assert result.found == int(printed), label
        assert document.sources[f"{label}_check_digit"] == printed, label


def test_each_result_is_computed_over_the_characters_its_own_field_holds():
    # The pairing, and the only place it can be checked: the four field rows
    # are computed over the field the layout names and the composite row over
    # the 39 characters of the standard's three spans, which 3.1 built
    # longhand above.  The whole of line 2 is the near miss -- it is also 44
    # characters of the same line, and it comes to a different digit, so a
    # result computed over the line rather than over the field is caught here
    # rather than looking like a pass.
    document = td3.parse_td3(SPECIMEN_ZONE)
    results = results_by_field(document)

    for label in EXPECTED_CHECK_DIGIT_FIELDS[:-1]:
        assert results[label].found == mrz.check_digit(EXPECTED_DOCUMENT_FIELDS[label]), label
    assert len(EXPECTED_COMPOSITE) == 39
    assert results["composite"].found == mrz.check_digit(EXPECTED_COMPOSITE)
    assert mrz.check_digit(SPECIMEN_LINE_2) != results["composite"].found


def test_a_mutated_field_is_named_and_the_other_three_are_still_reported():
    # 3.3's second half, and the question the task asks: given a document that
    # does not agree with itself, *which field* disagreed.  One row per field
    # mutated, each with the printed digit left exactly where the specimen
    # printed it, so the only thing that can have changed is the characters the
    # digit is computed over.
    #
    # **Every mutation fails two rows, and the second is always the
    # composite.**  That is the property worth having and it is a fact about
    # the spans rather than about the mutations: positions 1-10, 14-20 and
    # 22-43 cover all four fields, so no field can be edited without the
    # composite moving too.  A caller reading this list learns the local cause
    # and that the whole line is implicated as well -- which is the honest
    # reading, because the composite cannot tell them which of the two
    # mismatches came first.
    mutations = [
        ("document_number", "L898902A<"),
        ("date_of_birth", "740813"),
        ("date_of_expiry", "120416"),
        ("personal_number", "ZD184226B<<<<<"),
    ]
    assert len(mutations) == 4

    for name, printed in mutations:
        line_2 = line_2_with_field(SPECIMEN_LINE_2, name, printed)
        document = td3.parse_td3([SPECIMEN_LINE_1, line_2])

        assert document.sources[name] == printed, name
        assert document.sources[name + "_check_digit"] == EXPECTED_DOCUMENT_FIELDS[
            name + "_check_digit"
        ], name
        assert failed_fields(document) == [name, "composite"], name
        assert unchecked_fields(document) == [], name
        result = results_by_field(document)[name]
        assert result.expected == int(EXPECTED_DOCUMENT_FIELDS[name + "_check_digit"]), name
        assert result.found != result.expected, name
        assert result.passed is False, name
        # The three fields nobody touched keep passing, which is what makes
        # the failure local rather than a verdict on the whole document.
        assert [
            result.passed
            for result in document.check_digit_results
            if result.field not in (name, "composite")
        ] == [True] * 3, name


def test_a_forged_final_digit_fails_the_composite_row_and_nothing_else():
    # 3.2's nine wrong digits, now reported rather than merely answered: a
    # forger who recomputes nothing and edits position 44 is caught, and the
    # row that catches them names the composite, because the 39 characters it
    # is computed over are exactly what the specimen printed.
    wrong_digits = [d for d in string.digits if d != PRINTED_COMPOSITE_DIGIT]

    assert len(wrong_digits) == 9
    for digit in wrong_digits:
        document = td3.parse_td3(
            [SPECIMEN_LINE_1, line_2_with({"composite_check_digit": digit})]
        )
        result = results_by_field(document)["composite"]

        assert result.expected == int(digit), digit
        assert result.found == 6, digit
        assert result.passed is False, digit
        assert failed_fields(document) == ["composite"], digit


def test_a_field_the_arithmetic_cannot_see_still_passes_and_is_not_reported():
    # 2.14's limit, carried onto the record rather than restated: a
    # substitution inside one ICAO value class is invisible to the digit, so
    # the row passes.  The test that matters is what the record does *not* do
    # -- it does not invent a failure for a substitution the arithmetic cannot
    # see, which is the way a verdict list starts manufacturing evidence.
    number = EXPECTED_DOCUMENT_FIELDS["document_number"]
    alphabet = "".join(mrz.CHAR_VALUES)
    invisible = [
        (position, replacement)
        for position, character in enumerate(number, start=1)
        for replacement in alphabet
        if replacement != character
        and mrz.char_value(replacement) % 10 == mrz.char_value(character) % 10
    ]

    assert len(invisible) == 25
    for position, replacement in invisible:
        mutated = number[: position - 1] + replacement + number[position:]
        document = td3.parse_td3(
            [SPECIMEN_LINE_1, line_2_with_document_number(mutated)]
        )

        assert document.document_number == mutated, (position, replacement)
        assert failed_fields(document) == [], (position, replacement)
        assert unchecked_fields(document) == [], (position, replacement)
        assert results_by_field(document)["composite"].passed is True, (
            position,
            replacement,
        )


def test_a_printed_digit_that_is_not_a_digit_is_not_checked_and_is_not_a_failure():
    # 3.2 refused to call a letter at position 44 a mismatch, because a misread
    # last character is not evidence of forgery.  A list has no choice but to
    # keep going, so the refusal becomes a third answer rather than a dropped
    # row: `passed is None`, the row is still there, and the four rows beside
    # it are still verdicts.  The specimen's own composite characters are
    # untouched, so `found` is still 6 -- which is the half a flag wants and
    # the reason refusing the whole list would have thrown away the finding.
    for character in (mrz.FILLER, "A", "B"):
        document = td3.parse_td3(
            [SPECIMEN_LINE_1, line_2_with({"composite_check_digit": character})]
        )
        result = results_by_field(document)["composite"]

        assert result.expected is None, character
        assert result.found == 6, character
        assert result.readable is False, character
        assert result.passed is None, character
        assert failed_fields(document) == [], character
        assert unchecked_fields(document) == ["composite"], character
        assert [r.passed for r in document.check_digit_results[:-1]] == [True] * 4


def test_a_field_carrying_a_character_the_alphabet_lacks_is_not_checked_either():
    # The other direction, and the one 2.4 and 2.12 wrote their rules for: a
    # date or an optional field holding a character the MRZ alphabet cannot
    # print comes back exactly as printed, is judged by nothing, and -- because
    # it is also in the composite -- leaves two rows unchecked rather than
    # refusing the document.  `verify_check_digit` would have raised for either
    # of these; that is right for one field and wrong for a list, and this is
    # the case that says which one this is.
    for name, printed in (
        ("personal_number", "ZE184226 B<<<<"),
        ("date_of_birth", "7a0812"),
    ):
        line_2 = line_2_with_field(SPECIMEN_LINE_2, name, printed)
        document = td3.parse_td3([SPECIMEN_LINE_1, line_2])
        results = results_by_field(document)

        assert getattr(document, name) == printed, name
        assert document.sources[name] == printed, name
        assert results[name].found is None, name
        assert results[name].passed is None, name
        assert results[name].expected is not None, name
        assert results["composite"].found is None, name
        assert results["composite"].passed is None, name
        assert unchecked_fields(document) == [name, "composite"], name
        assert failed_fields(document) == [], name


def test_a_wrong_nationality_and_a_wrong_sex_marker_still_pass_everything():
    # 2.11's and 2.12's gap, now a property of the record rather than of the
    # assembler: positions 11-13 and 21 are outside the composite and carry no
    # digit of their own, so a document with both of them wrong produces five
    # passing rows.  The contrast is what keeps this honest -- a field the
    # composite does cover, with the same treatment, fails -- so the `[]`
    # below is the gap rather than a check that passes everything.
    changed = line_2_with({"nationality": "ZZZ", "sex": "M"})
    covered = line_2_with({"date_of_birth": "740813"})

    assert failed_fields(td3.parse_td3([SPECIMEN_LINE_1, changed])) == []
    assert failed_fields(td3.parse_td3([SPECIMEN_LINE_1, covered])) == [
        "date_of_birth",
        "composite",
    ]


def test_the_five_pairings_are_the_standard_five_in_printed_order():
    # The list is a claim about which digit checks which field, and the layout
    # cannot say it -- position 10 is the last character of the document number
    # *and* the first of the composite's first span, and only the standard
    # says which field the digit belongs to.  So it is checked against the
    # printed order of the two columns instead: each pairing is a digit field
    # whose position is one past the end of the field it checks, every such
    # pair in the layout is listed, and the composite is the only one of the
    # five with no characters of its own to read.
    layout = td3.TD3_LINE_2
    digit_fields = {
        name for name in layout if name.endswith("_check_digit") and name != "composite_check_digit"
    }
    listed = {digit for _, _, digit in td3.TD3_CHECK_DIGIT_FIELDS}

    assert list(td3.TD3_CHECK_DIGIT_FIELDS) == [
        ("document_number", "document_number", "document_number_check_digit"),
        ("date_of_birth", "date_of_birth", "date_of_birth_check_digit"),
        ("date_of_expiry", "date_of_expiry", "date_of_expiry_check_digit"),
        ("personal_number", "personal_number", "personal_number_check_digit"),
        ("composite", None, "composite_check_digit"),
    ]
    assert [digit for _, _, digit in td3.TD3_CHECK_DIGIT_FIELDS] == [
        "document_number_check_digit",
        "date_of_birth_check_digit",
        "date_of_expiry_check_digit",
        "personal_number_check_digit",
        "composite_check_digit",
    ]
    assert listed == digit_fields | {"composite_check_digit"}
    assert len(listed) == 5
    for label, characters, digit in td3.TD3_CHECK_DIGIT_FIELDS:
        assert label in EXPECTED_CHECK_DIGIT_FIELDS
        assert characters is None or characters in layout
        assert layout[digit][0] == layout[digit][1], digit
        if characters is not None:
            assert layout[characters][1] + 1 == layout[digit][0], label
    assert layout["composite_check_digit"][0] == 44


def test_the_results_are_frozen_records_and_two_parses_do_not_share_them():
    # The list is on a frozen record, so it has to be a tuple of frozen
    # records itself -- a list would be the one editable part of an
    # uneditable record, and a shared dict would let one document's verdicts be
    # changed by another's.
    specimen = td3.parse_td3(SPECIMEN_ZONE)
    second = td3.parse_td3(SPECIMEN_ZONE)
    results = specimen.check_digit_results

    assert isinstance(results, tuple)
    assert not isinstance(results, list)
    assert dataclasses.is_dataclass(mrz.CheckDigitResult)
    assert mrz.CheckDigitResult.__dataclass_params__.frozen is True
    for result in results:
        assert isinstance(result, mrz.CheckDigitResult)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.passed = True
    assert specimen == second
    assert results is not second.check_digit_results
    assert all(
        first is not other
        for first, other in zip(results, second.check_digit_results)
    )


def test_the_record_keeps_the_printed_digit_and_the_verdict_as_two_things():
    # The attribute above is evidence and the one below is this parse's reading
    # of it, and collapsing them would let a parse "repair" a document's digit
    # to make its own verdict pass.  The specimen is the only place this is
    # visible -- the two agree, so the test is that they are still *separate*
    # rather than that they differ.
    document = td3.parse_td3(SPECIMEN_ZONE)
    result = results_by_field(document)["composite"]

    assert document.composite_check_digit == "6"
    assert type(document.composite_check_digit) is str
    assert result.expected == 6
    assert document.composite_check_digit != result.expected
    assert str(result.expected) == document.composite_check_digit
