"""The TD2 layout constants: the positions, and the coverage they claim.

Task 3.8 asks for the two 36-character tables and for a test that every
position of every line is claimed exactly once.  The tables are written out
longhand here from ICAO 9303 rather than read back from the module -- a test
that compares ``td2.TD2_LINE_1`` with itself proves nothing -- so a field that
moved, was renamed or was given the wrong width is caught by name.

**The synthetic line is still how the positions are checked, and 3.9 adds a
printed specimen on top of it rather than replacing it.**  Thirty-six distinct
characters, each one naming the position it stands in, catches a slice that
lands a character early or late on a line that is otherwise meaningless; a
*printed* line catches a table that is right about a meaningless line and
wrong about a document.  They fail differently, so both stay.

**The specimen is the sample visa's line 1, and the 1.6 objection does not
arise on this line, for a reason that is the format's shape rather than
carefulness.**  1.6 declined to state a TD3 composite and 3.4 declined to
quote a TD1, because both meant publishing a printed check digit that nothing
in this repository could confirm.  **A TD2 line 1 prints no check digit at
all**, so the fixture below has no printed digit in it to take on trust: what
cannot be confirmed is the *name*, and no arithmetic in this project computes
anything over a name.  **3.10 is where that stops being true**, because line 2
prints five digits and 3.10 is where the span they are computed over has to
be settled -- which is why this fixture stops at the first line and says so.
What *is* checked about it here is the one thing this project can check: every
character on the line is one the MRZ alphabet prints.

**3.9's own field list named a TD1's line 1, and the list in the table is the
standard's.**  The task said "document code, issuing state, document number,
optional data with its own check digit"; in a TD2 the document number and its
digit are at 1-10 of **line 2**, and line 1 holds the holder's **name** at
6-36 -- the field a visa MRZ most visibly carries and the one the task text
named nowhere between 3.9 and 3.10.  So the readers below parse the
standard's line, ``tasks.md`` has been corrected to match, and a test says
which line each of those fields is on.

**36 is the first line length in this package that the digits and the letters
fill exactly**, ten digits then twenty-six letters with nothing left over, so
the line below is ``string.digits + string.ascii_uppercase`` and position 36
is ``Z``.  A boundary that is one character out therefore fails on a *value*
here, not only on a count -- which is what the second copy of the table in
``EXPECTED`` is for.

**3.10 is the second half of this file: line 2, the five printed digits and
the composite's span.**  3.8 wrote the positions and 3.9 read line 1 against
them, and 3.10 reads line 2 the same way *and* settles the one claim the
layout cannot: which of those positions a digit is computed over.  The task
list's 3.10 states the TD2 span as the TD1's line 2 spans copied verbatim, so
`td2.py` published no span at all until this task settled one -- the same
arrangement 3.5 and 3.7 had, and the reason
`test_the_composite_span_is_published_exactly_once` replaced an assertion of
absence with an assertion of single authorship.

The coverage claim is the one the task names, and it is stated twice on
purpose: once as a single sorted comparison per line, which is the compact
form, and once per boundary, which says which field broke the line when it
fails.
"""

import inspect
import string

import pytest

from app.pipeline.tier0 import mrz, td2, td3

# Written out longhand from the standard rather than read back from the module.
EXPECTED_LINE_1 = {
    "document_code": (1, 2),
    "issuing_state": (3, 5),
    "name": (6, 36),
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
    "optional_data": (29, 34),
    "optional_data_check_digit": (35, 35),
    "composite_check_digit": (36, 36),
}

EXPECTED = {
    "line_1": EXPECTED_LINE_1,
    "line_2": EXPECTED_LINE_2,
}

LAYOUTS = [(line_name, td2.TD2[line_name]) for line_name in sorted(EXPECTED)]

# One character per position, so a slice reports where it started and stopped.
# 10 digits then 26 letters is exactly 36, with nothing to spare.
PRINTED = string.digits + string.ascii_uppercase
PRINTED_LINES = {"line_1": PRINTED, "line_2": PRINTED}

# The five digits a TD2 prints, each with the line it is printed on.  Taken
# from the tables rather than restated, so 3.10 and 3.11 inherit one list.
PRINTED_DIGITS = [
    (line_name, field_name)
    for line_name, layout in LAYOUTS
    for field_name in layout
    if field_name.endswith("_check_digit")
]


def field(line, layout, name):
    """Slice ``name`` out of ``line`` the way a later TD2 parser will."""
    start, end = layout[name]
    return line[start - 1 : end]


def fields_in_printed_order(layout):
    """The layout's fields, the way they appear on the line."""
    return sorted(layout.items(), key=lambda item: item[1])


def width(span):
    """How many positions a ``(first, last)`` span claims."""
    first, last = span
    return last - first + 1


# --- the constants are the standard's field list --------------------------


@pytest.mark.parametrize("line_name", sorted(EXPECTED))
def test_the_layout_holds_the_fields_the_standard_lists(line_name):
    assert td2.TD2[line_name] == EXPECTED[line_name]


def test_the_line_is_36_characters():
    # Not "the tables happen to add up to 36": the line the positions are read
    # against below is a real string, so if the length were wrong neither table
    # nor slice would agree with it.
    assert td2.TD2_LINE_LENGTH == 36
    assert len(PRINTED) == td2.TD2_LINE_LENGTH


def test_a_td2_zone_is_two_lines():
    # Never a range: two lines is what makes a TD2 a TD2, so a table that grew
    # a third would be a different format rather than a fuller TD2.
    assert td2.TD2_LINE_COUNT == 2
    assert len(td2.TD2) == td2.TD2_LINE_COUNT


def test_the_aggregate_holds_the_line_tables_rather_than_copies():
    # A copy would be a second table to drift, which is the failure these
    # tables exist to prevent, so the identity is the assertion.
    assert td2.TD2["line_1"] is td2.TD2_LINE_1
    assert td2.TD2["line_2"] is td2.TD2_LINE_2
    assert set(td2.TD2) == {"line_1", "line_2"}


def test_the_layout_names_are_exported():
    # The twenty-eight names this module has published and nothing else.
    # Sorted rather than written in the module's order so the assertion is
    # about the set a caller importing by name relies on.
    #
    # 3.9 pinned the half of this that said line 1's readers were exported and
    # line 2's were not, so a reader copied forward from `td1.py` -- or a
    # composite assembled early -- failed rather than arriving quietly.  3.10
    # is the task that publishes them, and the negative half is gone with the
    # task that made it true: the span and the two-line assembly are in the
    # list below like everything else they are meant to have.
    assert sorted(td2.__all__) == sorted(
        [
            "TD2",
            "TD2_CHECK_DIGIT_FIELDS",
            "TD2_COMPOSITE_SPANS",
            "TD2_DOCUMENT_CODES",
            "TD2_LINE_1",
            "TD2_LINE_2",
            "TD2_LINE_COUNT",
            "TD2_LINE_LENGTH",
            "TD2_SEX_MARKERS",
            "parse_date_of_birth",
            "parse_date_of_expiry",
            "parse_document_code",
            "parse_document_number",
            "parse_issuing_state",
            "parse_name",
            "parse_nationality",
            "parse_optional_data",
            "parse_sex",
            "td2_check_digit_results",
            "td2_composite_input",
            "parse_td2_line_1",
            "parse_td2_line_2",
            "td2_field",
            "validate_date_of_birth",
            "validate_date_of_expiry",
            "validate_document_code",
            "validate_document_number",
            "validate_issuing_state",
            "validate_name",
            "validate_nationality",
            "validate_optional_data",
            "validate_sex",
            # 3.14: the zone gate and the whole-zone parser, the two names a
            # caller outside this package needs -- one to check a shape, one
            # to read a document -- and which no earlier task in this format
            # could publish while the record did not exist.
            "validate_td2_lines",
            "parse_td2",
        ]
    )


# --- the coverage this task asks for --------------------------------------


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_a_line_covers_positions_1_to_36_with_no_gap_or_overlap(line_name, layout):
    claimed = []
    for field_name, (start, end) in fields_in_printed_order(layout):
        assert isinstance(start, int), f"{line_name}.{field_name} start is not an int"
        assert isinstance(end, int), f"{line_name}.{field_name} end is not an int"
        assert 1 <= start <= end, f"{line_name}.{field_name} is an empty or inverted range"
        assert (
            end <= td2.TD2_LINE_LENGTH
        ), f"{line_name}.{field_name} runs past the line"
        claimed.extend(range(start, end + 1))

    # One sorted comparison carries the whole claim.  A gap drops a position, an
    # overlap repeats one, and an out-of-range index puts a value in the list
    # that is not in 1-36; whichever it is, the two lists first differ at the
    # position that broke.  Counting to 36 would not do: a gap and an overlap
    # can cancel out in the total.
    assert sorted(claimed) == list(range(1, td2.TD2_LINE_LENGTH + 1))


@pytest.mark.parametrize("line_name, layout", LAYOUTS)
def test_the_fields_are_adjacent_and_ordered(line_name, layout):
    # The same claim as above, reported per boundary, so a failure says which
    # field broke the line rather than only that 36 integers did not appear.
    expected_start = 1
    for field_name, (start, end) in fields_in_printed_order(layout):
        assert (
            start == expected_start
        ), f"{line_name}.{field_name} starts at {start}, not {expected_start}"
        expected_start = end + 1

    assert expected_start == td2.TD2_LINE_LENGTH + 1


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
        assert sum(len(one) for one in slices) == td2.TD2_LINE_LENGTH


# --- the positions against a line of labelled characters -------------------


@pytest.mark.parametrize(
    "line_name, field_name, expected",
    [
        ("line_1", "document_code", "01"),
        ("line_1", "issuing_state", "234"),
        ("line_1", "name", PRINTED[5:]),
        ("line_2", "document_number", "012345678"),
        ("line_2", "document_number_check_digit", "9"),
        ("line_2", "nationality", "ABC"),
        ("line_2", "date_of_birth", "DEFGHI"),
        ("line_2", "date_of_birth_check_digit", "J"),
        ("line_2", "sex", "K"),
        ("line_2", "date_of_expiry", "LMNOPQ"),
        ("line_2", "date_of_expiry_check_digit", "R"),
        ("line_2", "optional_data", "STUVWX"),
        ("line_2", "optional_data_check_digit", "Y"),
        ("line_2", "composite_check_digit", "Z"),
    ],
)
def test_a_field_slices_the_characters_its_own_positions_hold(
    line_name, field_name, expected
):
    # The expected strings are written out from the standard's positions, one
    # character per position, so a table that shifted a boundary by one fails
    # on the value rather than passing as self-consistent.  3.4 earned its keep
    # here: its optional_data_1 expectation was one character too long.
    layout = td2.TD2[line_name]

    assert field(PRINTED_LINES[line_name], layout, field_name) == expected


