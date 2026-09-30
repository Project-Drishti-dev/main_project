"""The TD1 layout constants: the positions, and the coverage they claim.

Task 3.4 asks for the three 30-character tables and for a test that every
position of every line is claimed exactly once.  The tables are written out
longhand here from ICAO 9303 Part 4 rather than read back from the module --
a test that compares ``td1.TD1_LINE_1`` with itself proves nothing -- so a
field that moved, was renamed or was given the wrong width is caught by name.

**The synthetic line below is still how the positions are checked, and 3.5
adds a printed specimen on top of it rather than replacing it.**  Thirty
distinct characters, each one naming the position it stands in, catches a
slice that lands a character early or late on a line that is otherwise
meaningless; a *printed* line catches a table that is right about a
meaningless line and wrong about a document.  They fail differently, so both
stay.

**The specimen is the ICAO 9303 Part 4 sample ID card, and the one printed
digit line 1 carries is checked against this project's own arithmetic.**  That
is what 3.5 was waiting for: 3.4 could only quote positions, because
quoting a specimen means quoting a check digit nobody has verified, and 1.6
declined to do exactly that for the TD3 composite.  Here the document number
is ``"D23145890"``, the digit printed beside it at position 15 is ``7``, and
:func:`~app.pipeline.tier0.mrz.check_digit` returns ``7`` for those nine
characters -- so the digit is quoted and confirmed rather than trusted.  The
confirmation is in the tests below, not in this comment.

**Line 2 of the same specimen is quoted here too, and its two printed date
digits are checked the way line 1's was.**  3.6 adds
``"7408122F1204159UTO<<<<<<<<<<<7"`` as the same card's second line:
:func:`~app.pipeline.tier0.mrz.check_digit` on ``"740812"`` is the ``2`` the
document prints at position 7 and on ``"120415"`` is the ``9`` it prints at
position 15, so both are quoted and confirmed rather than trusted.

**The composite at position 30 is the one printed digit in this fixture that
is *derived* rather than quoted, and 3.7 is what made it so.**  3.6 wrote
``6`` there from memory and said in a test name that it was verified by
nothing.  3.7 verified it, and it did not agree:
:func:`~app.pipeline.tier0.mrz.check_digit` over the standard's 51 characters
comes to ``7``, and no reading of the two candidate spans produces ``6``.  So
the ``6`` was one of the two values 1.6 refused to state -- a remembered digit
with no source behind it -- and the same choice ``test_td3.py`` made for its
own composite is made here: the digit at position 30 is
:func:`~app.pipeline.tier0.mrz.check_digit`'s own output over the span, the
tests below pin the *span* longhand rather than a published character, and
the fixture is the arithmetic's rather than a document's.

**That is a claim about this fixture and not about any ID card, and the
tests below say so where it is made.**  The four date and number digits are
quoted and confirmed, so a misremembered line is very unlikely to survive;
the composite is the one value here that no source in this repository can
confirm, exactly as 1.6 recorded for the TD3.

The coverage claim is the one the task names, and it is stated twice on
purpose: once as a single sorted comparison per line, which is the compact
form, and once per boundary, which says which field broke the line when it
fails.
"""

import inspect
import string

import pytest

from app.pipeline.tier0 import mrz, td1

# Written out longhand from the standard rather than read back from the module.
EXPECTED_LINE_1 = {
    "document_code": (1, 2),
    "issuing_state": (3, 5),
    "document_number": (6, 14),
    "document_number_check_digit": (15, 15),
    "optional_data_1": (16, 29),
    "optional_data_1_check_digit": (30, 30),
}

EXPECTED_LINE_2 = {
    "date_of_birth": (1, 6),
    "date_of_birth_check_digit": (7, 7),
    "sex": (8, 8),
    "date_of_expiry": (9, 14),
    "date_of_expiry_check_digit": (15, 15),
    "nationality": (16, 18),
    "optional_data_2": (19, 29),
    "composite_check_digit": (30, 30),
}

EXPECTED_LINE_3 = {
    "name": (1, 30),
}

EXPECTED = {
    "line_1": EXPECTED_LINE_1,
    "line_2": EXPECTED_LINE_2,
    "line_3": EXPECTED_LINE_3,
}

LAYOUTS = [(line_name, td1.TD1[line_name]) for line_name in sorted(EXPECTED)]

# One character per position, so a slice reports where it started and stopped.
# 10 digits then the first 20 letters is exactly 30.
PRINTED = string.digits + string.ascii_uppercase[:20]
PRINTED_LINES = {"line_1": PRINTED, "line_2": PRINTED, "line_3": PRINTED}


def field(line, layout, name):
    """Slice ``name`` out of ``line`` the way a later TD1 parser will."""
    start, end = layout[name]
    return line[start - 1 : end]


def fields_in_printed_order(layout):
    """The layout's fields, the way they appear on the line."""
    return sorted(layout.items(), key=lambda item: item[1])


# --- the constants are the standard's field list --------------------------


@pytest.mark.parametrize("line_name", sorted(EXPECTED))
def test_the_layout_holds_the_fields_the_standard_lists(line_name):
    assert td1.TD1[line_name] == EXPECTED[line_name]


def test_the_line_is_30_characters():
    # Not "the tables happen to add up to 30": the line the positions are read
    # against below is a real string, so if the length were wrong neither
    # table nor slice would agree with it.
    assert td1.TD1_LINE_LENGTH == 30
    assert len(PRINTED) == td1.TD1_LINE_LENGTH


def test_a_td1_zone_is_three_lines():
    # Never a range: the third line is the name, which is a field rather than a
    # longer zone.
    assert td1.TD1_LINE_COUNT == 3
    assert len(td1.TD1) == td1.TD1_LINE_COUNT


def test_the_aggregate_holds_the_line_tables_rather_than_copies():
    # A copy would be a second table to drift, which is the failure these
    # tables exist to prevent, so the identity is the assertion.
    assert td1.TD1["line_1"] is td1.TD1_LINE_1
    assert td1.TD1["line_2"] is td1.TD1_LINE_2
    assert td1.TD1["line_3"] is td1.TD1_LINE_3
    assert set(td1.TD1) == {"line_1", "line_2", "line_3"}


def test_the_layout_names_are_exported():
    # The six names 3.4 added, the twelve 3.5 added beside them, the twelve 3.6
    # added after that and the four 3.7 added last: three layouts' worth of
    # closed sets, the one slicer, nine parse/validate pairs, the two line
    # assemblers, the composite's span and the verdict list.  Sorted here
    # rather than written in the module's order so the assertion is about the
    # set, which is what a caller importing by name relies on.
    assert sorted(td1.__all__) == sorted(
        [
            "TD1",
            "TD1_CHECK_DIGIT_FIELDS",
            "TD1_COMPOSITE_SPANS",
            "TD1_LINE_1",
            "TD1_LINE_2",
            "TD1_LINE_3",
            "TD1_LINE_COUNT",
            "TD1_LINE_LENGTH",
            "TD1_DOCUMENT_CODES",
            "TD1_SEX_MARKERS",
            "td1_field",
            "validate_document_code",
            "parse_document_code",
            "validate_issuing_state",
            "parse_issuing_state",
            "validate_document_number",
            "parse_document_number",
            "validate_optional_data_1",
            "parse_optional_data_1",
            "parse_td1_line_1",
            "validate_date_of_birth",
            "parse_date_of_birth",
            "validate_sex",
            "parse_sex",
            "validate_date_of_expiry",
            "parse_date_of_expiry",
            "validate_nationality",
            "parse_nationality",
            "validate_optional_data_2",
            "parse_optional_data_2",
            "td1_check_digit_results",
            "td1_composite_input",
            "parse_td1_line_2",
            # 3.14: the zone gate and the whole-zone parser, which are the two
            # names a caller outside this package needs -- one to check a
            # shape, one to read a document -- and which no earlier task in
            # this format could publish while the record did not exist.
            "validate_td1_lines",
            "parse_td1",
        ]
    )


# --- the coverage this task asks for --------------------------------------


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_a_line_covers_positions_1_to_30_with_no_gap_or_overlap(line_name, layout):
    claimed = []
    for field_name, (start, end) in fields_in_printed_order(layout):
        assert isinstance(start, int), f"{line_name}.{field_name} start is not an int"
        assert isinstance(end, int), f"{line_name}.{field_name} end is not an int"
        assert 1 <= start <= end, f"{line_name}.{field_name} is an empty or inverted range"
        assert (
            end <= td1.TD1_LINE_LENGTH
        ), f"{line_name}.{field_name} runs past the line"
        claimed.extend(range(start, end + 1))

    # One sorted comparison carries the whole claim.  A gap drops a position, an
    # overlap repeats one, and an out-of-range index puts a value in the list
    # that is not in 1-30; whichever it is, the two lists first differ at the
    # position that broke.  Counting to 30 would not do: a gap and an overlap
    # can cancel out in the total.
    assert sorted(claimed) == list(range(1, td1.TD1_LINE_LENGTH + 1))


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_the_fields_are_adjacent_and_ordered(line_name, layout):
    # The same claim as above, reported per boundary, so a failure says which
    # field broke the line rather than only that 30 integers did not appear.
    expected_start = 1
    for field_name, (start, end) in fields_in_printed_order(layout):
        assert (
            start == expected_start
        ), f"{line_name}.{field_name} starts at {start}, not {expected_start}"
        expected_start = end + 1

    assert expected_start == td1.TD1_LINE_LENGTH + 1


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_every_field_is_readable_from_a_printed_line(line_name, layout):
    # A layout whose positions are all inside the line but land in the wrong
    # place still passes both coverage tests above, so the widths are checked
    # against a line of the right size here.
    line = PRINTED_LINES[line_name]
    for field_name, (start, end) in fields_in_printed_order(layout):
        assert len(field(line, layout, field_name)) == end - start + 1


