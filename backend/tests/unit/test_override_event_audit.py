"""10.6: the officer's choice against the band, as an event of its own.

The task's verify is "a test asserts the override is its own event, not a
mutation of the automated result", so that is the first test here.  The rest
is what keeps it an event rather than a habit:

- **the choice is written down, never derived.**  The abstract's three
  choices are declared in one module and no band names any of them, held by
  a walk over the module's own source beside a probe that is the shape a
  mapping is written in.
- **the rule is a comparison of two independent orderings**, so the three
  agreeing pairs and the six disagreeing ones are both answers, and a test
  walks all nine rather than one of them.
- **the automated result is untouched**: the same event id, payload, digest
  and the same row before and after, so "not a mutation" is a comparison and
  not an absence of a second write.
- **the override outlives the row it names**, which is what a record beside a
  mutable record means.
"""

import ast
import datetime
import inspect
import pathlib
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import screening
from app.audit import decision
from app.audit.decision import (
    BAND_ORDER,
    OFFICER_ACTIONS,
    OFFICER_ACTION_KEY,
    SYSTEM_BAND_KEY,
    DecisionError,
    contradicts_band,
    record_override,
)
from app.audit.emit import MODEL_VERSIONS_KEY, RULESET_VERSION_KEY
from app.audit.event_types import ANALYSIS_COMPLETED, OVERRIDE_RECORDED
from app.audit.record import event_record
from app.ledger.hashing import hash_record
from app.pipeline.tier0 import document
from app.risk.bands import to_band
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import WEIGHT_BANDS
from app.risk.hard_rules import MAX_SCORE, MIN_SCORE
from app.storage import db
from app.storage.models import AuditEvent, Base, Screening
from tests.fixtures import mrz_images

#: The day 5.8's own suite measures against; nothing here reads a clock.
REFERENCE = datetime.date(2026, 9, 30)

#: A page with no machine-readable zone on it: nothing fires, so the row reads
#: ``low`` and a choice against it has to be the officer's own.
BLANK = mrz_images.draw_page(("BORDER CONTROL",), size=(320, 90))

#: The three pairs where the choice and the band sit at the same point on
#: their own orderings, and no override is therefore recorded.
AGREEING = (
    ("low", OFFICER_ACTIONS[0]),
    ("review", OFFICER_ACTIONS[1]),
    ("high", OFFICER_ACTIONS[2]),
)

#: The nodes that open a scope rather than being one statement of behaviour:
#: walked through, never read whole, and their docstrings are prose.
SCOPE_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Module)


@pytest.fixture
def sessions() -> Iterator[sessionmaker[Session]]:
    """One in-memory database with the migrated schema in it, and a factory
    over it -- the shape :mod:`app.audit.emit`'s own suite writes to."""
    engine = db.build_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        yield db.build_session_factory(engine)
    finally:
        engine.dispose()


def _source() -> str:
    """The decision module's own source, read rather than remembered."""
    return pathlib.Path(decision.__file__).read_text(encoding="utf-8")


def _screening(sessions: sessionmaker[Session], **overrides: Any) -> Screening:
    """One screening of a page with no MRZ zone, and the row it left."""
    arguments: dict[str, Any] = {
        "sessions": sessions,
        "image": BLANK.image,
        "document_type": "passport",
        "filename": "a-name-that-must-not-travel.jpg",
    }
    arguments.update(overrides)
    return screening.run_screening(**arguments)


def _hard_failed(sessions: sessionmaker[Session]) -> Screening:
    """One screening of a page whose printed composite digit is wrong, which
    6.5 sends straight to ``high``."""
    zone = list(mrz_images.SPECIMENS["TD3"])
    printed = zone[1][43]
    zone[1] = zone[1][:43] + ("0" if printed != "0" else "1") + zone[1][44:]
    page = mrz_images.render_format("TD3", lines=tuple(zone))
    return _screening(
        sessions,
        image=page.image,
        parsed_document=document.parse_mrz(mrz_images.read_zone(page)),
        reference_date=REFERENCE,
    )