@pytest.mark.parametrize("line_name, field_name", PRINTED_DIGITS)
def test_every_printed_digit_sits_immediately_after_the_field_it_checks(
    line_name, field_name
):
    # A check digit is only correct for that exact field over that exact span,
    # so it is printed in the position straight after the characters it covers.
    # Derived from the table rather than restated, and uniform over all five
    # printed digits a TD2 carries.
    layout = td2.TD2[line_name]
    ordered = [name for name, _ in fields_in_printed_order(layout)]
    previous = ordered[ordered.index(field_name) - 1]

    assert layout[field_name][0] == layout[previous][1] + 1
    assert layout[field_name][0] == layout[field_name][1]


def test_a_td2_prints_five_digits_and_all_five_are_on_line_2():
    # The count and the line are both claims, and they are what a reader of
    # only this module would get wrong: a TD1 prints five across two lines and
    # a TD3 prints five on line 2 with a 14-character personal number, so
    # "five digits" by itself would pass for either of them.
    assert len(PRINTED_DIGITS) == 5
    assert {line_name for line_name, _ in PRINTED_DIGITS} == {"line_2"}


def test_line_1_carries_no_check_digit_and_the_name_runs_to_the_end():
    # The one thing about a TD2 line 1 that is easy to forget: it is the
    # document header and the name and nothing else, so its last position is
    # the last character of the name rather than a digit over anything.  A
    # reader pointed at the wrong line gets a name, and nothing objects.
    assert not any(name.endswith("_check_digit") for name in td2.TD2_LINE_1)
    assert td2.TD2_LINE_1["name"] == (6, td2.TD2_LINE_LENGTH)
    assert td2.TD2_LINE_2["composite_check_digit"] == (36, 36)
    assert "composite_check_digit" not in td2.TD2_LINE_1


def test_the_optional_data_is_six_characters_and_not_a_td3s_fourteen():
    # The whole of a TD2's 8-character shortfall against a TD3 is here: a TD3
    # spends 14 on a personal number, and a reader that carried that width
    # over would push the optional data's own digit and the composite off the
    # end of the line.  Stated as a comparison rather than as a number, so the
    # error is a disagreement with the sibling format rather than a typo.
    assert td2.TD2_LINE_2["optional_data"] == (29, 34)
    assert width(EXPECTED_LINE_2["optional_data"]) == 6
    assert width(td3.TD3_LINE_2["personal_number"]) == 14


def test_a_td2_line_2_is_a_td3_line_2_up_to_position_28():
    # The claim the module docstring makes about the two formats, asserted
    # against the sibling table rather than asserted in prose: the same fields,
    # in the same order, at the same positions, and then the formats part.  It
    # cannot catch a position both tables are wrong about -- nothing in this
    # repository holds the standard -- but it does catch either table drifting
    # away from the other, which is the mistake a new format invites.
    shared = {name: span for name, span in td2.TD2_LINE_2.items() if span[1] <= 28}

    assert shared == {
        name: span for name, span in td3.TD3_LINE_2.items() if span[1] <= 28
    }
    assert list(shared) == [
        name for name, _ in fields_in_printed_order(td2.TD2_LINE_2) if name in shared
    ]


def test_the_document_number_and_the_optional_data_are_line_2_fields():
    # 3.9's task text put both on line 1, where they are not: they are a
    # TD1's line 1, and in a TD2 they sit at 1-10 and 29-35 of *line 2*.  The
    # correction is written into the task list, and this is what keeps it
    # honest -- a reader that read a visa's document number off its first
    # line would find nothing there to read.
    assert "document_number" not in td2.TD2_LINE_1
    assert "optional_data" not in td2.TD2_LINE_1
    assert "name" not in td2.TD2_LINE_2
    assert td2.TD2_LINE_1["name"] == (6, td2.TD2_LINE_LENGTH)
    assert td2.TD2_LINE_2["document_number"] == (1, 9)
    assert td2.TD2_LINE_2["optional_data"] == (29, 34)


def test_the_field_names_are_unique_across_the_two_lines():
    # A name used on two lines would be ambiguous to a record keyed by field,
    # and the per-line tables are what 3.9 and 3.10 will read by name.
    names = [name for layout in td2.TD2.values() for name in layout]

    assert len(names) == len(set(names))


def test_no_field_spans_more_than_one_line():
    # A composite may be computed over characters on two lines, but it is
    # *printed* on one, so every span here stays inside a single line of 36.
    for line_name, layout in LAYOUTS:
        for field_name, (start, end) in layout.items():
            assert 1 <= start <= end <= td2.TD2_LINE_LENGTH, f"{line_name}.{field_name}"


def test_a_td2_is_two_lines_of_36_and_a_td3_is_two_lines_of_44():
    # The task's own phrase, "2 lines of 36", pinned against the sibling format
    # so the difference between the two is a measured fact here rather than a
    # memory.  This is the assertion a TD3 reader copied into a TD2 would fail.
    assert (td2.TD2_LINE_COUNT, td2.TD2_LINE_LENGTH) == (2, 36)
    assert (td3.TD3_LINE_COUNT, td3.TD3_LINE_LENGTH) == (2, 44)


# --- this module is a table and nothing else -------------------------------


def test_this_module_states_positions_and_computes_nothing():
    # **3.9 is the first readers in this module, and the first assertion is
    # rewritten rather than deleted, for the reason 3.3 rewrote td3.py's twin
    # and 3.7 rewrote td1.py's:** "this module defines no function at all" was
    # a true statement of the whole claim while the module was a table, and
    # `parse_td2_line_1` made it false.  What the loop below states instead
    # is the rule the old assertion was standing in for, and it is about the
    # code rather than about a list of names: no function in this module
    # multiplies, adds or takes a remainder, so no digit can come out of here
    # however a reader reaches the arithmetic.
    #
    # 3.10 is the first delegation into this rule, and the test is rewritten
    # for the reason 3.3 rewrote `td3.py`'s twin and 3.7 rewrote `td1.py`'s:
    # the banned list used to name `check_digit_results` as well, which was a
    # true statement of the whole claim while this module had no digit layer
    # imported, and `td2_check_digit_results` made it false.  It is relaxed by
    # one name and not by one rule: the names that would mean a *copy* of the
    # arithmetic rather than a delegation to it stay banned, and the loop over
    # every function's source -- the claim the banned list was standing in
    # for -- still holds however a caller reaches the digit.
    #
    # The last assertion is the one that says delegation and duplication are
    # different things: `td2.check_digit_results` **is** `mrz`'s function, the
    # same object, so the sum, the weights and the modulo live in exactly one
    # place in the package.
    for name, obj in vars(td2).items():
        if inspect.isfunction(obj):
            assert "%" not in inspect.getsource(obj), f"td2.{name} computes something"

    for banned in (
        "CHAR_VALUES",
        "WEIGHT_CYCLE",
        "char_value",
        "check_digit",
        "verify_check_digit",
        "weights",
    ):
        assert banned not in vars(td2), f"td2.{banned}"

    assert "%" not in inspect.getsource(td2.td2_composite_input)
    assert "%" not in inspect.getsource(td2.td2_check_digit_results)
    assert td2.check_digit_results is mrz.check_digit_results

    # 3.11 is the second delegation into this rule and the same assertion
    # carries it: the name in this module's namespace **is** mrz's function,
    # so the month and day a visa is refused for are decided in exactly one
    # place in the package and a TD1 or a TD3 cannot refuse a different one.
    assert td2.date_fault is mrz.date_fault
    assert mrz.date_fault("993199") == mrz.date_fault("013200") == "month"


def test_this_module_defines_no_error_type_of_its_own():
    # The package raises exactly one error type, and this module raises that
    # one and defines no other.  3.9 rewrote the assertion rather than
    # dropping it: a module with no readers could hold no exception type at
    # all, and `parse_td2_line_1`'s `from .mrz import MrzValueError` puts
    # mrz's class in `vars(td2)` without this module ever having defined one.
    # So the claim is now about *identity* rather than about absence -- the
    # class in here is the same object as mrz's, so a caller writing one
    # `except MrzValueError` catches everything this module raises, and
    # there is no second class for them to catch by mistake.
    defined = {
        name
        for name, obj in vars(td2).items()
        if isinstance(obj, type) and issubclass(obj, BaseException)
    }

    assert defined == {"MrzValueError"}
    assert td2.MrzValueError is mrz.MrzValueError


def test_the_composite_span_is_published_exactly_once():
    # 3.8 and 3.9 asserted the *absence* of a span, which was the right claim
    # while the span was 3.10's open question and the task list's version of
    # it was the TD1's line 2 spans copied verbatim: a wrong span cannot be
    # inherited by importing a constant that already exists.  3.10 publishes
    # one, so the claim becomes the other half of the same thought -- a single
    # table, not a constant and a hand-written slice in the assembler both
    # claiming the span.  The assembler's `%`-free source and the table
    # itself are checked by the two tests below.
    assert [name for name in vars(td2) if "COMPOSITE" in name or "SPAN" in name] == [
        "TD2_COMPOSITE_SPANS"
    ]
    assert isinstance(td2.TD2_COMPOSITE_SPANS, tuple)


# --- 3.9: line 1, read on a printed specimen ------------------------------

# The sample visa's line 1, written out longhand and 36 characters long: "V<"
# (a visa), "UTO" (the standard's fictitious issuing state, the same one the
# specimen ID card and passport use), and then 31 characters of name --
# "ERIKSSON", the "<<" that divides a surname from given names, "ANNA", the
# filler that divides one given name from the next, "MARIA", and eleven
# fillers of padding.  There is no check digit on this line, and no field this
# task reads is a digit.
SPECIMEN_LINE_1 = "V<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<"

SPECIMEN_EXPECTED = {
    "document_code": "V<",
    "issuing_state": "UTO",
    "name": "ERIKSSON<<ANNA<MARIA<<<<<<<<<<<",
}

# Two lines built rather than quoted, for the wrong-line tests.  Only their
# first five characters are ever read by anything in this section, and both
# are filler past them, so neither is a claim about any visa.  The number is
# the specimen's own, which is why the first two characters are "L8" and not
# a visa code.
OTHER_LINE_NUMBER = "L898902C<" + mrz.FILLER * 27
VISA_CODE_NUMBER = "V<" + mrz.FILLER * 34


def line_1_with(field_name, printed):
    """The specimen with ``field_name`` replaced by ``printed``, for a fault."""
    start, end = td2.TD2_LINE_1[field_name]
    return SPECIMEN_LINE_1[: start - 1] + printed + SPECIMEN_LINE_1[end:]


