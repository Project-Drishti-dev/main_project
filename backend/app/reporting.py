"""One stored screening as a standalone, printable HTML page.

18.9's read.  A JSON answer is something a screen renders; this is the
document an officer files, so it has to open on a machine with no network
and print years from now -- the stylesheet is inline, nothing is fetched,
and no value on the page needs a second request to be legible.

**Everything printed is read off the row.**  The band is the column a stage
wrote rather than a fresh reading of the score beside it, the findings are
the stored evidence rather than a re-run of the cascade, and the audit id
is the one event 11.1 answered with, read back through app.audit.trail.
The rationale is docs/DECISIONS.md D150.

**A value the row never received is printed as a sentence.**  A row no
stage has scored carries no score and no band, and a cascade that raised
leaves no completed event beside it; each prints as NOT_RECORDED rather
than as an empty cell, so a reader cannot mistake an unanswered question
for an answer that said nothing.

**Nothing read off the document is printed, and neither is the upload's
own name.**  A finding is printed by its id, label, tier, module, weight
band, its two numbers and the rule's own reason -- no expected or found
value, no region polygon, no image -- and the filename is caller-supplied
text a filed record does not carry.  app.explain.reasons' floor is
deliberately not reached here: wiring it to an officer's screen is 23.8's.

**Every value is escaped on the way out**, because a label, a reason and a
document type are all text a rule or a caller wrote.

**Invariants**

- The answer is one complete HTML document referencing no external asset:
  no link, script, image, frame, object or import, and no url() beside it.
- Every value on the page is escaped text, so a stored angle bracket,
  ampersand or quote prints as itself and executes as nothing.
- The score, band, ruleset version and findings are the row's own columns;
  no score and no band is recomputed here.
- The audit id is the one analysis_completed event for the row, or
  NOT_RECORDED where the cascade left none.
- A stored finding missing one of the eight fields printed shows
  NOT_RECORDED for it rather than raising.
- No filename, no field value and no image reaches the page.
- No file is read, no clock is reached, no session is opened, nothing is
  written.
"""

import html
import uuid
from datetime import datetime
from typing import Any

from app.storage.models import Screening

__all__ = ["NOT_RECORDED", "render_report"]

#: What a value the row never received is printed as.  A sentence rather
#: than an empty cell or a dash, so a reader cannot mistake an unanswered
#: question for an answer that said nothing.
NOT_RECORDED = "not recorded"

#: The one line break in the document, written as a character so that this
#: module holds no escape at all.
LINE_BREAK = chr(10)

#: The page's whole stylesheet, inline: a printed page that fetched one
#: would print without it.  No url(), no import and no remote font.
STYLESHEET = (
    "body { margin: 24px; font-family: Georgia, serif; color: #111; }"
    "h1 { font-size: 20px; margin: 0 0 4px; }"
    "h2 { font-size: 15px; margin: 24px 0 4px; }"
    "p.note { color: #444; font-size: 12px; }"
    "table { border-collapse: collapse; width: 100%; margin: 4px 0 12px; }"
    "th, td { border: 1px solid #999; padding: 4px 6px; text-align: left;"
    " vertical-align: top; font-size: 13px; }"
    "thead th { background: #eee; }"
    "td.number { text-align: right; white-space: nowrap; }"
    "@page { margin: 18mm; }"
    "@media print { body { margin: 0; } }"
)

#: The one fact table's headings and the columns beside them, in the order
#: they print.  Every one is a column the row already carries.
FACTS = (
    ("Screening id", "id"),
    ("Screened at (UTC)", "created_at"),
    ("Status", "status"),
    ("Document type", "document_type"),
    ("Score", "score"),
    ("Band", "band"),
    ("Ruleset version", "ruleset_version"),
)

#: The findings table's headings and the stored fields beside them, and the
#: two of the eight that are numbers rather than text.  The reason is the
#: rule's own sentence: the floor in app.explain.reasons is not read here.
FINDING_COLUMNS = (
    ("Finding", "id"),
    ("Label", "label"),
    ("Tier", "tier"),
    ("Module", "source_module"),
    ("Weight band", "weight_band"),
    ("Value", "value"),
    ("Confidence", "confidence"),
    ("Reason", "reason"),
)

