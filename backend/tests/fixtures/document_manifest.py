"""The ground truth a generated document is measured against, and its schema.

A manifest is one drawn page as plain JSON: what it prints, where every field
sits, which alterations were injected and where each put ink.  :func:`validate`
says whether a record is one -- against the tables below, and against the
cross-checks those tables cannot express, which read the generator's and the
format's own tables rather than restating them.
"""

from app.pipeline.tier0 import mrz_region
from tests.fixtures import document_corpus

__all__ = [
    "DOCUMENT_SCHEMA",
    "GENERATOR",
    "MRZ_SCHEMA",
    "PRINTED_SCHEMA",
    "SCHEMA_VERSION",
    "TAMPER_SCHEMA",
    "document_id",
    "manifest",
    "validate",
]

#: The version a manifest carries, so a harness reading one written against an
#: earlier table refuses it rather than reading a key that has since moved.
SCHEMA_VERSION = 1

#: The module the corpus is drawn from, named by that module itself, so a
#: manifest says which generator wrote it rather than only that one did.
GENERATOR = document_corpus.__name__

#: How many whole numbers a page size and a box hold, read out by both rules.
_PAIRED = 2
_BOXED = 4


def _rule(description):
    """Give the rule ``description`` a failed check is reported with."""

    def describes(function):
        function.description = description
        return function

    return describes


@_rule("text")
def _text(value):
    return isinstance(value, str) and value != ""


@_rule("text or nothing")
def _optional_text(value):
    return value is None or _text(value)


@_rule("a whole number")
def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


@_rule("a version this schema declares")
def _version(value):
    return _integer(value) and value == SCHEMA_VERSION


@_rule("a seed the generator could have drawn")
def _seed(value):
    return _integer(value) and value >= 0


@_rule("true or false")
def _flag(value):
    return isinstance(value, bool)


@_rule("a document type the generator draws")
def _document_type(value):
    return value in document_corpus.DOCUMENT_TYPES


@_rule("an MRZ format this project knows")
def _format(value):
    return value in mrz_region.MRZ_LAYOUTS


@_rule("a zone line numbered from one")
def _line_number(value):
    return _integer(value) and value >= 1


@_rule("a width and a height in pixels")
def _size(value):
    return _whole_numbers(value, _PAIRED) and all(number > 0 for number in value)


@_rule("a half-open box of four whole numbers, left and top before right and bottom")
def _box(value):
    return (
        _whole_numbers(value, _BOXED)
        and 0 <= value[0] < value[2]
        and 0 <= value[1] < value[3]
    )


@_rule("a list of text, one per zone line")
def _lines(value):
    return isinstance(value, list) and all(_text(line) for line in value)


@_rule("one row of boxes per zone line")
def _cells(value):
    return isinstance(value, list) and all(_boxes(row) for row in value)


@_rule("a row of boxes")
def _boxes(value):
    return isinstance(value, list) and all(_box(box) for box in value)


def _whole_numbers(value, count):
    """Whether ``value`` is a list of ``count`` whole numbers."""
    return (
        isinstance(value, list)
        and len(value) == count
        and all(_integer(number) for number in value)
    )


#: One printed row: its name, the label printed beside it, the value, and the
#: box each went in.  ``value_box`` is what 12.14 reports a field's position
#: off and what 27.5 will score an extracted field against.
PRINTED_SCHEMA = {
    "name": _text,
    "label": _text,
    "value": _text,
    "label_box": _box,
    "value_box": _box,
}

#: One MRZ field: the characters it prints, the line the standard gives them,
#: and the box they are printed in.
MRZ_SCHEMA = {
    "name": _text,
    "value": _text,
    "line_number": _line_number,
    "box": _box,
}

#: One injected alteration: its kind, the printed row it re-printed if it
#: re-printed one, the region it changed, and the text before and after.
TAMPER_SCHEMA = {
    "kind": _text,
    "field": _optional_text,
    "box": _box,
    "original": _optional_text,
    "replacement": _optional_text,
}

#: One document.  A key whose rule is itself a table holds a list of records
#: obeying that table; every other key holds one value its rule accepts.
DOCUMENT_SCHEMA = {
    "schema_version": _version,
    "document_id": _text,
    "generator": _text,
    "synthetic": _flag,
    "seed": _seed,
    "document_type": _document_type,
    "format": _format,
    "size": _size,
    "printed": PRINTED_SCHEMA,
    "mrz": MRZ_SCHEMA,
    "mrz_lines": _lines,
    "cells": _cells,
    "portrait": _box,
    "tampering": TAMPER_SCHEMA,
}


def _numbers(box):
    """``box`` as a list of Python ints, so a manifest is plain JSON."""
    return [int(number) for number in box]


