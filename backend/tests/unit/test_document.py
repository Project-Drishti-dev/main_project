"""One function that reads a zone of any of the three shapes, and the record
it hands back.

Task 3.14 asks for a ``format`` discriminator on the record and a dispatcher
that picks TD1, TD2 or TD3 from the line count and the widths.  This file is
the claim that both exist and that the third answer -- a shape nobody reads
-- is refused rather than guessed at.

**The three specimens are the ones the format files already use, quoted here
again rather than imported.**  ``test_td1.py``, ``test_td2.py`` and
``test_td3.py`` each write their specimen out longhand on purpose, so that a
table compared with itself proves nothing; importing them from here would make
that independence disappear, and a dispatcher that agreed with the format
modules *because* it shared their fixtures would agree with them by
construction.  The two lines a TD2 and a TD3 print for the same document
share their first 28 characters, which is 3.10's claim about the shape and is
visible in the fixtures below.

**The two derived digits in the TD1 and TD2 specimens are this project's
arithmetic, not quotations**, and 3.7 and 3.10 each wrote that down where
they quoted their own line: the TD1 composite at line 2 position 30 and the
TD2 optional data's and composite's digits.  A green check-digit row here
means *these characters, these printed digits and these verdicts are one
story*, and never that any real card or visa carries them.

**Every expected value below is written out rather than read back from the
module**, including the ``None``s, so a reader that filled the wrong field
with the wrong shape of value produces a different document instead of a
matching one.
"""

import ast
import dataclasses
import datetime
import pathlib

import pytest

from app.pipeline.tier0 import document, mrz, td1, td2, td3


def source_of(module):
    return pathlib.Path(module.__file__).read_text(encoding="utf-8")


TD1_ZONE = [
    "I<UTOD231458907<<<<<<<<<<<<<<<",
    "7408122F1204159UTO<<<<<<<<<<<7",
    # Line 3 is the holder's name and nothing reads it yet, so the characters
    # here are a filler-padded name of the right width and the only claim
    # about them is that they are 30 of them.
    "ERIKSSON<<ANNA<MARIA" + "<" * 10,
]

TD2_ZONE = [
    "V<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<",
    "L898902C<3UTO7408122F1204159ZE184283",
]

TD3_ZONE = [
    "P<UTOERIKSSON<<ANNA<MARIA" + "<" * 19,
    "L898902C<3"  # 1-10  document number + its published check digit
    "UTO"  # 11-13 nationality
    "7408122"  # 14-20 date of birth + its published check digit
    "F"  # 21     sex
    "1204159"  # 22-28 date of expiry + its published check digit
    "ZE184226B<<<<<1"  # 29-43 personal number + its check digit
    "6",  # 44     composite check digit
]


# The twelve fields all three formats print, and the seven that are one
# format's alone, written out so the ``None``s are assertions rather than
# whatever the record happened to hold.
COMMON_FIELDS = {
    "issuing_state": "UTO",
    "document_number": "D23145890",
    "document_number_check_digit": "7",
    "nationality": "UTO",
    "date_of_birth": "740812",
    "date_of_birth_check_digit": "2",
    "sex": "F",
    "date_of_expiry": "120415",
    "date_of_expiry_check_digit": "9",
    "composite_check_digit": "7",
}

TD1_ONLY_FIELDS = {
    "document_code": "I<",
    "optional_data_1": "<" * 14,
    "optional_data_1_check_digit": "<",
    "optional_data_2": "<" * 11,
}

TD2_ONLY_FIELDS = {
    "document_code": "V<",
    "optional_data": "ZE1842",
    "optional_data_check_digit": "8",
}

TD3_ONLY_FIELDS = {
    "document_code": "P<",
    "personal_number": "ZE184226B<<<<<",
    "personal_number_check_digit": "1",
}


def test_the_dispatcher_and_its_two_tables_are_exported():
    assert {"MRZ_PARSERS", "MRZ_SHAPES", "detect_mrz_format", "parse_mrz"} <= set(
        document.__all__
    )


