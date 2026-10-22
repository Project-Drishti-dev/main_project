"""No code path maps the ``review`` band onto an automatic rejection.

Task 7.10 asks for a test asserting an *absence*: that nothing anywhere in
the service turns 7.9's middle band into a rejection of a traveller.  The
claim is about what ``review`` may never **cause**, not about the band
existing -- 7.9 has already answered that -- and it is a claim about the
whole backend, not about one module, because the code that could carry a
mapping is code nobody has written yet.

**The claim is walked over the source, not observed at runtime.**  A band
reaches no response body, no score and no officer's screen today, so a
runtime assertion would pass for the wrong reason: there is no path left to
run.  The walk is the form of this assertion that is still true once
Part 7.15 produces a band and Part 8 records a decision.

**A unit here is a statement, and a mapping puts both words in one.**  A
mapping is a decision derived from a band, so it is written where the two
appear together: a lookup table keyed by a band, a conditional on
``to_band(score)`` or on a flag's ``weight_band``, a tuple of bands a
rejection is taken from, a call handed both.  Each statement's own subtree
is the unit, which is why a two-line ``if`` is caught as one statement
rather than as a band in one line and a rejection in the other.  A function
body is deliberately **not** a unit: Part 8's ledger will hold the officer's
own three choices in one module beside the band that was shown, and reading
the module as a single expression would report a validator refusing a
malformed band as a rejection of a traveller.

**A derivation split across two statements is the walk's limit, and the
claim beside it is what covers it.**  ``if to_band(score) == "review": return
_the_word()`` puts the band in one statement and the rejection in another,
and the walk cannot see that they are one path.  The second claim below does:
it is an absence of the *word*, so a rejection spelled anywhere in the
service fails it whether a band stands next to it or not.

**Docstrings and comments are not code and are not walked.**  The parsing
modules say they "reject" a line, a frame and a spelling many times over,
and 17.11's reject-and-fallback path rejects a *summary*.  A walk over
prose would either drown in those or, once tuned to miss them, be too weak
to catch a real mapping.

**Invariants**

- No statement in :mod:`app` puts a band and a rejection in the same
  expression, and no line of the service's data files does either.
- The service's only vocabulary for a decision is the officer's own three
  choices, declared once in :mod:`app.audit.decision` since 10.6: no
  identifier and no string in :mod:`app` is a rejection beside that
  declaration, so no band, no score and no flag can reach one.
- The walk is non-vacuous in both directions: it reaches every module in
  the package, it really does find ``review`` written in this tree's code,
  and it stays silent on a rejection that never mentions a band.
- The detector is held against the shapes a mapping is written in, so a
  walk that matched nothing would fail here rather than pass quietly.
"""

import ast
import pathlib
import re

import pytest

from app.risk import bands as bands_module
from app.risk.bands import to_band
from app.risk.config import LOW_MAX, REVIEW_MAX
from app.risk.flags import WEIGHT_BANDS
from app.risk.hard_rules import MAX_SCORE, MIN_SCORE
from app.audit import decision

#: The service, walked below.  Derived from this suite's own import rather
#: than spelled out, so a second application package cannot be added beside
#: the first without the walk reaching it.
APP_PACKAGE = pathlib.Path(bands_module.__file__).resolve().parents[1]

#: The data files inside the package.  A mapping written as configuration is
#: still a mapping, and a walk that stopped at ``.py`` would leave the whole
#: policy-as-data escape hatch open.
DATA_SUFFIXES = frozenset({".json", ".yaml", ".yml"})

#: The band this task protects, named once and read by everything below.
PROTECTED_BAND = "review"

#: The spellings an automatic rejection of a traveller can be written in.
#: Stems rather than whole words, so ``rejected`` and ``rejection`` are caught
#: beside ``reject``, and matched as substrings so an identifier such as
#: ``auto_reject_bands`` is caught too.
REJECT_STEMS = (
    "reject",
    "deny",
    "declin",
    "not_admitted",
    "not admitted",
    "entry_denied",
    "entry denied",
    "admission_denied",
    "admission denied",
    "entry_refused",
    "entry refused",
)

REJECT_PATTERN = re.compile(
    "|".join(re.escape(stem) for stem in REJECT_STEMS), re.IGNORECASE
)

