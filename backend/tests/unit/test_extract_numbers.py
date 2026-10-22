"""17.1 -- `extract_numbers`: the numbers a summary carries.

The task's claim has two sides and both are held below: a number in plain
prose is found, and a digit inside a word is not. The second side is the one
that can go quietly wrong, so `sha256`, `mp3`, `x86_64` and `1st` are each
asserted to carry nothing, and one line holds a word and a bare number
together so adjacency rather than a word list is what is being tested.
"""

import ast
from pathlib import Path

import pytest

from app import explain
from app.explain import verifier

extract_numbers = verifier.extract_numbers

#: Prose of the shape 17.5's fallback writes: a score and a count, beside a
#: field name whose digits name a format rather than a measurement.
SUMMARY = (
    "The tampering score of 0.98 dominates, and it was measured on 3 documents "
    "of the case. The checksum was read from a sha256 field."
)


def test_it_finds_the_numbers_in_a_summary():
    assert extract_numbers(SUMMARY) == ("0.98", "3")


@pytest.mark.parametrize(
    "text",
    ["sha256", "mp3", "x86_64", "utf8", "ISO8601", "cv2", "s3", "1st", "2nd", "3rd"],
)
def test_it_reads_no_number_out_of_a_word(text):
    assert extract_numbers(text) == ()


def test_adjacency_is_the_rule_and_not_a_list_of_words():
    assert extract_numbers("sha256 and 256 differ") == ("256",)


def test_a_decimal_is_one_token_kept_as_it_was_written():
    assert extract_numbers("0.98") == ("0.98",)
    assert extract_numbers("12 at 0.5") == ("12", "0.5")


def test_tokens_come_in_the_order_written_and_a_repeat_is_kept():
    assert extract_numbers("3 of 0.98, and 3 again") == ("3", "0.98", "3")


def test_prose_carrying_no_number_answers_an_empty_tuple():
    assert extract_numbers("The document was tampered with.") == ()
    assert extract_numbers("") == ()


def test_the_answer_is_a_tuple_of_strings():
    answer = extract_numbers("0.98")
    assert isinstance(answer, tuple)
    assert all(isinstance(token, str) for token in answer)


def test_the_module_names_what_it_exports():
    assert verifier.__all__ == [
        "extract_numbers",
        "extract_dates",
        "extract_field_names",
        "verify_summary",
    ]


def test_the_package_re_exports_nothing_so_there_is_one_import_path():
    assert not hasattr(explain, "extract_numbers")


def test_the_verifier_imports_the_id_registry_and_no_model():
    tree = ast.parse(Path(verifier.__file__).read_text(encoding="utf-8"))
    roots = set()
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
            modules.add(node.module)
    assert roots == {"re", "app"}
    assert modules == {"app.risk"}
