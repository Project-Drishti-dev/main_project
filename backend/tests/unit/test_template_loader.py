"""13.4 and 13.5 -- a committed template loads, and a new one is only a file.

A template is data rather than code, so the claim 13.4 is named for is small
and exact: the JSON this repository ships comes back as a record holding a
document type, a reference frame and a rectangle per field, and every way a
file could be none of those raises rather than answering with a half-read
layout.

**The committed file is read by path as well as through the loader**, so the
loader's answer is held against the file's own bytes rather than against itself
-- the same move ``test_weightset_loader.py`` makes for ``v1.yaml``.

**A layout with no field is a fault, not a template.**  Nothing in Tier 1 asks
for the fields of a document type yet, so the loader deliberately looks up no
name in Python; what it does hold is that a rectangle is a position on the
reference image, which is why the image is opened and why a rectangle outside
it raises.

**13.5 holds the other half of that.**  A document type nothing in Python has
heard of loads through the same call, and no module under ``app/`` names it, so
a new layout is a new JSON file -- which is what the three absences above buy.
"""

import json
from pathlib import Path

import pytest
from PIL import Image

from app.pipeline.tier1 import fields
from app.pipeline.tier1.templates import loader
from app.pipeline.tier1.templates.loader import (
    FieldRect,
    Template,
    TemplateError,
    load_template,
)
from tests.fixtures import document_images

#: The templates this repository ships, read by path so the loader's answer is
#: checked against the file's own text rather than against itself.
APP_DIR = Path(__file__).resolve().parents[2] / "app"
TEMPLATES_DIR = APP_DIR / "pipeline" / "tier1" / "templates"
TEMPLATE_NAME = "passport_td3"
TEMPLATE_PATH = TEMPLATES_DIR / (TEMPLATE_NAME + ".json")

#: The four keys one field row's rectangle is written with.  13.8 puts a
#: tolerance in the same row, so a row is not the rectangle and naming the four
#: keeps a test from passing a tolerance to :class:`FieldRect`.
RECT_KEYS = ("x", "y", "width", "height")


def file_document():
    """The template file's own bytes, parsed."""
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def file_reference_size():
    """The reference image's own size, read by path rather than by the loader."""
    with Image.open(TEMPLATES_DIR / file_document()["reference_image"]) as image:
        return image.size


@pytest.fixture
def in_a_directory(monkeypatch, tmp_path):
    """Point the loader's package read at ``tmp_path`` and hand it back.

    The committed directory is the loader's own, so a test that needs a file
    the repository does not ship reads one out of a directory of its own rather
    than writing into the source tree.
    """
    monkeypatch.setattr(
        loader.importlib.resources, "files", lambda _package: tmp_path
    )
    return tmp_path


def write_template(directory, document, name=TEMPLATE_NAME):
    """Write ``document`` as the loader's named template and return its path."""
    path = directory / (name + ".json")
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def a_document(**overrides):
    """A loadable document, with ``overrides`` replacing the keys given."""
    document = {
        "document_type": "passport",
        "reference_image": "reference.png",
        "fields": {"name": {"x": 10, "y": 20, "width": 30, "height": 40}},
    }
    document.update(overrides)
    return document


def a_reference(directory, size=(60, 80)):
    """A blank image of ``size`` at the name ``a_document`` names."""
    Image.new("L", size, 255).save(directory / "reference.png")
    return size


def test_the_committed_template_loads():
    """The claim 13.4 is named for: the shipped JSON comes back as a record."""
    template = load_template(TEMPLATE_NAME)

    assert isinstance(template, Template)
    assert template.document_type == file_document()["document_type"]
    assert template.reference_image == file_document()["reference_image"]


def test_the_frame_comes_off_the_reference_image_and_not_the_file():
    """A rectangle is a position on that image, so the size is read off it.

    The JSON carries no size of its own, and a second copy beside the file it
    describes could disagree with it and nothing would notice.
    """
    template = load_template(TEMPLATE_NAME)

    assert template.reference_size == file_reference_size()
    assert "width" not in file_document()
    assert "height" not in file_document()