#: The nodes that open a scope rather than being one statement of behaviour.
#: A function, a class and a module are walked *through*, never read whole:
#: their bodies are the statements that have to be judged, and reading a
#: module as one expression would join two unrelated claims.
SCOPE_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Module)

#: Every ``review`` score on the scale, one point apart.  Read off the
#: committed pair rather than typed, so a retune of ``D28`` moves the claim.
REVIEW_SCORES = [
    LOW_MAX + (index + 1) for index in range(int(REVIEW_MAX - LOW_MAX))
]


def _source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _python_modules() -> list[pathlib.Path]:
    """Every module in the service, in a stable order."""
    return sorted(APP_PACKAGE.rglob("*.py"))


def _data_files() -> list[pathlib.Path]:
    """Every data file the service loads from beside its code."""
    return sorted(
        path
        for path in APP_PACKAGE.rglob("*")
        if path.is_file() and path.suffix.lower() in DATA_SUFFIXES
    )


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
    if isinstance(node, ast.arg):
        return [node.arg]
    if isinstance(node, ast.keyword) and node.arg:
        return [node.arg]
    return []


def _is_the_protected_band(text: str) -> bool:
    """Whether a written spelling is the band this task protects.

    **Only ``review`` counts.**  A ``high`` mapping is 23.9's and Part 8's
    question -- the abstract gives the officer the decision on every case --
    and holding it here would be a claim this task cannot source.  A name
    carrying the word counts beside the plain spelling, so a threshold read
    by its own name is caught too.
    """
    folded = text.casefold()
    return PROTECTED_BAND in folded


def _statements(tree: ast.AST) -> list[ast.stmt]:
    """The statements of a tree, the units everything below is judged in."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt) and not isinstance(node, SCOPE_NODES)
    ]


def _evidence(node: ast.AST, docstrings: set[int]) -> tuple[set[str], set[str]]:
    """The band names and the rejection words inside one statement."""
    bands, rejections = set(), set()
    for inner in ast.walk(node):
        if id(inner) in docstrings:
            continue
        for text in _written_texts(inner):
            if _is_the_protected_band(text):
                bands.add(text)
            if REJECT_PATTERN.search(text):
                rejections.add(text)
    return bands, rejections


def _mapped_statements(source: str) -> list[tuple[int, str]]:
    """Every statement putting a band and a rejection in the same breath."""
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    mappings = []
    for node in _statements(tree):
        bands, rejections = _evidence(node, docstrings)
        if bands and rejections:
            mappings.append(
                (node.lineno, f"{sorted(bands)} beside {sorted(rejections)}")
            )
    return mappings


def _rejection_words(source: str) -> set[str]:
    """Every rejection spelling the code writes, docstrings aside."""
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, SCOPE_NODES) or id(node) in docstrings:
            continue
        for text in _written_texts(node):
            if REJECT_PATTERN.search(text):
                found.add(text)
    return found


def _mapped_data_lines(text: str) -> list[tuple[int, str]]:
    """Every data line putting a band and a rejection in the same breath."""
    mappings = []
    for number, line in enumerate(text.splitlines(), start=1):
        words = {word.casefold() for word in re.findall(r"[A-Za-z_]+", line)}
        # A data file is read as text rather than as Python, so the band side
        # is the spelled-out name rather than any word carrying "band".
        if PROTECTED_BAND in words and REJECT_PATTERN.search(line):
            mappings.append((number, line.strip()))
    return mappings


# --- the band being protected ---------------------------------------------


def test_the_band_to_protect_is_one_the_engine_actually_reaches():
    """A band nothing produces cannot be auto-rejected, so this is the floor.

    7.9 made this assertion possible and this is the half that keeps it
    meaningful: ``review`` is one of the three names, it is a range on the
    scale rather than a point, and every score inside it reads it.  The
    end-to-end case -- three low findings summing to 45 -- is in
    ``test_to_band.py``; this reads the same claim off the committed
    thresholds so the two cannot disagree.
    """
    assert PROTECTED_BAND in WEIGHT_BANDS
    assert MIN_SCORE < LOW_MAX < REVIEW_MAX < MAX_SCORE
    assert REVIEW_SCORES
    assert min(REVIEW_SCORES) > LOW_MAX
    assert max(REVIEW_SCORES) == REVIEW_MAX
    assert {to_band(score) for score in REVIEW_SCORES} == {PROTECTED_BAND}


# --- the walk over the service --------------------------------------------


def test_no_module_in_the_service_maps_a_band_onto_a_rejection():
    """7.10's claim, over every module the service ships."""
    mappings = {
        path.relative_to(APP_PACKAGE).as_posix(): found
        for path in _python_modules()
        if (found := _mapped_statements(_source(path)))
    }

    assert mappings == {}