def test_the_slices_rebuild_the_line_and_take_nothing_twice():
    # The coverage claim read back as text: concatenated in printed order the
    # slices are the whole line, and each character is in exactly one of them.
    for line_name, layout in LAYOUTS:
        slices = [
            field(PRINTED_LINES[line_name], layout, field_name)
            for field_name, _ in fields_in_printed_order(layout)
        ]

        assert "".join(slices) == PRINTED_LINES[line_name]
        assert sum(len(one) for one in slices) == td1.TD1_LINE_LENGTH


# --- the positions against a line of labelled characters -------------------


@pytest.mark.parametrize(
    "line_name, field_name, expected",
    [
        ("line_1", "document_code", "01"),
        ("line_1", "issuing_state", "234"),
        ("line_1", "document_number", "56789ABCD"),
        ("line_1", "document_number_check_digit", "E"),
        ("line_1", "optional_data_1", "FGHIJKLMNOPQRS"),
        ("line_1", "optional_data_1_check_digit", "T"),
        ("line_2", "date_of_birth", "012345"),
        ("line_2", "date_of_birth_check_digit", "6"),
        ("line_2", "sex", "7"),
        ("line_2", "date_of_expiry", "89ABCD"),
        ("line_2", "date_of_expiry_check_digit", "E"),
        ("line_2", "nationality", "FGH"),
        ("line_2", "optional_data_2", "IJKLMNOPQRS"),
        ("line_2", "composite_check_digit", "T"),
        ("line_3", "name", PRINTED),
    ],
)
def test_a_field_slices_the_characters_its_own_positions_hold(
    line_name, field_name, expected
):
    # The expected strings are written out from the standard's positions, one
    # character per position, so a table that shifted a boundary by one fails
    # on the value rather than passing as self-consistent.
    layout = td1.TD1[line_name]

    assert field(PRINTED_LINES[line_name], layout, field_name) == expected


@pytest.mark.parametrize(
    "field_name, line_name",
    [
        ("document_number_check_digit", "line_1"),
        ("optional_data_1_check_digit", "line_1"),
        ("date_of_birth_check_digit", "line_2"),
        ("date_of_expiry_check_digit", "line_2"),
        ("composite_check_digit", "line_2"),
    ],
)
def test_every_printed_digit_sits_immediately_after_the_field_it_checks(
    field_name, line_name
):
    # A check digit is only correct for that exact field over that exact span,
    # so it is printed in the position straight after the characters it covers.
    # Derived from the table rather than restated, and uniform over all five
    # printed digits a TD1 carries.
    layout = td1.TD1[line_name]
    ordered = [name for name, _ in fields_in_printed_order(layout)]
    previous = ordered[ordered.index(field_name) - 1]

    assert layout[field_name][0] == layout[previous][1] + 1
    assert layout[field_name][0] == layout[field_name][1]


def test_the_composite_is_the_last_position_of_line_2_and_not_of_line_1():
    # The one thing about a TD1 that is easy to get backwards: line 1's last
    # position is the check digit over optional data 1, and the composite is
    # printed at the end of line 2 while being computed over characters on both.
    assert td1.TD1_LINE_1["optional_data_1_check_digit"] == (30, 30)
    assert td1.TD1_LINE_2["composite_check_digit"] == (30, 30)
    assert "composite_check_digit" not in td1.TD1_LINE_1


def test_line_3_is_nothing_but_the_name():
    # Stated because it is the reason a TD1 has three lines where a TD3 has
    # two, and because a table that put a second field here would be a
    # different format rather than a fuller TD1.
    assert td1.TD1_LINE_3 == {"name": (1, 30)}
    assert td1.TD1_LINE_3["name"] == (1, td1.TD1_LINE_LENGTH)


def test_the_field_names_are_unique_across_the_three_lines():
    # A name used on two lines would be ambiguous to a record keyed by field,
    # and the per-line tables are what 3.5 and 3.6 will read by name.
    names = [name for layout in td1.TD1.values() for name in layout]

    assert len(names) == len(set(names))


def test_no_field_spans_more_than_one_line():
    # The composite is computed over characters on two lines, but it is
    # *printed* on one, so every span here stays inside a single line of 30 and
    # 3.7 is the first thing in this format that has to read two.
    for line_name, layout in LAYOUTS:
        for field_name, (start, end) in layout.items():
            assert 1 <= start <= end <= td1.TD1_LINE_LENGTH, f"{line_name}.{field_name}"


def test_this_module_states_positions_and_computes_nothing():
    # **3.7 is the first delegation into this rule, and the test is rewritten
    # rather than deleted, for the reason 3.3 rewrote td3.py's twin:** the
    # `banned in vars(td1)` loop used to be a true statement of the whole
    # claim -- a module with no digit layer imported could not do arithmetic
    # -- and `td1_check_digit_results` made it false.  The loop stays, because
    # this module still has no copy of the weights, the character table or the
    # single-field comparison.  What is added is the rule those names were
    # standing in for, which is about the code rather than about one import
    # line and holds however the function is reached: no function here
    # multiplies, adds or takes a remainder.
    #
    # The last assertion is the one that says delegation and duplication are
    # different things.  `td1.check_digit_results` **is** `mrz`'s function --
    # the same object, not a wrapper and not a re-implementation -- so the
    # sum, the weights and the modulo live in exactly one place in the package
    # and there is no second copy here that could disagree with the first.
    for name, obj in vars(td1).items():
        if inspect.isfunction(obj):
            assert "%" not in inspect.getsource(obj), f"td1.{name} computes something"

    for banned in ("CHAR_VALUES", "WEIGHT_CYCLE", "char_value", "check_digit", "weights"):
        assert banned not in vars(td1), f"td1.{banned}"

    assert "check_digit" not in vars(td1)
    assert "verify_check_digit" not in vars(td1)
    assert "%" not in inspect.getsource(td1.td1_composite_input)
    assert "%" not in inspect.getsource(td1.td1_check_digit_results)
    assert td1.check_digit_results is mrz.check_digit_results


# --- 3.5: line 1, read on a printed specimen ------------------------------

# The ICAO 9303 Part 4 sample ID card's line 1, written out longhand and 30
# characters long: "I<" (an identity card), "UTO" (the standard's fictitious
# issuing state, the same one the specimen passport uses), the nine-character
# document number "D23145890", its check digit "7", and fourteen fillers of
# optional data 1 followed by the filler in its check digit's place -- which
# is what an unused optional data field prints.
SPECIMEN_LINE_1 = "I<UTOD231458907<<<<<<<<<<<<<<<"

SPECIMEN_EXPECTED = {
    "document_code": "I<",
    "issuing_state": "UTO",
    "document_number": "D23145890",
    "document_number_check_digit": "7",
    "optional_data_1": "<" * 14,
    "optional_data_1_check_digit": "<",
}


def line_1_with(field_name, printed):
    """The specimen with ``field_name`` replaced by ``printed``, for a fault."""
    start, end = td1.TD1_LINE_1[field_name]
    return SPECIMEN_LINE_1[: start - 1] + printed + SPECIMEN_LINE_1[end:]


def test_the_specimen_is_a_line_of_thirty_characters():
    # Not "the tables happen to add up to 30": the line every slice below is
    # read out of is a real string, so a miscounted run of fillers would show
    # up here rather than as a short field further down.
    assert len(SPECIMEN_LINE_1) == td1.TD1_LINE_LENGTH


def test_the_specimens_printed_digit_is_the_one_the_arithmetic_computes():
    # The claim that lets a specimen be quoted at all.  The document number is
    # nine characters this project chose nothing about, and the digit printed
    # beside it is 1.6's "value this repository would not state for want of a
    # source" -- so it is checked against mrz.py's own weights rather than
    # agreed with.  A misremembered number would almost certainly not come to
    # the digit printed beside it.
    number = field(SPECIMEN_LINE_1, td1.TD1_LINE_1, "document_number")
    printed = field(
        SPECIMEN_LINE_1, td1.TD1_LINE_1, "document_number_check_digit"
    )

    assert number == "D23145890"
    assert printed == "7"
    assert mrz.check_digit(number) == int(printed)


@pytest.mark.parametrize("field_name, expected", sorted(SPECIMEN_EXPECTED.items()))
def test_a_field_slices_the_text_the_specimen_prints(field_name, expected):
    # The same shape as the synthetic-line test above, against a line that
    # means something: a table that is right about "56789ABCD" can still be
    # one character out on a document number.
    assert field(SPECIMEN_LINE_1, td1.TD1_LINE_1, field_name) == expected


def test_parse_td1_line_1_returns_every_field_of_the_line_in_printed_order():
    parsed = td1.parse_td1_line_1(SPECIMEN_LINE_1)

    assert list(parsed) == list(SPECIMEN_EXPECTED)
    assert dict(parsed) == SPECIMEN_EXPECTED


def test_the_parsed_fields_rebuild_the_line_they_were_read_from():
    # The coverage claim read back as text, and now on a document rather than
    # on labelled positions: six fields, in printed order, lose nothing.  A
    # reader that trimmed a field would break this as surely as one that read
    # the wrong span, and 2.4's "as printed, padding included" is the rule
    # this protects.
    parsed = td1.parse_td1_line_1(SPECIMEN_LINE_1)

    assert "".join(parsed.values()) == SPECIMEN_LINE_1
    assert sum(len(value) for value in parsed.values()) == td1.TD1_LINE_LENGTH