# --- the three formats ----------------------------------------------------


def test_three_lines_of_thirty_is_a_td1():
    assert document.detect_mrz_format(TD1_ZONE) == "TD1"


def test_two_lines_of_thirty_six_is_a_td2():
    assert document.detect_mrz_format(TD2_ZONE) == "TD2"


def test_two_lines_of_forty_four_is_a_td3():
    assert document.detect_mrz_format(TD3_ZONE) == "TD3"


def test_a_td1_zone_parses_into_every_field_its_layout_states():
    # The twelve common fields at their printed values, the three a TD1
    # alone prints, and the five `None`s a TD1 has no field for.  The three
    # `None`s that are *not* here -- `name`, `surname`, `given_names` -- are
    # the line 3 gap the next test names, not a format that prints no name.
    document_ = document.parse_mrz(TD1_ZONE)

    assert document_.format == "TD1"
    assert {
        name: getattr(document_, name)
        for name in COMMON_FIELDS | TD1_ONLY_FIELDS
    } == {**COMMON_FIELDS, **TD1_ONLY_FIELDS}
    assert document_.personal_number is None
    assert document_.personal_number_check_digit is None
    assert document_.optional_data is None
    assert document_.optional_data_check_digit is None


def test_a_td2_zone_parses_into_every_field_its_layout_states():
    document_ = document.parse_mrz(TD2_ZONE)

    assert document_.format == "TD2"
    assert {
        name: getattr(document_, name)
        for name in COMMON_FIELDS | TD2_ONLY_FIELDS
    } == {
        **COMMON_FIELDS,
        **TD2_ONLY_FIELDS,
        "document_number": "L898902C<",
        "document_number_check_digit": "3",
        "composite_check_digit": "3",
    }
    assert document_.personal_number is None
    assert document_.personal_number_check_digit is None
    assert document_.optional_data_1 is None
    assert document_.optional_data_1_check_digit is None
    assert document_.optional_data_2 is None


def test_a_td3_zone_parses_into_every_field_its_layout_states():
    document_ = document.parse_mrz(TD3_ZONE)

    assert document_.format == "TD3"
    assert {
        name: getattr(document_, name)
        for name in COMMON_FIELDS | TD3_ONLY_FIELDS
    } == {
        **COMMON_FIELDS,
        **TD3_ONLY_FIELDS,
        "document_number": "L898902C<",
        "document_number_check_digit": "3",
        "composite_check_digit": "6",
    }
    assert document_.optional_data_1 is None
    assert document_.optional_data_1_check_digit is None
    assert document_.optional_data_2 is None
    assert document_.optional_data is None
    assert document_.optional_data_check_digit is None


@pytest.mark.parametrize(
    ("zone", "parser"),
    [(TD1_ZONE, td1.parse_td1), (TD2_ZONE, td2.parse_td2), (TD3_ZONE, td3.parse_td3)],
)
def test_dispatching_gives_the_record_the_format_s_own_parser_gives(zone, parser):
    # The dispatcher adds a decision, not a reading.  Equality rather than a
    # field-by-field comparison, so a dispatcher that re-sliced a line, cleaned
    # a field, or rebuilt a verdict would produce a record that differs
    # somewhere the next test does not have to name.
    assert document.parse_mrz(zone) == parser(zone)


@pytest.mark.parametrize(
    ("zone", "verdicts"),
    [
        (TD1_ZONE, [True, None, True, True, True]),
        (TD2_ZONE, [True, True, True, True, True]),
        (TD3_ZONE, [True, True, True, True, True]),
    ],
)
def test_every_format_reports_five_check_digit_rows_in_printed_order(zone, verdicts):
    # The `None` in the TD1 row is 3.7's: an unused optional data field prints
    # filler in its check digit's place, so there is no printed half to
    # disagree with.  It is the third answer, not a failure, and a record that
    # dropped the row or made it `False` would be 2.14's bug.
    results = document.parse_mrz(zone).check_digit_results

    assert [result.passed for result in results] == verdicts