def test_every_rectangle_comes_off_the_file_as_it_writes_it():
    """Nothing is rounded, reordered or invented between the file and the record.

    The row carries more than its rectangle since 13.8, and only the four keys
    below reach the record: ``D95`` keeps a key the loader does not read
    ignored, so a tolerance stored beside the rectangle is not a loader change.
    """
    template = load_template(TEMPLATE_NAME)

    assert template.fields == {
        field: FieldRect(**{key: row[key] for key in RECT_KEYS})
        for field, row in file_document()["fields"].items()
    }


def test_every_field_the_committed_template_names_is_a_printed_one():
    """The four fields Tier 1 already extracts, plus the photo region.

    ``photo`` is a rectangle and not a printed field, which is the one thing
    this file adds to the four :data:`~app.pipeline.tier1.fields.PASSPORT_FIELDS`
    names -- a layout says where things are, and what a rectangle is for belongs
    to the part that reads it.
    """
    template = load_template(TEMPLATE_NAME)

    assert set(template.fields) - {"photo"} == {
        rule.field for rule in fields.PASSPORT_FIELDS
    }
    assert template.document_type in fields.DOCUMENT_TYPES


def test_every_rectangle_lies_inside_the_reference_image():
    """A rectangle off the page locates nothing, and 13.9 would compare it."""
    template = load_template(TEMPLATE_NAME)
    width, height = template.reference_size

    for field, rect in template.fields.items():
        assert rect.x >= 0 and rect.y >= 0, field
        assert rect.x + rect.width <= width, field
        assert rect.y + rect.height <= height, field


def test_a_rectangle_answers_four_corners_clockwise_from_the_top_left():
    """The shape ``app.risk.flags.EvidenceFlag.region`` is already written in."""
    rect = FieldRect(x=10, y=20, width=30, height=40)

    assert rect.corners == (
        (10, 20),
        (40, 20),
        (40, 60),
        (10, 60),
    )


def test_the_fields_are_frozen_after_the_loader_read_them():
    """A rectangle moved after the read is a layout nobody committed."""
    template = load_template(TEMPLATE_NAME)

    with pytest.raises(TypeError):
        template.fields["name"] = FieldRect(0, 0, 1, 1)


def test_a_template_that_is_not_there_raises_rather_than_answers():
    """An absent layout is a fault, and an empty set of fields is not the fix."""
    with pytest.raises(TemplateError, match="no template named"):
        load_template("no_such_template")


def test_there_is_no_default_template():
    """Nothing has chosen the layout Tier 1 should reach for yet.

    A default would be that choice made on the loader's behalf, and the next
    caller would inherit a document type nobody asked for.
    """
    with pytest.raises(TypeError):
        load_template()


def test_a_document_type_is_read_as_the_string_the_file_carries():
    """The template's type is 13.4's data, so a type nobody knows still loads.

    ``fields.DOCUMENT_TYPES`` is checked in a test over the file that shipped
    rather than here: a registry looked up in the loader is what would make a
    new document type a Python change, which is 13.5's whole claim.
    """
    assert load_template(TEMPLATE_NAME).document_type == "passport"
    assert load_template(TEMPLATE_NAME).document_type in fields.DOCUMENT_TYPES


@pytest.mark.parametrize(
    "document",
    [
        pytest.param({}, id="empty"),
        pytest.param({"document_type": ""}, id="empty_document_type"),
        pytest.param({"document_type": 1}, id="document_type_is_not_text"),
        pytest.param(
            {"document_type": "passport"}, id="no_reference_image"
        ),
        pytest.param(
            {"document_type": "passport", "reference_image": ""},
            id="empty_reference_image",
        ),
        pytest.param(
            {"document_type": "passport", "reference_image": 7},
            id="reference_image_is_not_text",
        ),
    ],
)
def test_a_file_that_cannot_be_a_template_is_refused(monkeypatch, document):
    """Nothing is defaulted, so every one of these raises rather than loads.

    The shapes are handed straight to the loader rather than written to disk,
    because what is under test is what the loader does with what it read.
    """
    monkeypatch.setattr(loader, "read_document", lambda _name: document)

    with pytest.raises(TemplateError):
        load_template(TEMPLATE_NAME)