def _trail(
    sessions: sessionmaker[Session], screening_id: uuid.UUID
) -> list[AuditEvent]:
    """The events one screening wrote, read back over a fresh session."""
    with sessions() as session:
        return list(
            session.execute(
                select(AuditEvent)
                .where(AuditEvent.screening_id == screening_id)
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
            .scalars()
            .all()
        )


def _of_type(events: list[AuditEvent], event_type: str) -> list[AuditEvent]:
    """Every event of that name, so a count can be asserted on its own."""
    return [event for event in events if event.event_type == event_type]


def _one_of(events: list[AuditEvent], event_type: str) -> AuditEvent:
    """The single event of that name, failing loudly on zero or two."""
    found = _of_type(events, event_type)
    assert len(found) == 1, f"expected one {event_type}, got {len(found)}"
    return found[0]


def _rebuilds(event: AuditEvent) -> bool:
    """Whether the stored digest is the one this record hashes to."""
    return event.record_hash == hash_record(
        event_record(
            event.event_type, event.screening_id, event.actor, event.payload
        ),
        bytes.fromhex(event.record_salt),
    )


def _leaves(value: Any) -> Any:
    """Every leaf of a payload, so a ``float`` can be looked for anywhere."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item)
    else:
        yield value


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """The docstring expressions in a tree, which are prose and not code."""
    docstrings = set()
    for node in ast.walk(tree):
        if not isinstance(node, SCOPE_NODES):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            docstrings.add(id(first.value))
    return docstrings


def _written_texts(node: ast.AST) -> list[str]:
    """The literal spellings a node writes into the code around it."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    return []


def _pairings(source: str) -> list[int]:
    """Every statement carrying a band name and a choice in the same breath.

    A band that names an outcome is the mapping 7.10 forbids, in the one
    place Part 10 was always going to have to be careful: this module is
    about a band and about the officer's choices.  **A statement is the
    unit**, so a two-line ``if`` is judged as one thing rather than as a
    band on one line and a choice on the next.  **Its limit is the same one
    7.10's walk has**: two statements that between them derive a choice from
    a band are two findings, not one, which is why this module holds two
    independent orderings rather than a table keyed by a band and why the
    tree as a whole is 7.10's walk rather than this one.
    """
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt) or isinstance(node, SCOPE_NODES):
            continue
        bands, actions = set(), set()
        for inner in ast.walk(node):
            if id(inner) in docstrings:
                continue
            for text in _written_texts(inner):
                if text in BAND_ORDER:
                    bands.add(text)
                if text in OFFICER_ACTIONS:
                    actions.add(text)
        if bands and actions:
            found.append(node.lineno)
    return found


# --- the task's claim ------------------------------------------------------


def test_the_override_is_its_own_event_and_the_automated_result_is_untouched(
    sessions: sessionmaker[Session],
):
    """The verify: a new event beside the result, and the result unchanged."""
    row = _screening(sessions)
    before = _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED)
    before_row = (row.score, row.band, row.status, row.ruleset_version)

    recorded = record_override(
        row.id,
        system_band=row.band,
        officer_action=decision.REJECT_ENTRY,
        sessions=sessions,
        ruleset_version=row.ruleset_version,
        model_versions={"tier2.forgery": "0.1.0"},
    )

    events = _trail(sessions, row.id)
    override = _one_of(events, OVERRIDE_RECORDED)
    assert override.id != before.id
    assert override.payload[SYSTEM_BAND_KEY] == row.band == "low"
    assert override.payload[OFFICER_ACTION_KEY] == decision.REJECT_ENTRY
    assert override.record_hash != before.record_hash

    after = _one_of(events, ANALYSIS_COMPLETED)
    assert (after.id, after.payload, after.record_hash) == (
        before.id,
        before.payload,
        before.record_hash,
    )
    with sessions() as session:
        reread = session.get(Screening, row.id)
    assert (reread.score, reread.band, reread.status, reread.ruleset_version) == (
        before_row
    )


def test_a_choice_that_agrees_with_the_band_records_nothing(
    sessions: sessionmaker[Session],
):
    """An agreeing choice is an answer, not a refusal and not an event."""
    row = _screening(sessions)
    before = _trail(sessions, row.id)

    recorded = record_override(
        row.id,
        system_band=row.band,
        officer_action=decision.ALLOW_ENTRY,
        sessions=sessions,
    )

    assert recorded is None
    assert [event.id for event in _trail(sessions, row.id)] == [
        event.id for event in before
    ]


# --- the rule the event follows from --------------------------------------


@pytest.mark.parametrize(("band", "action"), AGREEING)
def test_the_three_agreeing_pairs_record_nothing(
    sessions: sessionmaker[Session], band: str, action: str
):
    """``low``/allow, ``review``/further inspection and ``high``/the adverse
    choice are the three pairs where nothing is recorded."""
    row = _screening(sessions)

    assert contradicts_band(band, action) is False
    assert (
        record_override(
            row.id, system_band=band, officer_action=action, sessions=sessions
        )
        is None
    )
    assert _of_type(_trail(sessions, row.id), OVERRIDE_RECORDED) == []


