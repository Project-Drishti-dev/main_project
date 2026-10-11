"""27.4 -- the ground-truth manifest schema, and every drawn page against it.

The subject of this file is that the corpus's ground truth is a *declaration*
rather than a reading: the keys a manifest holds, the kind of value each takes
and what must be true of the page behind them are stated once, and a manifest
built out of a drawn page is checked against exactly that.  Every document the
generator can draw validates, and every rule in the schema has a manifest it
refuses -- a rule nothing refuses could be deleted and the sweep would still be
green.  What is *not* claimed is that anything has been measured against one:
no harness has read a manifest yet, which is 27.5.
"""

import copy
import json

import pytest

from tests.fixtures import document_corpus, document_manifest


#: The seeds the sweep is drawn over, and the document types, both read out of
#: the generator rather than restated here.
SEEDS = (0, 1, 2)
DOCUMENT_TYPES = tuple(document_corpus.DOCUMENT_TYPES)

#: No injection, each of the four alone, and all four on one page.  A schema
#: checked only against a fully tampered page would say nothing about a clean
#: one, and checked only against a clean page nothing about an injection.
TAMPER_SELECTIONS = (
    (),
    *((kind,) for kind in document_corpus.TAMPER_KINDS),
    document_corpus.TAMPER_KINDS,
)

#: Every page the sweep draws, as the three arguments the generator takes.
PAGES = tuple(
    (document_type, seed, tampers)
    for document_type in DOCUMENT_TYPES
    for seed in SEEDS
    for tampers in TAMPER_SELECTIONS
)

#: Where each kind sits in the fully tampered page, read out of the order the
#: generator injects in rather than written down beside it.
TAMPER_INDEX = {
    kind: number for number, kind in enumerate(document_corpus.TAMPER_KINDS)
}

def tampered():
    """The manifest of one passport seed 0 page carrying all four injections."""
    return document_manifest.manifest(
        document_corpus.generate(
            0, document_type="passport", tampers=document_corpus.TAMPER_KINDS
        )
    )


def page(document_type="passport", seed=0, tampers=()):
    """One drawn page, straight from the generator."""
    return document_corpus.generate(seed, document_type=document_type, tampers=tampers)


def manifest_of(document_type="passport", seed=0, tampers=()):
    """The manifest of one drawn page."""
    return document_manifest.manifest(page(document_type, seed, tampers))


def ids(case):
    """A page's place in the sweep, readable in a failed case's name."""
    document_type, seed, tampers = case
    return f"{document_type}-{seed}-{'+'.join(tampers) or 'clean'}"


def _with(record, path, value):
    """A copy of ``record`` with the value at ``path`` replaced by ``value``."""
    body = copy.deepcopy(record)
    target = body
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = value
    return body


def _without(record, path):
    """A copy of ``record`` with the key at ``path`` taken out."""
    body = copy.deepcopy(record)
    target = body
    for step in path[:-1]:
        target = target[step]
    del target[path[-1]]
    return body