@pytest.mark.parametrize(
    "fields_row",
    [
        pytest.param([], id="a_list"),
        pytest.param("name", id="a_string"),
        pytest.param({}, id="no_field_at_all"),
    ],
)
def test_a_file_naming_no_rectangle_is_refused(monkeypatch, in_a_directory, fields_row):
    """A layout with no field on it is a fault and not a template."""
    a_reference(in_a_directory)
    write_template(in_a_directory, a_document(fields=fields_row))

    with pytest.raises(TemplateError, match="fields|field"):
        load_template(TEMPLATE_NAME)


@pytest.mark.parametrize(
    "rectangle",
    [
        pytest.param([10, 20, 30, 40], id="a_list"),
        pytest.param("10,20,30,40", id="a_string"),
        pytest.param({"x": 10, "y": 20, "height": 40}, id="no_width"),
        pytest.param(
            {"x": 10.5, "y": 20, "width": 30, "height": 40}, id="a_fractional_pixel"
        ),
        pytest.param(
            {"x": 10, "y": 20, "width": "30", "height": 40}, id="a_quoted_width"
        ),
        pytest.param(
            {"x": True, "y": 20, "width": 30, "height": 40}, id="a_boolean_x"
        ),
        pytest.param(
            {"x": 10, "y": 20, "width": 0, "height": 40}, id="no_width_of_its_own"
        ),
        pytest.param(
            {"x": 10, "y": 20, "width": 30, "height": -1}, id="a_negative_height"
        ),
    ],
)
def test_a_rectangle_this_cannot_read_is_refused(in_a_directory, rectangle):
    """A rectangle missing a key, or carrying something other than four whole
    pixels, raises rather than being read as a position."""
    a_reference(in_a_directory)
    write_template(in_a_directory, a_document(fields={"name": rectangle}))

    with pytest.raises(TemplateError, match="name"):
        load_template(TEMPLATE_NAME)


@pytest.mark.parametrize(
    "rectangle",
    [
        pytest.param(
            {"x": -1, "y": 20, "width": 30, "height": 40}, id="off_the_left"
        ),
        pytest.param(
            {"x": 10, "y": -1, "width": 30, "height": 40}, id="above_the_page"
        ),
        pytest.param(
            {"x": 40, "y": 20, "width": 30, "height": 40}, id="off_the_right"
        ),
        pytest.param(
            {"x": 10, "y": 50, "width": 30, "height": 40}, id="below_the_page"
        ),
    ],
)
def test_a_rectangle_off_the_reference_image_is_refused(in_a_directory, rectangle):
    """The reference image is the frame the rectangle claims to sit on."""
    a_reference(in_a_directory, size=(60, 80))
    write_template(in_a_directory, a_document(fields={"name": rectangle}))

    with pytest.raises(TemplateError, match="outside the reference image"):
        load_template(TEMPLATE_NAME)


def test_a_field_named_nothing_is_refused(in_a_directory):
    """An empty name is addressable by nobody, and would be a silent orphan."""
    a_reference(in_a_directory)
    write_template(
        in_a_directory,
        a_document(fields={"": {"x": 10, "y": 20, "width": 30, "height": 40}}),
    )

    with pytest.raises(TemplateError, match="named ''"):
        load_template(TEMPLATE_NAME)


def test_the_frame_is_the_one_the_loader_reported(in_a_directory):
    """A loadable document answers the size of the image beside it.

    The sizes differ on purpose: a loader that answered a size from anywhere but
    the image would pass every other test in this file and place 13.9's
    comparison against a frame no page was ever measured on.
    """
    size = a_reference(in_a_directory, size=(60, 80))
    write_template(in_a_directory, a_document())

    template = load_template(TEMPLATE_NAME)

    assert template.reference_size == size
    assert template.reference_size != (1000, 700)


