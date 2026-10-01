"""The v1 weightset holds a weight and a band for every id, and the file says so.

Task 7.1 is a completeness claim, and the failure it exists to prevent is a
flag reaching the risk engine with no weight for it: 7.3's lookup raises on an
unknown id rather than scoring a flag as zero, so a missing row stops a whole
screening rather than quietly under-counting one finding.  **That is why the
headline test below is one set comparison and nothing clever.**

The rest of this file is the rest of that claim's integrity, because a file
that is complete can still be wrong in four ways that are only visible here:
an id the vocabulary does not have (dead policy, and one 7.3 could never
reach), a band outside the record's own three names, a weight that is not a
number, and a vocabulary of three bands of which only two are ever used.

**The numbers are read, never retyped.**  The bands are checked against
:data:`app.risk.flags.WEIGHT_BANDS`, the vocabulary against
:data:`app.risk.flag_ids.FLAG_IDS`, and the bands of the three watchlist ids
against the runner's own table -- because 6.4 states a kind's severity beside
its label and this file states it a second time, and two tables holding one
fact is how the two halves of a weightset drift apart.

The file is read by path here, deliberately: this file's claim is about the
file's own contents, and 7.2's loader is how the engine reaches the same file
as a package resource, held by ``test_weightset_loader.py``.
"""

from pathlib import Path

import pytest
import yaml

from app import version
from app.pipeline.tier0 import runner
from app.risk import flag_ids, flags
from app.risk.config import REVIEW_MAX

#: The weightset this file is written against.  A path under the tests, not an
#: import: 7.2 is what turns this file into an object.
WEIGHTSET_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "risk" / "weightsets" / "v1.yaml"
)

#: The bands in the order the record names them, severity first, so a range
#: comparison below reads as "low is below review is below high".
BAND_ORDER = ("low", "review", "high")

def weightset():
    """The file parsed, or a loud failure rather than an empty mapping.

    **Parsed once per test and never cached between them**, so a test that
    rewrote the file would not be answered from a neighbour's reading.  A
    missing file raises here rather than being read as an empty weightset: an
    engine handed an empty weightset scores every flag at zero, which is the
    failure this whole file is about.
    """
    return yaml.safe_load(WEIGHTSET_PATH.read_text(encoding="utf-8"))


def entries():
    """The per-id entries, read past the file's own two top-level keys."""
    return weightset()["flags"]


def test_the_weightset_holds_a_weight_and_a_band_for_every_flag_id():
    """The claim 7.1 is named for: no id is left without a number."""
    missing = sorted(flag_ids.FLAG_IDS - set(entries()))

    assert missing == [], (
        "every id in flag_ids.py needs a weight and a band; these have none: "
        + ", ".join(missing)
    )


def test_the_weightset_holds_no_id_the_vocabulary_does_not_have():
    """A row for an id no rule can emit is policy nothing will ever read."""
    unknown = sorted(set(entries()) - flag_ids.FLAG_IDS)

    assert unknown == [], (
        "these rows are not ids in flag_ids.py, so no rule can ever emit them "
        "and no test can reach them: " + ", ".join(unknown)
    )


def test_the_file_holds_only_a_version_and_the_flags():
    """**No hard-fail list is written here**, on 6.5's reason.

    Which rules override is ``runner._HARD_FAIL_IDS``, a union of each family's
    own table held beside its labels, so a second list in this file could
    disagree with those without either one noticing.  A top-level key is the
    place such a list would go, so the keys are held to the two this file owns.
    """
    assert set(weightset()) == {"ruleset_version", "flags"}


def test_the_entries_hold_a_weight_and_a_band_and_nothing_else():
    """A key nothing reads is a claim no test can hold to."""
    wrong = {
        flag_id: sorted(set(row) - {"weight", "band"})
        for flag_id, row in entries().items()
        if set(row) != {"weight", "band"}
    }

    assert wrong == {}