@pytest.mark.parametrize(
    ("band", "action"),
    [(band, action) for band in BAND_ORDER for action in OFFICER_ACTIONS],
)
def test_every_disagreeing_pair_records_one_override(
    sessions: sessionmaker[Session], band: str, action: str
):
    """All nine pairs, so the six overrides are a rule and not three cases."""
    row = _screening(sessions)
    agreeing = (band, action) in AGREEING

    recorded = record_override(
        row.id, system_band=band, officer_action=action, sessions=sessions
    )

    assert contradicts_band(band, action) is not agreeing
    overrides = _of_type(_trail(sessions, row.id), OVERRIDE_RECORDED)
    assert len(overrides) == (0 if agreeing else 1)
    if not agreeing:
        assert recorded is not None and recorded.id == overrides[0].id
        assert overrides[0].payload == {
            **overrides[0].payload,
            SYSTEM_BAND_KEY: band,
            OFFICER_ACTION_KEY: action,
        }


def test_a_release_of_a_high_band_document_is_an_override(
    sessions: sessionmaker[Session],
):
    """The other direction: the officer overrode the system the other way."""
    row = _hard_failed(sessions)
    assert row.band == "high"

    released = record_override(
        row.id,
        system_band=row.band,
        officer_action=decision.ALLOW_ENTRY,
        sessions=sessions,
        ruleset_version=row.ruleset_version,
    )
    refused = record_override(
        row.id,
        system_band=row.band,
        officer_action=decision.REJECT_ENTRY,
        sessions=sessions,
    )

    overrides = _of_type(_trail(sessions, row.id), OVERRIDE_RECORDED)
    assert released is not None
    assert refused is None
    assert len(overrides) == 1
    assert overrides[0].payload[OFFICER_ACTION_KEY] == decision.ALLOW_ENTRY
    assert _one_of(_trail(sessions, row.id), ANALYSIS_COMPLETED).payload["band"] == "high"


# --- the two vocabularies are two vocabularies ---------------------------


def test_the_three_choices_are_the_abstracts_own_in_its_order():
    """The abstract's sentence, in the order it writes it, spelled once."""
    assert OFFICER_ACTIONS == ("allow", "further_inspection", "reject")
    assert len(set(OFFICER_ACTIONS)) == 3


def test_the_band_order_is_the_engines_three_in_the_order_the_scale_puts_them():
    """Read off the committed thresholds, so a retune of ``D28`` moves it."""
    assert set(BAND_ORDER) == WEIGHT_BANDS
    assert MIN_SCORE <= LOW_MAX < REVIEW_MAX <= MAX_SCORE
    ranks = [BAND_ORDER.index(to_band(score)) for score in range(101)]
    assert ranks == sorted(ranks)
    assert {to_band(score) for score in range(101)} == set(BAND_ORDER)


def test_no_statement_in_the_module_pairs_a_band_with_a_choice():
    """7.10's mapping, in the one module that holds both vocabularies."""
    assert _pairings(_source()) == []


@pytest.mark.parametrize(
    "source",
    [
        pytest.param('CHOICE = {"low": "allow"}\n', id="a-lookup-table"),
        pytest.param(
            'def agree(band):\n    if band == "review":\n        return "allow"\n',
            id="a-conditional-on-a-band",
        ),
        pytest.param(
            'ACTION = "reject" if to_band(score) == "high" else "allow"\n',
            id="an-action-derived-from-a-banded-score",
        ),
    ],
)
def test_the_pairing_detector_finds_the_shapes_a_mapping_is_written_in(source):
    """Held against the detector, so a walk that matched nothing would not
    have passed the test above for the wrong reason."""
    assert _pairings(source)


def test_the_choices_ranked_strictly_in_the_officers_own_order():
    """The two orderings are comparable because each one is an ordering."""
    assert [OFFICER_ACTIONS.index(action) for action in OFFICER_ACTIONS] == [0, 1, 2]


# --- what the event carries ------------------------------------------------


def test_the_override_carries_both_sides_and_nothing_else(
    sessions: sessionmaker[Session],
):
    """Two keys and the two versions, and no float, name or image."""
    row = _screening(sessions)
    record_override(
        row.id,
        system_band=row.band,
        officer_action=decision.FURTHER_INSPECTION,
        sessions=sessions,
        ruleset_version=row.ruleset_version,
        model_versions={"tier2.forgery": "0.1.0"},
    )

    payload = _one_of(_trail(sessions, row.id), OVERRIDE_RECORDED).payload
    assert set(payload) == {
        SYSTEM_BAND_KEY,
        OFFICER_ACTION_KEY,
        RULESET_VERSION_KEY,
        MODEL_VERSIONS_KEY,
    }
    assert payload[RULESET_VERSION_KEY] == row.ruleset_version
    assert payload[MODEL_VERSIONS_KEY] == {"tier2.forgery": "0.1.0"}
    assert not any(isinstance(leaf, float) for leaf in _leaves(payload))
    assert row.filename not in repr(payload)
    assert "filename" not in payload and "document_type" not in payload