#: One way a manifest can be broken, and the complaint each must draw.  Every
#: entry breaks a different rule, and the sweep below is what says the rules
#: left unbroken by this table are the ones still standing.
BROKEN = (
    (
        "a key the schema declares, removed",
        lambda record: _without(record, ["size"]),
        "holds no 'size'",
    ),
    (
        "a key the schema does not declare",
        lambda record: _with(record, ["confidence"], 0.91),
        "holds 'confidence', which its schema does not declare",
    ),
    (
        "a version from another schema",
        lambda record: _with(record, ["schema_version"], 99),
        "schema_version is not a version this schema declares",
    ),
    (
        "a size of one number",
        lambda record: _with(record, ["size"], [1000]),
        "size is not a width and a height in pixels",
    ),
    (
        "a box whose right is left of its left",
        lambda record: _with(record, ["portrait"], [900, 0, 100, 20]),
        "portrait is not a half-open box",
    ),
    (
        "a label a printed row does not hold",
        lambda record: _without(record, ["printed", 0, "label"]),
        "the manifest.printed[0] holds no 'label'",
    ),
    (
        "a line numbered from zero",
        lambda record: _with(record, ["mrz", 0, "line_number"], 0),
        "line_number is not a zone line numbered from one",
    ),
    (
        "a confidence on one injection",
        lambda record: _with(
            record, ["tampering", TAMPER_INDEX["stamp_edit"], "confidence"], 0.5
        ),
        "the manifest.tampering[3] holds 'confidence'",
    ),
    (
        "a manifest not saying it is synthetic",
        lambda record: _with(record, ["synthetic"], False),
        "the manifest does not say it is synthetic",
    ),
    (
        "a generator that did not draw it",
        lambda record: _with(record, ["generator"], "tests.fixtures.document_images"),
        "names 'tests.fixtures.document_images' as its generator",
    ),
    (
        "an id naming another seed",
        lambda record: _with(record, ["document_id"], "passport-9999"),
        "the id 'passport-9999' does not name the passport seed 0 draws",
    ),
    (
        "a format the document type does not carry",
        lambda record: _with(record, ["format"], "TD1"),
        "the manifest calls a passport a TD1, not a TD3",
    ),
    (
        "a format this project does not know",
        lambda record: _with(record, ["format"], "TD9"),
        "format is not an MRZ format this project knows",
    ),
    (
        "a document type the generator does not draw",
        lambda record: _with(record, ["document_type"], "driving_licence"),
        "document_type is not a document type the generator draws",
    ),
    (
        "a negative seed",
        lambda record: _with(record, ["seed"], -1),
        "seed is not a seed the generator could have drawn",
    ),
    (
        "a printed row recorded twice",
        lambda record: _with(
            record, ["printed"], record["printed"] + [record["printed"][0]]
        ),
        "printed row 'surname' is recorded twice",
    ),
    (
        "a box off the page",
        lambda record: _with(
            record,
            ["tampering", TAMPER_INDEX["photo_replacement"], "box"],
            [0, 0, record["size"][0] + 5, 20],
        ),
        "so tampering[0] [0, 0, 1005, 20] runs off it",
    ),
    (
        "a zone line with more cells than characters",
        lambda record: _with(
            record, ["cells", 0], record["cells"][0] + [record["cells"][0][-1]]
        ),
        "zone line 1 prints",
    ),
    (
        "an MRZ field the format does not print",
        lambda record: _with(record, ["mrz", 0, "name"], "signature"),
        "a TD3 prints no MRZ field named 'signature'",
    ),
    (
        "an MRZ field recorded twice",
        lambda record: _with(record, ["mrz"], record["mrz"] + [record["mrz"][0]]),
        "MRZ field 'document_code' is recorded twice",
    ),
    (
        "an MRZ field that rebuilds no line",
        lambda record: _with(
            record, ["mrz", 0, "value"], record["mrz"][0]["value"] + "X"
        ),
        "do not rebuild the zone lines",
    ),
    (
        "an MRZ field named a line the zone does not print",
        lambda record: _with(record, ["mrz", 0, "line_number"], 9),
        "mrz[0] names line 9",
    ),
    (
        "a tamper the generator does not inject",
        lambda record: _with(
            record, ["tampering", 0, "kind"], "photo_swap"
        ),
        "'photo_swap' is not a tamper this generator injects",
    ),
    (
        "a tamper recorded twice",
        lambda record: _with(
            record, ["tampering"], record["tampering"] + [record["tampering"][0]]
        ),
        "tamper 'photo_replacement' is recorded twice",
    ),
    (
        "a text edit aiming at another row",
        lambda record: _with(
            record, ["tampering", TAMPER_INDEX["text_edit"], "field"], "sex"
        ),
        "edits 'sex', not the row 'document_number' its kind edits",
    ),
    (
        "a text edit changing nothing",
        lambda record: _with(
            record,
            ["tampering", TAMPER_INDEX["text_edit"], "original"],
            record["tampering"][TAMPER_INDEX["text_edit"]]["replacement"],
        ),
        "records no text change",
    ),
    (
        "a replacement the page does not print",
        lambda record: _with(
            record,
            ["tampering", TAMPER_INDEX["text_edit"], "replacement"],
            record["tampering"][TAMPER_INDEX["text_edit"]]["original"],
        ),
        "leaves row 'document_number' printing",
    ),
    (
        "a paste recording text",
        lambda record: _with(
            record, ["tampering", TAMPER_INDEX["stamp_edit"], "field"], "sex"
        ),
        "pastes ink and yet records text",
    ),
    (
        "a region reaching into the zone",
        lambda record: _with(
            record,
            ["tampering", TAMPER_INDEX["date_of_birth_change"], "box"],
            record["cells"][-1][-1],
        ),
        "reaches into zone line",
    ),
)


