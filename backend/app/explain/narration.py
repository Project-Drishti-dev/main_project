"""The sentence an officer reads, and the record of where it came from.

One call reads the findings, asks the summariser once, holds what came back to
the flag data that summariser was given, and answers a record.  The record is
what a response carries: the summary, whether :data:`MODEL` or
:data:`TEMPLATE` wrote it, what the verifier made of the model text, the model
behind the summary, the tokens a refusal named, and the prompt version.

**A refused summary is discarded rather than repaired.**  The template stands in
its place and the record answers :data:`FAILED`, so an officer reading a
fallback can tell that a model wrote something and that it did not survive being
checked -- which is the difference between a fallback and a working model.  The
refused text is not held on the record at all, so it cannot be read back out of
one.

**Nothing here raises on model text.**  17.7's client answers ``None`` rather
than raising, and that is the whole of its failure contract; a refusal is a
verdict the record carries, not an exception the caller has to catch.
"""

import dataclasses
from collections.abc import Iterable

from app.explain.payload import build_flag_payload
from app.explain.prompts.loader import Prompt, load_prompt
from app.explain.summarizer import Summarizer
from app.explain.template import template_summary
from app.explain.verifier import verify_summary

__all__ = [
    "FAILED",
    "MODEL",
    "NOT_CHECKED",
    "PASSED",
    "SUMMARY_SOURCES",
    "TEMPLATE",
    "VERIFICATION_STATUSES",
    "Narration",
    "narrate",
]

#: A summary a model wrote, and which a model then backed with its own name.
MODEL = "model"

#: A summary 17.5 wrote from the flags themselves.  No model is involved, so
#: no model is named beside one.
TEMPLATE = "template"

#: The two answers to where the sentence an officer reads came from.
SUMMARY_SOURCES = (MODEL, TEMPLATE)

#: The model text was held to the flag data it was given, and every token in
#: it was printed there.
PASSED = "passed"

#: The model text carried a token the flag data never printed, and was thrown
#: away for it.  The summary on the record is then the template's, so this
#: verdict is a statement about what was discarded.
FAILED = "failed"

#: There was no model text to hold to anything -- no summariser, or one that
#: answered ``None`` -- so the record says the check did not happen rather than
#: claiming a verdict it never reached.
NOT_CHECKED = "not_checked"

#: The three answers to what the verifier made of the model text.  **The shipped
#: deployment answers :data:`NOT_CHECKED`**, because ``LOCAL_LLM_ENABLED`` ships
#: off, so a record claiming :data:`PASSED` there would be reporting a check that
#: never ran on every document the system ever writes.
VERIFICATION_STATUSES = (PASSED, FAILED, NOT_CHECKED)

#: What separates the prompt from the data it is handed.  A blank line and
#: nothing else: the payload is the one rendering D139 built, and a heading
#: written beside it would be prose no decision recorded.
_SEPARATOR = "\n\n"


@dataclasses.dataclass(frozen=True)
class Narration:
    """One screening's summary, and everything an answer has to say about it.

    :attr:`summary` is the text an officer reads, and is never the model's
    own where :attr:`verification` is :data:`FAILED`.  :attr:`model_name` names
    who wrote *this* summary, so it is ``None`` on every template summary
    whatever a model was configured to answer with.

    :attr:`unsupported` is the verifier's own diagnosis of what was refused,
    in the order the refused text wrote it (D134), and is empty whenever nothing
    was refused -- so it is the record of a rejection rather than the text of
    one.  Frozen, because a summary an officer has read cannot be amended
    afterwards by anything holding the record.
    """

    summary: str
    summary_source: str
    verification: str
    model_name: str | None
    unsupported: tuple[str, ...]
    prompt_version: str

    def as_dict(self) -> dict[str, object]:
        """The record as a response body: the same six values, JSON-shaped."""
        return {
            "summary": self.summary,
            "summary_source": self.summary_source,
            "verification": self.verification,
            "model_name": self.model_name,
            "unsupported": list(self.unsupported),
            "prompt_version": self.prompt_version,
        }


def narrate(
    flags: Iterable[object],
    band: str,
    contributions: Iterable[object],
    summarizer: Summarizer | None = None,
    prompt: Prompt | None = None,
) -> Narration:
    """The summary for ``flags``, and the record of how that summary came to be.

    :param flags: the findings in cascade order, read once and used for both
        the payload and the template.
    :param band: one of :data:`app.risk.flags.WEIGHT_BANDS`.
    :param contributions: 7.11's rows beside the findings.
    :param summarizer: where the model text is asked for.  ``None``, or one
        that answers ``None``, is :data:`NOT_CHECKED` rather than a failure,
        because there was no text written to check.
    :param prompt: the prompt to ask with; ``None`` loads the shipped one.
    :returns: a :class:`Narration` whose summary always reaches the officer.
    :raises app.risk.flags.FlagValueError: on a band, a finding or a
        contribution the payload or the template cannot read.

    **The payload is built on every path, including the one with no
    summariser**, so a finding that cannot be narrated is refused the same way
    whether or not a model is configured -- and so the flag data the verifier
    searched is the exact text the model was given (D139), on the pass path and
    the reject path alike.

    **The template is built before the model is asked.**  It is the answer to
    every failure, so building it first means a finding the template cannot
    narrate is refused before anything is sent anywhere rather than after.
    """

    findings = tuple(flags)
    data = build_flag_payload(findings, band, contributions)
    asked = load_prompt() if prompt is None else prompt
    fallback = template_summary(findings, band)
    if summarizer is None:
        return _template(fallback, asked.version)
    text = summarizer.summarize(asked.text + _SEPARATOR + data.to_json())
    if text is None:
        return _template(fallback, asked.version)
    passed, unsupported = verify_summary(text, data)
    if passed:
        return Narration(
            summary=text,
            summary_source=MODEL,
            verification=PASSED,
            model_name=summarizer.model_name,
            unsupported=(),
            prompt_version=asked.version,
        )
    return Narration(
        summary=fallback,
        summary_source=TEMPLATE,
        verification=FAILED,
        model_name=None,
        unsupported=unsupported,
        prompt_version=asked.version,
    )


def _template(summary: str, version: str) -> Narration:
    """A fallback summary as a record: the template wrote it and nothing was checked."""
    return Narration(
        summary=summary,
        summary_source=TEMPLATE,
        verification=NOT_CHECKED,
        model_name=None,
        unsupported=(),
        prompt_version=version,
    )
