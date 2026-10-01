"""One value, one spelling: the bytes 9.3 hashes and 9.17 recomputes.

Task 9.1 asks for ``canonical_json(obj)`` and one test: key order in the
input does not change the output.  Each of the five named rules is pinned
here -- sorted keys, no whitespace, explicit nulls, no floats, dates as ISO
strings -- plus the two type questions the task leaves open (bool is not the
integer behind it, and an unsupported type is refused rather than stringified).
9.2 adds the three deeper pins: unicode, nesting, and a float refused from
inside an array.
"""

import datetime as dt
import uuid

import pytest

from app.ledger.canonical import CanonicalJsonError, canonical_json


# --- one value, one spelling ------------------------------------------------


def test_the_key_order_of_the_input_does_not_change_the_output() -> None:
    """The task's test, and the claim the whole of Part 9 rests on.

    Two dicts built in opposite orders are equal objects, so they must spell
    equally -- otherwise the same screening would hash differently depending
    on which column a writer happened to touch first.
    """
    first = {"actor": "station-3", "band": "review", "event_type": "overridden"}
    second = {"event_type": "overridden", "band": "review", "actor": "station-3"}

    assert first == second
    assert canonical_json(first) == canonical_json(second)


def test_keys_are_spelled_in_sorted_order_rather_than_in_the_order_given() -> None:
    assert canonical_json({"b": 1, "a": 2, "c": 3}) == '{"a":2,"b":1,"c":3}'


def test_there_is_no_whitespace_between_the_tokens() -> None:
    """A space is a byte a writer could add and a verifier would not."""
    spelled = canonical_json({"a": 1, "b": [1, 2], "c": {"d": "e"}})

    assert spelled == '{"a":1,"b":[1,2],"c":{"d":"e"}}'
    assert " " not in spelled


def test_a_list_keeps_the_order_it_arrived_in() -> None:
    """Sorting is for keys; an array's order is part of its value."""
    assert canonical_json({"a": [3, 1, 2]}) == '{"a":[3,1,2]}'


# --- the four rules that are not sorted keys --------------------------------


def test_a_null_is_written_rather_than_dropped() -> None:
    """Dropping it would let ``{"a": null}`` and ``{}`` hash alike.

    ``Screening.score`` and the rest of the result columns are nullable, so a
    record read back from storage carries real ``None``s.
    """
    assert canonical_json({"a": None, "b": 1}) == '{"a":null,"b":1}'


def test_a_float_is_refused_rather_than_spelled() -> None:
    """``score`` is a float on the row, and its shortest repr is Python's
    decision rather than a canonical one."""
    with pytest.raises(CanonicalJsonError) as caught:
        canonical_json({"payload": {"score": 41.7}})

    assert "float" in str(caught.value)


def test_a_datetime_is_spelled_as_an_iso_string() -> None:
    when = dt.datetime(2026, 2, 1, 9, 0, tzinfo=dt.timezone.utc)

    assert canonical_json({"created_at": when}) == (
        '{"created_at":"2026-02-01T09:00:00+00:00"}'
    )


def test_one_instant_has_one_spelling_whatever_offset_it_carries() -> None:
    """The same instant written in two zones is the same record, so it must
    hash as one -- D46's offset question applied to a serialisation."""
    east = dt.datetime(
        2026, 2, 1, 14, 30, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30))
    )
    utc = dt.datetime(2026, 2, 1, 9, 0, tzinfo=dt.timezone.utc)

    assert east == utc
    assert canonical_json({"created_at": east}) == canonical_json(
        {"created_at": utc}
    )


def test_a_naive_datetime_is_spelled_as_the_wall_clock_it_is() -> None:
    """SQLite hands a ``DateTime(timezone=True)`` column back without a
    timezone (measured in 8.4), and 9.17 recomputes a hash from exactly such
    a read -- so a naive stamp is spelled as it stands rather than refused,
    and is not silently read as UTC.
    """
    naive = dt.datetime(2026, 2, 1, 9, 0)

    assert canonical_json({"created_at": naive}) == (
        '{"created_at":"2026-02-01T09:00:00"}'
    )
    assert canonical_json({"created_at": naive}) != canonical_json(
        {"created_at": naive.replace(tzinfo=dt.timezone.utc)}
    )