def test_the_specimen_is_a_line_of_thirty_six_characters():
    # Not "the tables happen to add up to 36": the line every slice below is
    # read out of is a real string, so a miscounted run of fillers would show
    # up here rather than as a short field further down.
    assert len(SPECIMEN_LINE_1) == td2.TD2_LINE_LENGTH
    assert len(SPECIMEN_EXPECTED["name"]) == 31


def test_every_character_of_the_specimen_is_one_the_mrz_alphabet_prints():
    # The one thing this project *can* check about a quoted line, and the
    # reason the fixture is quotable at all.  A specimen with a space, a
    # lower-case letter or a diacritic in it is not a line any MRZ could
    # print, so this catches a misremembered line that no check digit would
    # have caught -- there is no check digit on this line to catch it.
    for character in SPECIMEN_LINE_1:
        assert character in mrz.CHAR_VALUES, character

    assert [mrz.char_value(letter) for letter in SPECIMEN_LINE_1[:5]] == [31, 0, 30, 29, 24]


def test_line_1_prints_no_check_digit_so_the_specimen_holds_no_remembered_digit():
    # 1.6's rule, and the reason it does not bite here.  1.6 declined to
    # state a TD3 composite and 3.4 declined to quote a TD1 because both meant
    # publishing a printed digit nothing here could confirm; a TD2 line 1
    # prints none, so this fixture has no digit to take on trust and the one
    # value that cannot be confirmed -- the name -- is a value no arithmetic
    # in this package computes over.  **3.10 is where that stopped being true**,
    # because 3.10's span settles the name inside the composite's arithmetic:
    # the section below checks this same claim for the whole zone, where the
    # two derived digits live, and this one keeps the line-1 half of it.
    assert not [name for name in td2.TD2_LINE_1 if name.endswith("_check_digit")]
    assert len(PRINTED_DIGITS) == 5
    assert {line_name for line_name, _ in PRINTED_DIGITS} == {"line_2"}
    assert not [position for position in range(1, 37) if SPECIMEN_LINE_1[position - 1].isdigit()]


def test_the_name_is_thirty_one_characters_where_a_td3s_is_thirty_nine():
    # The width difference between the two formats, stated as a comparison
    # against the sibling table rather than as a number: 3.9 is the task that
    # reads the field, and a reader that carried a TD3's 39 over would slice
    # nine characters past the end of the line and report a name of the wrong
    # width on a correctly printed visa.
    assert len(SPECIMEN_EXPECTED["name"]) == 31
    assert width(td2.TD2_LINE_1["name"]) == 31
    assert width(td3.TD3_LINE_1["name"]) == 39


@pytest.mark.parametrize("field_name, expected", sorted(SPECIMEN_EXPECTED.items()))
def test_a_field_slices_the_text_the_specimen_prints(field_name, expected):
    # The same shape as the synthetic-line test above, against a line that
    # means something: a table that is right about "56789ABCDE" can still be
    # one character out on a document number or a name.
    assert field(SPECIMEN_LINE_1, td2.TD2_LINE_1, field_name) == expected


def test_parse_td2_line_1_returns_every_field_of_the_line_in_printed_order():
    # The order the keys are in is the order the fields are printed in, read
    # out of the layout rather than written as a literal -- which matters here
    # because for these three field names the two orders happen to coincide,
    # so a literal would pass a mapping that was built in the wrong order and
    # would only be caught by a change of name.
    printed_order = [name for name, _ in fields_in_printed_order(td2.TD2_LINE_1)]
    parsed = td2.parse_td2_line_1(SPECIMEN_LINE_1)

    assert list(parsed) == printed_order
    assert dict(parsed) == SPECIMEN_EXPECTED


def test_the_parsed_fields_rebuild_the_line_they_were_read_from():
    # The coverage claim read back as text, and now on a document rather than
    # on labelled positions: three fields, in printed order, lose nothing.  A
    # reader that trimmed the name would break this as surely as one that
    # read the wrong span, and "as printed, padding included" is the rule this
    # protects -- 3.10's composite may compute over that padding.
    parsed = td2.parse_td2_line_1(SPECIMEN_LINE_1)

    assert "".join(parsed.values()) == SPECIMEN_LINE_1
    assert sum(len(value) for value in parsed.values()) == td2.TD2_LINE_LENGTH


def test_the_parsed_fields_cannot_be_edited_by_a_caller():
    # The evidence of what the document printed.  A mapping a caller could
    # change would let a cleaned-up name look exactly like a read one, which
    # is the same argument MrzDocument.sources makes on the TD3 side.
    parsed = td2.parse_td2_line_1(SPECIMEN_LINE_1)

    with pytest.raises(TypeError):
        parsed["name"] = "ERIKSSON"  # type: ignore[index]


# --- the document code: a closed set, and a line that is not a visa --------


@pytest.mark.parametrize("code", ["V<", "V"])
def test_a_visa_code_is_accepted(code):
    assert td2.validate_document_code(code) == code
    assert code in td2.TD2_DOCUMENT_CODES


def test_a_visa_code_that_lost_its_filler_is_the_same_document():
    # The reason a bare "V" is accepted, checked with mrz's own arithmetic
    # rather than asserted: the second position is filler, filler is worth
    # zero, and a character worth zero contributes nothing to a digit
    # computed over the line -- so the two codes cannot differ in any verdict
    # this project will ever reach.
    assert mrz.char_value(mrz.FILLER) == 0
    assert mrz.check_digit("V<") == mrz.check_digit("V")


@pytest.mark.parametrize(
    "code",
    [
        "P<",  # a passport: a TD3, printed as two lines of 44
        "I<",  # an identity card: a TD1, printed as three lines of 30
        "AC",  # an ICAO-compliant document of some other kind
        "<<",
        "v<",
        "V<1",
        " V",
        "",
        None,
        7,
    ],
)
def test_a_code_that_is_not_a_visa_is_refused(code):
    # Closed on purpose: these are well-formed MRZ codes belonging to other
    # documents, and a reader that waved them through would report a passport
    # or a card as a visa.  The message names the code, which describes a
    # document and not a person.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_document_code(code)

    assert "V<" in str(excinfo.value)


def test_the_document_code_is_read_from_the_specimen():
    assert td2.parse_document_code(SPECIMEN_LINE_1) == "V<"
    assert td2.parse_td2_line_1(SPECIMEN_LINE_1)["document_code"] == "V<"


def test_a_line_that_is_not_a_td2_is_refused_rather_than_read():
    # The strongest cheap check there is: the synthetic line from 3.8 is 36
    # characters of nonsense, and its first two characters are "01".  Nothing
    # else has to be wrong for the zone to be refused.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_td2_line_1(PRINTED)

    assert "'01'" in str(excinfo.value)


# --- the issuing state: three uppercase letters, and no code list ----------


@pytest.mark.parametrize("code", ["UTO", "IND", "GBR", "AAA"])
def test_a_well_formed_issuing_state_is_accepted(code):
    # IND is in this list for the reason td1.py gives: ISO 3166-1 alpha-3
    # assigns it to India, so a parser holding a code list without it would
    # refuse every genuine Indian visa.  Whether DRISHTI *recognises* a state
    # is the rules engine's question, and answering it here would need a list
    # this project cannot source.
    assert td2.validate_issuing_state(code) == code


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
        td2.validate_issuing_state(code)

    assert "3" in str(excinfo.value)


@pytest.mark.parametrize("code", [None, b"UTO", 7, ["UTO"]])
def test_an_issuing_state_that_is_not_a_string_is_refused(code):
    # bytes again: it is a sequence of integers that happens to spell UTO,
    # and a validator that measured before it checked the type would wave it
    # through and then fail to slice it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_issuing_state(code)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_issuing_state_is_read_from_the_specimen():
    assert td2.parse_issuing_state(SPECIMEN_LINE_1) == "UTO"
    assert td2.parse_td2_line_1(SPECIMEN_LINE_1)["issuing_state"] == "UTO"


def test_the_issuing_state_message_carries_the_state_and_the_width():
    # The one field on this line whose message may carry what it found, and
    # the width is read out of the table rather than typed in, so the two
    # cannot disagree.  Three characters naming a *state* describe a
    # document; the name two fields later is a person, and its message says
    # neither.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_issuing_state("UT0")

    assert "UT0" in str(excinfo.value)
    assert "3-5" in str(excinfo.value)


# --- the name: extracted, judged for its width, and for nothing else ------


@pytest.mark.parametrize(
    "printed",
    [
        "ERIKSSON<<ANNA<MARIA" + "<" * 11,  # the specimen's own name
        "ERIKSSON<<ANNA<MARIA<<<<<<<<<<<",
        "<" * 31,  # a name field nothing was printed into
        "ERIKSSON" + "<" * 23,  # a surname and no given names
        "ERIKSSON<<ANA<MARÍA" + "<" * 12,  # a diacritic an MRZ cannot print
        "eriksson<<anna<maria" + "<" * 11,  # lower case
        "ERIKSSON<<ANNA MARIA" + "<" * 11,  # a space where a filler belongs
        "MUSTERMANN<<ERIKA" + "<" * 14,  # a name filling all 31
    ],
)
def test_a_name_is_extracted_and_judged_only_for_its_width(printed):
    # The rule td3.py gives and 3.9 carries over: the standard fixes where the
    # name sits and how wide it is, and nothing about the characters, because
    # the names it has to carry are not a set anyone can enumerate.  A
    # diacritic, a lower-case read or a space where a "<<" belongs is a misread
    # a flag wants to point at, not a reason to drop the visa.
    assert len(printed) == 31
    assert td2.validate_name(printed) == printed
    assert td2.parse_name(line_1_with("name", printed)) == printed


@pytest.mark.parametrize(
    "name", ["ERIKSSON<<ANNA<MARIA" + "<" * 10, "ERIKSSON<<ANNA<MARIA" + "<" * 12, "", None, 7]
)
def test_a_name_of_the_wrong_width_or_type_is_refused(name):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_name(name)

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_short_name_comes_back_padded_rather_than_stripped():
    # "No name" is a *value* a line may print rather than an absence, and the
    # padding is load-bearing: 3.10 settles whether any part of this line is
    # inside the composite's arithmetic, and a stripped filler here would
    # change the digit 3.10 computes.
    parsed = td2.parse_td2_line_1(line_1_with("name", "ERIKSSON" + "<" * 23))

    assert parsed["name"] == "ERIKSSON" + "<" * 23
    assert len(parsed["name"]) == 31
    assert mrz.char_value(mrz.FILLER) == 0