def test_the_parsed_fields_cannot_be_edited_by_a_caller():
    # The evidence of what the document printed.  A mapping a caller could
    # change would let a cleaned-up field look exactly like a read one, which
    # is the same argument MrzDocument.sources makes on the TD3 side.
    parsed = td1.parse_td1_line_1(SPECIMEN_LINE_1)

    with pytest.raises(TypeError):
        parsed["document_number"] = "A12345678"  # type: ignore[index]


# --- the document code: a closed set, and a line that is not a card --------


@pytest.mark.parametrize("code", ["I<", "I"])
def test_an_identity_card_code_is_accepted(code):
    assert td1.validate_document_code(code) == code
    assert code in td1.TD1_DOCUMENT_CODES


@pytest.mark.parametrize(
    "code",
    [
        "P<",  # a passport: a TD3, printed as two lines of 44
        "V<",  # a visa
        "AC",  # an ICAO-compliant card of some other kind
        "<<",
        "i<",
        "I<1",
        " I",
        "",
        None,
        7,
    ],
)
def test_a_code_that_is_not_an_identity_card_is_refused(code):
    # Closed on purpose: these are well-formed MRZ codes belonging to other
    # documents, and a reader that waved them through would report a passport
    # as a card.  The message names the code, which describes a document and
    # not a person.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_document_code(code)

    assert "I<" in str(excinfo.value)


def test_the_document_code_is_read_from_the_specimen():
    assert td1.parse_document_code(SPECIMEN_LINE_1) == "I<"
    assert td1.parse_td1_line_1(SPECIMEN_LINE_1)["document_code"] == "I<"


def test_a_line_that_is_not_a_td1_is_refused_rather_than_read():
    # The strongest cheap check there is: the synthetic line from 3.4 is 30
    # characters of nonsense, and its first two characters are "01".  Nothing
    # else has to be wrong for the zone to be refused.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.parse_td1_line_1(PRINTED)

    assert "'01'" in str(excinfo.value)


# --- the issuing state: three uppercase letters, and no code list ----------


@pytest.mark.parametrize("code", ["UTO", "IND", "GBR", "AAA"])
def test_a_well_formed_issuing_state_is_accepted(code):
    # IND is in this list for the reason td3.py gives: ISO 3166-1 alpha-3
    # assigns it to India, so a parser holding a code list without it would
    # refuse every genuine Indian card.  Whether DRISHTI *recognises* a state
    # is the rules engine's question, and answering it here would need a list
    # this project cannot source.
    assert td1.validate_issuing_state(code) == code


@pytest.mark.parametrize(
    "code",
    [
        "uto",  # lower case
        "UtO",
        "UT0",  # a digit read for the letter O
        "UT<",  # filler where a letter belongs
        "UT ",  # a space
        "UTOX",
        "UT",
        "",
        "UTO1",
    ],
)
def test_an_issuing_state_that_is_not_three_uppercase_letters_is_refused(code):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_issuing_state(code)

    assert "3" in str(excinfo.value)


@pytest.mark.parametrize("code", [None, b"UTO", 7, ["UTO"]])
def test_an_issuing_state_that_is_not_a_string_is_refused(code):
    # bytes again: it is a sequence of integers that happens to spell UTO,
    # and a validator that measured before it checked the type would wave it
    # through and then fail to slice it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_issuing_state(code)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_issuing_state_is_read_from_the_specimen():
    assert td1.parse_issuing_state(SPECIMEN_LINE_1) == "UTO"
    assert td1.parse_td1_line_1(SPECIMEN_LINE_1)["issuing_state"] == "UTO"


def test_a_line_2_cannot_be_mistaken_for_a_line_1():
    # A TD1 line 2's positions 3-5 are the third, fourth and fifth characters
    # of a date of birth, so a zone handed over the wrong way round is refused
    # here -- before the document number reader, which is the reader that
    # cannot tell the two lines apart, is ever reached.  The line is
    # SPECIMEN_LINE_2, defined in the 3.6 section below.

    with pytest.raises(mrz.MrzValueError):
        td1.parse_td1_line_1(SPECIMEN_LINE_2)


# --- the document number: printed as printed, padding and all -------------


def test_the_document_number_is_read_from_the_specimen():
    assert td1.parse_document_number(SPECIMEN_LINE_1) == "D23145890"
    assert td1.parse_td1_line_1(SPECIMEN_LINE_1)["document_number"] == "D23145890"


@pytest.mark.parametrize("number", ["A", "A1234567", "A12345678", "D23145890"])
def test_a_document_number_shorter_than_its_field_is_padded_not_refused(number):
    # A real card prints a five-character number in a nine-character field, so
    # the padding has to come back rather than be refused.  And it has to come
    # back: position 15 is the check digit over these nine characters as they
    # stand, so a stripped number is a different document to the arithmetic.
    printed = number.ljust(9, mrz.FILLER)

    assert td1.validate_document_number(printed) == printed
    assert td1.parse_document_number(line_1_with("document_number", printed)) == printed


def test_a_field_of_nothing_but_filler_is_no_document_number_at_all():
    # The rule 2.4 turned on: neither is an empty string, so `if not number`
    # would accept this.  The filler is the only character the standard uses to
    # say "no value here", which is why it is the one removed before the
    # emptiness is judged.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_document_number(mrz.FILLER * 9)

    assert "6-14" in str(excinfo.value)


@pytest.mark.parametrize("number", ["A123456", "A1234567890", ""])
def test_a_document_number_of_the_wrong_width_is_refused(number):
    with pytest.raises(mrz.MrzValueError):
        td1.validate_document_number(number)


@pytest.mark.parametrize("number", [None, 7, b"D23145890", ["D23145890"]])
def test_a_document_number_that_is_not_a_string_is_refused(number):
    # bytes is the case that matters: it has a length, so a validator that
    # measured before it checked the type would wave it through.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_document_number(number)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_number_is_never_tidied_even_when_the_digit_would_not_notice():
    # The trap 2.10 recorded, and the reason this field is returned as
    # printed.  A *trailing* filler is worth nothing to the arithmetic -- the
    # filler's value is 0 and nothing sits after it -- so a reader that
    # stripped it would agree with the digit on this specimen.  Anywhere else
    # it is a different document, because the 7,3,1 weight cycle means a
    # leading filler moves every character onto a different weight: the two
    # fields below hold the same number and come to different digits.
    right_padded = "D23145" + mrz.FILLER * 3
    left_padded = mrz.FILLER * 2 + "D23145" + mrz.FILLER

    assert len(right_padded) == len(left_padded) == 9
    assert mrz.check_digit(right_padded) == mrz.check_digit("D23145")
    assert mrz.check_digit(left_padded) != mrz.check_digit("D23145")
    # Both are accepted, because both print something, and both come back
    # exactly as printed -- it is the digit that would expose the difference,
    # not the reader.
    assert td1.validate_document_number(right_padded) == right_padded
    assert td1.validate_document_number(left_padded) == left_padded


def test_the_document_number_message_never_carries_the_number():
    # A document number identifies one holder's document, so unlike the
    # document code and the issuing state -- which name a *document* and a
    # *state* -- it stays out of the message and out of the logs it reaches.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_document_number("D2314589")

    assert "D2314589" not in str(excinfo.value)
    assert "6-14" in str(excinfo.value)


# --- optional data 1: judged for its width and for nothing else ------------


def test_an_unused_optional_data_field_comes_back_as_fourteen_fillers():
    # The specimen prints none, and "none" is a *value* here rather than an
    # absence -- the same shape as the filler in the sex marker.  Returning
    # an empty string instead would hand the caller a blank it has to guess
    # the meaning of.
    parsed = td1.parse_td1_line_1(SPECIMEN_LINE_1)

    assert parsed["optional_data_1"] == mrz.FILLER * 14
    assert parsed["optional_data_1_check_digit"] == mrz.FILLER


@pytest.mark.parametrize(
    "printed",
    ["ID2345678<<<<<", "AB< 1234567890", "<<<<<<<<<<<<<<", "ZZZZZZZZZZZZZZ"],
)
def test_optional_data_1_is_carried_as_printed_and_judged_by_nothing(printed):
    # Four cases the standard's own rules do not touch: a used field, one
    # carrying a character the MRZ alphabet cannot print (a misread -- which
    # is 3.7's arithmetic to raise on, not a reader's to refuse), an unused
    # one, and one that is nothing but letters.  None of them is a number or a
    # date, so no rule about one applies; the width is the whole judgement.
    assert td1.validate_optional_data_1(printed) == printed
    assert (
        td1.parse_optional_data_1(line_1_with("optional_data_1", printed)) == printed
    )


@pytest.mark.parametrize("data", ["", "ID2345678<<<<", "ID2345678<<<<<<", None, 7])
def test_optional_data_1_of_the_wrong_width_or_type_is_refused(data):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_optional_data_1(data)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_optional_data_message_never_carries_the_characters():
    # Optional data is whatever the issuing authority wrote about the holder,
    # so the width it wanted is the whole of the diagnosis.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_optional_data_1("ID2345678<")

    assert "ID2345678" not in str(excinfo.value)
    assert "16-29" in str(excinfo.value)


# --- the two printed digits: carried, never judged ------------------------


def test_a_document_whose_printed_digit_disagrees_still_parses():
    # 2.14's rule, seen from the parse: reading a document is not verifying
    # one.  A mutated digit is a *finding* for 3.7 to report, and a parse that
    # refused the line would have thrown the finding away.
    mutated = line_1_with("document_number_check_digit", "1")
    parsed = td1.parse_td1_line_1(mutated)

    assert parsed["document_number_check_digit"] == "1"
    assert parsed["document_number"] == "D23145890"
    assert mrz.check_digit(parsed["document_number"]) != 1