#: The two fields of the eight printed as numbers rather than as text.
NUMERIC_FIELDS = ("value", "confidence")

#: What a page with no findings says instead of an empty table.
NO_FINDINGS = "<p>No findings were recorded for this screening.</p>"

#: The note under the tables: what the page is, and what the audit id is
#: for.  Fixed prose, so no value reaches the page from here.
THE_NOTE = (
    '<p class="note">This page carries its own styles and needs no network '
    "to print. The audit id above names the event whose record can be "
    "checked against the log.</p>"
)


def render_report(row: Screening, *, audit_id: uuid.UUID | None) -> str:
    """The stored row as one standalone, printable HTML page.

    :param row: the screening as the repository read it, live or not.
    :param audit_id: the one analysis_completed event beside it, or None
        where the cascade left none.  Keyword-only, and read rather than
        recomputed, on app.audit.trail's own reasoning.
    :returns: a complete HTML document, referencing no external asset.
    """
    head = (
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Screening report</title>",
        f"<style>{STYLESHEET}</style>",
        "</head>",
        "<body>",
        "<h1>Screening report</h1>",
    )
    body = (_facts(row, audit_id), _findings(row), THE_NOTE)
    return LINE_BREAK.join(head + body + ("</body>", "</html>"))


def _facts(row: Screening, audit_id: uuid.UUID | None) -> str:
    """The row's own columns, one row each, beside the audit id.

    :param row: the screening as the repository read it.
    :param audit_id: the one event beside it, or None.
    :returns: a two-column table whose cells are escaped text.
    """
    cells = [(label, _text(getattr(row, name))) for label, name in FACTS]
    cells.append(("Audit id", _text(audit_id)))
    return _table(
        ("Field", "Value"),
        [
            f'<tr><th scope="row">{label}</th><td>{value}</td></tr>'
            for label, value in cells
        ],
    )


def _findings(row: Screening) -> str:
    """Every stored finding, one row each, with the reason the rule wrote.

    :param row: the screening as the repository read it.
    :returns: the findings table, or a sentence when the row carries none.
    """
    findings = row.flags or []
    if not findings:
        return NO_FINDINGS
    return _table(
        tuple(label for label, _ in FINDING_COLUMNS),
        [_finding_row(finding) for finding in findings],
    )


def _finding_row(finding: dict[str, Any]) -> str:
    """One finding's eight printed values, in FINDING_COLUMNS order.

    :param finding: one stored finding, read for the eight named fields and
        nothing else -- so a field this table does not print cannot reach
        the page by being stored beside one it does.
    :returns: one escaped table row.
    """
    cells = [
        f'<td class="number">{_text(finding.get(name))}</td>'
        if name in NUMERIC_FIELDS
        else f"<td>{_text(finding.get(name))}</td>"
        for _, name in FINDING_COLUMNS
    ]
    return '<tr class="finding">' + LINE_BREAK.join(cells) + "</tr>"


def _table(headings: tuple[str, ...], rows: list[str]) -> str:
    """A table with the headings above and the rows already rendered.

    :param headings: the column headings, in the order the rows use.
    :param rows: the rendered rows, each one already escaped.
    :returns: the table, with a head and a body.
    """
    head = "".join(
        f'<th scope="col">{heading}</th>' for heading in headings
    )
    return (
        "<table>"
        "<thead><tr>" + head + "</tr></thead>"
        "<tbody>" + LINE_BREAK.join(rows) + "</tbody>"
        "</table>"
    )


def _text(value: object) -> str:
    """``value`` as escaped text, or NOT_RECORDED where there is none.

    :param value: what the row carries: text, a number, an id, an instant,
        or None for a value nothing has written.
    :returns: the value as it prints -- an instant in ISO 8601, anything
        else as its own text -- escaped with its quotes, so a stored angle
        bracket or ampersand is a character on the page and nothing else.
    """
    if value is None:
        return NOT_RECORDED
    if isinstance(value, datetime):
        return html.escape(value.isoformat(), quote=True)
    return html.escape(str(value), quote=True)