def test_the_name_message_never_carries_the_name():
    # The one field on this line that is a person rather than a document, and
    # the place 2.2's rule would have been easiest to break by accident: a
    # name is the longest string in the zone and the one an operator most
    # wants to see.  The message carries the positions and the two lengths
    # and never a character of the name.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_name("ERIKSSON<<ANNA<MARIA<<<<<<<<<<")

    assert "ERIKSSON" not in str(excinfo.value)
    assert "6-36" in str(excinfo.value)


# --- the wrong line, and the shape of the line the assembler was given ----


def test_a_line_2_cannot_be_mistaken_for_a_line_1():
    # A TD2's line 2 begins with the document number, so a number that does
    # not start with the visa code is refused on its first two characters and
    # nothing else about it has to be wrong.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_document_code(OTHER_LINE_NUMBER)

    assert "'L8'" in str(excinfo.value)

    with pytest.raises(mrz.MrzValueError) as assembler:
        td2.parse_td2_line_1(OTHER_LINE_NUMBER)

    assert "L8" in str(assembler.value)


def test_a_number_beginning_with_the_visa_code_is_caught_by_the_state_instead():
    # The honest asymmetry, and the reason the document code is not the whole
    # of what tells a TD2's two lines apart.  A document number is filler-
    # padded on the right and may be as short as an authority likes, so a
    # number whose first two characters are "V<" reaches the code reader as a
    # perfectly good visa code; what catches it is the issuing state three
    # positions later, because positions 3-5 are then the third through fifth
    # characters of a number rather than three uppercase letters.  Two
    # fields, two different rules, and neither of them a check digit.
    assert td2.parse_document_code(VISA_CODE_NUMBER) == "V<"

    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_td2_line_1(VISA_CODE_NUMBER)

    assert "uppercase letters" in str(excinfo.value)


@pytest.mark.parametrize(
    "line",
    [
        SPECIMEN_LINE_1[:-1],  # 35 characters: a line that stopped early
        SPECIMEN_LINE_1 + "<",  # 37 characters
        "",
    ],
)
def test_a_line_that_is_not_thirty_six_characters_is_refused(line):
    # Without the width gate the name slices to whatever arrived and the parse
    # reports a visa whose name lost a position.  The message is the
    # diagnosis, so it is asserted as well as the type: this is the *line*
    # being refused, not a field.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_td2_line_1(line)

    assert type(excinfo.value) is mrz.MrzValueError
    assert f"{len(line)} characters" in str(excinfo.value)
    assert f"not {td2.TD2_LINE_LENGTH}" in str(excinfo.value)


@pytest.mark.parametrize("line", [None, 7, SPECIMEN_LINE_1.encode(), []])
def test_a_line_that_is_not_a_string_is_refused(line):
    # One error type for the whole package: a caller writes one
    # except MrzValueError, so a bare TypeError out of a slice would escape it.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_td2_line_1(line)

    assert type(excinfo.value) is mrz.MrzValueError


# --- the reads go through the table, not through a hand-written index ------


def test_the_name_is_read_through_the_layout(monkeypatch):
    # The one reader a hand-written `line[5:36]` would get right on the
    # specimen and wrong everywhere else, because the specimen's name does
    # fill the field.  Moving the field in the table and putting a different
    # name at its new position is what tells the two apart; monkeypatch
    # restores the table.
    line = "V<UTOERIKSSON<<ANA" + "<" * 18
    moved_slice = line[5:30]

    assert len(moved_slice) == 25
    assert td2.parse_name(SPECIMEN_LINE_1) == SPECIMEN_EXPECTED["name"]

    monkeypatch.setitem(td2.TD2_LINE_1, "name", (6, 30))

    # The width moved with the span, so the validator -- which reads the width
    # out of the table rather than typing in a 31 -- accepted a 25-character
    # field rather than refusing it as the wrong width.
    assert td2.parse_name(line) == moved_slice
    assert td2.parse_td2_line_1(line)["name"] == moved_slice


def test_the_issuing_state_is_read_through_the_layout(monkeypatch):
    # Same argument for the middle of the line: the width is read out of the
    # table rather than typed in as a 3, so a wider field is judged by the
    # wider field's rule.
    assert td2.parse_issuing_state(SPECIMEN_LINE_1) == "UTO"

    monkeypatch.setitem(td2.TD2_LINE_1, "issuing_state", (3, 6))

    # "UTOE": the specimen's fourth character, read as a fourth letter.
    assert td2.parse_issuing_state(SPECIMEN_LINE_1) == "UTOE"
    assert td2.parse_td2_line_1(SPECIMEN_LINE_1)["issuing_state"] == "UTOE"


def test_the_document_code_is_read_through_the_layout(monkeypatch):
    # And for the first two characters, where a TD2's code is also the two
    # characters a document number would print.
    assert td2.parse_document_code(SPECIMEN_LINE_1) == "V<"

    monkeypatch.setitem(td2.TD2_LINE_1, "document_code", (1, 1))

    # A one-character field reading "V" is still in the closed set, which is
    # the second of the two codes 3.9 accepts.
    assert td2.parse_document_code(SPECIMEN_LINE_1) == "V"
    assert td2.parse_td2_line_1(SPECIMEN_LINE_1)["document_code"] == "V"


def test_td2_field_is_the_one_place_a_line_is_sliced():
    # Positions are 1-indexed and inclusive, so (1, 2) is `line[0:2]` and the
    # conversion is the whole of what this function adds.  Checked from the
    # layout rather than from a literal, so it holds for every field of every
    # line rather than for the three this test thought to name.
    for line_name, layout in td2.TD2.items():
        line = SPECIMEN_LINE_1 if line_name == "line_1" else PRINTED
        for name, (start, end) in layout.items():
            assert td2.td2_field(line, layout, name) == line[start - 1 : end]


@pytest.mark.parametrize("line", [None, 7, b"V<UTO"])
def test_td2_field_reports_a_line_that_is_not_a_string(line):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.td2_field(line, td2.TD2_LINE_1, "document_code")

    assert type(excinfo.value) is mrz.MrzValueError


def test_td2_field_reports_a_field_the_layout_does_not_have():
    # A caller mistake rather than a bad document, reported as this rather
    # than escaping the KeyError a bare lookup would raise.  Line 2's fields
    # are asked for here on purpose: both lines are read as of 3.10, so a
    # reader that reached into the *other* line's table is the mistake this
    # is for -- the one a copied `td1.py` reader makes, since a TD1's
    # document number is on line 1 and a TD2's is not.
    with pytest.raises(mrz.MrzValueError):
        td2.td2_field(SPECIMEN_LINE_1, td2.TD2_LINE_1, "document_number")


def test_this_module_reads_no_line_but_through_td2_field(monkeypatch):
    # The rule 3.9 has to be able to break: every read of a line goes through
    # the one function that slices it, so a future reader that reaches for an
    # index of its own fails here.  The count is the claim: three reads, one
    # per field of line 1, and no fourth.
    calls = []
    real = td2.td2_field

    def counting_field(line, layout, name):
        calls.append(name)
        return real(line, layout, name)

    monkeypatch.setattr(td2, "td2_field", counting_field)
    td2.parse_td2_line_1(SPECIMEN_LINE_1)

    assert sorted(calls) == ["document_code", "issuing_state", "name"]


@pytest.mark.parametrize(
    "line_name, judged_fields",
    [
        ("line_1", ["document_code", "issuing_state", "name"]),
        (
            "line_2",
            [
                "document_number",
                "nationality",
                "date_of_birth",
                "sex",
                "date_of_expiry",
                "optional_data",
            ],
        ),
    ],
)
def test_the_assembler_hands_every_field_to_its_validator(
    monkeypatch, line_name, judged_fields
):
    # The other half of the rule above: `td2_field` slices, `validate_*`
    # judges, and the assembler goes through both for every field it judges.
    # A raw read of a field would be *equivalent* on a well-formed line -- the
    # width gate has already run, so the slice is 31 characters whatever else
    # happens -- and equivalence is exactly why this needs a test rather than
    # a demonstration: the difference only shows when a field's width rule
    # moves, which is what the name monkeypatch above is for and what the
    # three tests below make visible here.
    #
    # 3.10 extends it to line 2 rather than leaving it as one call site, and
    # **line 2's five printed digits are deliberately not in the list**: they
    # have no `validate_*` of their own, because a printed character is
    # evidence rather than a value -- so a count that grew to eleven would be
    # claiming the parse judges digits, which is 2.4's rule and is not true.
    judged = []
    for name in judged_fields:
        real = getattr(td2, f"validate_{name}")

        def counting(value, _name=name, _real=real):
            judged.append(_name)
            return _real(value)

        monkeypatch.setattr(td2, f"validate_{name}", counting)

    line = SPECIMEN_LINE_1 if line_name == "line_1" else SPECIMEN_LINE_2
    getattr(td2, f"parse_td2_{line_name}")(line)

    assert sorted(judged) == sorted(judged_fields)


# --- 3.10: line 2, the five printed digits, and the composite --------------

# The same fictitious visa as line 1 above, built the way this format builds
# it: the same document number -- "L898902C<", the standard's own, eight
# characters and a filler -- the same issuing state turned into a nationality,
# the same dates and sex marker, and the standard's own personal number
# "ZE184226B<<<<<" cut from a TD3's fourteen characters to this format's six,
# "ZE1842".  **Every character below is the standard's**, and the document
# number is the one field on this line whose padding is a *value* rather than
# a corner case: an authority may as easily print a seven-character number.
#
# **Three of the five printed digits are quoted and confirmed against the
# characters beside them, in the test two below: the "3" at position 10, the
# "2" at 20 and the "9" at 28.**  Those are the same three the TD1 and TD3
# specimens print for the same fields, so a misremembered field here could not
# have survived.  **The other two are derived, and that is 1.6's rule applied
# rather than avoided:** the optional data's own digit and the composite are
# computed by `mrz` and written in, which is the choice 3.7 made for a TD1
# composite after finding its remembered digit was wrong.  A green row below
# means this line agrees with itself over the characters it printed, and says
# nothing about any real visa.
SPECIMEN_LINE_2 = "L898902C<3UTO7408122F1204159ZE184283"

SPECIMEN_EXPECTED_LINE_2 = {
    "document_number": "L898902C<",
    "document_number_check_digit": "3",
    "nationality": "UTO",
    "date_of_birth": "740812",
    "date_of_birth_check_digit": "2",
    "sex": "F",
    "date_of_expiry": "120415",
    "date_of_expiry_check_digit": "9",
    "optional_data": "ZE1842",
    "optional_data_check_digit": "8",
    "composite_check_digit": "3",
}

# The two digits this file derives rather than quotes, named so a test can say
# which is which: the other three printed digits on this line are confirmed
# against the characters beside them above.
PRINTED_OPTIONAL_DATA_DIGIT = "8"
PRINTED_COMPOSITE_DIGIT = "3"