def test_a_document_number_digit_printed_as_filler_is_carried_as_filler():
    # The standard makes that digit optional, so a card may print "<" where a
    # digit would be.  That is a character the layout reads and nothing
    # refuses; whether it means "no digit was printed" or "a digit was
    # misread" is 3.7's question, and it needs the filler to reach it.
    parsed = td1.parse_td1_line_1(
        line_1_with("document_number_check_digit", mrz.FILLER)
    )

    assert parsed["document_number_check_digit"] == mrz.FILLER


# --- the shape of the line the assembler was given ------------------------


@pytest.mark.parametrize(
    "line",
    [
        SPECIMEN_LINE_1[:-1],  # 29 characters: a line that stopped early
        SPECIMEN_LINE_1 + "<",  # 31 characters
        "",
    ],
)
def test_a_line_that_is_not_thirty_characters_is_refused(line):
    # Without this the last field slices to nothing, and the parse reports a
    # document number and an optional data field while having silently lost
    # the position the line stopped at.  The zone gate that will cover all
    # three lines takes this over; until then the assembler holds it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.parse_td1_line_1(line)

    assert type(excinfo.value) is mrz.MrzValueError


@pytest.mark.parametrize("line", [None, 7, b"I<UTOD231458907<<<<<<<<<<<<<<<", []])
def test_a_line_that_is_not_a_string_is_refused(line):
    # One error type for the whole package: a caller writes one except
    # MrzValueError, so a bare TypeError out of a slice would escape it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.parse_td1_line_1(line)

    assert type(excinfo.value) is mrz.MrzValueError


# --- the reads go through the table, not through a hand-written index ------


def test_the_document_number_is_read_through_the_layout(monkeypatch):
    # The one reader a hand-written `line[5:14]` would get wrong without
    # anything noticing, because the specimen's number is nine characters and
    # so is the field.  Moving the field in the table and putting a different
    # number at its new position is what tells the two apart; monkeypatch
    # restores the table.
    line = "I<UT" + "A12345678" + "<" + mrz.FILLER * 16
    reader_free_slice = line[4:13]

    assert td1.parse_document_number(SPECIMEN_LINE_1) == "D23145890"
    assert reader_free_slice == "A12345678"

    monkeypatch.setitem(td1.TD1_LINE_1, "document_number", (5, 13))

    assert td1.parse_document_number(line) == reader_free_slice
    assert td1.parse_td1_line_1(line)["document_number"] == reader_free_slice


def test_the_optional_data_field_is_read_through_the_layout(monkeypatch):
    # Same argument for the other end of the line, and for the assembler: a
    # map built from anything other than the table would not move with it.
    line = "I<UTOD231458907" + "OPT<1234567890" + mrz.FILLER
    moved_slice = line[15:26]

    assert len(moved_slice) == 11
    assert td1.parse_optional_data_1(SPECIMEN_LINE_1) == mrz.FILLER * 14

    monkeypatch.setitem(td1.TD1_LINE_1, "optional_data_1", (16, 26))

    # The width moved with the span, so the validator -- which reads the width
    # out of the table rather than typing in a 14 -- accepted an 11-character
    # field rather than refusing it as the wrong width.
    assert td1.parse_optional_data_1(line) == moved_slice
    assert td1.parse_td1_line_1(line)["optional_data_1"] == moved_slice


def test_td1_field_is_the_one_place_a_line_is_sliced():
    # Positions are 1-indexed and inclusive, so (1, 2) is `line[0:2]` and the
    # conversion is the whole of what this function adds.  Checked from the
    # layout rather than from a literal, so it holds for every field of every
    # line rather than for the three this test thought to name.
    lines = {"line_1": SPECIMEN_LINE_1, "line_2": PRINTED, "line_3": PRINTED}

    for line_name, layout in td1.TD1.items():
        line = lines[line_name]
        for name, (start, end) in layout.items():
            assert td1.td1_field(line, layout, name) == line[start - 1 : end]


@pytest.mark.parametrize("line", [None, 7, b"I<UTO"])
def test_td1_field_reports_a_line_that_is_not_a_string(line):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.td1_field(line, td1.TD1_LINE_1, "document_code")

    assert type(excinfo.value) is mrz.MrzValueError


def test_td1_field_reports_a_field_the_layout_does_not_have():
    # A caller mistake rather than a bad document, reported as this rather
    # than escaping as the KeyError a bare lookup would raise.
    with pytest.raises(mrz.MrzValueError):
        td1.td1_field(SPECIMEN_LINE_1, td1.TD1_LINE_1, "nationality")


def test_this_module_reads_no_line_but_through_td1_field(monkeypatch):
    # The rule is 3.5's to be able to break: every read of a line goes through
    # the one function that slices it, so a future reader that reaches for an
    # index of its own fails here.  The count is the claim: six reads of the
    # six fields of line 1, through the two readers that carry a printed digit
    # and the four that judge a field.
    calls = []
    real = td1.td1_field

    def counting_field(line, layout, name):
        calls.append(name)
        return real(line, layout, name)

    monkeypatch.setattr(td1, "td1_field", counting_field)
    td1.parse_td1_line_1(SPECIMEN_LINE_1)

    assert sorted(calls) == [
        "document_code",
        "document_number",
        "document_number_check_digit",
        "issuing_state",
        "optional_data_1",
        "optional_data_1_check_digit",
    ]


# --- 3.6: line 2, read on the same specimen -------------------------------

# The same ICAO 9303 Part 4 sample ID card's second line, 30 characters, and
# every part of it written out longhand below: the date of birth "740812" with
# its digit "2", the sex marker "F", the expiry "120415" with its digit "9",
# the nationality "UTO" -- the same fictitious issuing state line 1 carries,
# and here the *holder's* -- eleven unused fillers of optional data 2, and the
# composite digit at position 30, which is DERIVED rather than quoted: see the
# module docstring.  3.6 put "6" here from memory; 3.7 computed the standard's
# 51 characters and got "7", so "7" is what this line now carries.
SPECIMEN_LINE_2 = "7408122F1204159UTO<<<<<<<<<<<7"

SPECIMEN_EXPECTED_LINE_2 = {
    "date_of_birth": "740812",
    "date_of_birth_check_digit": "2",
    "sex": "F",
    "date_of_expiry": "120415",
    "date_of_expiry_check_digit": "9",
    "nationality": "UTO",
    "optional_data_2": "<" * 11,
    "composite_check_digit": "7",
}


def line_2_with(field_name, printed):
    """The specimen with ``field_name`` replaced by ``printed``, for a fault."""
    start, end = td1.TD1_LINE_2[field_name]
    return SPECIMEN_LINE_2[: start - 1] + printed + SPECIMEN_LINE_2[end:]


def test_the_specimens_line_2_is_a_line_of_thirty_characters():
    # The same claim as line 1's, and for the same reason: the line every slice
    # below is read out of is a real string, so a miscounted run of fillers
    # shows up here rather than as a short field further along.
    assert len(SPECIMEN_LINE_2) == td1.TD1_LINE_LENGTH


@pytest.mark.parametrize("field_name", ["date_of_birth", "date_of_expiry"])
def test_the_specimens_printed_digits_are_the_ones_the_arithmetic_computes(
    field_name,
):
    # The claim that lets line 2 be quoted at all, and it is two claims: both
    # dates are six characters this project chose nothing about, and both
    # printed digits would be 1.6's "value this repository would not state for
    # want of a source" without it.  A misremembered date would almost
    # certainly not come to the digit printed beside it.
    date = field(SPECIMEN_LINE_2, td1.TD1_LINE_2, field_name)
    printed = field(SPECIMEN_LINE_2, td1.TD1_LINE_2, f"{field_name}_check_digit")

    assert printed in "0123456789"
    assert mrz.check_digit(date) == int(printed)


def test_the_composite_is_carried_as_printed_and_still_never_judged_by_the_parse():
    # 3.6 wrote this test with "nothing" in the name and "6" in the assertion.
    # 3.7 is the task that answers, so the name loses "nothing" and the digit
    # is the derived one -- but the second half is unchanged and is the half
    # that was ever the point: the parse carries the character and judging it
    # is somebody else's job.  A reader that recomputed a printed digit to
    # make its own parse tidier would break 2.14's rule, and this is where
    # that stays visible.
    parsed = td1.parse_td1_line_2(SPECIMEN_LINE_2)
    mutated = td1.parse_td1_line_2(line_2_with("composite_check_digit", "0"))

    assert parsed["composite_check_digit"] == "7"
    assert mutated["composite_check_digit"] == "0"
    assert {k: v for k, v in mutated.items() if k != "composite_check_digit"} == {
        k: v for k, v in parsed.items() if k != "composite_check_digit"
    }


@pytest.mark.parametrize(
    "field_name, expected", sorted(SPECIMEN_EXPECTED_LINE_2.items())
)
def test_a_line_2_field_slices_the_text_the_specimen_prints(field_name, expected):
    # The same shape as the synthetic-line test and as line 1's, against the
    # line that means something: a table that is right about "56789ABCD" can
    # still be one character out on a date of birth.
    assert field(SPECIMEN_LINE_2, td1.TD1_LINE_2, field_name) == expected


def test_parse_td1_line_2_returns_every_field_of_the_line_in_printed_order():
    parsed = td1.parse_td1_line_2(SPECIMEN_LINE_2)

    assert list(parsed) == list(SPECIMEN_EXPECTED_LINE_2)
    assert dict(parsed) == SPECIMEN_EXPECTED_LINE_2


