"""What a summary carries, and the question of whether the flags back it.

A number is a digit run with no word character beside it, a date is a digit run
joined by ``-`` or ``/``, and a field name is a flag id the registry knows or a
capitalised token shaped like an identifier.  Every token comes back as
written, in order, repeats kept.
"""

import re

from app.risk import flag_ids

__all__ = [
    "extract_numbers",
    "extract_dates",
    "extract_field_names",
    "verify_summary",
]

#: A digit run and at most one decimal part. The two lookarounds are the rule
#: in prose: no word character directly before the run or directly after it,
#: so a digit inside a word is not a number and a standalone digit always is.
_NUMBER = re.compile(r"(?<![\w])\d+(?:\.\d+)?(?![\w])")

#: The two spellings a date is written in: ISO ``YYYY-MM-DD``, and the slash
#: form with a two- or four-digit year.  The lookarounds are 17.1's, so a date
#: stands alone as written and an ISO timestamp is not read as one.
_DATE = re.compile(r"(?<![\w])(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})(?![\w])")

#: A capitalised word holding no underscore.  An id is left to :data:`_FLAG_ID`
#: rather than answered twice, so one flag id is one token.
_CAPITALISED = re.compile(r"(?<![\w])[A-Z][A-Za-z0-9]*(?![\w])")

#: Every id the registry knows, longest first so the longer of two ids wins,
#: and word-bounded so an id inside a longer word is not read out of it.
_FLAG_ID = re.compile(
    r"(?<![\w])(?:{0})(?![\w])".format(
        "|".join(
            re.escape(f) for f in sorted(flag_ids.ALL_FLAG_IDS, key=len, reverse=True)
        )
    )
)


def extract_numbers(text: str) -> tuple[str, ...]:
    """The number tokens ``text`` carries, in order, repeats kept."""
    return tuple(match.group() for match in _NUMBER.finditer(text))


def extract_dates(text: str) -> tuple[str, ...]:
    """The date tokens ``text`` carries, in order, repeats kept."""
    return tuple(match.group() for match in _DATE.finditer(text))


def extract_field_names(text: str) -> tuple[str, ...]:
    """The field names ``text`` carries: the ids it names and what looks like one."""
    hits = [
        (match.start(), match.group())
        for pattern in (_CAPITALISED, _FLAG_ID)
        for match in pattern.finditer(text)
    ]
    hits.sort()
    return tuple(token for _, token in hits if _names_a_field(token))


def verify_summary(summary: str, flag_data: object) -> tuple[bool, tuple[str, ...]]:
    """Whether every token ``summary`` carries is printed in ``flag_data``, and those that are not.

    ``flag_data`` is searched as the text it prints.  The offending tokens come
    back once each, in the order the summary writes them, so an empty tuple is
    the pass.  Nothing raises: a refusal has to be a value the caller can act on.
    """
    printed = str(flag_data)
    unsupported: list[str] = []
    for extract in (extract_numbers, extract_dates, extract_field_names):
        for token in extract(summary):
            if token not in printed and token not in unsupported:
                unsupported.append(token)
    return not unsupported, tuple(
        sorted(unsupported, key=lambda token: summary.index(token))
    )


def _names_a_field(token: str) -> bool:
    """Whether a capitalised word is a name rather than the first word of a sentence."""
    return (
        any(character.isdigit() for character in token)
        or any(character.isupper() for character in token[1:])
        or (len(token) > 1 and token.isupper())
    )