# The span `tasks.md` 3.10 states, written out longhand so the argument
# against it is a comparison rather than an assertion about prose.  These are
# `TD1_COMPOSITE_SPANS`'s line 2 spans, verbatim, with a line 1 portion in
# front of them.
TASK_LIST_SPANS = [
    ("line_1", 6, 30),
    ("line_2", 1, 7),
    ("line_2", 9, 15),
    ("line_2", 19, 29),
]

# The span `td2.py` publishes, written out longhand from the standard rather
# than read back from the module: the whole of line 1's name, then the
# document number with its digit, the date of birth with its digit, and the
# date of expiry, the optional data and their two digits as one run.
EXPECTED_COMPOSITE_SPANS = [
    ("line_1", 6, 36),
    ("line_2", 1, 10),
    ("line_2", 14, 20),
    ("line_2", 22, 35),
]

# The same fictitious visa as a TD3 prints it, for the one test that compares
# this format's composite with the sibling module's.  Forty-four characters:
# the 28 the two formats share, then the personal number "ZE184226B<<<<<",
# its own digit and the composite.
TD3_SPECIMEN_LINE_2 = (
    "L898902C<3"  # 1-10  document number + its published check digit
    "UTO"  # 11-13 nationality
    "7408122"  # 14-20 date of birth + its published check digit
    "F"  # 21     sex
    "1204159"  # 22-28 date of expiry + its published check digit
    "ZE184226B<<<<<1"  # 29-43 personal number + its check digit
    "6"  # 44     composite check digit
)

# The same 62 characters again, written out by hand from the positions above
# so the span table and the concatenated text are two independent statements
# and a span moved by one position cannot make both come out right.
EXPECTED_COMPOSITE_INPUT = (
    # line 1 6-36: the name, all 31 characters of it, padding included
    "ERIKSSON<<ANNA<MARIA<<<<<<<<<<<"
    # line 2 1-10: the document number, filler and all, and its own digit
    + "L898902C<3"
    # line 2 14-20: the date of birth and its own digit
    + "7408122"
    # line 2 22-35: the date of expiry and its digit, the optional data and
    # its own digit
    + "1204159ZE18428"
)


def line_2_with(field_name, printed):
    """The specimen with ``field_name`` replaced by ``printed``, for a fault."""
    start, end = td2.TD2_LINE_2[field_name]
    return SPECIMEN_LINE_2[: start - 1] + printed + SPECIMEN_LINE_2[end:]


def line_2_with_several(**replacements):
    """The specimen with each named field replaced, for a two-part fault."""
    line = SPECIMEN_LINE_2
    for field_name, printed in replacements.items():
        start, end = td2.TD2_LINE_2[field_name]
        line = line[: start - 1] + printed + line[end:]
    return line


def specimen_results(line_1=SPECIMEN_LINE_1, line_2=SPECIMEN_LINE_2):
    """The five verdicts for a pair of lines, parsed the way 3.14 will parse."""
    sources = {**td2.parse_td2_line_1(line_1), **td2.parse_td2_line_2(line_2)}
    return td2.td2_check_digit_results(line_1, line_2, sources)


def spans_covering(line_name, field_name):
    """The published spans that touch ``field_name`` on ``line_name``."""
    start, end = td2.TD2[line_name][field_name]
    return [span for span in td2.TD2_COMPOSITE_SPANS if span[0] == line_name
            and span[1] <= end and start <= span[2]]


def cuts_through_a_field(spans, line_name):
    """The fields ``spans`` cross, as ``(name, start, end)``, in printed order."""
    cut = []
    for field_name, (start, end) in fields_in_printed_order(td2.TD2[line_name]):
        overlapping = [span for span in spans if span[0] == line_name
                       and span[1] <= end and start <= span[2]]
        whole = [span for span in overlapping if span[1] <= start and end <= span[2]]
        if overlapping and len(whole) != len(overlapping):
            cut.append((field_name, start, end))
    return cut


def test_the_specimens_line_2_is_a_line_of_thirty_six_characters():
    # Not "the tables happen to add up": the line every slice below is read out
    # of is a real string, so a miscounted run of fillers would show up here.
    assert len(SPECIMEN_LINE_2) == td2.TD2_LINE_LENGTH
    assert "".join(SPECIMEN_EXPECTED_LINE_2.values()) == SPECIMEN_LINE_2
    assert len(SPECIMEN_EXPECTED_LINE_2["optional_data"]) == 6


def test_every_character_of_the_specimens_line_2_is_one_the_mrz_alphabet_prints():
    # The same check the line-1 fixture gets, and the reason a line carrying
    # digits is quotable at all: a space, a lower-case letter or a diacritic in
    # it is not a line any MRZ could print.
    for character in SPECIMEN_LINE_2:
        assert character in mrz.CHAR_VALUES, character


@pytest.mark.parametrize(
    "field_name, digit_field",
    [
        ("document_number", "document_number_check_digit"),
        ("date_of_birth", "date_of_birth_check_digit"),
        ("date_of_expiry", "date_of_expiry_check_digit"),
    ],
)
def test_the_specimens_three_quoted_digits_are_the_ones_the_arithmetic_computes(
    field_name, digit_field
):
    # **The half of the fixture 1.6 allows: three printed digits this project
    # confirms rather than trusts.**  The same three fields print the same
    # three digits on the TD1 and TD3 specimens, so a misremembered field
    # would have to come to its own digit three times over to survive.  The
    # other two printed digits on this line are derived, and the test below
    # says which is which rather than leaving it to be inferred.
    assert mrz.check_digit(SPECIMEN_EXPECTED_LINE_2[field_name]) == int(
        SPECIMEN_EXPECTED_LINE_2[digit_field]
    )
    assert td2.parse_td2_line_2(SPECIMEN_LINE_2)[digit_field] == (
        SPECIMEN_EXPECTED_LINE_2[digit_field]
    )


def test_the_two_remaining_printed_digits_are_this_projects_own_arithmetic():
    # The other half of 1.6: the optional data's digit and the composite are
    # not quoted from anything, they are what `mrz` computes over the
    # characters above.  3.7 found a TD1's remembered composite wrong by
    # exactly this test, so the fixture carries the arithmetic's answer and
    # says so in the two constants' names.
    assert mrz.check_digit(SPECIMEN_EXPECTED_LINE_2["optional_data"]) == int(
        PRINTED_OPTIONAL_DATA_DIGIT
    )
    assert mrz.check_digit(EXPECTED_COMPOSITE_INPUT) == int(PRINTED_COMPOSITE_DIGIT)


@pytest.mark.parametrize(
    "field_name, expected",
    sorted(SPECIMEN_EXPECTED_LINE_2.items()),
)
def test_a_line_2_field_slices_the_text_the_specimen_prints(field_name, expected):
    # The same shape as the line-1 test above, against a line that means
    # something: a table that is right about "56789ABCDE" can still be one
    # character out on a document number or an optional data field.
    assert field(SPECIMEN_LINE_2, td2.TD2_LINE_2, field_name) == expected


def test_parse_td2_line_2_returns_every_field_of_the_line_in_printed_order():
    # Eleven fields, the order the document prints them in, read out of the
    # layout rather than written as a literal.
    printed_order = [name for name, _ in fields_in_printed_order(td2.TD2_LINE_2)]
    parsed = td2.parse_td2_line_2(SPECIMEN_LINE_2)

    assert list(parsed) == printed_order
    assert dict(parsed) == SPECIMEN_EXPECTED_LINE_2


def test_the_parsed_line_2_fields_rebuild_the_line_they_were_read_from():
    # The coverage claim read back as text, and now on a document rather than
    # on labelled positions: eleven fields in printed order lose nothing.  A
    # reader that trimmed the optional data would break this as surely as one
    # that read the wrong span, and "as printed, padding included" is the rule
    # this protects -- the composite is computed over some of that padding.
    parsed = td2.parse_td2_line_2(SPECIMEN_LINE_2)

    assert "".join(parsed.values()) == SPECIMEN_LINE_2
    assert sum(len(value) for value in parsed.values()) == td2.TD2_LINE_LENGTH


def test_the_parsed_line_2_fields_cannot_be_edited_by_a_caller():
    # The evidence of what the document printed, for line 2 as for line 1: a
    # mapping a caller could change would let a cleaned-up document number
    # look exactly like a read one.
    parsed = td2.parse_td2_line_2(SPECIMEN_LINE_2)

    with pytest.raises(TypeError):
        parsed["document_number"] = "L898902C8"  # type: ignore[index]


def test_a_printed_digit_that_disagrees_still_parses():
    # 2.4's rule, and the reason the five digits are carried rather than
    # judged: a parse reports what the document printed, and the verdict is
    # asked for separately.  The document number's digit is put one out, which
    # is what a forgery would do, and the line still parses.
    printed = SPECIMEN_EXPECTED_LINE_2["document_number_check_digit"]
    wrong = "0" if printed != "0" else "1"

    parsed = td2.parse_td2_line_2(line_2_with("document_number_check_digit", wrong))

    assert parsed["document_number"] == "L898902C<"
    assert parsed["document_number_check_digit"] == wrong


@pytest.mark.parametrize(
    "line", [SPECIMEN_LINE_2[:-1], SPECIMEN_LINE_2 + mrz.FILLER, ""]
)
def test_a_line_2_that_is_not_thirty_six_characters_is_refused(line):
    # The same width gate 3.9 checked for line 1, and the same reason: without
    # it the composite's last span slices short and the parse reports a visa
    # that lost a position.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_td2_line_2(line)

    assert f"{len(line)} characters" in str(excinfo.value)
    assert f"not {td2.TD2_LINE_LENGTH}" in str(excinfo.value)


@pytest.mark.parametrize("line", [None, 7, SPECIMEN_LINE_2.encode(), []])
def test_a_line_2_that_is_not_a_string_is_refused(line):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_td2_line_2(line)

    assert type(excinfo.value) is mrz.MrzValueError


def test_a_line_1_cannot_be_mistaken_for_a_line_2():
    # **The other half of 3.9's finding, and it is not caught.**  3.9 said two
    # fields tell a TD2's lines apart -- the document code and the issuing
    # state -- and both are on line 1, so line 1 read as a line 2 meets no
    # closed set: its positions 1-9 are "V<UTOERIK", which is not filler and
    # so is a short padded number; 11-13 are "SON", three characters of a
    # name, and **an MRZ prints a name in capitals**, so they are three
    # uppercase letters; 21 is an "M"; and 14-19 and 22-27 are only judged
    # for their width until 3.11.  The parse therefore *succeeds*.
    #
    # **What it does not do is accuse the document**, and that is the half
    # worth having.  Every printed digit position on a line 1 holds a letter
    # or the filler, so all five rows come back "could not be read" rather
    # than "failed": a caller handed this is told the document could not be
    # checked, which is what happened, rather than that a digit disagrees.
    # A reader that "detected" the wrong line here would be guessing, and a
    # guess that produced a finding would be 2.14's mistake one level up.
    assert td2.parse_document_number(SPECIMEN_LINE_1) == "V<UTOERIK"

    parsed = td2.parse_td2_line_2(SPECIMEN_LINE_1)

    assert parsed["nationality"] == "SON"
    assert parsed["sex"] == "M"
    assert [result.passed for result in specimen_results(SPECIMEN_LINE_1, SPECIMEN_LINE_1)] == [
        None,
        None,
        None,
        None,
        None,
    ]