def test_the_parsed_line_2_fields_rebuild_the_line_they_were_read_from():
    # The coverage claim read back as text, on the line where a field that
    # returned "" instead of eleven fillers would still add up to 30 by being
    # replaced rather than shortened -- so the second assertion is the real
    # one, and it is 2.4's "as printed, padding included" this protects.
    parsed = td1.parse_td1_line_2(SPECIMEN_LINE_2)

    assert "".join(parsed.values()) == SPECIMEN_LINE_2
    assert sum(len(value) for value in parsed.values()) == td1.TD1_LINE_LENGTH


def test_the_parsed_line_2_fields_cannot_be_edited_by_a_caller():
    # The same argument line 1's map makes, for the same reason: this is the
    # evidence of what the document printed.
    parsed = td1.parse_td1_line_2(SPECIMEN_LINE_2)

    with pytest.raises(TypeError):
        parsed["date_of_birth"] = "010101"  # type: ignore[index]


# --- the sex marker: a closed set, and the one field no digit covers ------


def test_the_sex_markers_are_exactly_four_characters():
    # Written out longhand rather than read back from the module: this is the
    # one field on line 2 whose rule is a *list* rather than a shape, so a set
    # that quietly lost "X" -- or gained "N" -- would refuse or accept a card
    # without a single other test moving.  See td1.py's docstring for where the
    # set comes from: this repository holds no copy of the standard, so the set
    # is pinned here as a decision rather than checked against a source.
    assert td1.TD1_SEX_MARKERS == {"M", "F", "X", mrz.FILLER}
    assert not hasattr(td1.TD1_SEX_MARKERS, "add")


@pytest.mark.parametrize("marker", ["M", "F", "X", mrz.FILLER])
def test_a_sex_marker_a_card_may_print_is_accepted(marker):
    # "F" is what the specimen prints, so the set is not a list of markers no
    # card has ever used; "M" is the same shape on the other side, and "X" and
    # the filler are the two ways of saying something other than a sex.
    assert td1.validate_sex(marker) == marker
    assert marker in td1.TD1_SEX_MARKERS


@pytest.mark.parametrize(
    "marker",
    [
        "N",  # a letter no card may print: the closed set is the whole point
        "Q",
        "3",  # a digit misread for a letter, which is this line's own risk
        "8",
        "f",  # a lower-case read
        "m",
        " ",  # a space where a character belongs
        "-",
        "MM",  # one character at position 8, however it is spelled
        "F ",
        "",
        None,
        7,
        ["F"],
    ],
)
def test_a_sex_marker_that_is_not_one_of_the_four_is_refused(marker):
    # A rule such as "one uppercase letter, or the filler" would accept "N",
    # "Q", "3" is not a letter at all, and nothing underneath this field would
    # object to any of them: the composite skips position 8 and neither date's
    # own digit reaches it.  So this membership test is the only judgement any
    # arithmetic in this project makes about the character.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_sex(marker)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_sex_marker_is_read_from_the_specimen():
    assert td1.parse_sex(SPECIMEN_LINE_2) == "F"
    assert td1.parse_td1_line_2(SPECIMEN_LINE_2)["sex"] == "F"


def test_the_sex_marker_message_names_the_set_and_never_the_marker():
    # The four are the standard's rather than the holder's, so they are safe to
    # print; the one that was found is a property of the person.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_sex("N")

    message = str(excinfo.value)
    assert "'M'" in message and "'F'" in message and "'X'" in message
    assert "8-8" in message
    assert "not 'N'" not in message


# --- the two dates: as printed, judged for their width and their range -----


@pytest.mark.parametrize("date", ["740812", "120415", "AAAAAA", "<<<<<<"])
def test_a_date_that_is_not_impossible_comes_back_exactly_as_printed(date):
    # 3.11 answered its own question, so this list is what is left of the old
    # "judged for its width and for nothing else": the specimen's two dates,
    # and the three fields of characters nobody could read.  **Those three are
    # still here, and they are the half of the rule that costs a document
    # rather than catching one** -- a filler or a letter inside a date is a
    # misread for the check digit over positions 1-6 to report, and refusing
    # it here would throw that finding away.
    assert td1.validate_date_of_birth(date) == date
    assert td1.validate_date_of_expiry(date) == date


@pytest.mark.parametrize(
    "date, fault",
    [
        pytest.param("993199", "month", id="month-31"),
        pytest.param("013200", "month", id="month-32"),
        pytest.param("740000", "month", id="month-00"),
        pytest.param("740132", "day", id="day-32-in-january"),
        pytest.param("740230", "day", id="day-30-in-february"),
    ],
)
@pytest.mark.parametrize(
    "validate, field_name",
    [
        ("validate_date_of_birth", "date_of_birth"),
        ("validate_date_of_expiry", "date_of_expiry"),
    ],
)
def test_a_date_whose_month_or_day_could_not_be_a_day_is_refused(
    date, fault, validate, field_name
):
    # 3.11's rule, reached through this format's reader rather than restated
    # in it: "993199" and "013200" are the two values the task names, and the
    # three beside them are the same rule one step in.  The component name is
    # the whole of what comes back, because a month is two digits of a
    # holder's date and a message is the most likely thing here to reach a log.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        getattr(td1, validate)(date)

    message = str(excinfo.value)
    start, end = td1.TD1_LINE_2[field_name]
    assert type(excinfo.value) is mrz.MrzValueError
    assert fault in message
    assert f"{start}-{end}" in message
    assert date not in message


@pytest.mark.parametrize("date", ["993199", "013200"])
@pytest.mark.parametrize(
    "parse, field_name",
    [
        ("parse_date_of_birth", "date_of_birth"),
        ("parse_date_of_expiry", "date_of_expiry"),
    ],
)
def test_a_line_2_carrying_an_impossible_date_is_refused_by_its_reader(
    date, parse, field_name
):
    # The refusal reaches the assembler, which is the point of doing it here
    # rather than in a rule engine later: a line that prints month 32 says so
    # at the moment the line is read, and it says which part rather than
    # reporting the whole document as unreadable.
    with pytest.raises(mrz.MrzValueError):
        getattr(td1, parse)(line_2_with(field_name, date))


def test_a_date_is_still_judged_for_its_width_before_its_contents():
    # The width is read out of TD1_LINE_2 and it runs first, so a five-character
    # field is still "stopped early" and a seven-character one is still a
    # misread -- neither is reported as a month.  3.11's rule cannot be the
    # first thing a wrong-width value meets, or a short line would come back
    # talking about a day it never printed.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_date_of_birth("99319")

    assert "1-6" in str(excinfo.value)
    assert "month" not in str(excinfo.value)


@pytest.mark.parametrize("date", ["74081", "7408123", "", None, 7, b"740812"])
def test_a_date_of_the_wrong_width_or_type_is_refused(date):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_date_of_birth(date)

    assert type(excinfo.value) is mrz.MrzValueError


@pytest.mark.parametrize("printed", ["740 12", "74o812", "7<0812", "74/812", "740812"])
def test_a_date_is_never_tidied(printed):
    # As printed, filler included and errors included: position 7 is the check
    # digit over positions 1-6 as they stand, so an edited date is a different
    # document to the arithmetic.  mrz.check_digit is what raises on the
    # characters outside the MRZ alphabet, and 3.7 is what reports it -- a
    # reader that refused here would throw the finding away.
    assert td1.validate_date_of_birth(printed) == printed
    assert td1.parse_date_of_birth(line_2_with("date_of_birth", printed)) == printed


def test_the_date_message_never_carries_the_date():
    # A date of birth is the holder's, not the document's, so the message names
    # the positions and the width and stops -- the rule the nationality message
    # states and the document-number message already follows.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_date_of_expiry("1204159")

    assert "120415" not in str(excinfo.value)
    assert "9-14" in str(excinfo.value)


@pytest.mark.parametrize(
    "field_name, wrong",
    [("date_of_birth_check_digit", "1"), ("date_of_expiry_check_digit", "4")],
)
def test_a_printed_digit_that_disagrees_still_parses(field_name, wrong):
    # 2.14's rule, seen from the parse: reading a document is not verifying
    # one.  A mutated digit is a *finding* for 3.7 to report, and a parse that
    # refused the line would have thrown the finding away.  The date is left
    # exactly where the specimen printed it, so what is compared is the
    # document against itself.
    date = field_name.removesuffix("_check_digit")
    parsed = td1.parse_td1_line_2(line_2_with(field_name, wrong))

    assert parsed[field_name] == wrong
    assert parsed[date] == SPECIMEN_EXPECTED_LINE_2[date]
    assert mrz.check_digit(parsed[date]) != int(wrong)


# --- the nationality: the holder's, so the message says less --------------


@pytest.mark.parametrize("code", ["UTO", "IND", "AAA", "GBR"])
def test_a_nationality_of_three_uppercase_letters_is_accepted(code):
    # "IND" is the case 2.4 turned on: it is three uppercase letters, ISO
    # 3166-1 alpha-3 assigns it to India, and a list without it refuses every
    # genuine Indian ID card.  No list of codes ships here.
    assert td1.validate_nationality(code) == code


@pytest.mark.parametrize(
    "code",
    [
        "<<<",  # the filler: no such thing as an unknown nationality
        "uTO",
        "UT0",  # a digit read for a letter
        "UT",  # a code too short is a misread, not a padded code
        "UTOX",
        "UT O",
        "",
        None,
        7,
        b"UTO",
    ],
)
def test_a_nationality_that_is_not_three_uppercase_letters_is_refused(code):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_nationality(code)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_nationality_message_never_carries_the_code():
    # Where the issuing state's message does carry a state: a state describes
    # the document, a nationality describes the holder, and the width, the
    # positions and the alphabet are the whole of the diagnosis.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_nationality("UT0")

    assert "UT0" not in str(excinfo.value)
    assert "16-18" in str(excinfo.value)


