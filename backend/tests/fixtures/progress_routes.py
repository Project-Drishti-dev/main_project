"""What the two progress routes' tests share: three rows, and a stream reader.

18.10's stream and 18.11's polling document are two transports over one
sequence, so a case comparing them has to build its rows the same way in both
files and read the stream with a parser that knows nothing about the document.
Two copies of that reader would let the two files disagree about the stream
without either of them noticing, which is the one thing the comparison between
them exists to catch.

Everything here is a plain function rather than a fixture: a case decides
which row it needs, and a case needing none of them pays nothing for them.
"""

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.pipeline.tier0 import document
from app.progress import DONE_EVENT, PROGRESS_EVENT
from app.screening import run_screening
from app.storage.models import Screening
from app.storage.repository import ScreeningRepository
from tests.fixtures import mrz_images


#: The exact keys one step carries, whichever route spells it.  Held as a set
#: so an added key fails a case rather than being read past: both routes are a
#: public surface, and a sixth field is a field a client has to parse.
FRAME_KEYS = {"screening_id", "unit", "state", "tier", "module"}

#: The exact keys the one ``done`` frame carries, for the same reason.
DONE_KEYS = {"screening_id", "units"}

#: A name that must not travel to a caller in either route' answer.
UPLOAD_NAME = "a-name-that-must-not-travel.jpg"


def screened(sessions: sessionmaker[Session]) -> Screening:
    """One real screening, so a case is asked about a run with findings.

    A drawn TD3 whose printed composite digit is wrong is screened through
    app.screening.run_screening with its own parse, which is how a rule gets
    its characters, and 6.2 then boxes the failing digit on the page -- so
    the row carries findings, and the modules that made them are the ones
    both routes go on to report.
    """
    zone = list(mrz_images.SPECIMENS["TD3"])
    printed = zone[1][43]
    zone[1] = zone[1][:43] + ("0" if printed != "0" else "1") + zone[1][44:]
    page = mrz_images.render_format("TD3", lines=tuple(zone))
    return run_screening(
        sessions=sessions,
        image=page.image,
        document_type="passport",
        filename=UPLOAD_NAME,
        parsed_document=document.parse_mrz(mrz_images.read_zone(page)),
    )


def store_flags(
    sessions: sessionmaker[Session], row: Screening, flags: list[Any]
) -> None:
    """Rewrite one row' stored findings, as a damaged row would carry them.

    :param sessions: the factory the row is written through.
    :param row: the screening whose findings are being replaced.
    :param flags: what the JSON column will hold afterwards.
    The reader is asked about shapes this repository' own writer does not
    produce, and no writer produces them: the flow writes a list of
    asdict results, so the column is rewritten here rather than reached for
    through the flow.
    """
    with sessions() as session:
        stored = session.merge(row)
        stored.flags = flags
        session.commit()
    row.flags = flags


def pending(sessions: sessionmaker[Session]) -> Screening:
    """One row 11.1 wrote before any stage ran, carrying no result at all."""
    return ScreeningRepository(sessions).create(
        document_type="passport",
        filename=UPLOAD_NAME,
        image_width=320,
        image_height=90,
    )


def stream_text(client: TestClient, screening_id: uuid.UUID) -> str:
    """The stream for one screening, read to the end as one string."""
    with client.stream(
        "GET", f"/api/screenings/{screening_id}/progress/stream"
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return "".join(response.iter_text())


def parse_frames(stream: str) -> list[tuple[str, dict[str, Any]]]:
    """The frames a stream carries, read without knowing the document' shape.

    :param stream: the body the stream endpoint answered with.
    :returns: one (event name, data object) pair per frame, in order.
    :raises AssertionError: for a block that is not exactly a name line and
        a data line, which is what the frame format is.
    """
    frames: list[tuple[str, dict[str, Any]]] = []
    for block in stream.split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        assert len(lines) == 2, block
        assert lines[0].startswith("event: "), block
        assert lines[1].startswith("data: "), block
        frames.append(
            (
                lines[0][len("event: ") :],
                json.loads(lines[1][len("data: ") :]),
            )
        )
    return frames


def progress_steps(
    frames: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """The ``progress`` events alone, so a case reads about steps."""
    return [data for name, data in frames if name == PROGRESS_EVENT]


def done_frame(frames: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """The one ``done`` frame' object, which a stream carries exactly once.

    :param frames: the frames the stream carried, in order.
    :returns: that frame' data object.
    :raises AssertionError: for a stream with no ``done`` frame or with more
        than one, which is a stream whose end a reader cannot find.
    """
    found = [data for name, data in frames if name == DONE_EVENT]
    assert len(found) == 1, f"expected one done frame, found {len(found)}"
    return found[0]
