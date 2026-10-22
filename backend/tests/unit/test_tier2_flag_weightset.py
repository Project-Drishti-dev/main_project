"""15.14 -- every id a Tier 2 flag reports under is a row in weightsets/v1.yaml.

7.1's completeness test works out what the file has no row for by walking
:data:`app.risk.flag_ids.FLAG_IDS`, so it cannot see a rule naming an id the
vocabulary never held: an id in neither the vocabulary nor the file leaves that
missing set empty and 7.1 green, and 7.3's lookup is the first thing to notice
-- at scoring time, on a document nobody suspected.  **The claim is therefore
read from the emitting side**, the ids :data:`~app.pipeline.tier2.flags.RULES`
names rather than the vocabulary they ought to sit in, and the two links in
that chain are held separately below so a failure names which one broke.

**The file is read by path and never through 7.2's loader**, as 7.1's own file
does: the claim is about what this file holds, and the loader is how the engine
reaches the same bytes as a package resource.  It is parsed per test and never
cached, so a test that rewrote the file would not be answered from a
neighbour's reading and a missing file raises here rather than reading as an
empty weightset, which scores every flag at zero.

**An empty rule table would make every claim below vacuously true**, so the
table is asserted to hold a rule before it is read instead of being left to
the set arithmetic to notice.
"""

from pathlib import Path

import yaml

from app.pipeline.tier2 import flags
from app.risk import flag_ids

#: The weightset this file is written against, read by path rather than
#: imported: 7.2 is what turns this file into an object.
WEIGHTSET_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "risk" / "weightsets" / "v1.yaml"
)


def entries():
    """Return the per-id rows, read past the file's own two top-level keys."""
    return yaml.safe_load(WEIGHTSET_PATH.read_text(encoding="utf-8"))["flags"]


def reported_ids():
    """Return the ids the Tier 2 rules report under, or a refusal of none.

    An empty table is refused rather than returned as an empty set, because an
    empty set is a subset of every weightset and would pass the claims below
    on a table that reports nothing at all.
    """
    assert flags.RULES, (
        "app.pipeline.tier2.flags.RULES names no module, so every id claim "
        "here would be answered by an empty table rather than by the six "
        "rules that ship"
    )
    return {rule.flag_id for rule in flags.RULES}


def test_every_id_the_tier_2_rules_report_under_is_a_row_in_the_weightset():
    """The claim 15.14 is named for: no rule reports under a row that is not there.

    7.3's lookup raises on an id the file holds no row for, so a flag built
    under one and carried into a screening stops the cascade rather than
    quietly scoring as zero.  The ids are named in the failure, since six of
    them is short enough to read.
    """
    missing = sorted(reported_ids() - set(entries()))

    assert missing == [], (
        "these ids are named by app.pipeline.tier2.flags.RULES and "
        "weightsets/v1.yaml holds no row for them: " + ", ".join(missing)
    )


def test_the_weightset_completeness_test_still_covers_every_tier_2_id():
    """7.1's claim is only a completeness claim while RULES stays in the vocabulary.

    The missing-id set it computes comes from :data:`flag_ids.FLAG_IDS`, so a
    rule added ahead of its constant leaves that set empty and 7.1 passing.
    This is the link the test above leans on, held on its own so the failure
    says which of the two broke rather than only that something did.
    """
    unknown = sorted(reported_ids() - flag_ids.FLAG_IDS)

    assert unknown == [], (
        "these ids are in app.pipeline.tier2.flags.RULES and not in "
        "flag_ids.py, so no completeness test can ever reach them: "
        + ", ".join(unknown)
    )


def test_the_band_a_tier_2_flag_carries_is_the_one_its_own_row_declares():
    """`Rule.weight_band` says it mirrors this file, and two tables can drift.

    The band is the half an officer reads and the weight is the number that
    scored it, so a flag carrying a band its own row does not declare reads as
    one severity and was measured as another.  A row that is not there at all
    reads as `None` and fails here rather than raising a `KeyError` that names
    no rule; the test above owns that claim and owns the naming of the id.
    """
    rows = entries()
    declared = {flag_id: row["band"] for flag_id, row in rows.items()}

    wrong = {
        rule.flag_id: (rule.weight_band, declared.get(rule.flag_id))
        for rule in flags.RULES
        if rule.weight_band != declared.get(rule.flag_id)
    }

    assert wrong == {}