def test_a_td1_record_carries_line_three_s_name_as_printed_though_nothing_reads_it():
    # The gap is in the three derived attributes and not in the evidence: the
    # thirty characters are in `sources` under the layout's own name, so a
    # caller can reach them without 3.14 inventing a reader for a field the
    # standard does print.
    parsed = document.parse_mrz(TD1_ZONE)

    assert parsed.name is None
    assert parsed.surname is None
    assert parsed.given_names is None
    assert parsed.sources["name"] == TD1_ZONE[2]


def test_a_td2_record_reads_its_name_the_way_a_td3_does():
    # Same field, same MRZ shape, so the same pipeline -- imported from td3
    # rather than reimplemented, which the identity of the halves is the
    # evidence for.
    parsed = document.parse_mrz(TD2_ZONE)

    assert parsed.surname == "ERIKSSON"
    assert parsed.given_names == ("ANNA", "MARIA")
    assert parsed.name == "ERIKSSON<<ANNA<MARIA<<<<<<<<<<<"


def test_the_sources_map_is_complete_for_whichever_format_was_parsed():
    # Every field every layout of that format states, in printed order, and
    # concatenating a line's own fields rebuilds it.  A map that is only the
    # parts someone thought to keep would make `sources` a summary of the
    # parse rather than evidence of it.
    assert set(document.parse_mrz(TD1_ZONE).sources) == {
        name
        for layout in td1.TD1.values()
        for name in layout
    }
    assert set(document.parse_mrz(TD2_ZONE).sources) == {
        name for layout in td2.TD2.values() for name in layout
    }
    assert set(document.parse_mrz(TD3_ZONE).sources) == {
        name for layout in td3.TD3.values() for name in layout
    }


# --- the unrecognised shape ----------------------------------------------


@pytest.mark.parametrize(
    "zone",
    [
        [],  # no lines at all
        [TD3_ZONE[0]],  # one line of 44
        [TD1_ZONE[0], TD1_ZONE[1]],  # a TD1 missing its name line
        [TD1_ZONE[0]] * 4,  # a fourth line of 30
        [TD3_ZONE[0]] * 3,  # three lines of 44 -- a TD3 with a line too many
        [TD2_ZONE[0], TD2_ZONE[1]] * 2,  # four lines of 36
        [TD3_ZONE[0][:43], TD3_ZONE[1]],  # a TD3 one character short
        [TD3_ZONE[0], TD3_ZONE[1][:43]],  # the same on line 2
        [TD2_ZONE[0], TD1_ZONE[1]],  # ragged: 36 and 30
        [None, None],  # lines that are not strings at all
        [TD3_ZONE[0], 44],  # one good line and one integer
    ],
)
def test_a_shape_this_project_does_not_read_is_refused_by_name(zone):
    # Every one of these is a *shape* question and not a document question:
    # none of them is refused for what it says, and none of them may reach a
    # format's readers, because a reader given the wrong line will not object
    # (3.10) and a report of "the document number is not a document number"
    # would be an invention.
    with pytest.raises(mrz.MrzValueError) as caught:
        document.parse_mrz(zone)

    assert "does not name a machine-readable zone" in str(caught.value)
    for name in ("TD1", "TD2", "TD3"):
        assert name in str(caught.value)


@pytest.mark.parametrize("zone", ["x" * 44, None, 44, {"line": 1}])
def test_something_that_is_not_a_zone_at_all_is_refused_as_the_wrong_thing(zone):
    # A string is a sequence of one-character lines, so measuring it would
    # report 44 lines and point at the wrong mistake; `None` and a dict are
    # not sequences of strings and would otherwise escape as a bare
    # `TypeError` a caller catching `MrzValueError` would never see.
    with pytest.raises(mrz.MrzValueError) as caught:
        document.parse_mrz(zone)

    assert "machine-readable zone" in str(caught.value)