def test_this_module_reads_no_line_2_but_through_td2_field(monkeypatch):
    # The line-2 twin of the line-1 rule above: eleven reads, one per field of
    # the line, every one of them through the one function that slices a TD2
    # line.  The count is the claim -- a hand-written index would make this
    # eleven short.
    calls = []
    real = td2.td2_field

    def counting_field(line, layout, name):
        calls.append(name)
        return real(line, layout, name)

    monkeypatch.setattr(td2, "td2_field", counting_field)
    td2.parse_td2_line_2(SPECIMEN_LINE_2)

    assert sorted(calls) == sorted(SPECIMEN_EXPECTED_LINE_2)


def test_line_2_fields_are_read_through_the_layout(monkeypatch):
    # The same argument as line 1's three monkeypatch tests, on the field
    # whose width is this format's most likely to be carried over: the
    # optional data.  Moving it in the table moves what the reader reads, so
    # the width has to be read out of the layout rather than typed in as a 6.
    assert td2.parse_optional_data(SPECIMEN_LINE_2) == "ZE1842"

    monkeypatch.setitem(td2.TD2_LINE_2, "optional_data", (29, 33))

    assert td2.parse_optional_data(SPECIMEN_LINE_2) == "ZE184"
    assert td2.parse_td2_line_2(SPECIMEN_LINE_2)["optional_data"] == "ZE184"


# --- 3.10: the document number, the nationality, the dates, the sex --------


@pytest.mark.parametrize(
    "number", ["L898902C<", "L8989<<<", "L<<<<<<<<", "A1", "L898902C9"]
)
def test_a_document_number_shorter_than_its_field_is_padded_not_refused(number):
    # A document number is filler-padded on the right and may be as short as
    # an authority likes, so a nine-character field holding a shorter number is
    # a complete number rather than a short field.
    padded = number.ljust(9, mrz.FILLER)

    assert td2.validate_document_number(padded) == padded
    assert td2.parse_document_number(line_2_with("document_number", padded)) == padded


def test_a_field_of_nothing_but_filler_is_no_document_number_at_all():
    # The other half of that rule, and it is why the emptiness is judged
    # *before* the width: a field nine characters long is the right width, and
    # it holds no number, so the message has to say which of the two it found.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.parse_document_number(line_2_with("document_number", mrz.FILLER * 9))

    assert "nothing but it" in str(excinfo.value)
    assert "1-9" in str(excinfo.value)


@pytest.mark.parametrize("number", ["L898902C", "L898902C34", "", None, 7, b"L898902C<"])
def test_a_document_number_of_the_wrong_width_or_type_is_refused(number):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_document_number(number)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_document_number_message_never_carries_the_number():
    # The identifier the screening is about, unique to one holder's document:
    # this names the width it wanted and never the value.  A document code and
    # an issuing state may be echoed -- they describe a document -- and this
    # is the field where that habit would be most expensive.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_document_number("L898902C45")

    assert "L898902C45" not in str(excinfo.value)
    assert "9 characters" in str(excinfo.value)


@pytest.mark.parametrize("code", ["UTO", "IND", "GBR", "AAA"])
def test_a_nationality_of_three_uppercase_letters_is_accepted(code):
    # IND is here for `td1.py`'s reason: ISO 3166-1 alpha-3 assigns it to
    # India, so a list without it would refuse every genuine Indian visa.
    assert td2.validate_nationality(code) == code


@pytest.mark.parametrize(
    "code", ["uto", "UtO", "UT0", "UT<", "UT ", "UTOX", "UT", "<<<", None, 7]
)
def test_a_nationality_that_is_not_three_uppercase_letters_is_refused(code):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_nationality(code)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_nationality_message_names_the_positions_and_never_the_code():
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_nationality("UT0")

    assert "UT0" not in str(excinfo.value)
    assert "11-13" in str(excinfo.value)


@pytest.mark.parametrize("date", ["740812", "120415", "AAAAAA", "<<<<<<"])
@pytest.mark.parametrize(
    "validate, parse, field_name",
    [
        ("validate_date_of_birth", "parse_date_of_birth", "date_of_birth"),
        ("validate_date_of_expiry", "parse_date_of_expiry", "date_of_expiry"),
    ],
)
def test_a_date_that_is_not_impossible_comes_back_exactly_as_printed(
    date, validate, parse, field_name
):
    # What is left of the old "judged for its width and for nothing else" once
    # 3.11 answered its own question: the two specimen dates, and the two
    # fields of characters nobody could read.  **The unreadable half is the
    # half that costs a document rather than catching one** -- a visa whose
    # date printed a filler is a misread for the digit at position 20 or 28 to
    # report, and refusing it in the reader would throw that finding away.
    assert getattr(td2, validate)(date) == date
    assert getattr(td2, parse)(line_2_with(field_name, date)) == date


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
    "validate, parse, field_name",
    [
        ("validate_date_of_birth", "parse_date_of_birth", "date_of_birth"),
        ("validate_date_of_expiry", "parse_date_of_expiry", "date_of_expiry"),
    ],
)
def test_a_date_whose_month_or_day_could_not_be_a_day_is_refused(
    date, fault, validate, parse, field_name
):
    # 3.11's two named values and three beside them, reached through this
    # format's readers rather than restated in them: `date_fault` is mrz's, so
    # a TD1, a TD2 and a TD3 refuse the same month for the same reason, and the
    # message adds only what the layout knows -- which field, and where.
    start, end = td2.TD2_LINE_2[field_name]
    with pytest.raises(mrz.MrzValueError) as excinfo:
        getattr(td2, validate)(date)

    message = str(excinfo.value)
    assert type(excinfo.value) is mrz.MrzValueError
    assert fault in message
    assert f"{start}-{end}" in message
    assert date not in message
    with pytest.raises(mrz.MrzValueError):
        getattr(td2, parse)(line_2_with(field_name, date))


@pytest.mark.parametrize(
    "validate", ["validate_date_of_birth", "validate_date_of_expiry"]
)
@pytest.mark.parametrize("date", ["74081", "7408123", "", None, 7, b"740812"])
def test_a_date_of_the_wrong_width_or_type_is_refused(validate, date):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        getattr(td2, validate)(date)

    assert type(excinfo.value) is mrz.MrzValueError


@pytest.mark.parametrize(
    "validate", ["validate_date_of_birth", "validate_date_of_expiry"]
)
def test_the_date_message_never_carries_the_date(validate):
    # A date of birth is a property of the holder and an expiry still dates
    # the holder's presence in a country, so neither message carries the value
    # -- only the positions and the two lengths.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        getattr(td2, validate)("74081")

    assert "74081" not in str(excinfo.value)


def test_the_sex_markers_are_exactly_four_characters():
    # The count, the set and the type are all claims, and they are the same
    # four characters the TD1 and TD3 hold: position 21 is the one field no
    # digit in this project reaches, so this closed set is the whole of the
    # judgement any arithmetic here makes about the character.
    assert td2.TD2_SEX_MARKERS == frozenset({"M", "F", "X", mrz.FILLER})
    assert isinstance(td2.TD2_SEX_MARKERS, frozenset)
    assert len(td2.TD2_SEX_MARKERS) == 4


@pytest.mark.parametrize("marker", ["M", "F", "X", mrz.FILLER])
def test_a_sex_marker_a_visa_may_print_is_accepted(marker):
    assert td2.validate_sex(marker) == marker
    assert td2.parse_sex(line_2_with("sex", marker)) == marker


@pytest.mark.parametrize("marker", ["N", "Q", "m", "f", "<<", "MM", "", None, 7])
def test_a_sex_marker_that_is_not_one_of_the_four_is_refused(marker):
    # N and Q are the two this rules out that a "one uppercase letter, or the
    # filler" rule would wave through on the one field nothing else checks.
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_sex(marker)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_sex_marker_is_read_from_the_specimen_and_its_message_names_the_set():
    assert td2.parse_sex(SPECIMEN_LINE_2) == "F"
    assert td2.parse_td2_line_2(SPECIMEN_LINE_2)["sex"] == "F"

    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_sex("N")

    assert "'M'" in str(excinfo.value)
    assert "'N'" not in str(excinfo.value)


@pytest.mark.parametrize("printed", ["ZE1842", "<<<<<<", "ID1234", "ze1842", "ZE18 2"])
def test_the_optional_data_is_carried_as_printed_and_judged_by_nothing(printed):
    # The same rule as a TD3's personal number: optional data is whatever the
    # authority put there, so this judges the width and nothing else.  A
    # character the MRZ alphabet cannot print comes back untouched, because
    # `mrz.check_digit` is what raises on it in the verdicts below and a flag
    # wants the printed characters, not a lost document.
    assert td2.validate_optional_data(printed) == printed
    assert td2.parse_optional_data(line_2_with("optional_data", printed)) == printed


@pytest.mark.parametrize("data", ["ZE184", "ZE18422", "", None, 7, b"ZE1842"])
def test_the_optional_data_of_the_wrong_width_or_type_is_refused(data):
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_optional_data(data)

    assert type(excinfo.value) is mrz.MrzValueError


def test_the_optional_data_is_six_characters_where_a_td3s_is_fourteen():
    # The reader, as the layout: 3.8 pinned the table, and a reader that
    # carried a TD3's 14 across would take the optional data's own digit and
    # the composite off the end of the line.  Stated against the sibling
    # table so the error is a disagreement with the other format rather than
    # a number that could have been mistyped.
    with pytest.raises(mrz.MrzValueError):
        td2.validate_optional_data("ID12345678901234")

    assert width(td2.TD2_LINE_2["optional_data"]) == 6
    assert width(td3.TD3_LINE_2["personal_number"]) == 14


def test_the_optional_data_message_never_carries_the_characters():
    with pytest.raises(mrz.MrzValueError) as excinfo:
        td2.validate_optional_data("ZE184")

    assert "ZE184" not in str(excinfo.value)
    assert "29-34" in str(excinfo.value)


# --- 3.10: the span, and the composite over both lines ---------------------