def _duplicates(names):
    """The names recorded more than once, in the order they first repeat."""
    seen, repeated = set(), []
    for name in names:
        if name in seen and name not in repeated:
            repeated.append(name)
        seen.add(name)
    return repeated


def _inside(box, size):
    """Whether the half-open ``box`` sits wholly within a ``size`` page."""
    return box[2] <= size[0] and box[3] <= size[1]


def _overlaps(one, other):
    """Whether two half-open boxes overlap."""
    return (
        one[0] < other[2] and other[0] < one[2]
        and one[1] < other[3] and other[1] < one[3]
    )


def _walk(record, schema, where, problems):
    """Report every way ``record`` fails to obey ``schema``."""
    if not isinstance(record, dict):
        problems.append(f"{where} is not an object")
        return
    for key, rule in schema.items():
        if key not in record:
            problems.append(f"{where} holds no {key!r}")
        elif isinstance(rule, dict):
            _records(record[key], rule, f"{where}.{key}", problems)
        elif not rule(record[key]):
            problems.append(f"{where}.{key} is not {rule.description}")
    for key in sorted(record, key=str):
        if key not in schema:
            problems.append(f"{where} holds {key!r}, which its schema does not declare")


def _records(value, schema, where, problems):
    """Report every way the records ``value`` holds fail to obey ``schema``."""
    if not isinstance(value, list):
        problems.append(f"{where} is not a list of records")
        return
    for number, record in enumerate(value):
        _walk(record, schema, f"{where}[{number}]", problems)


def _shape(record):
    """The keys the schema declares, and the kind of value each one holds."""
    problems = []
    _walk(record, DOCUMENT_SCHEMA, "the manifest", problems)
    return problems


def _identity(record):
    """The keys naming the page, checked against each other and the generator."""
    kind = record["document_type"]
    problems = []
    if record["synthetic"] is not True:
        problems.append("the manifest does not say it is synthetic")
    if record["generator"] != GENERATOR:
        problems.append(
            f"the manifest names {record['generator']!r} as its generator, "
            f"not {GENERATOR!r}"
        )
    if record["document_id"] != document_id(record["seed"], kind):
        problems.append(
            f"the id {record['document_id']!r} does not name the {kind} "
            f"seed {record['seed']} draws"
        )
    carried = document_corpus.DOCUMENT_TYPES[kind]
    if record["format"] != carried:
        problems.append(
            f"the manifest calls a {kind} a {record['format']}, not a {carried}"
        )
    return problems


def _geometry(record):
    """Every box the manifest holds, checked against the page it claims."""
    size = record["size"]
    boxes = [(f"printed[{number}].{key}", field[key])
             for number, field in enumerate(record["printed"])
             for key in ("label_box", "value_box")]
    boxes += [(f"mrz[{number}]", field["box"])
              for number, field in enumerate(record["mrz"])]
    boxes += [(f"cells[{line}][{index}]", box)
              for line, row in enumerate(record["cells"])
              for index, box in enumerate(row)]
    boxes += [(f"tampering[{number}]", tamper["box"])
              for number, tamper in enumerate(record["tampering"])]
    boxes.append(("portrait", record["portrait"]))

    problems = [
        f"the manifest holds a {size[0]}x{size[1]} page, so {where} {box} runs off it"
        for where, box in boxes
        if not _inside(box, size)
    ]
    for repeated in _duplicates([field["name"] for field in record["printed"]]):
        problems.append(f"printed row {repeated!r} is recorded twice")
    return problems


def _zone(record):
    """The manifest's zone, checked against the format it claims to carry."""
    lines, cells = record["mrz_lines"], record["cells"]
    problems = []
    if len(cells) != len(lines):
        problems.append(
            f"the manifest holds {len(cells)} cell rows for {len(lines)} zone lines"
        )
    for number, (row, line) in enumerate(zip(cells, lines), start=1):
        if len(row) != len(line):
            problems.append(
                f"zone line {number} prints {len(line)} characters in "
                f"{len(row)} cells"
            )

    layout = mrz_region.MRZ_LAYOUTS[record["format"]]
    printed = {name for spans in layout.values() for name in spans}
    for number, field in enumerate(record["mrz"]):
        if field["name"] not in printed:
            problems.append(
                f"a {record['format']} prints no MRZ field named "
                f"{field['name']!r}, at mrz[{number}]"
            )
    for repeated in _duplicates([field["name"] for field in record["mrz"]]):
        problems.append(f"MRZ field {repeated!r} is recorded twice")

    rebuilt = [""] * len(lines)
    for number, field in enumerate(record["mrz"]):
        line_number = field["line_number"]
        if 1 <= line_number <= len(lines):
            rebuilt[line_number - 1] += field["value"]
        else:
            problems.append(
                f"mrz[{number}] names line {line_number}, which the zone does not print"
            )
    if rebuilt != lines:
        problems.append(
            "the MRZ fields do not rebuild the zone lines the manifest holds"
        )
    return problems