@pytest.mark.parametrize("length", [30, 36, 44])
def test_one_string_of_zones_length_is_refused_as_the_string_it_is(length):
    # The message is the diagnosis, and iterating a string would report `length`
    # one-character lines instead -- a caller would be told to go and find the
    # missing `length - 1` lines of a document that arrived as one string.
    with pytest.raises(mrz.MrzValueError) as caught:
        document.parse_mrz("x" * length)

    assert f"one string of {length} characters" in str(caught.value)


def test_the_refusal_names_the_shape_and_never_echoes_a_character():
    # Widths are shape -- how many characters a line has -- and the
    # characters are the identity data the screening is about, so a message
    # may carry the first and must not carry the second.  Asserted by taking
    # a real specimen and checking that none of its own fields appear in the
    # complaint about it.
    edited = [TD3_ZONE[0], TD3_ZONE[1][:20]]

    with pytest.raises(mrz.MrzValueError) as caught:
        document.parse_mrz(edited)

    message = str(caught.value)
    assert "2 lines of 44 and 20 characters" in message
    for line in edited:
        for start in range(len(line) - 5):
            assert line[start : start + 6] not in message


def test_a_zone_of_the_right_shape_but_the_wrong_document_is_the_reader_s_fault():
    # Three lines of 30 with a passport code in positions 1-2: the dispatcher
    # must hand it to the TD1 parser rather than notice, because "a TD1 is
    # three lines of 30" is a claim about the shape and `TD1_DOCUMENT_CODES`
    # is the format's own list.  The error is therefore that reader's own
    # message, naming the field and the two codes that are allowed.
    zone = ["P<UTO" + TD1_ZONE[0][5:], TD1_ZONE[1], TD1_ZONE[2]]

    with pytest.raises(mrz.MrzValueError) as caught:
        document.parse_mrz(zone)
    with pytest.raises(mrz.MrzValueError) as from_the_reader:
        td1.parse_document_code(zone[0])

    message = str(caught.value)
    assert message == str(from_the_reader.value)  # the reader's own message
    assert "document code" in message
    assert "P<" in message
    assert "does not name a machine-readable zone" not in message


def test_a_malformed_line_is_reported_by_the_format_s_own_gate():
    # Uniform-width detection, then the gate.  A zone of three 30-character
    # lines is a TD1 by shape even when one of them carries a date that could
    # not exist, and the error that says so is the field reader's own -- it
    # names the field and the component at fault, never the date.
    zone = [TD1_ZONE[0], "9931992F1204159UTO<<<<<<<<<<<7", TD1_ZONE[2]]

    with pytest.raises(mrz.MrzValueError) as caught:
        document.parse_mrz(zone)

    message = str(caught.value)
    assert "date of birth" in message
    assert "month" in message
    assert "993199" not in message


# --- the discriminator, and the decisions it rests on ---------------------


def test_the_record_carries_a_format_discriminator_and_nothing_else_new():
    # The fourteen printed fields of a TD3 in printed order, then the three
    # verdicts, the two derived name halves, the raw map, the five optional
    # data attributes the other two formats print and a TD3 does not, and the
    # discriminator last.  A field added to the record without a place in this
    # list fails here rather than going missing quietly.
    assert [field.name for field in dataclasses.fields(document.MrzDocument)] == (
        [
            "document_code",
            "issuing_state",
            "name",
            "document_number",
            "document_number_check_digit",
            "nationality",
            "date_of_birth",
            "date_of_birth_check_digit",
            "sex",
            "date_of_expiry",
            "date_of_expiry_check_digit",
            "personal_number",
            "personal_number_check_digit",
            "composite_check_digit",
            "check_digit_results",
            "surname",
            "given_names",
            "sources",
        ]
        + ["optional_data_1", "optional_data_1_check_digit", "optional_data_2"]
        + ["optional_data", "optional_data_check_digit"]
        + ["format"]
    )