def test_the_composite_spans_are_the_ones_this_task_settles_on():
    # **The test that settles the span, and the one 3.8 could not write.**  It
    # is written from the format's shape rather than from a table read back
    # out of the module: line 1 contributes the name whole, and line 2
    # contributes every field that has a printed digit beside it, in printed
    # order.  The order matters as much as the spans, because the weights
    # restart at the first character of the second span.
    assert list(td2.TD2_COMPOSITE_SPANS) == EXPECTED_COMPOSITE_SPANS
    assert isinstance(td2.TD2_COMPOSITE_SPANS, tuple)


def test_every_composite_span_lies_inside_a_real_line():
    # The claim a span naming a line, or a position past 36, would fail on a
    # value rather than as a silent short slice.
    for line_name, start, end in td2.TD2_COMPOSITE_SPANS:
        assert line_name in {"line_1", "line_2"}, line_name
        assert 1 <= start <= end <= td2.TD2_LINE_LENGTH, (line_name, start, end)


def test_the_composite_is_sixty_two_characters_thirty_one_from_each_line():
    # Not "the spans add up": a span that ran past the end of its line would
    # slice short and the total would be the only thing to notice.
    composite = td2.td2_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2)
    by_line = {"line_1": 0, "line_2": 0}

    for line_name, start, end in td2.TD2_COMPOSITE_SPANS:
        by_line[line_name] += end - start + 1

    assert by_line == {"line_1": 31, "line_2": 31}
    assert len(composite) == 62
    assert td2.TD2_LINE_LENGTH * 2 == 72


@pytest.mark.parametrize("line_name", ["line_1", "line_2"])
def test_every_span_is_a_run_of_whole_fields(line_name):
    # **How a reader knows a span here is not one position out, and it is a
    # stronger claim than the TD1's twin can make.**  Every field the layout
    # declares is either wholly inside the composite or wholly outside it --
    # no field is cut through, on either line, at all.  A span moved by one
    # position starts or ends mid-field and fails here rather than producing
    # a composite that happens to agree with a derived digit.
    assert cuts_through_a_field(td2.TD2_COMPOSITE_SPANS, line_name) == []


def test_the_fields_the_composite_covers_are_exactly_the_checked_ones():
    # The claim the span makes, stated as the set of fields it reaches: on
    # line 1 the name, and on line 2 every field that has a printed digit
    # standing beside it.  The complement is stated too, because the gaps are
    # as much a part of the claim as the spans.
    covered = {
        (line_name, field_name)
        for line_name in ("line_1", "line_2")
        for field_name in td2.TD2[line_name]
        if spans_covering(line_name, field_name)
    }

    assert covered == {
        ("line_1", "name"),
        ("line_2", "document_number"),
        ("line_2", "document_number_check_digit"),
        ("line_2", "date_of_birth"),
        ("line_2", "date_of_birth_check_digit"),
        ("line_2", "date_of_expiry"),
        ("line_2", "date_of_expiry_check_digit"),
        ("line_2", "optional_data"),
        ("line_2", "optional_data_check_digit"),
    }
    assert not spans_covering("line_2", "nationality")
    assert not spans_covering("line_2", "sex")
    assert not spans_covering("line_2", "composite_check_digit")
    assert not spans_covering("line_1", "document_code")
    assert not spans_covering("line_1", "issuing_state")


@pytest.mark.parametrize(
    "line_name, field_name",
    [
        ("line_2", "document_number_check_digit"),
        ("line_2", "date_of_birth_check_digit"),
        ("line_2", "date_of_expiry_check_digit"),
        ("line_2", "optional_data_check_digit"),
    ],
)
def test_the_composite_contains_every_digit_the_line_prints(line_name, field_name):
    # The rule both sibling formats follow and the one the TD1's original
    # span broke: the composite includes every printed digit except its own.
    # Four here, all on line 2 -- a statement a reader of the task list's
    # version could not have made, since that version leaves position 35 out
    # entirely and cuts positions 1-9 and 14-19 in half.
    assert spans_covering(line_name, field_name)
    assert td2.TD2[line_name][field_name][0] == td2.TD2[line_name][field_name][1]


def test_the_task_lists_span_would_cut_four_fields_and_take_in_two_of_them():
    # **The argument against inheriting 3.10's own text, as a measurement
    # rather than as prose.**  Those three line 2 spans are `TD1_COMPOSITE_
    # SPANS`'s line 2 spans verbatim, and the same helper above reports what
    # they do to a TD2's layout: they cut the document number (twice, once per
    # span that crosses it), the date of birth and the optional data, and they
    # take in the nationality and the sex marker -- the two fields no
    # composite in this package reaches.  The line 1 portion cuts the name,
    # which nothing in the format's shape explains.  A test that asserted
    # "the spans are runs of whole fields" would be satisfied by neither.
    assert cuts_through_a_field(TASK_LIST_SPANS, "line_1") == [("name", 6, 36)]
    assert cuts_through_a_field(TASK_LIST_SPANS, "line_2") == [
        ("document_number", 1, 9),
        ("date_of_birth", 14, 19),
        ("optional_data", 29, 34),
    ]

    line_2_spans = [span for span in TASK_LIST_SPANS if span[0] == "line_2"]
    for line_name, field_name in (("line_2", "nationality"), ("line_2", "sex")):
        start, end = td2.TD2[line_name][field_name]
        assert any(s <= end and start <= e for _, s, e in line_2_spans)

    assert td2.TD2_COMPOSITE_SPANS != tuple(TASK_LIST_SPANS)


def test_the_line_2_part_is_a_td3s_composite_without_its_last_eight_positions():
    # The structural claim the module docstring makes, asserted against the
    # sibling module rather than asserted in prose: the two formats share line
    # 2 up to position 28, so the composite covers the same three runs, and
    # the eight positions a TD3 gives to the tail of a personal number are the
    # eight a TD2 does not have.  This is the argument the task list's span
    # cannot be reconciled with, because that one is not field-aligned at all.
    td3_input = td3.td3_composite_input(TD3_SPECIMEN_LINE_2)
    td2_line_2_part = SPECIMEN_LINE_2[0:10] + SPECIMEN_LINE_2[13:20] + SPECIMEN_LINE_2[21:35]

    # The same fictitious visa, as a TD3 prints it: the same 28 characters,
    # then a fourteen-character personal number, its digit and the composite.
    assert len(TD3_SPECIMEN_LINE_2) == td3.TD3_LINE_LENGTH == 44
    assert TD3_SPECIMEN_LINE_2[:28] == SPECIMEN_LINE_2[:28]
    assert TD3_SPECIMEN_LINE_2[28:42] == "ZE184226B<<<<<"
    assert TD3_SPECIMEN_LINE_2[42] == "1"

    assert len(td3_input) == 39
    assert len(td2_line_2_part) == 31
    assert td3_input[:17] == td2_line_2_part[:17]
    assert len(td3_input) - len(td2_line_2_part) == 8
    assert td3_input[17:] == TD3_SPECIMEN_LINE_2[21:43]
    assert td2_line_2_part[17:] == SPECIMEN_LINE_2[21:35]


def test_the_composite_input_is_the_sixty_two_characters_the_spans_name():
    # The concatenation, against a string written out longhand from the
    # positions above.  The expectation is sliced with the *expected*
    # positions, so this fails on the value if the module's spans move.
    expected = "".join(
        {"line_1": SPECIMEN_LINE_1, "line_2": SPECIMEN_LINE_2}[line_name][start - 1 : end]
        for line_name, start, end in EXPECTED_COMPOSITE_SPANS
    )

    assert expected == EXPECTED_COMPOSITE_INPUT
    assert len(EXPECTED_COMPOSITE_INPUT) == 62
    assert td2.td2_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2) == expected


def test_the_composite_reads_two_lines_because_no_line_holds_it_alone():
    # Why two parameters and not one: the name is on line 1 and every printed
    # digit is on line 2, so 31 characters come from each.  A caller who
    # passed only the line that *prints* the digit would be computing a
    # different number over half the evidence, and nothing about the result
    # would say so.
    from_line_1 = "".join(
        SPECIMEN_LINE_1[start - 1 : end]
        for line_name, start, end in td2.TD2_COMPOSITE_SPANS
        if line_name == "line_1"
    )

    assert from_line_1 == SPECIMEN_EXPECTED["name"]
    assert len(from_line_1) == 31 == width(td2.TD2_LINE_1["name"])
    assert len(td2.td2_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2)) == 62


def test_the_name_is_inside_the_composite_so_its_padding_is_load_bearing():
    # 3.9 returned the name with its filler rather than stripped, and said the
    # reason was 3.10's arithmetic.  Here it is: a filler changed inside the
    # name's padding moves the composite and nothing else, so a parser that
    # tidied the field would quietly change the digit 3.10 computes.  The
    # character is "B" rather than "A" for a reason worth stating: the filler
    # is worth zero and so is "A", ten, so a filler printed as an "A" is
    # invisible to every digit in this package -- 2.14's blind spot, one
    # field along, and a property of the arithmetic rather than of the span.
    tampered = "V<UTOERIKSSON<<ANNA<MARIA" + mrz.FILLER * 10 + "B"
    results = specimen_results(tampered, SPECIMEN_LINE_2)

    assert len(td2.parse_td2_line_1(tampered)["name"]) == 31
    assert [result.passed for result in results] == [True, True, True, True, False]
    assert results[-1].field == "composite"
    assert mrz.char_value(mrz.FILLER) == 0
    assert mrz.char_value("A") == 10
    assert specimen_results(
        "V<UTOERIKSSON<<ANNA<MARIA" + mrz.FILLER * 10 + "A", SPECIMEN_LINE_2
    )[-1].passed is True


def test_the_specimens_composite_agrees_with_its_own_sixty_two_characters():
    # **The task's "a test on a correct specimen", and the fifth printed
    # digit this fixture derives.**  The green row is a claim about this
    # project and not about any visa: the composite digit is whatever the
    # arithmetic over the published span comes to, exactly as 1.6 recorded
    # for a TD3's and 3.7 for a TD1's.  A green parse here means the 36
    # characters of each line, the span, the printed digits and the verdicts
    # are one story.
    composite = td2.td2_composite_input(SPECIMEN_LINE_1, SPECIMEN_LINE_2)

    assert mrz.check_digit(composite) == int(PRINTED_COMPOSITE_DIGIT)
    assert specimen_results()[-1].field == "composite"
    assert specimen_results()[-1].passed is True
    assert td2.parse_td2_line_2(SPECIMEN_LINE_2)["composite_check_digit"] == (
        PRINTED_COMPOSITE_DIGIT
    )