def _tampering(record):
    """Every injection the manifest holds, checked against the generator's kinds."""
    kinds = [tamper["kind"] for tamper in record["tampering"]]
    problems = [
        f"{kind!r} is not a tamper this generator injects"
        for kind in kinds
        if kind not in document_corpus.TAMPER_KINDS
    ]
    for repeated in _duplicates(kinds):
        problems.append(f"tamper {repeated!r} is recorded twice")

    rows = {field["name"]: field["value"] for field in record["printed"]}
    for number, tamper in enumerate(record["tampering"]):
        kind = tamper["kind"]
        if kind not in document_corpus.TAMPER_KINDS:
            continue
        if kind in document_corpus.TAMPER_FIELDS:
            problems += _reprinted(rows, number, tamper)
        else:
            problems += _pasted(number, tamper)
        problems += _inside_zone(record, number, tamper)
    return problems


def _reprinted(rows, number, tamper):
    """The problems with a tamper that re-printed a row rather than pasting ink."""
    kind = tamper["kind"]
    where = f"tampering[{number}] ({kind})"
    field = document_corpus.TAMPER_FIELDS[kind]
    problems = []
    if tamper["field"] != field:
        problems.append(
            f"{where} edits {tamper['field']!r}, not the row {field!r} its kind edits"
        )
    elif rows.get(field) != tamper["replacement"]:
        problems.append(
            f"{where} leaves row {field!r} printing {rows.get(field)!r}, not the "
            f"replacement {tamper['replacement']!r} it claims"
        )
    if tamper["original"] is None or tamper["original"] == tamper["replacement"]:
        problems.append(f"{where} records no text change")
    return problems


def _pasted(number, tamper):
    """The problems with a tamper that pastes a picture or a stamp."""
    recorded = [tamper["field"], tamper["original"], tamper["replacement"]]
    if any(value is not None for value in recorded):
        return [
            f"tampering[{number}] ({tamper['kind']}) pastes ink and yet records "
            f"text: {recorded}"
        ]
    return []


def _inside_zone(record, number, tamper):
    """The problem with a region that reaches into the zone left untouched."""
    for line, row in enumerate(record["cells"], start=1):
        for index, cell in enumerate(row):
            if _overlaps(tamper["box"], cell):
                return [
                    f"tampering[{number}] ({tamper['kind']}) reaches into zone line "
                    f"{line} cell {index}, which no injection in this corpus touches"
                ]
    return []


#: The layers a manifest is checked in, each run only once the one before it
#: has passed, so a record is reported against the first layer that fails it.
_STEPS = (_shape, _identity, _geometry, _zone, _tampering)


def manifest(document):
    """The ground truth ``document`` was drawn from, as plain JSON.

    Every box becomes an array and every number a Python ``int``, so the record
    is what :func:`validate` declares and what a harness can read back off disk.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": document_id(document.seed, document.document_type),
        "generator": GENERATOR,
        "synthetic": True,
        "seed": document.seed,
        "document_type": document.document_type,
        "format": document.format,
        "size": _numbers(document.size),
        "printed": [
            {
                "name": field.name,
                "label": field.label,
                "value": field.value,
                "label_box": _numbers(field.label_box),
                "value_box": _numbers(field.value_box),
            }
            for field in document.printed
        ],
        "mrz": [
            {
                "name": field.name,
                "value": field.value,
                "line_number": field.line_number,
                "box": _numbers(field.box),
            }
            for field in document.mrz
        ],
        "mrz_lines": list(document.mrz_lines),
        "cells": [[_numbers(box) for box in row] for row in document.cells],
        "portrait": _numbers(document.portrait),
        "tampering": [
            {
                "kind": injection.kind,
                "field": injection.field,
                "box": _numbers(injection.box),
                "original": injection.original,
                "replacement": injection.replacement,
            }
            for injection in document.tampering
        ],
    }


def document_id(seed, document_type):
    """The name a harness files one drawn page under, and finds it again by."""
    return f"{document_type}-{seed:04d}"


def validate(record):
    """Every way ``record`` is not a manifest, as strings; ``()`` when it is.

    A layer is only measured once the one above it has passed, so what comes
    back are the first complaints about a record rather than every complaint
    downstream of them.
    """
    for step in _STEPS:
        problems = step(record)
        if problems:
            return tuple(problems)
    return ()