def test_the_override_is_hashed_as_its_own_record(sessions: sessionmaker[Session]):
    """A record of its own, verifiable by 9.17 with no change at all."""
    row = _screening(sessions)
    record_override(
        row.id,
        system_band=row.band,
        officer_action=decision.REJECT_ENTRY,
        sessions=sessions,
    )

    events = _trail(sessions, row.id)
    assert all(_rebuilds(event) for event in events)
    assert len({event.record_hash for event in events}) == len(events)
    assert len({event.record_salt for event in events}) == len(events)


def test_an_override_outlives_the_row_its_result_lives_on(
    sessions: sessionmaker[Session],
):
    """Beside a mutable record, and not inside it: the row can go."""
    row = _screening(sessions)
    record_override(
        row.id,
        system_band=row.band,
        officer_action=decision.REJECT_ENTRY,
        sessions=sessions,
    )

    with sessions() as session:
        session.delete(session.get(Screening, row.id))
        session.commit()

    remaining = _trail(sessions, row.id)
    assert _one_of(remaining, OVERRIDE_RECORDED).payload[SYSTEM_BAND_KEY] == "low"
    assert all(_rebuilds(event) for event in remaining)


def test_two_screenings_do_not_share_an_override(
    sessions: sessionmaker[Session],
):
    """The event lands on the row it names, so an id reused fails here."""
    first = _screening(sessions)
    second = _screening(sessions)
    for row in (first, second):
        record_override(
            row.id,
            system_band=row.band,
            officer_action=decision.REJECT_ENTRY,
            sessions=sessions,
        )

    first_events = _of_type(_trail(sessions, first.id), OVERRIDE_RECORDED)
    second_events = _of_type(_trail(sessions, second.id), OVERRIDE_RECORDED)
    assert [event.screening_id for event in first_events] == [first.id]
    assert [event.screening_id for event in second_events] == [second.id]
    assert first_events[0].id != second_events[0].id


# --- what the function refuses, and where it writes -----------------------


@pytest.mark.parametrize(
    ("band", "action"),
    [
        pytest.param("Low", "allow", id="a-band-in-the-wrong-case"),
        pytest.param("", "allow", id="an-empty-band"),
        pytest.param(None, "allow", id="no-band-at-all"),
        pytest.param(0, "allow", id="a-band-that-is-a-number"),
        pytest.param("low", "approve", id="a-choice-this-project-cannot-read"),
        pytest.param("low", None, id="no-choice-at-all"),
        pytest.param("low", 7, id="a-choice-that-is-a-number"),
        pytest.param(
            "low", decision.REJECT_ENTRY + " ", id="a-choice-with-trailing-space"
        ),
    ],
)
def test_a_name_this_project_cannot_read_is_refused_and_nothing_is_written(
    sessions: sessionmaker[Session], band: Any, action: Any
):
    """The refusal comes before the write, so no half-record is left."""
    row = _screening(sessions)
    before = _trail(sessions, row.id)

    with pytest.raises(DecisionError):
        contradicts_band(band, action)
    with pytest.raises(DecisionError):
        record_override(
            row.id, system_band=band, officer_action=action, sessions=sessions
        )

    assert [event.id for event in _trail(sessions, row.id)] == [
        event.id for event in before
    ]


def test_the_sessions_factory_is_a_required_keyword():
    """The factory is the seam, so no module-level one is reachable here."""
    signature = inspect.signature(record_override)

    assert list(signature.parameters) == [
        "screening_id",
        "system_band",
        "officer_action",
        "sessions",
        "ruleset_version",
        "model_versions",
    ]
    for name in ("system_band", "officer_action", "sessions", "ruleset_version",
                 "model_versions"):
        assert signature.parameters[name].kind.name == "KEYWORD_ONLY"
    assert signature.parameters["sessions"].default is inspect.Parameter.empty
    assert signature.parameters["ruleset_version"].default is None
    assert signature.parameters["model_versions"].default is None


def test_the_event_is_written_through_the_one_writer_and_named_by_it():
    """10.2's writer is the only one, and 10.1's vocabulary is the only
    spelling: this module builds no row and names no event type as text."""
    tree = ast.parse(_source())

    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AuditEvent"
    ]
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.endswith("_recorded")
    ]
    assert not {
        (node.module or "") for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } & {"app.storage.db"}