def test_every_weight_is_a_real_positive_number_and_not_a_boolean():
    """``True`` is one point in Python's own arithmetic, and it is not a weight."""
    wrong = {
        flag_id: row["weight"]
        for flag_id, row in entries().items()
        if isinstance(row["weight"], bool)
        or not isinstance(row["weight"], (int, float))
        or not row["weight"] > 0
    }

    assert wrong == {}


@pytest.mark.parametrize("flag_id", flag_ids.ALL_FLAG_IDS, ids=flag_ids.ALL_FLAG_IDS)
def test_every_band_is_one_the_flag_record_allows(flag_id):
    """The bands are the record's three names and not four or two."""
    assert entries()[flag_id]["band"] in flags.WEIGHT_BANDS


def test_all_three_bands_are_used():
    """A vocabulary of three names with two in it is two names wearing a third.

    Read against ``WEIGHT_BANDS`` rather than against :data:`BAND_ORDER`, so
    the claim is that the record's whole vocabulary is exercised here and not
    that this file happens to use the three it was written with.
    """
    used = {row["band"] for row in entries().values()}

    assert used == flags.WEIGHT_BANDS


def test_the_bands_sit_in_three_disjoint_ranges_high_a_real_distance_above_review():
    """D18's condition on 7.1, and the reason the bands are not decoration.

    ``low``, ``review`` and ``high`` are severity classes, so every ``high``
    weight has to sit above every ``review`` weight and every ``review`` above
    every ``low`` -- otherwise the band an officer reads is decided by a one
    point difference rather than by the finding.  ``D18`` names the gap between
    ``review`` and ``high`` in particular, so it is the one asserted here
    rather than only the ordering.
    """
    ranges = {
        band: [row["weight"] for row in entries().values() if row["band"] == band]
        for band in BAND_ORDER
    }

    assert max(ranges["low"]) < min(ranges["review"])
    assert max(ranges["review"]) < min(ranges["high"])
    assert min(ranges["high"]) - max(ranges["review"]) > 1


def test_no_single_weight_reaches_the_high_threshold_on_its_own():
    """One finding never sends a document to High by itself.

    A flag contributes at most its own weight, because its ``value`` is in
    ``[0, 1]``, so this is the whole of that guarantee: High needs either
    corroboration or 7.6's hard-fail floor of 90.  **It is what keeps a
    stand-in tier-2 classifier from rejecting a genuine traveller by itself**,
    since every module in Part 15 ships as a labelled stub.
    """
    assert max(row["weight"] for row in entries().values()) <= REVIEW_MAX


def test_the_weightset_is_ordered_as_the_vocabulary_orders_the_cascade():
    """The file reads top to bottom in the order the tiers run."""
    assert list(entries()) == list(flag_ids.ALL_FLAG_IDS)


def test_the_bands_the_runner_emits_are_the_bands_here():
    """6.4 states a kind's severity beside its label, and this file states it again.

    The three watchlist ids are the only ones a rule emits today with a band
    of its own, and they are read straight out of
    :data:`~app.pipeline.tier0.runner._WATCHLIST_FLAG` rather than retyped: two
    tables holding one fact is how a weightset and the flags it scores drift
    apart, which is the same reason 6.5 unions the hard-fail tables rather
    than keeping a fourth.
    """
    emitted = {row[0]: row[2] for row in runner._WATCHLIST_FLAG.values()}

    assert emitted, "6.4 states a band for every kind, and there are three"
    assert {flag_id: entries()[flag_id]["band"] for flag_id in emitted} == emitted


def test_the_file_names_the_ruleset_version_the_api_reports():
    """A score is only comparable against the ruleset that produced it.

    ``app.version`` says its own ``RULESET_VERSION`` changes whenever a flag,
    threshold or weight changes, so this file's version and that constant are
    one fact about the same thing and a disagreement between them is a weight
    that was retuned without the version moving -- which is exactly the change
    the abstract requires to be recorded.
    """
    assert weightset()["ruleset_version"] == version.RULESET_VERSION