def test_no_data_file_in_the_service_maps_a_band_onto_a_rejection():
    """The same claim where a mapping would be written as data, not as code."""
    mappings = {
        path.relative_to(APP_PACKAGE).as_posix(): _mapped_data_lines(_source(path))
        for path in _data_files()
        if _mapped_data_lines(_source(path))
    }

    assert mappings == {}


def test_the_only_rejection_words_in_the_service_are_the_officers_own_choice():
    """7.10's second claim, narrowed by 10.6 to the part that still holds.

    10.6 is the first change to write a rejection into the backend, and it
    wrote **the officer's own choice** -- the abstract's "the officer chooses
    to allow entry, send the traveller for further inspection, or reject
    entry" -- which is what this file's docstring said the first such change
    would have to record in :mod:`docs.DECISIONS` (D70).  It is a choice
    *written down*, not a band acted on.

    **What survives is the half that matters**: the word is in one module,
    it is there as the declaration of the three choices and nowhere else, so
    no band, no score and no flag can reach one.  A walk that matched nothing
    passed this claim before 10.6 for the wrong reason; now it has to find
    the declaration, and it has to find nothing else.  **It is still what
    covers the walk's limit**: a path that builds the rejection in one
    function and chooses it in another is a mapping the statement walk cannot
    see, and is a word this one finds.
    """
    vocabulary = {
        path.relative_to(APP_PACKAGE).as_posix(): _rejection_words(_source(path))
        for path in _python_modules()
        if _rejection_words(_source(path))
    }
    # The adverse choice and the constant that declares it: one declaration,
    # and the walk finds it as the two spellings it is written in.  Renaming
    # either of them fails this, which is the point.
    declared = {choice.casefold() for choice in decision.OFFICER_ACTIONS} | {
        "reject_entry"
    }

    assert set(vocabulary) == {"audit/decision.py"}
    for words in vocabulary.values():
        assert {word.casefold() for word in words} <= declared


# --- the walk is a walk, and it is of this tree ---------------------------


def test_the_walk_reaches_every_module_the_service_ships():
    """An absence nobody looked for is not an absence, so the file set is
    held: every ``.py`` under the package, the named modules included, and
    the data files beside them."""
    walked = {path.relative_to(APP_PACKAGE).as_posix() for path in _python_modules()}
    data = {path.relative_to(APP_PACKAGE).as_posix() for path in _data_files()}

    assert walked == {
        path.relative_to(APP_PACKAGE).as_posix() for path in APP_PACKAGE.rglob("*.py")
    }
    assert {
        "risk/bands.py",
        "risk/config.py",
        "main.py",
        "pipeline/tier0/runner.py",
    } <= walked
    assert {"risk/weightsets/v1.yaml", "seed/watchlist.json"} <= data


def test_the_walk_finds_a_band_written_in_this_tree_and_reports_nothing():
    """The band side of the detector is live, so the silence means something.

    :func:`~app.risk.bands.to_band` answers ``review`` in its own code, the
    runner names the band on a flag, and 10.6's ``app.audit.decision`` writes
    all three band names into one tuple, so the walk does read bands in the
    real tree -- including the one module that also holds the officer's
    choices -- and it finds no rejection beside one.  **A detector that
    never matched a band would pass the test above for the wrong reason**,
    and this is what closes that.
    """
    written = set()
    for path in _python_modules():
        tree = ast.parse(_source(path))
        docstrings = _docstring_nodes(tree)
        for node in _statements(tree):
            if _evidence(node, docstrings)[0]:
                written.add(path.relative_to(APP_PACKAGE).as_posix())
                break

    assert {
        "risk/bands.py",
        "pipeline/tier0/runner.py",
        "audit/decision.py",
    } <= written