def test_a_date_is_spelled_as_an_iso_string() -> None:
    assert canonical_json({"expires_on": dt.date(2027, 1, 31)}) == (
        '{"expires_on":"2027-01-31"}'
    )


# --- the two type questions the task leaves open ----------------------------


def test_a_bool_is_a_json_boolean_and_not_the_integer_behind_it() -> None:
    """``bool`` is a subclass of ``int``, so the two must not collide --
    a record field changed from ``1`` to ``true`` has to change the digest.
    """
    assert canonical_json({"override": True}) == '{"override":true}'
    assert canonical_json({"override": False}) == '{"override":false}'
    assert canonical_json({"override": True}) != canonical_json({"override": 1})


def test_a_key_that_is_not_text_is_refused() -> None:
    with pytest.raises(CanonicalJsonError) as caught:
        canonical_json({7: "seven"})

    assert "int" in str(caught.value)


def test_an_unsupported_type_is_refused_rather_than_stringified() -> None:
    """A set has no order and a UUID has two spellings; neither is guessed."""
    for unsupported in ({"b", "a"}, b"bytes", uuid.uuid4(), object()):
        with pytest.raises(CanonicalJsonError):
            canonical_json({"payload": unsupported})


def test_a_refusal_names_the_path_and_never_the_value() -> None:
    """A record's values are where document-derived text arrives, so the
    message names the field that was refused and the type it was."""
    printed = "L898902C<3UTO6908061F9406236ZE184226<7390"

    with pytest.raises(CanonicalJsonError) as caught:
        canonical_json({"payload": {"mrz_line": [printed, object()]}})

    message = str(caught.value)
    assert "$.payload.mrz_line[1]" in message
    assert "object" in message
    assert printed not in message


# --- 9.2: unicode ----------------------------------------------------------


def test_an_accented_name_spells_as_escapes_and_not_as_the_character() -> None:
    """``ensure_ascii=True`` is load-bearing: the digest is taken over bytes,
    and one spelling of those bytes is what a second process must reproduce."""
    assert canonical_json({"nom": "MÜLLER"}) == '{"nom":"M\\u00dcLLER"}'


def test_a_non_latin_name_spells_as_escapes_and_the_text_stays_ascii() -> None:
    """A name read from a document can be in any script, and the spelled text
    is pure ASCII, so encoding it before hashing can never be the failing
    step."""
    spelled = canonical_json({"nom": "日本語"})

    assert spelled == '{"nom":"\\u65e5\\u672c\\u8a9e"}'
    spelled.encode("ascii")


def test_a_key_that_is_not_ascii_is_escaped_too() -> None:
    """Sorting is over code points and printing over ASCII; a non-ASCII key
    must not slip past the second of those."""
    assert canonical_json({"café": 1}) == '{"caf\\u00e9":1}'


def test_a_lone_surrogate_spells_rather_than_raising() -> None:
    """A damaged name field can carry an unpaired surrogate, which is a
    ``str`` Python holds happily.  It has to reach 9.3 as escaped text the
    caller can encode, not as a ``UnicodeEncodeError`` mid-hash."""
    spelled = canonical_json({"nom": "a\ud800"})

    assert spelled == '{"nom":"a\\ud800"}'
    spelled.encode("ascii")


def test_a_name_is_not_normalised_so_two_spellings_stay_different() -> None:
    """A precomposed and a decomposed accent are two code-point sequences,
    and the serialiser says so rather than guessing which one the document
    held -- 9.17 recomputes from stored bytes and could not repair it."""
    precomposed = canonical_json({"nom": "é"})
    decomposed = canonical_json({"nom": "e" + chr(0x0301)})

    assert precomposed == '{"nom":"\\u00e9"}'
    assert decomposed == '{"nom":"e\\u0301"}'
    assert precomposed != decomposed