def test_the_nationality_is_read_from_the_specimen():
    assert td1.parse_nationality(SPECIMEN_LINE_2) == "UTO"
    assert td1.parse_td1_line_2(SPECIMEN_LINE_2)["nationality"] == "UTO"


# --- optional data 2: eleven fillers, and nothing inferred from them ------


def test_an_unused_optional_data_2_comes_back_as_eleven_fillers():
    # "Filler only means unused" is not a rule the standard states, so the
    # specimen's field is eleven fillers rather than the empty string a caller
    # would have to interpret -- 2.4's rule applied to the second of the two
    # fields.
    parsed = td1.parse_td1_line_2(SPECIMEN_LINE_2)

    assert parsed["optional_data_2"] == mrz.FILLER * 11
    assert len(parsed["optional_data_2"]) == 11


@pytest.mark.parametrize(
    "data", ["<" * 10, "<" * 12, "ID1234567890", "", None, 7, b"<<<<<<<<<<<"]
)
def test_optional_data_2_of_the_wrong_width_or_type_is_refused(data):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_optional_data_2(data)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_optional_data_2_message_never_carries_the_characters():
    # Whatever the issuing authority wrote about the holder, the message names
    # the positions and the width.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.validate_optional_data_2("ID1234567890")

    assert "ID1234567890" not in str(excinfo.value)
    assert "19-29" in str(excinfo.value)


@pytest.mark.parametrize(
    "printed", ["<<<<<<<<<<<", "ID12345678<", "national u<", "OPTIONAL 12"]
)
def test_optional_data_2_is_carried_as_printed_and_judged_by_nothing(printed):
    # The composite at position 30 is computed over positions 19-29 as they
    # stand, so nothing here is tidied -- including the space and the
    # lower-case letter, which the MRZ alphabet cannot print: mrz.check_digit
    # is what raises on those in 3.7, and a reader that refused them here would
    # lose the printed characters a flag needs to point at.
    assert td1.validate_optional_data_2(printed) == printed
    assert td1.parse_optional_data_2(line_2_with("optional_data_2", printed)) == printed


# --- the wrong line, and the shape of the line the assembler was given -----


def test_a_line_1_cannot_be_mistaken_for_a_line_2():
    # The other direction of the test 3.5 wrote, and it is caught by a
    # different field: line 1's positions 1-6 are "I<UTOD", six characters of
    # the right width that the date-of-birth validator accepts -- what a date
    # may print is 3.11's question -- and position 8 is a digit of the
    # document number.  So the sex marker is the reader that refuses, and it
    # does so before the expiry and the nationality are reached.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.parse_td1_line_2(SPECIMEN_LINE_1)

    assert "sex marker" in str(excinfo.value)


@pytest.mark.parametrize(
    "field_name, printed",
    [
        # Each of these is a wrong-line read this parser would accept, which
        # is why the caller has to pass the right line rather than lean on the
        # widths: line 1's positions 1-6 and 9-14 are six characters each.
        ("date_of_birth", "I<UTOD"),
        ("date_of_expiry", "145890"),
    ],
)
def test_a_line_1_read_as_a_line_2_gives_six_characters_the_width_accepts(
    field_name, printed
):
    # Stated as a fact about the two fields rather than as a pass: this is the
    # cost of 3.11's range validation living in a later task, and it is why
    # test_a_line_1_cannot_be_mistaken_for_a_line_2 leans on position 8 and
    # not on the dates.
    assert td1.TD1_LINE_2[field_name][0] <= 14
    assert field(SPECIMEN_LINE_1, td1.TD1_LINE_2, field_name) == printed


@pytest.mark.parametrize(
    "line",
    [
        SPECIMEN_LINE_2[:-1],  # 29 characters: a line that stopped early
        SPECIMEN_LINE_2 + "<",  # 31 characters
        "",
    ],
)
def test_a_line_2_that_is_not_thirty_characters_is_refused(line):
    # The width check is shared with line 1 rather than written twice, so the
    # gate that will cover all three lines takes it over once.  Without it, the
    # composite at position 30 would slice to nothing and the map would report
    # what the document printed having lost a position.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.parse_td1_line_2(line)

    assert type(excinfo.value) is mrz.MrzValueError
    assert "line 2" in str(excinfo.value)


@pytest.mark.parametrize("line", [None, 7, b"7408122F1204159UTO<<<<<<<<<<<6", []])
def test_a_line_2_that_is_not_a_string_is_refused(line):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td1.parse_td1_line_2(line)

    assert type(excinfo.value) is mrz.MrzValueError


def test_line_2_fields_are_read_through_the_layout(monkeypatch):
    # The same argument 3.5 makes for line 1, and it fails differently for the
    # two lines: every field here is either a width the layout states or a
    # fixed set, so moving a span moves both the slice and the width, and a
    # hand-written `line[0:6]` would follow neither.  This line's own printed
    # digits are the ones its dates compute to, so the only thing wrong with it
    # is the span the test moves.
    line = "9901018X9901018UTO" + mrz.FILLER * 11 + "0"
    reader_free_slice = line[3:9]

    assert td1.parse_date_of_birth(SPECIMEN_LINE_2) == "740812"
    assert reader_free_slice == "1018X9"

    monkeypatch.setitem(td1.TD1_LINE_2, "date_of_birth", (4, 9))

    # "1018X9" is the width the table now states, so the validator accepts it
    # rather than refusing it as the wrong width -- which is the point: the
    # width is read out of the layout rather than typed in as a 6.
    assert td1.parse_date_of_birth(line) == reader_free_slice
    assert td1.parse_td1_line_2(line)["date_of_birth"] == reader_free_slice


def test_this_module_reads_no_line_2_but_through_td1_field(monkeypatch):
    # The rule is 3.5's to be able to break, now that a second line is read.
    # The count is the claim: eight reads of the eight fields of line 2,
    # through the three readers that carry a printed digit and the five that
    # judge a field.
    calls = []
    real = td1.td1_field

    def counting_field(line, layout, name):
        calls.append(name)
        return real(line, layout, name)

    monkeypatch.setattr(td1, "td1_field", counting_field)
    td1.parse_td1_line_2(SPECIMEN_LINE_2)

    assert sorted(calls) == [
        "composite_check_digit",
        "date_of_birth",
        "date_of_birth_check_digit",
        "date_of_expiry",
        "date_of_expiry_check_digit",
        "nationality",
        "optional_data_2",
        "sex",
    ]


# --- 3.7: the composite, over both lines ----------------------------------

# The spans, written out longhand from the standard rather than read back from
# td1.TD1_COMPOSITE_SPANS -- a test that compared the table with itself proves
# nothing.  Line 1 supplies the document code, the issuing state and the first
# five characters of the document number, then the document number's own digit
# and the whole of optional data 1 with its digit.  Line 2 supplies the date of
# birth with its digit, the date of expiry with its digit, and optional data
# 2.  The sex marker (8), the nationality (16-18) and the composite's own
# position (30) are outside it on line 2; positions 11-14 are outside it on
# line 1.
EXPECTED_COMPOSITE_SPANS = [
    ("line_1", 1, 10),
    ("line_1", 15, 30),
    ("line_2", 1, 7),
    ("line_2", 9, 15),
    ("line_2", 19, 29),
]

# The same 51 characters again, written as the string the standard's spans
# select out of the specimen -- so the span table and the concatenated text are
# two independent statements and a table moved by one position cannot make both
# come out right.  The chunks are sliced by the *expected* positions below, not
# by the module's, for the same reason.
EXPECTED_COMPOSITE_INPUT = (
    # line 1 1-10: the document code, the issuing state and "D2314"
    "I<UTOD2314"
    # line 1 15-30: the document number's own digit, then optional data 1 and
    # the place its own digit would go -- filler, the field being unused
    + "7"
    + mrz.FILLER * 15
    # line 2 1-7: the date of birth and its digit
    + "7408122"
    # line 2 9-15: the date of expiry and its digit
    + "1204159"
    # line 2 19-29: unused optional data 2
    + mrz.FILLER * 11
)

PRINTED_COMPOSITE_DIGIT = "7"


def specimen_results(line_1=SPECIMEN_LINE_1, line_2=SPECIMEN_LINE_2):
    """The five verdicts for a pair of lines, parsed the way 3.14 will parse."""
    sources = {**td1.parse_td1_line_1(line_1), **td1.parse_td1_line_2(line_2)}
    return td1.td1_check_digit_results(line_1, line_2, sources)


def test_the_composite_spans_are_the_ones_the_standard_states():
    # 3.5 could not write this test: it is the test that settles the span, and
    # it is written from the standard's own sentence rather than from either
    # source this project held.  The order matters as much as the spans, since
    # the weights restart at the first character of the second span.
    assert list(td1.TD1_COMPOSITE_SPANS) == EXPECTED_COMPOSITE_SPANS
    assert isinstance(td1.TD1_COMPOSITE_SPANS, tuple)


def test_the_composite_is_fifty_one_characters_twenty_six_and_twenty_five():
    # Not "the spans add up": a span that ran past the end of its line would
    # slice short and the total would be the only thing to notice.  51 is the
    # standard's number and it is the number a caller would have to remember in
    # order to sanity-check what comes back.
    composite = td1.td1_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2)
    by_line = {"line_1": 0, "line_2": 0}

    for line_name, start, end in td1.TD1_COMPOSITE_SPANS:
        by_line[line_name] += end - start + 1

    assert by_line == {"line_1": 26, "line_2": 25}
    assert len(composite) == 51