# --- every drawn page validates against the schema -----------------------


@pytest.mark.parametrize("case", PAGES, ids=ids)
def test_every_generated_document_validates(case):
    """27.4's Verify: the manifest of every page the generator draws is one."""
    document_type, seed, tampers = case
    assert document_manifest.validate(manifest_of(document_type, seed, tampers)) == ()


@pytest.mark.parametrize("document_type", DOCUMENT_TYPES)
@pytest.mark.parametrize("seed", SEEDS)
def test_a_manifest_is_what_a_harness_reads_back(document_type, seed):
    """Plain JSON both ways: 27.5 writes one to disk and reads it off again."""
    record = manifest_of(document_type, seed, document_corpus.TAMPER_KINDS)
    written = json.dumps(record)
    assert json.loads(written) == record
    assert document_manifest.validate(json.loads(written)) == ()


def test_the_sweep_holds_a_clean_page_and_a_fully_tampered_one():
    """The sweep is not one-sided; the injection counts say which pages it holds."""
    carried = {
        len(page(document_type, seed, tampers).tampering)
        for document_type in DOCUMENT_TYPES
        for seed in SEEDS
        for tampers in TAMPER_SELECTIONS
    }
    assert carried == {0, 1, len(document_corpus.TAMPER_KINDS)}


def test_the_sweep_injects_every_kind_the_generator_offers():
    """A fifth kind added to the generator is swept here without being named."""
    covered = {kind for tampers in TAMPER_SELECTIONS for kind in tampers}
    assert covered == set(document_corpus.TAMPER_KINDS)


# --- the schema is a closed declaration, read out of the generator ------


def test_a_manifest_holds_exactly_the_keys_its_schema_declares():
    """No key missing and none extra, at every level of the record."""
    record = manifest_of(tampers=document_corpus.TAMPER_KINDS)
    assert set(record) == set(document_manifest.DOCUMENT_SCHEMA)
    assert set(record["printed"][0]) == set(document_manifest.PRINTED_SCHEMA)
    assert set(record["mrz"][0]) == set(document_manifest.MRZ_SCHEMA)
    assert set(record["tampering"][0]) == set(document_manifest.TAMPER_SCHEMA)


def test_every_rule_says_what_it_accepts():
    """A rule added without a description is reported as ``None`` otherwise."""
    tables = (
        document_manifest.DOCUMENT_SCHEMA,
        document_manifest.PRINTED_SCHEMA,
        document_manifest.MRZ_SCHEMA,
        document_manifest.TAMPER_SCHEMA,
    )
    rules = {
        rule
        for table in tables
        for rule in table.values()
        if callable(rule)
    }
    assert rules
    assert all(getattr(rule, "description", None) for rule in rules)


# --- every rule refuses something ---------------------------------------


@pytest.mark.parametrize("broken", BROKEN, ids=[case[0] for case in BROKEN])
def test_a_broken_manifest_is_reported(broken):
    """One manifest per rule the schema states, and the complaint each draws."""
    _label, breakage, complaint = broken
    record = tampered()
    problems = document_manifest.validate(breakage(record))

    assert problems, "nothing complained about the manifest"
    assert any(complaint in problem for problem in problems), problems