def test_all_three_records_are_the_same_type_and_say_which_format_they_are():
    # One record for three documents, told apart by the discriminator.  Three
    # separate types would have been the alternative, and the cost of it is
    # that a caller holding a zone and no idea what it is would have to
    # branch on the type instead of reading a field.
    records = [document.parse_mrz(zone) for zone in (TD1_ZONE, TD2_ZONE, TD3_ZONE)]

    assert {type(record) for record in records} == {document.MrzDocument}
    assert [record.format for record in records] == ["TD1", "TD2", "TD3"]


def test_the_two_tables_agree_and_no_shape_can_match_two_formats():
    # `MRZ_SHAPES` names a format and `MRZ_PARSERS` is reached by that name,
    # so a row added to one and not the other would dispatch to nothing --
    # a `KeyError`, from a function whose contract is to raise `MrzValueError`
    # for anything it cannot read.  The counts and widths are checked distinct
    # rather than assumed: two entries sharing both would be a tie with no
    # tiebreak, and a dict would silently pick one.
    assert set(document.MRZ_SHAPES.values()) == set(document.MRZ_PARSERS)
    assert len(set(document.MRZ_SHAPES)) == 3
    assert set(document.MRZ_SHAPES) == {
        (3, 30),
        (2, 36),
        (2, 44),
    }


def test_the_shapes_come_from_each_format_s_own_constants_not_from_retyping_them():
    # A width corrected in `td2.py` has to be corrected here by construction.
    # The count is asserted as well as the length, because "two lines of 36 is
    # a TD2" is a claim about both numbers and only the second is obvious.
    assert document.MRZ_SHAPES == {
        (td1.TD1_LINE_COUNT, td1.TD1_LINE_LENGTH): "TD1",
        (td2.TD2_LINE_COUNT, td2.TD2_LINE_LENGTH): "TD2",
        (td3.TD3_LINE_COUNT, td3.TD3_LINE_LENGTH): "TD3",
    }


def test_the_record_still_comes_from_the_td3_module_that_declared_it():
    # 3.1 declared the record next to the parser that first returned one, and
    # 3.14 made it the common currency rather than moving a type that 500
    # lines of `test_td3.py` pin.  One declaration, imported by everyone.
    assert document.MrzDocument is td3.MrzDocument
    assert td1.MrzDocument is td3.MrzDocument
    assert td2.MrzDocument is td3.MrzDocument


def test_the_record_is_still_a_frozen_dataclass_in_all_three_formats():
    # Frozen for the reason 3.1 gave: nothing downstream has any business
    # editing the nationality of the document it is screening, and a record
    # that could be edited would let a cleaned-up field look exactly like a
    # read one.  Checked through a TD1 and a TD2, not only a TD3, because
    # those are the records that did not exist before this task.
    assert dataclasses.is_dataclass(document.MrzDocument)
    assert document.MrzDocument.__dataclass_params__.frozen is True

    for zone in (TD1_ZONE, TD2_ZONE, TD3_ZONE):
        with pytest.raises(dataclasses.FrozenInstanceError):
            document.parse_mrz(zone).nationality = "XXX"


def test_the_record_carries_no_reference_date_and_no_inferred_year():
    # 3.14 is the first task that puts the two century inferences anywhere,
    # and the decision is that it does not.  Two nullable year fields would
    # put two readings of one field on one record; a `reference` attribute is
    # the one shape that could put `datetime.now()` back at the edge of the
    # package, which `tasks.md` bans inside check logic.  So the years stay
    # with the caller, who asks `mrz` about the printed field directly -- and
    # the two names are asserted absent rather than merely unused.
    names = {field.name for field in dataclasses.fields(document.MrzDocument)}

    assert "reference" not in names
    assert "reference_date" not in names
    assert "birth_year" not in names
    assert "expiry_year" not in names
    assert {"date_of_birth", "date_of_expiry"} <= names