def test_every_composite_span_lies_inside_a_real_line():
    # The claim that a span naming a line, or a position past 30, would fail
    # on a value rather than as a silent short slice.
    for line_name, start, end in td1.TD1_COMPOSITE_SPANS:
        assert line_name in {"line_1", "line_2"}, line_name
        assert 1 <= start <= end <= td1.TD1_LINE_LENGTH, (line_name, start, end)


@pytest.mark.parametrize("line_name", ["line_1", "line_2"])
def test_the_spans_are_runs_of_whole_fields_bar_one_documented_cut(line_name):
    # **This is the test the span table needs and cannot give itself, and it is
    # the answer to "how do you know a span is not one position out".**  Every
    # field the layout declares is either wholly inside a span, wholly outside
    # it, or -- exactly once, on line 1 -- cut through by it.  A span moved by
    # one position either starts or ends mid-field and fails here, rather than
    # producing a composite that disagrees with a remembered digit.
    spans = [span for span in td1.TD1_COMPOSITE_SPANS if span[0] == line_name]
    layout = td1.TD1[line_name]
    cut = []

    for field_name, (start, end) in fields_in_printed_order(layout):
        overlapping = [(s, e) for _, s, e in spans if s <= end and start <= e]
        wholly_inside = [span for span in overlapping if span[0] <= start and end <= span[1]]

        if not overlapping or len(wholly_inside) == len(overlapping):
            continue  # outside the composite, or inside it whole
        cut.append((field_name, start, end, overlapping))

    # Line 1's document number is 6-14 and the span ends at 10, so this cut is
    # the standard's own -- it takes the first five characters of a nine-
    # character field.  Nothing else on either line may be cut, which is what
    # makes "positions on a named line" a narrow departure from td3.py's
    # field-name spans rather than a second, looser convention.
    if line_name == "line_1":
        assert [(name, start, end) for name, start, end, _ in cut] == [
            ("document_number", 6, 14)
        ]
        assert cut[0][3] == [(1, 10)]
    else:
        assert cut == []


def test_the_composite_input_is_the_fifty_one_characters_the_spans_name():
    # The concatenation, against a string written out longhand from the
    # standard's positions.  The expectations below are sliced with the
    # *expected* positions, so this fails on the value if the module's spans
    # move.
    expected = "".join(
        {"line_1": SPECIMEN_LINE_1, "line_2": SPECIMEN_LINE_2}[line_name][start - 1 : end]
        for line_name, start, end in EXPECTED_COMPOSITE_SPANS
    )

    assert expected == EXPECTED_COMPOSITE_INPUT
    assert len(EXPECTED_COMPOSITE_INPUT) == 51
    assert td1.td1_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2) == expected


def test_the_composite_reads_two_lines_because_no_field_can_carry_it():
    # Why two parameters and not one: the whole of the composite is on no
    # single line, and the layout says so too.  A TD1's first two lines hold 60
    # characters between them; the composite covers 51 of them, which is more
    # than either line has.
    from_line_1 = "".join(
        SPECIMEN_LINE_1[start - 1 : end]
        for line_name, start, end in td1.TD1_COMPOSITE_SPANS
        if line_name == "line_1"
    )

    assert len(from_line_1) == 26 < td1.TD1_LINE_LENGTH
    assert len(td1.td1_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2)) == 51
    assert td1.TD1_LINE_LENGTH * 2 == 60


def test_the_specimens_composite_agrees_with_its_own_fifty_one_characters():
    # **The task's "a test on a correct specimen", and the fourth of the five
    # printed digits whose values this fixture quotes and confirms.**  The
    # other three are in the sections above; this one is *derived*, and the
    # difference matters: 3.6 wrote a "6" here from memory, 3.7 computed the
    # standard's 51 characters and got a "7", so the fixture now carries the
    # arithmetic's answer.  **That makes the agreement below a claim about
    # this project and not about any ID card**, exactly as 1.6 recorded for the
    # TD3 composite, and the difference between the two fixtures is worth
    # stating rather than leaving implied: a misremembered date would have to
    # come to the digit printed beside it three times over, whereas this one
    # is whatever the arithmetic says.
    composite = td1.td1_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2)

    assert mrz.check_digit(composite) == int(PRINTED_COMPOSITE_DIGIT)
    assert specimen_results()[-1].field == "composite"
    assert specimen_results()[-1].passed is True
    assert td1.parse_td1_line_2(SPECIMEN_LINE_2)["composite_check_digit"] == "7"


def test_the_five_verdicts_are_reported_in_printed_order():
    # Line 1's two digits, then line 2's three -- position 15, position 30, 7,
    # 15, 30.  An order a caller reads top to bottom has to be the order the
    # document prints, so the list says the same thing about itself the parse
    # does.
    results = specimen_results()

    assert [result.field for result in results] == [
        "document_number",
        "optional_data_1",
        "date_of_birth",
        "date_of_expiry",
        "composite",
    ]
    assert all(isinstance(result, mrz.CheckDigitResult) for result in results)
    assert [result.passed for result in results] == [True, None, True, True, True]


def test_an_unused_optional_data_field_is_reported_as_unchecked_not_as_failed():
    # **The row that is not ``True`` on a correct specimen, and the reason it
    # is not ``False``.**  Optional data 1 is fourteen fillers, so its check
    # digit position prints filler rather than a digit -- what the field's own
    # section in 3.5 documents.  The arithmetic still comes to a real answer
    # (zero, over fourteen fillers), and the printed half is unreadable, so
    # 3.3's three-way answer is the honest one: `found 0`, `expected None`,
    # `passed None`.  A `False` here would put a forged-digit claim in front
    # of an officer on the strength of a field nobody filled in, which is
    # 2.14's mistake at a different level.
    row = next(r for r in specimen_results() if r.field == "optional_data_1")

    assert row.expected is None
    assert row.found == 0
    assert row.readable is False
    assert row.passed is None


def test_a_mutated_composite_digit_fails_the_composite_and_nothing_else():
    # The task's "one on a mutated composite", over all nine wrong digits
    # rather than the one chosen digit, so no digit of the ten is special.
    # Only line 2 position 30 moves: the 51 characters the composite is
    # computed over are byte-identical and still come to 7 for every one of
    # the nine.  That is what makes the disagreement the *printed* digit and
    # nothing else -- and it is the same shape as 3.3's "a field and the
    # composite fail together", seen from the other end.
    wrong_digits = [d for d in string.digits if d != PRINTED_COMPOSITE_DIGIT]
    assert len(wrong_digits) == 9

    for digit in wrong_digits:
        line_2 = line_2_with("composite_check_digit", digit)
        results = specimen_results(SPECIMEN_LINE_1, line_2)

        assert mrz.check_digit(td1.td1_composite_input(SPECIMEN_LINE_1, line_2)) == 7
        assert [r.passed for r in results] == [True, None, True, True, False], digit
        composite = results[-1]
        assert composite.field == "composite"
        assert (composite.expected, composite.found) == (int(digit), 7)


@pytest.mark.parametrize(
    "line_name, field_name, printed, own_row, unchanged_rows",
    [
        ("line_1", "document_number", "E23145890", False, ["date_of_birth", "date_of_expiry"]),
        ("line_1", "optional_data_1", "<" * 13 + "B", None, ["document_number", "date_of_birth", "date_of_expiry"]),
        ("line_2", "date_of_birth", "740813", False, ["document_number", "date_of_expiry"]),
        ("line_2", "date_of_expiry", "120416", False, ["document_number", "date_of_birth"]),
    ],
)
def test_a_mutated_field_inside_the_span_fails_its_own_row_and_the_composite(
    line_name, field_name, printed, own_row, unchanged_rows
):
    # Four mutations, one per covered field, each with its printed digit left
    # exactly where the specimen printed it -- so the field's own row and the
    # composite both have something to disagree with.  The mutations are
    # chosen so the *field* changes but no parser refuses: a birth date of
    # "740813" is one the width check and 3.11's future range check both
    # accept, which is what lets a verdict be reached at all.  Each also lands
    # on a character the *span* covers, and that is a second constraint rather
    # than a detail -- see the test below the other four, which is the
    # document number's last four characters.
    #
    # **`own_row` is ``None`` for the optional data field, and that is the
    # interesting one.**  Its check digit position prints filler, so there is
    # no printed half to disagree with: the field was edited, the arithmetic
    # over it changed from 0 to 3, and its own row still cannot say "failed".
    # The composite row is the only thing on the card that notices.  A list
    # that had reported this as a failure of the field would be claiming a
    # disagreement that was never available, and one that had raised would have
    # lost the other four verdicts over an unused field.
    if line_name == "line_1":
        line_1 = line_1_with(field_name, printed)
        line_2 = SPECIMEN_LINE_2
    else:
        line_1 = SPECIMEN_LINE_1
        line_2 = line_2_with(field_name, printed)

    results = specimen_results(line_1, line_2)
    rows = {result.field: result for result in results}

    assert rows[field_name].passed is own_row
    assert rows["optional_data_1"].found == (3 if own_row is None else 0)
    assert rows["composite"].passed is False
    # The other rows are untouched, and the one whose printed half is filler
    # stays unreadable rather than becoming a second failure.
    for other in unchanged_rows:
        assert rows[other].passed is True, other