# --- 9.2: nested objects ---------------------------------------------------


def test_a_nested_objects_keys_are_sorted_too() -> None:
    """9.1's claim one level down: the sort has to reach every object,
    because a record's payload is where the nesting lives."""
    first = {"payload": {"band": "review", "actor": "station-3"}}
    second = {"payload": {"actor": "station-3", "band": "review"}}

    assert first == second
    assert canonical_json(first) == canonical_json(second)
    assert canonical_json(first) == '{"payload":{"actor":"station-3","band":"review"}}'


def test_the_sorting_reaches_every_level_of_a_three_deep_record() -> None:
    """One spelling of the whole record, whichever order each level arrived
    in -- the shape a screening record actually takes."""
    ordered = {
        "event_type": "overridden",
        "payload": {
            "flags": [{"id": "DATE_MISMATCH", "value": 0}],
            "score": "41.7",
        },
    }
    shuffled = {
        "payload": {
            "score": "41.7",
            "flags": [{"value": 0, "id": "DATE_MISMATCH"}],
        },
        "event_type": "overridden",
    }

    assert ordered == shuffled
    assert canonical_json(ordered) == canonical_json(shuffled)
    assert canonical_json(ordered) == (
        '{"event_type":"overridden","payload":{"flags":[{"id":"DATE_MISMATCH",'
        '"value":0}],"score":"41.7"}}'
    )


def test_an_array_of_objects_sorts_each_object_but_not_the_array() -> None:
    """Array order is part of the value; key order inside each element is not.
    A contributions list relies on exactly that distinction."""
    first = canonical_json(
        {"contributions": [{"id": "a", "weight": 3}, {"weight": 1, "id": "b"}]}
    )
    second = canonical_json(
        {"contributions": [{"weight": 1, "id": "b"}, {"weight": 3, "id": "a"}]}
    )

    assert first == '{"contributions":[{"id":"a","weight":3},{"id":"b","weight":1}]}'
    assert first != second


def test_an_empty_object_and_an_empty_array_stay_distinct() -> None:
    """``{}`` and ``[]`` are different values and must not collapse, or an
    empty payload would read as an absent one."""
    assert canonical_json({"payload": {}}) == '{"payload":{}}'
    assert canonical_json({"payload": []}) == '{"payload":[]}'


# --- 9.2: a float refused from inside an array ------------------------------


def test_a_float_nested_inside_an_array_is_refused_and_names_its_slot() -> None:
    """The refusal reaches into arrays -- a contributions list is where a
    float would actually sit -- and the path has to be the slot's."""
    with pytest.raises(CanonicalJsonError) as caught:
        canonical_json(
            {"payload": {"contributions": [{"id": "a"}, {"id": "b", "value": 0.5}]}}
        )

    message = str(caught.value)
    assert "$.payload.contributions[1].value" in message
    assert "float" in message


def test_an_int_in_the_slot_spells_where_a_float_is_refused() -> None:
    """Same record, same field, one value changed -- the reason refusing is
    the honest answer: the two can never be allowed to spell alike."""
    with pytest.raises(CanonicalJsonError):
        canonical_json({"payload": {"value": 0.5}})

    assert canonical_json({"payload": {"value": 1}}) == '{"payload":{"value":1}}'


def test_a_refused_record_leaves_the_value_it_was_given_unchanged() -> None:
    """The refusal happens mid-walk, so the caller's object has to survive it
    -- a writer that catches the error cannot be left holding a half-rewritten
    record to retry or log."""
    record = {"payload": {"contributions": [{"id": "a"}, {"id": "b", "value": 0.5}]}}
    before = {"payload": {"contributions": [{"id": "a"}, {"id": "b", "value": 0.5}]}}

    with pytest.raises(CanonicalJsonError):
        canonical_json(record)

    assert record == before
    record["payload"]["contributions"][1]["value"] = "0.5"
    assert canonical_json(record) == (
        '{"payload":{"contributions":[{"id":"a"},{"id":"b","value":"0.5"}]}}'
    )