def test_the_five_verdicts_are_reported_in_printed_order():
    # Positions 10, 20, 28, 35 and 36 -- an order a caller reads top to bottom
    # has to be the order the document prints, so the list says the same thing
    # about itself the parse does.  **Five ``True`` rows and no ``None``**, the
    # one thing this format's correct specimen does *not* share with the TD1's:
    # this optional data is filled in, so its own digit position prints a
    # digit.  The unused case is below.
    results = specimen_results()

    assert [result.field for result in results] == [
        "document_number",
        "date_of_birth",
        "date_of_expiry",
        "optional_data",
        "composite",
    ]
    assert all(isinstance(result, mrz.CheckDigitResult) for result in results)
    assert [result.passed for result in results] == [True, True, True, True, True]


def test_an_unused_optional_data_field_is_reported_as_unchecked_not_as_failed():
    # The row that is not ``True`` once the optional data is left empty, and
    # the reason it is not ``False``: six fillers compute to a real answer
    # (zero) while the printed half is unreadable, so 3.3's three-way answer
    # is the honest one.  A ``False`` here would put a forged-digit claim in
    # front of an officer on the strength of a field nobody filled in.
    line_2 = line_2_with_several(
        optional_data=mrz.FILLER * 6, optional_data_check_digit=mrz.FILLER
    )
    sources = {**td2.parse_td2_line_1(SPECIMEN_LINE_1), **td2.parse_td2_line_2(line_2)}
    row = next(
        r
        for r in td2.td2_check_digit_results(SPECIMEN_LINE_1, line_2, sources)
        if r.field == "optional_data"
    )

    assert row.expected is None
    assert row.found == 0
    assert row.readable is False
    assert row.passed is None


def test_an_edit_to_an_unused_optional_data_is_caught_by_the_composite_alone():
    # The consequence of the ``None`` row above, asserted rather than assumed:
    # with the optional data's own digit position printing filler, that row
    # cannot say "failed", so the composite is the only row on the card that
    # can see an edit to the field.
    empty = line_2_with_several(
        optional_data=mrz.FILLER * 6, optional_data_check_digit=mrz.FILLER
    )
    edited = line_2_with_several(
        optional_data="1" + mrz.FILLER * 5, optional_data_check_digit=mrz.FILLER
    )

    before = specimen_results(SPECIMEN_LINE_1, empty)
    after = specimen_results(SPECIMEN_LINE_1, edited)

    assert [result.passed for result in before][:4] == [True, True, True, None]
    assert [result.passed for result in after][:4] == [True, True, True, None]
    # The optional data's own row cannot say "failed" in either case -- the
    # printed half is filler in both -- so the composite's *found* value is
    # the only thing on the card that moved.
    assert before[-1].found != after[-1].found
    assert before[-1].found is not None


def test_a_mutated_composite_digit_fails_the_composite_and_nothing_else():
    # The task's "one on a mutated composite", over all nine wrong digits
    # rather than the one chosen, so no digit of the ten is special.  Only
    # line 2 position 36 moves: the 62 characters the composite is computed
    # over are byte-identical and still come to 3 for every one of the nine.
    wrong_digits = [d for d in string.digits if d != PRINTED_COMPOSITE_DIGIT]
    assert len(wrong_digits) == 9

    for digit in wrong_digits:
        line_2 = line_2_with("composite_check_digit", digit)
        results = specimen_results(SPECIMEN_LINE_1, line_2)

        assert mrz.check_digit(td2.td2_composite_input(SPECIMEN_LINE_1, line_2)) == 3
        assert [r.passed for r in results] == [True, True, True, True, False], digit
        composite = results[-1]
        assert composite.field == "composite"
        assert (composite.expected, composite.found) == (int(digit), 3)


@pytest.mark.parametrize(
    "field_name, printed, own_row",
    [
        ("document_number", "L898902C9", 0),
        ("date_of_birth", "740813", 1),
        ("date_of_expiry", "120416", 2),
        ("optional_data", "ZE1843", 3),
    ],
)
def test_a_field_inside_the_span_fails_its_own_row_and_the_composite(
    field_name, printed, own_row
):
    # A character edited inside the composite is caught twice: by the digit
    # printed beside it and by the composite.  A forger who edits such a field
    # *and* recomputes its own digit defeats the first row, and the composite
    # is what is left -- which is the honest reading to hand an officer, and
    # not a claim that any one of them is stronger than the other.
    results = specimen_results(SPECIMEN_LINE_1, line_2_with(field_name, printed))
    passed = [result.passed for result in results]

    assert passed[own_row] is False
    assert passed[4] is False
    assert [index for index, value in enumerate(passed) if value is not True] == sorted(
        [own_row, 4]
    )
    assert td2.td2_composite_input(
        SPECIMEN_LINE_1, line_2_with(field_name, printed)
    ) != EXPECTED_COMPOSITE_INPUT


@pytest.mark.parametrize("field_name, printed", [("sex", "M"), ("nationality", "GBR")])
def test_the_two_fields_the_span_skips_cannot_move_the_composite(field_name, printed):
    # The complement of the span, stated as a fact about the arithmetic: the
    # nationality and the sex marker are covered by no printed digit in this
    # format, so this is the honest limit of what a TD2's composite can see.
    # A rules engine (Part 12) is the answer to a nationality that changed;
    # no check digit here would ever object.
    line_2 = line_2_with(field_name, printed)

    assert td2.td2_composite_input(SPECIMEN_LINE_1, line_2) == EXPECTED_COMPOSITE_INPUT
    assert [result.passed for result in specimen_results(SPECIMEN_LINE_1, line_2)] == [
        True,
        True,
        True,
        True,
        True,
    ]


@pytest.mark.parametrize(
    "line_1, line_2, message_holds",
    [
        (SPECIMEN_LINE_1[:-1], SPECIMEN_LINE_2, "36"),  # 35 characters
        (SPECIMEN_LINE_1, SPECIMEN_LINE_2 + mrz.FILLER, "36"),  # 37 characters
        (None, SPECIMEN_LINE_2, "string"),
        (SPECIMEN_LINE_1, None, "string"),
    ],
)
def test_the_composite_refuses_a_line_of_the_wrong_width(line_1, line_2, message_holds):
    # The width check `_checked_line` already does for both parsers, reached
    # here in its sharpest form: a silently short 62-character span would come
    # back as a composite that *failed* rather than as an error, which is the
    # one failure mode a caller could not tell from a forged document.  The
    # message is `_checked_line`'s own, which is why this asserts what it
    # holds rather than that it exists.
    with pytest.raises(mrz.MrzValueError) as error:
        td2.td2_composite_input(line_1, line_2)

    assert message_holds in str(error.value)


def test_the_verdicts_name_a_field_this_format_actually_prints():
    # A pairing naming a field the layout does not have would raise `KeyError`
    # at the call rather than reporting a field nobody printed, so all three
    # elements of every pairing have to be real names -- on either line, since
    # the composite's characters are the exception that carries `None` for
    # exactly that reason.
    layouts = {**td2.TD2_LINE_1, **td2.TD2_LINE_2}

    for label, field, digit_field in td2.TD2_CHECK_DIGIT_FIELDS:
        assert label in layouts or label == "composite"
        assert field is None or field in layouts, field
        assert digit_field in layouts, digit_field

    assert [pair[0] for pair in td2.TD2_CHECK_DIGIT_FIELDS] == [
        result.field for result in specimen_results()
    ]


def test_a_field_the_caller_omitted_raises_key_error_and_not_a_document_error():
    # 3.3's rule, kept for this format: a missing key is a bug in the caller,
    # and dressing it up as a `MrzValueError` would put a fact about a visa
    # into a log entry that describes none.  A document that is *wrong* raises
    # nothing here at all -- that is a row with `passed is False`.
    sources = {**td2.parse_td2_line_1(SPECIMEN_LINE_1), **td2.parse_td2_line_2(SPECIMEN_LINE_2)}
    del sources["date_of_birth"]

    with pytest.raises(KeyError):
        td2.td2_check_digit_results(SPECIMEN_LINE_1, SPECIMEN_LINE_2, sources)


# --- the zone gate, which 3.14 brought ------------------------------------


def specimen_zone():
    return [SPECIMEN_LINE_1, SPECIMEN_LINE_2]


def test_the_gate_returns_three_or_two_lines_in_printed_order():
    # The gate never tells a caller which line is which by index: it returns
    # them in the order the standard prints them, so a parser can write
    # `line_1, line_2 = validate_td2_lines(lines)` and be right.
    assert td2.validate_td2_lines(specimen_zone()) == (
        SPECIMEN_LINE_1,
        SPECIMEN_LINE_2,
    )


@pytest.mark.parametrize(
    "zone",
    [
        "x" * 36,  # one string, not two lines
        None,  # not a sequence at all
        [SPECIMEN_LINE_1],  # one line of 36
        [SPECIMEN_LINE_1] * 3,  # a TD1's three lines
        [SPECIMEN_LINE_1, SPECIMEN_LINE_2[:-1]],  # line 2 one short
        [SPECIMEN_LINE_1[:-1], SPECIMEN_LINE_2],  # line 1 one short
        [None, SPECIMEN_LINE_2],  # a line that is not a string
    ],
)
def test_the_gate_refuses_anything_that_is_not_two_lines_of_thirty_six(zone):
    # A `MrzValueError` and nothing else, so a caller catching that one type
    # catches the `None` zone and the `None` line as well: 1.9's rule.
    with pytest.raises(mrz.MrzValueError):
        td2.validate_td2_lines(zone)


def test_the_gate_names_the_line_and_the_width_it_wanted_and_never_a_character():
    # Widths are shape; the characters are the identity data the screening is
    # about, so a message that named the line would leak the document and one
    # that named only the count would not be a diagnosis.
    with pytest.raises(mrz.MrzValueError) as caught:
        td2.validate_td2_lines([SPECIMEN_LINE_1, SPECIMEN_LINE_2[:20]])

    message = str(caught.value)
    assert "line 2" in message
    assert "20" in message
    assert "36" in message
    assert SPECIMEN_LINE_2[:20] not in message


@pytest.mark.parametrize(
    "zone",
    [
        [SPECIMEN_LINE_1],  # line 2 missing
        [SPECIMEN_LINE_1, SPECIMEN_LINE_2[:35]],  # line 2 one short
        "x" * 36,
    ],
)
def test_the_parser_runs_the_gate_before_it_reads_anything(zone):
    # 3.10's trade, made sharp by 3.14: a TD2's composite is computed over
    # characters on *both* lines, so a parser handed a short or missing one
    # would come back with a composite that failed rather than with an error.
    # The gate runs first, and the type it raises is the one error type this
    # package raises -- never a bare `ValueError` from unpacking two names out
    # of one.
    with pytest.raises(mrz.MrzValueError):
        td2.parse_td2(zone)