def test_the_document_numbers_last_four_characters_are_outside_the_composite():
    # **The one consequence of this span that is easy to be surprised by, and
    # the reason the span test above is not a formality.**  Line 1 positions
    # 1-10 stop at the *fifth* character of a nine-character document number, so
    # positions 11-14 are outside the composite: editing the tail of the number
    # on a card whose composite still agrees changes the number's own row and
    # nothing else.  The other three covered fields are wholly inside a span,
    # and the layout test above says so -- this is the single boundary the
    # standard's sentence cuts.
    mutated = line_1_with("document_number", "D23145891")

    assert mutated[10:14] == "5891"  # positions 11-14, the part left out
    assert mutated[:10] == SPECIMEN_LINE_1[:10]  # 1-10, the part inside
    assert td1.td1_composite_input(mutated, SPECIMEN_LINE_2) == EXPECTED_COMPOSITE_INPUT
    assert [r.passed for r in specimen_results(mutated, SPECIMEN_LINE_2)] == [
        False,
        None,
        True,
        True,
        True,
    ]


@pytest.mark.parametrize("field_name, printed", [("sex", "M"), ("nationality", "UTO")])
def test_the_two_fields_outside_the_span_cannot_move_the_composite(field_name, printed):
    # The gaps, and they are the reason 3.6 called the sex marker the only
    # character no arithmetic here judges.  The composite skips line 2 position
    # 8 and positions 16-18, so replacing the specimen's "F" with "M" or its
    # nationality with any other three letters changes nothing it is computed
    # over -- and every verdict still stands.  A span that wrongly included
    # either would fail this test, which is a value failing rather than a
    # count.
    line_2 = line_2_with(field_name, printed)
    composite = td1.td1_composite_input(SPECIMEN_LINE_1, line_2)

    assert composite == EXPECTED_COMPOSITE_INPUT
    assert [r.passed for r in specimen_results(SPECIMEN_LINE_1, line_2)] == [
        True,
        None,
        True,
        True,
        True,
    ]


def test_the_composite_contains_the_digits_printed_beside_the_fields():
    # Why the standard's span *includes* line 1's own position 30, which the
    # span this module used to state left out.  Two positions inside the span
    # hold printed check digits, and both are part of what the composite is
    # computed over -- the same treatment a TD3 gives the four digits at its
    # positions 10, 20, 28 and 43.  A span that dropped one would be a
    # different claim about the format, and this is the assertion that would
    # notice.
    composite = td1.td1_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2)
    inside = {
        "line_1": SPECIMEN_LINE_1,
        "line_2": SPECIMEN_LINE_2,
    }

    for line_name, digit_field in [
        ("line_1", "document_number_check_digit"),
        ("line_1", "optional_data_1_check_digit"),
        ("line_2", "date_of_birth_check_digit"),
        ("line_2", "date_of_expiry_check_digit"),
    ]:
        start, end = td1.TD1[line_name][digit_field]
        covered = any(
            span_line == line_name and s <= start and end <= e
            for span_line, s, e in td1.TD1_COMPOSITE_SPANS
        )
        assert covered, f"{line_name}.{digit_field} is outside the composite"
        assert inside[line_name][start - 1 : end] in composite

    # And the composite's own printed digit is not an input to itself, which is
    # why position 30 is the one line 2 position the table leaves out.
    assert ("line_2", 30, 30) not in [
        (n, s, s) for n, s, _ in td1.TD1_COMPOSITE_SPANS
    ]
    # Stated by moving the digit rather than by looking for it in the string:
    # this specimen's composite happens to be "7", and "7" also appears at
    # line 1 position 15 and inside the date of birth, so a membership test
    # would be testing the specimen's characters rather than the span.
    assert td1.td1_composite_input(
        SPECIMEN_LINE_1, line_2_with("composite_check_digit", "0")
    ) == EXPECTED_COMPOSITE_INPUT


@pytest.mark.parametrize(
    "line_1, line_2, message_holds",
    [
        (SPECIMEN_LINE_1[:-1], SPECIMEN_LINE_2, "30"),  # 29 characters
        (SPECIMEN_LINE_1, SPECIMEN_LINE_2 + "<", "30"),  # 31 characters
        (None, SPECIMEN_LINE_2, "string"),
        (SPECIMEN_LINE_1, None, "string"),
    ],
)
def test_the_composite_refuses_a_line_of_the_wrong_width(line_1, line_2, message_holds):
    # The width check `_checked_line` already does for both parsers, reached
    # here for the same reason: a silently short span would come back as a
    # composite that failed rather than as an error, which is the one failure
    # mode a caller could not tell from a forged document.  The message is
    # `_checked_line`'s own, so a caller learns nothing new in it -- including
    # the fact that the two kinds of refusal are worded differently, which is
    # why this asserts what the message holds rather than that it exists.
    with pytest.raises(mrz.MrzValueError) as error:
        td1.td1_composite_input(line_1, line_2)

    assert message_holds in str(error.value)


def test_the_verdicts_name_a_field_this_format_actually_prints():
    # A pairing that named a field the layout does not have would raise
    # `KeyError` at the call rather than reporting a field nobody printed, so
    # the check is that all three elements of every pairing are real names --
    # on either line, since the composite's characters are the exception that
    # carries `None` for exactly that reason.
    layouts = {**td1.TD1_LINE_1, **td1.TD1_LINE_2}

    for label, field, digit_field in td1.TD1_CHECK_DIGIT_FIELDS:
        assert label in layouts or label == "composite"
        assert field is None or field in layouts, field
        assert digit_field in layouts, digit_field

    assert [pair[0] for pair in td1.TD1_CHECK_DIGIT_FIELDS] == [
        result.field for result in specimen_results()
    ]


def test_a_field_the_caller_omitted_raises_key_error_and_not_a_document_error():
    # 3.3's rule, kept for this format: a missing key is a bug in the caller,
    # and dressing it up as a `MrzValueError` would put a fact about a card
    # into a log entry that describes none.  A document that is *wrong* raises
    # nothing here at all -- that is a row with `passed is False`.
    sources = {**td1.parse_td1_line_1(SPECIMEN_LINE_1), **td1.parse_td1_line_2(SPECIMEN_LINE_2)}
    del sources["date_of_birth"]

    with pytest.raises(KeyError):
        td1.td1_check_digit_results(SPECIMEN_LINE_1, SPECIMEN_LINE_2, sources)


# --- the zone gate, which 3.14 brought ------------------------------------


SPECIMEN_LINE_3 = "ERIKSSON<<ANNA<MARIA" + "<" * 10


def specimen_zone():
    return [SPECIMEN_LINE_1, SPECIMEN_LINE_2, SPECIMEN_LINE_3]


def test_the_gate_returns_three_lines_in_printed_order():
    # The gate never tells a caller which line is which by index: it returns
    # them in the order the standard prints them, so a parser can write
    # `line_1, line_2, line_3 = validate_td1_lines(lines)` and be right.
    assert td1.validate_td1_lines(specimen_zone()) == (
        SPECIMEN_LINE_1,
        SPECIMEN_LINE_2,
        SPECIMEN_LINE_3,
    )


@pytest.mark.parametrize(
    "zone",
    [
        "x" * 30,  # one string, not three lines
        None,  # not a sequence at all
        [],  # no lines
        [SPECIMEN_LINE_1, SPECIMEN_LINE_2],  # a name line missing
        [SPECIMEN_LINE_1] * 4,  # a fourth line
        [SPECIMEN_LINE_1, SPECIMEN_LINE_2, SPECIMEN_LINE_3[:-1]],  # line 3 short
        [None, SPECIMEN_LINE_2, SPECIMEN_LINE_3],  # not a string
    ],
)
def test_the_gate_refuses_anything_that_is_not_three_lines_of_thirty(zone):
    # A `MrzValueError` and nothing else, so a caller catching that one type
    # catches the `None` zone and the `None` line as well: 1.9's rule.
    with pytest.raises(mrz.MrzValueError):
        td1.validate_td1_lines(zone)


def test_the_gate_names_the_line_and_the_width_it_wanted_and_never_a_character():
    # Widths are shape; the characters are the identity data the screening is
    # about, so a message that named the line would leak the document and one
    # that named only the count would not be a diagnosis.
    with pytest.raises(mrz.MrzValueError) as caught:
        td1.validate_td1_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2, SPECIMEN_LINE_3[:5]])

    message = str(caught.value)
    assert "line 3" in message
    assert "5" in message
    assert "30" in message
    assert SPECIMEN_LINE_3[:5] not in message


def test_the_gate_agrees_with_the_line_count_the_module_states():
    # The gate is where "three lines of 30" is said in a check rather than in
    # a comment, so a constant changed without it fails here.
    assert len(specimen_zone()) == td1.TD1_LINE_COUNT == 3
    assert all(len(line) == td1.TD1_LINE_LENGTH for line in specimen_zone())


@pytest.mark.parametrize(
    "zone",
    [
        [SPECIMEN_LINE_1, SPECIMEN_LINE_2],  # the name line missing
        [SPECIMEN_LINE_1, SPECIMEN_LINE_2, SPECIMEN_LINE_3[:29]],  # line 3 short
        "x" * 30,
    ],
)
def test_the_parser_runs_the_gate_before_it_reads_anything(zone):
    # 3.7's trade, made sharp by 3.14: the six TD1 assemblers check their own
    # line's width, and a TD1 is the format where skipping the zone gate costs
    # a *silently short* two-line span -- a composite that comes back failed
    # rather than as an error.  So the whole-zone parser runs the gate first,
    # and the type it raises for a wrong shape is the one error type this
    # package raises, never an `IndexError` from indexing three lines out of
    # two.
    with pytest.raises(mrz.MrzValueError):
        td1.parse_td1(zone)