def test_a_reference_image_that_is_not_there_raises(in_a_directory):
    """A layout whose image cannot be found locates nothing."""
    write_template(in_a_directory, a_document())

    with pytest.raises(TemplateError, match="reference image is not in"):
        load_template(TEMPLATE_NAME)


def test_a_reference_that_is_not_an_image_raises(in_a_directory):
    """The frame comes off the image, so a file that is not one has no size."""
    (in_a_directory / "reference.png").write_text("not an image", encoding="utf-8")
    write_template(in_a_directory, a_document())

    with pytest.raises(TemplateError, match="not an image this can open"):
        load_template(TEMPLATE_NAME)


def test_a_file_that_is_not_json_raises(in_a_directory):
    """A template that cannot be parsed is a fault rather than an empty one."""
    (in_a_directory / (TEMPLATE_NAME + ".json")).write_text("{", encoding="utf-8")

    with pytest.raises(TemplateError, match="not readable JSON"):
        load_template(TEMPLATE_NAME)


def test_a_json_file_that_is_not_a_mapping_raises(in_a_directory):
    """A file whose top level is a list is not a template either."""
    (in_a_directory / (TEMPLATE_NAME + ".json")).write_text(
        "[]", encoding="utf-8"
    )

    with pytest.raises(TemplateError, match="not a mapping"):
        load_template(TEMPLATE_NAME)


def test_a_key_the_file_names_twice_raises(in_a_directory):
    """``json.loads`` keeps the last of a repeated key and says nothing.

    A rectangle written twice is one the author believes is on the page and the
    loader would drop without a word, which is the whole failure a hand-written
    data file is prone to.
    """
    a_reference(in_a_directory)
    (in_a_directory / (TEMPLATE_NAME + ".json")).write_text(
        '{"document_type": "passport", "reference_image": "reference.png", '
        '"fields": {"name": {"x": 10, "y": 20, "width": 30, "height": 40}, '
        '"name": {"x": 0, "y": 0, "width": 1, "height": 1}}}',
        encoding="utf-8",
    )

    with pytest.raises(TemplateError, match="names 'name' twice|names 'document_type' twice"):
        load_template(TEMPLATE_NAME)


def test_the_committed_template_carries_no_rectangle_the_fixture_does_not_print():
    """The four rectangles are where ``document_images`` printed those fields.

    The reference image is a blank page with its labels on it, so a rectangle
    measured off the fixture rather than invented is a claim a test can make.
    """
    page = document_images.render_document("passport")
    template = load_template(TEMPLATE_NAME)

    for printed in page.fields:
        x0, y0, x1, y1 = printed.value_box
        rect = template.fields[printed.name]
        assert x0 - rect.x <= 8 and rect.x + rect.width - x1 <= 8
        assert y0 - rect.y <= 8 and rect.y + rect.height - y1 <= 8


# ---------------------------------------------------------------------------
# 13.5 -- a new document type is a new JSON file, and no Python change
# ---------------------------------------------------------------------------

#: A document type this repository has never heard of.  Every name below is
#: invented on purpose: each is absent from the registries, so the load can only
#: succeed while no Python looks a document type, a template or a field up.
NEW_DOCUMENT_TYPE = "estate_agent_licence"
NEW_TEMPLATE_NAME = "estate_agent_licence_td1"
NEW_FIELDS = {
    "agent_number": {"x": 120, "y": 300, "width": 200, "height": 30},
    "issuing_body": {"x": 120, "y": 360, "width": 420, "height": 26},
}