# --- the detector against the shapes a mapping is written in --------------


@pytest.mark.parametrize(
    ("kind", "source"),
    [
        pytest.param(
            "code",
            'DECISIONS = {"low": "allow", "review": "reject", "high": "reject"}\n',
            id="a-lookup-table",
        ),
        pytest.param(
            "code",
            "def decide(band):\n"
            '    return "reject" if band == "review" else "allow"\n',
            id="a-conditional-expression",
        ),
        pytest.param(
            "code",
            "def decide(score):\n"
            '    if to_band(score) == "review":\n'
            '        return "entry denied"\n'
            '    return "allow"\n',
            id="an-if-on-a-banded-score",
        ),
        pytest.param(
            "code",
            'AUTO_REJECT_BANDS = ("high", "review")\n',
            id="a-tuple-of-bands-named-after-the-rejection",
        ),
        pytest.param(
            "code",
            "def outcome(flag):\n"
            '    if flag.weight_band == "review":\n'
            '        return DENY_WORD\n'
            '    return "allow"\n',
            id="an-if-on-a-flags-weight-band",
        ),
        pytest.param(
            "data", 'DECISIONS:\n  low: allow\n  review: reject\n', id="as-data"
        ),
    ],
)
def test_a_mapping_written_in_any_of_its_shapes_is_reported(kind, source):
    """The shapes above are the ways 7.10's opposite is actually written.

    A table keyed by a band, a conditional on one, a two-line ``if`` over
    :func:`~app.risk.bands.to_band`, a tuple of bands named after the
    rejection, a test on a flag's own ``weight_band``, and the same thing
    written as configuration.  **Held against the detector and not against
    the tree**, because a walk that matched nothing is exactly what a test
    asserting an absence would otherwise report as a pass.
    """
    found = (
        _mapped_data_lines(source)
        if kind == "data"
        else _mapped_statements(source)
    )

    assert found


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            'DECISIONS = {"low": "allow", "high": "reject"}\n',
            id="a-high-mapping",
        ),
        pytest.param(
            'OUTCOME = "reject"\n', id="a-rejection-with-no-band-in-sight"
        ),
        pytest.param(
            "def decide(band):\n"
            "    if band not in WEIGHT_BANDS:\n"
            '        raise FlagValueError("a band this project cannot read")\n'
            '    return "allow"\n',
            id="a-validation-refusal-beside-a-band",
        ),
        pytest.param(
            "def decide(band):\n"
            "    if band == 'high':\n"
            '        return "refused entry"\n'
            "    if band not in WEIGHT_BANDS:\n"
            '        raise FlagValueError("refused: not one of the three")\n'
            '    return "allow"\n',
            id="refused-spelled-as-a-word",
        ),
    ],
)
def test_a_rejection_that_never_derives_from_a_band_is_not_reported(source):
    """The precision half: 7.10 is about ``review``, not about rejections.

    A ``high`` mapping is left for 23.9 and Part 8, which own the officer's
    decision, and a bare ``"reject"`` is how 17.11's rejected *summary* is
    spelled.  **A refusal of a malformed value is not a refusal of a
    traveller**, which is why ``refuse``/``refused`` is deliberately absent
    from the vocabulary: this codebase uses it for a gate refusing bad
    input, and a walk that read it as a rejection would fire on every
    validator that sits beside a band.
    """
    assert _mapped_statements(source) == []


def test_the_walk_ignores_prose_that_rejects_a_line_or_a_summary():
    """Docstrings and comments are why this reads a tree rather than a file.

    Three shapes this repository really contains: a parser rejecting a
    spelling, a comment about a misread being rejected, and a verifier's
    rejection of a summary.  Read as code, each is the forbidden mapping.
    """
    source = (
        "def parse(code):\n"
        '    """Reject ``IND`` -- it is three uppercase letters."""\n'
        "    # A misread is rejected on the ordinary ground.\n"
        "    if code in KNOWN:\n"
        "        return code\n"
        '    raise MrzValueError("unread")\n'
    )

    assert _mapped_statements(source) == []
    assert _rejection_words(source) == set()
