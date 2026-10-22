"""Cross-document name comparison: two printed names, one answer.

16.4.  :func:`names_match` compares two names over the keys 16.3 builds and
returns a similarity beside the tokens that did not agree.  D128 records why.
"""

import dataclasses
import numbers

from app.pipeline.tier0.td3 import MrzValueError, transliterate_names

__all__ = ["NameMatch", "names_match", "normalise_name"]

#: The similarity two names must reach before they are called one name.
#: Measured: it refuses ``Rahman``/``Rahmani`` at 0.857, one letter apart.
DEFAULT_TOLERANCE = 0.95

#: Digraphs two spellings disagree about, each folded to the letter it stands
#: for.  D127 kept these out of the key so that this could forgive them here.
FOLDED_DIGRAPHS = {"UE": "U", "SS": "S", "PH": "F"}

#: What a compound surname may be printed with, each read as a token edge.
COMPOUND_SEPARATORS = "-.,"


@dataclasses.dataclass(frozen=True)
class NameMatch:
    """How alike two names are, and which tokens did not agree.

    ``similarity`` is in ``[0, 1]``; ``differing`` holds folded-token pairs,
    one per compared position, with ``""`` where a side had nothing to pair.
    ``matched`` is that similarity read against the tolerance asked for.
    """

    similarity: float
    differing: tuple[tuple[str, str], ...]
    tolerance: float

    @property
    def matched(self) -> bool:
        """True when the similarity reaches the tolerance asked for."""
        return self.similarity >= self.tolerance


def normalise_name(s: str) -> str:
    """Return ``s`` as an upper-case, unaccented, single-spaced comparison key.

    Casing and diacritics are Tier 0's, reached through
    ``td3.transliterate_names``; only the whitespace is this function's own.
    Digraphs stay as printed (D127).

    :raises MrzValueError: if ``s`` is not a string.  The guard is here rather
        than left to Tier 0 because ``s.upper()`` runs first, and a bare
        ``AttributeError`` is not a :class:`ValueError`.
    """
    if not isinstance(s, str):
        raise MrzValueError(
            f"a cross-document name must be a string, not {type(s).__name__}"
        )
    return " ".join(transliterate_names(s.upper(), ())[0].split())


def names_match(
    a: str, b: str, tolerance: float = DEFAULT_TOLERANCE
) -> NameMatch:
    """Compare two printed names, forgiving digraphs, compounds and order.

    A similarity over the whole name plus the tokens that did not agree, so
    a caller that is told "not the same name" is also told which token.

    :raises MrzValueError: if either name is not a string or holds no token,
        or if ``tolerance`` is not a real number in ``[0, 1]``.  Tier 0's
        error, so a caller catching one around its cascade keeps working.
    """
    _check_tolerance(tolerance)
    left = _folded_tokens(a)
    right = _folded_tokens(b)
    if not left or not right:
        raise MrzValueError(
            "a cross-document name match needs a name on both sides"
        )
    pairs = _pairing(left, right)
    return NameMatch(
        similarity=sum(_ratio(x, y) for x, y in pairs) / len(pairs),
        differing=tuple((x, y) for x, y in pairs if x != y),
        tolerance=tolerance,
    )


def _check_tolerance(tolerance: float) -> None:
    """Refuse a tolerance that is not a real number in ``[0, 1]``.

    Nothing is coerced: a clipped or rounded threshold is a tolerance
    nobody chose, and D116's rule is that a malformed number is refused
    rather than repaired.
    """
    if isinstance(tolerance, bool) or not isinstance(tolerance, numbers.Real):
        raise MrzValueError(
            "a name tolerance must be a real number, not "
            f"{type(tolerance).__name__}"
        )
    if not 0.0 <= tolerance <= 1.0:
        raise MrzValueError(
            f"a name tolerance must be in [0, 1], not {tolerance}"
        )


def _folded_tokens(name: str) -> tuple[str, ...]:
    """Return ``name``'s tokens, folded and sorted, with compounds split.

    Every compound edge becomes a space so ``SMITH-JONES`` and
    ``SMITH JONES`` hold the same tokens, and sorting makes token order
    unable to reach the answer at all.
    """
    spaced = normalise_name(name)
    for separator in COMPOUND_SEPARATORS:
        spaced = spaced.replace(separator, " ")
    return tuple(sorted(_fold(token) for token in spaced.split()))


def _fold(token: str) -> str:
    """Return ``token`` with each folded digraph replaced by its letter.

    One left-to-right pass that never overlaps, so a fold cannot swallow a
    letter the next fold would have begun on.
    """
    folded = []
    index = 0
    while index < len(token):
        digraph = token[index:index + 2]
        if digraph in FOLDED_DIGRAPHS:
            folded.append(FOLDED_DIGRAPHS[digraph])
            index += 2
        else:
            folded.append(token[index])
            index += 1
    return "".join(folded)


def _ratio(a: str, b: str) -> float:
    """Return how alike two folded tokens are, 1.0 equal and 0.0 unlike.

    One minus the Levenshtein distance over the longer token's length, so a
    single letter added to a seven-letter surname scores exactly 6/7.
    """
    if a == b:
        return 1.0
    row = list(range(len(b) + 1))
    for seen, first in enumerate(a, start=1):
        column = [seen]
        for index, second in enumerate(b, start=1):
            column.append(
                min(
                    row[index] + 1,
                    column[index - 1] + 1,
                    row[index - 1] + (first != second),
                )
            )
        row = column
    return 1.0 - row[len(b)] / max(len(a), len(b))


def _pairing(
    left: tuple[str, ...], right: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Return the pairs covering every token of both names, one-to-one.

    Both orders are paired greedily and the higher total wins, with the
    pairing itself as the tie-break.  Either side is padded to the longer
    of the two first, so no token is dropped and the answer does not depend
    on which name was passed as ``a``.
    """
    width = max(len(left), len(right))
    padded_left = left + ("",) * (width - len(left))
    padded_right = right + ("",) * (width - len(right))
    return max(
        (
            _greedy(padded_left, padded_right),
            _greedy(padded_right, padded_left),
        ),
        key=lambda pairs: (
            sum(_ratio(x, y) for x, y in pairs),
            tuple(pairs),
        ),
    )


def _greedy(
    over: tuple[str, ...], spare: tuple[str, ...]
) -> list[tuple[str, str]]:
    """Pair each token of ``over`` with its nearest free token of ``spare``.

    Ties go to the greater token, so the pairs do not depend on the order
    the names were printed in.
    """
    pairs = []
    free = list(spare)
    for token in over:
        best = None
        for index, candidate in enumerate(free):
            ranked = (_ratio(token, candidate), candidate)
            if best is None or ranked > best[0]:
                best = (ranked, index)
        if best is None:
            pairs.append((token, ""))
        else:
            pairs.append((token, free.pop(best[1])))
    return pairs