def test_a_document_type_no_python_has_heard_of_loads(in_a_directory):
    """13.5's claim: the file is the whole of a new document type.

    One file is written, the JSON.  The reference image is the one this
    repository already ships, because what is under test is that the type is
    new and not that the pixels are -- a layout with a reference image of its
    own adds that image too and still changes no Python.

    A loader that checked a document type against
    :data:`~app.pipeline.tier1.fields.DOCUMENT_TYPES` would refuse this rather
    than answer it, and that refusal is the Python change 13.5 denies.
    """
    (in_a_directory / "passport_td3.png").write_bytes(
        (TEMPLATES_DIR / "passport_td3.png").read_bytes()
    )
    write_template(
        in_a_directory,
        a_document(
            document_type=NEW_DOCUMENT_TYPE,
            reference_image="passport_td3.png",
            fields=NEW_FIELDS,
        ),
        name=NEW_TEMPLATE_NAME,
    )

    template = load_template(NEW_TEMPLATE_NAME)

    assert template.document_type == NEW_DOCUMENT_TYPE
    assert template.document_type not in fields.DOCUMENT_TYPES
    assert template.document_type not in fields.FIELD_TABLES
    assert template.reference_size == file_reference_size()
    assert template.fields == {
        field: FieldRect(**rectangle) for field, rectangle in NEW_FIELDS.items()
    }


def test_a_new_layout_is_named_in_no_python_file():
    """No registry, no default template, no per-type code -- D95's three absences.

    ``load_template`` reaches a layout only through the file it sits in, so a
    table listing this type or these fields would be a Python change.  The
    search covers every module in ``app/`` rather than the loader alone, because
    a per-type table elsewhere would deny the claim just as a registry in the
    loader would.
    """
    searched = (NEW_DOCUMENT_TYPE, NEW_TEMPLATE_NAME, *NEW_FIELDS)
    named = sorted(
        f"{path.relative_to(APP_DIR).as_posix()}: {name}"
        for path in APP_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
        for name in searched
        if name in path.read_text(encoding="utf-8")
    )

    assert named == [], f"a new document type is named in Python: {named}"


# ---------------------------------------------------------------------------
# 13.8 -- every field says how far it may sit from where the template puts it
# ---------------------------------------------------------------------------

#: The three allowances 13.9 measures a printed field against, as the file
#: spells them.  Named here rather than read out of the loader because ``D95``
#: settled that the loader reads none of them.
TOLERANCE_KEYS = ("position", "size", "rotation")

#: How far ``m8_coverage.find_card``'s corners land from the page's own on the
#: 1000x700 reference, in pixels.  ``D96`` names that detector and this
#: project's handover records the measurement.
DETECTOR_ERROR = 5


def shipped_rows():
    """``(template, field, row)`` for every field of every template that shipped."""
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for field, row in document["fields"].items():
            yield path.name, field, row


def test_every_field_of_every_shipped_template_carries_a_tolerance():
    """13.8's claim: no field is left with nothing to be compared against.

    Over every file that shipped rather than the passport alone, so a layout
    added later cannot land without its tolerances.  ``D95`` keeps this out of
    the loader -- a key it does not read is ignored -- which leaves the files
    and this test as the only two places that can catch a field with no
    tolerance on it.
    """
    unnamed = [
        f"{template}:{field}"
        for template, field, row in shipped_rows()
        if not isinstance(row.get("tolerance"), dict)
        or not all(key in row["tolerance"] for key in TOLERANCE_KEYS)
    ]

    assert unnamed == []


def test_every_tolerance_is_a_positive_number():
    """A tolerance of zero or less is written down and not a tolerance.

    ``D95`` holds nothing here by default, so a hand-written figure of ``0`` or
    a typo'd negative would be read as the tightest layout possible rather
    than refused, and 13.9 would flag every field it is given.
    """
    for template, field, row in shipped_rows():
        for key in TOLERANCE_KEYS:
            value = row["tolerance"][key]
            assert isinstance(value, (int, float)) and not isinstance(value, bool), (
                f"{template}:{field}:{key} is not a number"
            )
            assert 0 < value < float("inf"), f"{template}:{field}:{key} is {value}"


def test_a_position_tolerance_is_wider_than_the_detector_that_feeds_it():
    """The corners 13.6 hands 13.7 are the detector's, and they are not exact.

    ``find_card`` lands 4 to 5 pixels off the page's own on this reference, and
    that error reaches template space as every field's displacement.  A
    tolerance no wider than it would read a correctly photographed document as
    a displaced one, field after field.
    """
    for _template, field, row in shipped_rows():
        assert row["tolerance"]["position"] > DETECTOR_ERROR, field