def test_the_dispatcher_module_names_no_date_and_infers_no_century():
    # The two claims above are only worth something if this module holds to
    # them, and a walk over the AST rather than a substring test is what holds
    # it: the module's own docstring names `datetime.now()`, `infer_birth_year`
    # and `infer_expiry_year` in order to say it uses none of the three, so a
    # test that read the source would have to forbid the sentences that
    # document the rule.
    tree = ast.parse(pathlib.Path(document.__file__).read_text(encoding="utf-8"))
    names = {
        node.id if isinstance(node, ast.Name) else node.attr
        for node in ast.walk(tree)
        if isinstance(node, (ast.Name, ast.Attribute))
    }

    assert "datetime" not in names
    assert "infer_birth_year" not in names
    assert "infer_expiry_year" not in names


def test_a_caller_can_ask_about_the_century_without_the_record_helping():
    # The positive half of the decision above: the printed field is the
    # argument, so nothing has to be plumbed through the record to get there.
    parsed = document.parse_mrz(TD3_ZONE)
    reference = datetime.date(2026, 9, 30)

    assert mrz.infer_birth_year(parsed.date_of_birth, reference) == 1974
    # 2012 has passed, so the nearest year ahead carrying "12" is 2112 -- the
    # two rules disagreeing here is 3.13's whole point, and a record that
    # answered both with one function would get one of these wrong.
    assert mrz.infer_expiry_year(parsed.date_of_expiry, reference) == 2112


def test_no_format_module_reaches_the_dispatcher_and_the_dispatcher_reaches_no_field():
    # The import direction, which is what keeps a cycle impossible and a
    # second set of rules from appearing: the three formats know nothing about
    # each other, and `document.py` calls their parsers rather than reading a
    # field of its own.  Asserted on the modules, not the docstrings.
    for module in (td1, td2, td3):
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert "from .document" not in source
        assert "parse_mrz" not in source

    assert "td1_field(" not in source_of(document)
    assert "td2_field(" not in source_of(document)
    assert "td3_field(" not in source_of(document)


def test_the_dispatcher_does_not_reach_into_a_format_for_a_field():
    # And the same claim stated on the code rather than on the prose: the
    # only names this module takes from a format are its two constants, its
    # parser and its record.  A field reader here would be a fourth copy of
    # a position, and the handover's rule is that a format may delegate but
    # may not reimplement -- which cuts both ways.
    source = source_of(document)

    for name in ("parse_document_number", "validate_document_number", "char_value"):
        assert name not in source


def test_detect_mrz_format_is_answered_by_the_shape_and_by_nothing_else():
    # Two zones that differ in every character and agree in shape read the
    # same, which is the whole contract: a dispatcher's job is to find out
    # which reader to hand the lines to, and a reader that also judged would
    # be a fourth set of rules nobody wrote a standard section for.
    nonsense = ["?" * 30] * 3
    passport = ["P" * 30] * 3

    assert document.detect_mrz_format(nonsense) == document.detect_mrz_format(
        passport
    ) == "TD1"


def test_parse_mrz_takes_any_iterable_of_lines_and_returns_in_printed_order():
    # The OCR step hands over a list or a tuple, and a generator is the same
    # question asked lazily: the dispatcher materialises the zone once to
    # count it, and the parser it then calls is handed the same lines.
    for zone in (tuple(TD3_ZONE), (line for line in TD3_ZONE)):
        assert document.parse_mrz(zone).format == "TD3"


def test_the_dispatcher_module_documents_the_task_it_serves():
    assert document.__doc__ is not None


def test_the_dispatcher_reports_a_format_rather_than_a_parser_name():
    # `MRZ_PARSERS` is looked up by the value `MRZ_SHAPES` returns, so the
    # two cannot drift into a pair of different vocabularies -- and the
    # detector's own answer is what a caller reads, so it is the three names
    # the standard uses.
    assert set(document.detect_mrz_format(zone) for zone in (TD1_ZONE, TD2_ZONE, TD3_ZONE)) == {
        "TD1",
        "TD2",
        "TD3",
    }
    assert all(
        parser.__name__ == f"parse_{name.lower()}" for name, parser in document.MRZ_PARSERS.items()
    )
