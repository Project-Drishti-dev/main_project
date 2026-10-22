"""The two tree hashes, domain-separated: 0x00 for a leaf, 0x01 for a node.

Task 9.5 asks for RFC 6962-style leaf and node hashing "with known-answer
tests".  The known answers are computed here from ``hashlib`` directly and
also pinned as literals, so a refactor that changes what is hashed fails
here rather than agreeing with itself forever.  The rest of the file pins
what the separation buys: a leaf cannot be read as a node, nor a node as a
leaf, which is the reason RFC 6962 prefixes at all.

9.6's ``build_tree`` joins those hashes into a tree, and the root for three
known leaves is pinned the same way -- computed here from ``hashlib`` over
the same digests, and as a literal -- so the split rule cannot drift into
agreeing with itself.  9.7's odd count is pinned from the other side: on
three and five leaves the unpaired leaf reaches the root without being
hashed on the way up, which is a claim about how many hashes the tree spent
and which bytes the root was handed.  9.8's degenerate ends are pinned the
same way: one leaf is its own root and spends no hash at all, and no empty
iterable of any kind answers one.

9.9 answers the sibling path -- ``proof_for`` from one leaf, ``verify_proof``
back up to the root -- and this file pins what a proof *is* rather than only
that one round trip: the steps are a leaf's siblings in walk order with the
side each was on, a promoted leaf's path is one step short of its
neighbours', and a proof is checked by walking rather than by shape, so a
tampered leaf, a swapped side, a malformed sibling and another tree's root
all answer ``False`` rather than raising.

9.10 sweeps the sixteen-leaf tree rather than one spot-checked path: every
index walks up to the root, and one bit flipped in any leaf verifies against
none of the sixteen proofs.

9.7's ``read_digest`` is the reader of the stored spelling -- the 64 hex
characters ``audit_events.record_hash`` and ``ledger_entries.merkle_root``
are written in -- so 9.16 and 9.17 both widen a column through it rather than
each doing it for themselves.
"""

import hashlib
from typing import Any, Iterator

import pytest

from app.ledger import merkle
from app.ledger.canonical import canonical_json
from app.ledger.hashing import hash_record
from app.ledger.merkle import (
    DIGEST_BYTES,
    LEAF_PREFIX,
    NODE_PREFIX,
    MerkleError,
    MerkleTree,
    ProofStep,
    build_tree,
    leaf_hash,
    node_hash,
    read_digest,
    verify_proof,
)


#: A stand-in for the per-record salt 9.4 generates and 9.17 reads back.
SALT = b"\x9a\x1f\x4c\xd2"

RECORD: dict[str, Any] = {
    "actor": "station-3",
    "event_type": "flag_overridden",
    "payload": {"flags": [{"id": "DATE_MISMATCH", "value": 0}], "score": "41.7"},
}

#: The digest 9.3 answers for ``RECORD`` under ``SALT``, pinned from
#: ``test_hashing.py``'s known answer.  A leaf is built from this, not from
#: the record.
RECORD_DIGEST = bytes.fromhex(
    "94219251f9602f5bdc4a324ff4695f71306f83bb69a42d7669816ed57094f7c7"
)


def _sha256(*parts: bytes) -> str:
    """SHA-256 over ``parts`` in the order given, as 64 lowercase hex."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


# --- the known answers ------------------------------------------------------


def test_a_leaf_hashes_to_a_known_digest() -> None:
    """SHA-256 over ``0x00 || data``.  Two data values, so a leaf hash that
    quietly became a plain digest of its data would fail one of them."""
    expected_empty = _sha256(b"\x00")
    expected_abc = _sha256(b"\x00", b"abc")

    assert expected_empty == (
        "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d"
    )
    assert expected_abc == (
        "609f6e36d2405585188d5cfd761f407c7cc46a7d3f314c88270469dde315fcd1"
    )
    assert leaf_hash(b"").hex() == expected_empty
    assert leaf_hash(b"abc").hex() == expected_abc


def test_a_node_hashes_to_a_known_digest() -> None:
    """SHA-256 over ``0x01 || left || right``, over two real leaves rather
    than arbitrary digests, so the vector also pins that leaves compose."""
    left = leaf_hash(b"")
    right = leaf_hash(b"abc")
    expected = _sha256(b"\x01", left, right)

    assert expected == (
        "87c93eee22bfdd3e6dfed019ad8adc8a357e90bc6388d9ef0c2fe461e633204f"
    )
    assert node_hash(left, right).hex() == expected


def test_a_leaf_is_built_from_a_records_digest_and_not_from_the_record() -> None:
    """The ledger holds hashes, not identity data, so a leaf commits to the
    digest 9.3 produced.  Hashing the record itself would commit to the
    payload and put it in the tree's root."""
    expected = _sha256(b"\x00", RECORD_DIGEST)

    assert expected == (
        "a78d21e1d3403125ca62017d1ffd34aec6227a858ae70f59c8eebb3fa9102e50"
    )
    assert hash_record(RECORD, SALT) == RECORD_DIGEST.hex()
    assert leaf_hash(RECORD_DIGEST).hex() == expected
    assert leaf_hash(canonical_json(RECORD).encode("ascii")) != leaf_hash(
        RECORD_DIGEST
    )


# --- the prefixes are the domain separation --------------------------------


def test_the_prefixes_are_the_bytes_rfc_6962_names() -> None:
    """``0x00`` for a leaf and ``0x01`` for an internal node, named rather
    than written inline, so 9.6 and 9.10 cannot pick a different one."""
    assert LEAF_PREFIX == b"\x00"
    assert NODE_PREFIX == b"\x01"
    assert LEAF_PREFIX != NODE_PREFIX


def test_neither_hash_is_a_digest_of_its_payload_without_the_prefix() -> None:
    """The prefix is in the hashed bytes, not added to the output: dropping it
    on the way in changes the answer, so it cannot be decoration."""
    left = leaf_hash(b"")
    right = leaf_hash(b"abc")

    assert leaf_hash(b"abc").hex() != _sha256(b"abc")
    assert node_hash(left, right).hex() != _sha256(left, right)


def test_a_node_cannot_be_passed_off_as_a_leaf() -> None:
    """A leaf over ``0x01 || left || right`` would equal the node over
    ``(left, right)`` if the two domains shared a prefix.  They do not."""
    left = leaf_hash(b"")
    right = leaf_hash(b"abc")

    assert leaf_hash(NODE_PREFIX + left + right) != node_hash(left, right)


def test_a_leaf_cannot_be_passed_off_as_a_node() -> None:
    """The other direction: the same 64 bytes of children, spelled as a
    leaf, is a different hash from the node over those children."""
    left = leaf_hash(b"")
    right = leaf_hash(b"abc")

    assert leaf_hash(LEAF_PREFIX + left + right) != node_hash(left, right)


# --- what the tree above this needs -----------------------------------------


def test_the_same_input_always_hashes_alike() -> None:
    """What 9.10's proof walk and 9.17's recomputation rest on: the root a
    batch was anchored under must still fall out months later."""
    left = leaf_hash(b"a")
    right = leaf_hash(b"b")

    assert leaf_hash(b"a") == leaf_hash(bytearray(b"a")) == left
    assert node_hash(left, right) == node_hash(
        leaf_hash(b"a"), leaf_hash(b"b")
    )


def test_every_hash_is_32_raw_bytes_and_composes_as_a_child() -> None:
    """A node's answer is fed straight back in as a child, so the width has
    to be SHA-256's and it has to be bytes -- ``record_hash``'s 64 hex
    characters are the storage spelling, and a tree is not stored."""
    leaf = leaf_hash(b"a")
    node = node_hash(leaf, leaf_hash(b"b"))

    assert leaf_hash(b"a") == leaf
    for digest in (leaf, node):
        assert isinstance(digest, bytes)
        assert len(digest) == DIGEST_BYTES == 32
        assert digest.hex() != digest.decode("latin-1")
    assert len(node_hash(node, node)) == DIGEST_BYTES


def test_the_order_of_two_children_is_the_trees_and_not_an_arbitrary_one() -> None:
    """A proof that swapped its two siblings would otherwise verify."""
    left = leaf_hash(b"a")
    right = leaf_hash(b"b")

    assert node_hash(left, right) != node_hash(right, left)


def test_a_bytearray_child_is_hashed_as_the_bytes_it_is() -> None:
    """Consistent with 9.3's salt: a caller holding a mutable buffer is no
    reason to refuse a hash, and it is hashed as the bytes it is."""
    left = leaf_hash(b"a")

    assert node_hash(bytearray(left), bytearray(left)) == node_hash(left, left)


# --- the refusals -----------------------------------------------------------


@pytest.mark.parametrize("bad", [b"", b"\x00" * 31, b"\x00" * 33, b"\x00" * 64])
def test_a_node_refuses_a_child_that_is_not_a_digest(bad: bytes) -> None:
    """A child of the wrong width is a truncated or unhashed value, and a
    tree built on one cannot be walked by 9.10.  Refused, not padded."""
    digest = leaf_hash(b"a")

    with pytest.raises(MerkleError):
        node_hash(bad, digest)
    with pytest.raises(MerkleError):
        node_hash(digest, bad)


def test_the_child_refusal_names_the_width_and_shows_no_value() -> None:
    """The message carries the width so the caller can see what was wrong,
    and no bytes of the value, which is a record digest."""
    with pytest.raises(MerkleError) as caught:
        node_hash(b"a", leaf_hash(b"a"))

    assert "1 bytes" in str(caught.value)
    assert isinstance(caught.value, ValueError)


@pytest.mark.parametrize("bad", ["not-bytes", 42, None, ["00" * 32]], ids=repr)
@pytest.mark.parametrize("call", ["leaf", "node"])
def test_a_value_that_is_not_bytes_is_refused_and_its_value_is_not_shown(
    bad: Any, call: str
) -> None:
    """The refusal names the type alone, the way ``_refuse`` does, so a
    record payload reaches no log.  A hex string is refused too, which is
    what stops ``record_hash``'s own spelling being hashed as text."""
    with pytest.raises(TypeError) as caught:
        if call == "leaf":
            leaf_hash(bad)
        else:
            node_hash(bad, leaf_hash(b"a"))

    assert type(bad).__name__ in str(caught.value)
    assert "not-bytes" not in str(caught.value)


def test_hashing_a_leaf_leaves_the_callers_bytes_unchanged() -> None:
    """A builder that handed a buffer in still holds it, and a digest taken
    from it must not move when the buffer does."""
    held = bytearray(b"a")
    first = leaf_hash(held)

    held[0] = ord("b")

    assert first == leaf_hash(b"a") != leaf_hash(b"b")


# --- build_tree -------------------------------------------------------------

#: Two more records and salts, so the tree is built from three *record
#: digests* rather than from arbitrary bytes -- the shape 9.16 hands it.
OTHER_SALT = bytes.fromhex("11223344")
THIRD_SALT = bytes.fromhex("abcdef01")

OTHER_RECORD: dict[str, Any] = {
    "actor": "station-1",
    "event_type": "screening_created",
    "payload": {"document_type": "passport"},
}

THIRD_RECORD: dict[str, Any] = {
    "actor": "station-2",
    "event_type": "batch_anchored",
    "payload": {"size": 3},
}

#: The three record digests the tree is built from, pinned from
#: ``hash_record`` so a later task cannot quietly change what a leaf is.
DIGESTS: tuple[bytes, ...] = (
    RECORD_DIGEST,
    bytes.fromhex(
        "595c43fbf7517bd22af5343a8f7f665f32fba41b9c18a7bf379d78c2116f392b"
    ),
    bytes.fromhex(
        "bd564627435bd8b558f1d2d1f7da0a41bedac1932103ba7ca986c5b5f17d1373"
    ),
)


def test_the_root_of_three_known_leaves_is_a_known_digest() -> None:
    """The 9.6 known answer: three record digests, hashed as leaves, joined
    by ``node_hash``.  Computed here from ``hashlib`` *and* pinned, so the
    root is not whatever the builder happens to say."""
    leaves = [_sha256(b"\x00", digest) for digest in DIGESTS]
    # Three leaves split 2|1, so the right leaf is promoted as-is.
    expected_left = _sha256(b"\x01", bytes.fromhex(leaves[0]),
                             bytes.fromhex(leaves[1]))
    expected_root = _sha256(b"\x01", bytes.fromhex(expected_left),
                             bytes.fromhex(leaves[2]))

    assert expected_root == (
        "4818ebe9dcc3e4132f7cb6da6cb481e8970e411c996531e752503472abfbd5cf"
    )
    assert build_tree(DIGESTS).root == bytes.fromhex(expected_root)


def test_build_tree_takes_record_digests_and_hashes_them_itself() -> None:
    """The leaves a caller passes in are *not* what the tree stores: each is
    hashed with ``leaf_hash`` inside the builder.  A caller cannot skip the
    prefix, and a record payload never reaches the tree."""
    tree = build_tree(DIGESTS)

    assert tree.leaves == tuple(leaf_hash(digest) for digest in DIGESTS)
    assert tree.leaves != DIGESTS
    assert len(tree) == len(DIGESTS)
    assert isinstance(tree, MerkleTree)


def test_build_tree_refuses_a_leaf_that_is_not_a_digest() -> None:
    """A leaf is a record digest like any other child, so a truncated digest
    is refused rather than hashed as data.  A hex string is a ``str`` and so
    is refused by the type check, which is what stops ``record_hash``'s own
    spelling being hashed as text (``D51``)."""
    with pytest.raises(MerkleError):
        build_tree([RECORD_DIGEST[:31]])
    with pytest.raises(TypeError):
        build_tree([RECORD_DIGEST.hex()])
    with pytest.raises(TypeError):
        build_tree(["not-bytes"])


def test_build_tree_from_no_leaves_is_refused() -> None:
    """A root over nothing commits to nothing, so it is refused here rather
    than answered.  9.8 pins the rest of the degenerate cases, below."""
    with pytest.raises(MerkleError):
        build_tree([])


@pytest.mark.parametrize(
    "count, root",
    [
        (2, "604d540f09268b91672ab011394d5266ccd7d4484d0d109411a55848126a1b2c"),
        (3, "d1f13800048f5909d4043fc0c152f6643280cba608b672715e56ce159a20629f"),
        (4, "0dcc2b645c00dfa2338e1c7ac2c4b570beda5a476d58836e55e28bde55e6bee1"),
        (5, "6b313b611b40676b9e1dfd70c4503f2379f88f0f1c2740fb7e1cacc32c113465"),
        (6, "33d501ae67e6e5745c0aa49e3aff95130969b568208b07210c508caa5ff39b3c"),
        (7, "bee2275db16667589a4515f63e0d053a2fa602c1d9f9703e98920a5bdad59baf"),
        (16, "cc6e692ad24b6d105fa005c1028345bd7fd47c0221444ae3e6b9aa3708cacfc2"),
    ],
)
def test_the_root_of_n_leaves_is_a_known_digest(count: int, root: str) -> None:
    """The split rule, pinned as literals over ``leaf_hash(bytes([i]))``
    for ``i`` in ``range(count)``, each fed to ``build_tree`` as a *record
    digest* -- so the leaves are hashed once, inside the builder.
    Recomputing the rule here would only let a wrong rule agree with
    itself; these answers were taken from an independent reference."""
    digests = [bytes.fromhex(_sha256(bytes([i]))) for i in range(count)]

    assert build_tree(digests).root.hex() == root


@pytest.mark.parametrize(
    "count, split", [(3, 2), (5, 4), (6, 4), (7, 4)]
)
def test_the_split_is_not_a_plain_halving(count: int, split: int) -> None:
    """The rule that fixes the shape: the split is the largest power of two
    *strictly below* the count, so 5 splits ``4 | 1`` where a halving would
    split ``2 | 3`` and 6 splits ``4 | 2`` where a halving would give
    ``3 | 3``.  Without this, "halve the list" would pass every known
    answer above that agreed with it."""
    digests = [bytes.fromhex(_sha256(bytes([i]))) for i in range(count)]
    leaves = [leaf_hash(digest) for digest in digests]

    assert build_tree(digests).root != _halved(leaves)
    assert build_tree(digests).root == _split_at(leaves, split)


def _split_at(leaves: list[bytes], split: int) -> bytes:
    """The root over leaf ``leaves`` split at ``split``, computed
    independently of the builder under test."""
    return node_hash(_join(leaves[:split]), _join(leaves[split:]))


def _halved(digests: list[bytes]) -> bytes:
    """The root over ``digests`` by plain halving -- the rule 9.6 is *not*."""
    if len(digests) == 1:
        return digests[0]
    half = len(digests) // 2
    return node_hash(_halved(digests[:half]), _halved(digests[half:]))


def _join(digests: list[bytes]) -> bytes:
    """The root over ``digests`` by the same largest-power-of-two rule the
    builder uses, written out here rather than called, so a wrong rule in
    the builder cannot be mirrored here by accident."""
    if len(digests) == 1:
        return digests[0]
    split = 1 << ((len(digests) - 1).bit_length() - 1)
    return node_hash(_join(digests[:split]), _join(digests[split:]))


# --- the odd-count case: a lone node promoted unchanged ---------------------


def _digests_for(count: int) -> list[bytes]:
    """``count`` record digests, the same shape the known answers use."""
    return [bytes.fromhex(_sha256(bytes([i]))) for i in range(count)]


def test_three_leaves_promote_the_third_one_unchanged() -> None:
    """Three leaves split ``2 | 1``, so the third leaf is the lone node and
    goes into the root as it is -- no hash of its own on the way up.  The
    root is spelled out longhand rather than through ``_join``, so the
    answer does not borrow the builder's split rule, and pinned as the same
    literal 9.6 pinned."""
    first, second, third = (leaf_hash(digest) for digest in _digests_for(3))
    expected = node_hash(node_hash(first, second), third)

    assert expected.hex() == (
        "d1f13800048f5909d4043fc0c152f6643280cba608b672715e56ce159a20629f"
    )
    assert build_tree(_digests_for(3)).root == expected


def test_five_leaves_promote_the_fifth_one_unchanged() -> None:
    """Five leaves split ``4 | 1``, so the lone node is the fifth leaf again
    -- and the four under it are balanced, so the odd count is answered at
    one level rather than by halving into ``2 | 3``."""
    leaves = [leaf_hash(digest) for digest in _digests_for(5)]
    left = node_hash(
        node_hash(leaves[0], leaves[1]), node_hash(leaves[2], leaves[3])
    )
    expected = node_hash(left, leaves[4])

    assert expected.hex() == (
        "6b313b611b40676b9e1dfd70c4503f2379f88f0f1c2740fb7e1cacc32c113465"
    )
    assert build_tree(_digests_for(5)).root == expected


@pytest.mark.parametrize("count", [3, 5])
def test_a_lone_node_is_never_hashed_again_on_the_way_up(count: int) -> None:
    """The three ways to promote a lone node that are not this one: hashed
    as a leaf a second time, padded against itself under ``0x01``, or
    handed over as the *left* child.  None of them is the root 9.6 pinned,
    so "promoted unchanged" is a claim about the bytes, not a comment."""
    digests = _digests_for(count)
    leaves = [leaf_hash(digest) for digest in digests]
    lone = leaves[-1]
    joined = _join(leaves[:-1])
    root = build_tree(digests).root

    assert root != node_hash(joined, leaf_hash(lone))
    assert root != node_hash(joined, node_hash(lone, lone))
    assert root != node_hash(lone, joined)


@pytest.mark.parametrize("count", [3, 5])
def test_a_promotion_spends_no_hash_and_hands_the_leaf_over_once(
    count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What "unchanged" costs: a tree over ``n`` leaves runs ``n - 1`` node
    hashes, and the lone leaf appears as a child of exactly one of them --
    the root's.  A promotion that hashed it again would make ``n``, and one
    that hashed it under ``0x01`` would never hand it over at all."""
    children: list[tuple[bytes, bytes]] = []
    hashing = merkle.node_hash

    def counting(left: bytes, right: bytes) -> bytes:
        children.append((left, right))
        return hashing(left, right)

    monkeypatch.setattr(merkle, "node_hash", counting)
    digests = _digests_for(count)
    build_tree(digests)
    lone = leaf_hash(digests[-1])

    assert len(children) == count - 1
    assert children[-1][1] == lone
    assert sum(1 for pair in children if lone in pair) == 1


# --- the degenerate cases: one leaf, and none ------------------------------


def test_a_single_leaf_becomes_the_root() -> None:
    """One record digests to one leaf, and that leaf *is* the root.  The same
    promotion ``D53`` applies at 3 and 5 leaves, at ``n = 1``: the leaf is
    handed over rather than joined to anything.  Spelled through
    ``leaf_hash`` alone and pinned as a literal, so the answer does not come
    out of the builder's own rule."""
    digest = _digests_for(1)[0]
    expected = leaf_hash(digest)
    tree = build_tree([digest])

    assert expected.hex() == (
        "d9de27625445003d8a9739a851e3ff8d41c0683630b4d63a88327a6aaa37c409"
    )
    assert tree.root == expected
    assert tree.leaves == (expected,)
    assert len(tree) == 1


def test_a_tree_over_one_record_digest_roots_at_that_records_leaf_hash() -> None:
    """The shape 9.16 hands the builder: one audit event, so one record
    digest and one leaf.  The root is the leaf hash 9.5 already pinned for
    this very digest, so ``n = 1`` is not a rule of its own."""
    tree = build_tree([RECORD_DIGEST])

    assert tree.root == leaf_hash(RECORD_DIGEST)
    assert tree.root.hex() == (
        "a78d21e1d3403125ca62017d1ffd34aec6227a858ae70f59c8eebb3fa9102e50"
    )
    assert tree.leaves == (tree.root,)


def test_the_root_of_one_leaf_is_never_a_hash_of_that_leaf() -> None:
    """The three wrong roots a single leaf has that are not this one: the
    record digest passed straight through with no leaf hash at all, the leaf
    hashed a second time under ``0x00``, and the leaf padded against itself
    under ``0x01``."""
    digest = _digests_for(1)[0]
    leaf = leaf_hash(digest)

    assert build_tree([digest]).root != digest
    assert build_tree([digest]).root != leaf_hash(leaf)
    assert build_tree([digest]).root != node_hash(leaf, leaf)


def test_one_leaf_runs_one_leaf_hash_and_no_node_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What the promotion costs, counted rather than read: the builder hashes
    the digest once and then stops, so ``node_hash`` is never reached.  This
    is ``D53``'s ``n - 1`` claim at ``n = 1``, where it says ``n - 1`` is
    no hash at all."""
    hashed: list[bytes] = []
    joined: list[tuple[bytes, bytes]] = []
    leafing, joining = merkle.leaf_hash, merkle.node_hash

    def counting_leaf(data: bytes) -> bytes:
        hashed.append(data)
        return leafing(data)

    def counting_node(left: bytes, right: bytes) -> bytes:
        joined.append((left, right))
        return joining(left, right)

    monkeypatch.setattr(merkle, "leaf_hash", counting_leaf)
    monkeypatch.setattr(merkle, "node_hash", counting_node)
    digest = _digests_for(1)[0]
    root = build_tree([digest]).root

    assert hashed == [digest]
    assert joined == []
    assert root == leafing(digest)


def test_a_one_leaf_root_is_the_same_child_a_bigger_tree_is_built_from() -> None:
    """The lone root and the child a two-leaf tree hands its parent are the
    same bytes, so a leaf's own hash has one spelling at every size.  This
    is what lets 9.9 walk a proof without a rule for a one-step path."""
    digests = _digests_for(2)
    lone = build_tree(digests[:1])
    pair = build_tree(digests)

    assert lone.root == pair.leaves[0]
    assert pair.root == node_hash(lone.root, pair.leaves[1])


def _drained() -> Iterator[bytes]:
    """An iterator that has already yielded everything it had."""
    source = iter(tuple(DIGESTS))
    for _ in source:
        pass
    return source


@pytest.mark.parametrize(
    "empty",
    [
        (),
        [],
        iter(()),
        (digest for digest in ()),
        "",
        frozenset(),
        b"",
        _drained(),
    ],
    ids=[
        "tuple",
        "list",
        "iterator",
        "generator",
        "str",
        "frozenset",
        "bytes",
        "drained",
    ],
)
def test_no_empty_batch_answers_a_root(empty: Any) -> None:
    """A root over nothing commits to nothing, so *every* empty iterable is
    refused rather than answered -- whatever kind of empty it is, including
    one that has already yielded everything it held.  A caller batching a
    quiet window has to be told so, not handed a root it could anchor."""
    with pytest.raises(MerkleError):
        build_tree(empty)


def test_the_empty_refusal_is_one_merkle_error_wherever_it_is_reached() -> None:
    """One refusal with one spelling.  ``MerkleTree`` is public and frozen,
    so the builder is not the only way in -- and a caller who builds one by
    hand gets the same ``ValueError`` with the same words, rather than a
    tree whose root commits to nothing."""
    leaf = leaf_hash(_digests_for(1)[0])

    with pytest.raises(MerkleError) as built:
        build_tree([])
    with pytest.raises(MerkleError) as by_hand:
        MerkleTree(leaves=(), root=leaf)

    assert isinstance(built.value, ValueError)
    assert "at least one leaf" in str(built.value)
    assert str(by_hand.value) == str(built.value)


def test_a_tree_built_by_hand_over_leaves_is_still_allowed() -> None:
    """The refusal above is about having no leaves, not about who built the
    tree: a hand-built one over a real leaf equals the builder's, leaf for
    leaf and root for root."""
    digest = _digests_for(1)[0]
    leaf = leaf_hash(digest)

    assert MerkleTree(leaves=(leaf,), root=leaf) == build_tree([digest])


def test_the_smallest_batch_is_one_leaf_and_not_zero() -> None:
    """The boundary itself, from both sides: a single record anchors, and no
    record does not."""
    assert build_tree(_digests_for(1)).root == leaf_hash(_digests_for(1)[0])

    with pytest.raises(MerkleError):
        build_tree(_digests_for(0))


# --- the sibling path: proof_for and verify_proof ---------------------------


def test_a_proof_carries_a_leaf_up_to_the_root() -> None:
    """The task's own claim: build a tree, ask for a leaf's path, walk it,
    land on the root.  On three leaves, so the walk crosses a pair *and* the
    promotion of 9.7's unpaired leaf -- and the root is the literal 9.6
    pinned, not the builder's own answer."""
    digests = _digests_for(3)
    tree = build_tree(digests)

    for index, leaf in enumerate(tree.leaves):
        proof = tree.proof_for(index)
        assert verify_proof(leaf, proof, tree.root) is True

    assert tree.root.hex() == (
        "d1f13800048f5909d4043fc0c152f6643280cba608b672715e56ce159a20629f"
    )


def test_a_proof_is_the_siblings_in_walk_order_with_their_sides() -> None:
    """What a proof *is*, spelled longhand on the three-leaf tree rather
    than read back through the builder.  Leaf-first, and each step names the
    sibling plus the side it was a child on -- so the two halves of a step
    cannot be confused, and the order is the one a verifier can replay."""
    leaves = build_tree(_digests_for(3)).leaves
    joined = node_hash(leaves[0], leaves[1])
    tree = build_tree(_digests_for(3))

    assert tree.proof_for(0) == (
        ProofStep(leaves[1], False),
        ProofStep(leaves[2], False),
    )
    assert tree.proof_for(1) == (
        ProofStep(leaves[0], True),
        ProofStep(leaves[2], False),
    )
    assert tree.proof_for(2) == (ProofStep(joined, True),)
    assert joined.hex() == (
        "604d540f09268b91672ab011394d5266ccd7d4484d0d109411a55848126a1b2c"
    )


def test_a_step_is_the_sibling_itself_and_not_a_hash_of_it() -> None:
    """A step carries the sibling's *existing* digest, never a hash taken
    again on the way out.  The verifier has to re-hash the pair with the
    same ``0x01`` prefix ``node_hash`` uses, so a step that arrived
    pre-hashed would put a leaf's own digest through a second domain and
    the walk would land on nothing."""
    leaves = build_tree(_digests_for(3)).leaves
    step = build_tree(_digests_for(3)).proof_for(0)[0]

    assert step.sibling == leaves[1]
    assert step.sibling != leaf_hash(leaves[1])
    assert step.sibling != node_hash(leaves[1], leaves[1])


def test_the_sibling_on_the_left_is_the_right_child() -> None:
    """The side flag is not decoration: it is what says which of the two
    ``node_hash`` arguments the walked hash was.  On the three-leaf tree the
    middle leaf is a right child at one level and a left child at another,
    so the same leaf contributes ``True`` and ``False`` steps."""
    proof = build_tree(_digests_for(3)).proof_for(1)

    assert [step.sibling_on_left for step in proof] == [True, False]


def test_swapping_the_two_sides_of_a_step_does_not_verify() -> None:
    """``node_hash`` takes its children in the tree's order, so a proof that
    swaps the two of a step must not verify.  Both directions are planted:
    the leaf that was on the left and the leaf that was on the right."""
    tree = build_tree(_digests_for(3))
    leaf = tree.leaves[1]
    first = tree.proof_for(1)[0]
    swapped_first = ProofStep(first.sibling, not first.sibling_on_left)

    assert first.sibling_on_left is True
    assert verify_proof(leaf, (swapped_first,) + tree.proof_for(1)[1:],
                        tree.root) is False

    other = tree.proof_for(0)[1]
    assert other.sibling_on_left is False
    swapped_other = ProofStep(other.sibling, not other.sibling_on_left)
    assert verify_proof(tree.leaves[0],
                        tree.proof_for(0)[:1] + (swapped_other,),
                        tree.root) is False


def test_a_promoted_leaf_carries_one_step_short_of_its_neighbours() -> None:
    """9.7's unpaired leaf is a child of the root and of nothing else, so
    its path stops there -- one step, where the leaves below it carry two.
    This is the shorter path 9.7 left for this task, spelled out rather
    than counted, because a count alone would not say *which* step."""
    tree = build_tree(_digests_for(3))
    lengths = [len(tree.proof_for(index)) for index in range(3)]

    assert lengths == [2, 2, 1]
    assert tree.proof_for(2)[-1].sibling == node_hash(
        tree.leaves[0], tree.leaves[1]
    )


@pytest.mark.parametrize("count, steps", [(1, 0), (2, 1), (4, 2), (8, 3),
                                          (16, 4)])
def test_a_proof_has_one_step_per_level_above_its_leaf(
    count: int, steps: int
) -> None:
    """The path is exactly as long as the tree is deep, for a balanced tree:
    ``log2(n)`` levels, so 16 leaves is a four-step proof.  Written as a
    table rather than a formula so the doubling is visible.  Only powers of
    two are listed: an odd count promotes its last leaf, and that leaf's
    path is one step shorter, which the two tests above pin.  9.10 is where
    every index of the 16-leaf tree is walked."""
    tree = build_tree(_digests_for(count))

    assert all(len(tree.proof_for(i)) == steps for i in range(count))


def test_a_promoted_leaf_is_the_only_short_path_at_five_leaves() -> None:
    """Five leaves split ``4 | 1``, so the fifth leaf's single step is the
    whole four-leaf subtree as one sibling.  The four below it still carry
    three steps each -- the promotion shortens one path, not the tree."""
    tree = build_tree(_digests_for(5))
    lengths = [len(tree.proof_for(index)) for index in range(5)]

    assert lengths == [3, 3, 3, 3, 1]
    assert tree.proof_for(4)[-1].sibling == _join(list(tree.leaves[:4]))


def test_a_leaf_that_is_its_own_root_has_the_empty_proof() -> None:
    """9.8's ``n = 1`` at proof level: the leaf is the root, so there is
    nothing to walk and nothing to check but the root itself.  This is the
    case 9.8's test -- a lone root equals a two-leaf tree's first child --
    made walkable, and it is why no rule for a one-step path was needed."""
    digest = _digests_for(1)[0]
    tree = build_tree([digest])

    assert tree.proof_for(0) == ()
    assert verify_proof(tree.leaves[0], (), tree.root) is True
    assert verify_proof(tree.leaves[0], (), leaf_hash(digest)) is True


def test_the_empty_proof_verifies_against_no_root_but_one_leaf() -> None:
    """The empty proof is only ever right for a one-leaf tree: with an
    empty path the walk never moves, so the root has to *be* the leaf.
    Checked against a three-leaf root and a one-leaf root at once, so the
    pass is not just "empty verifies"."""
    one = build_tree(_digests_for(1))
    three = build_tree(_digests_for(3))

    assert verify_proof(one.leaves[0], (), one.root) is True
    assert verify_proof(three.leaves[0], (), three.root) is False


def test_a_proof_does_not_carry_any_other_leaf() -> None:
    """The point of a proof: it commits to one leaf.  Every leaf of a
    five-leaf tree is tried against every leaf's proof, and only its own
    verifies -- a proof is not a general membership test."""
    tree = build_tree(_digests_for(5))
    proofs = [tree.proof_for(index) for index in range(5)]
    accepted = [
        (claim, index)
        for index, proof in enumerate(proofs)
        for claim in range(5)
        if verify_proof(tree.leaves[claim], proof, tree.root)
    ]

    assert accepted == [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]


def test_a_proof_does_not_verify_against_another_tree_s_root() -> None:
    """A proof is only meaningful against the root it was cut from.  The
    three- and five-leaf roots are both pinned literals in this file, so
    they are known to be different roots over different leaves."""
    three = build_tree(_digests_for(3))
    five = build_tree(_digests_for(5))

    assert verify_proof(
        three.leaves[0], three.proof_for(0), three.root) is True
    assert verify_proof(
        three.leaves[0], three.proof_for(0), five.root) is False
    assert verify_proof(five.leaves[0], five.proof_for(0), three.root) is False


def test_a_swapped_leaf_does_not_verify() -> None:
    """The mutation 9.10 will sweep across sixteen leaves, pinned here on
    the smallest case that shows it: hand the walk a leaf that is not the
    one the proof was cut for, and the path is a well-formed path to a
    different answer."""
    tree = build_tree(_digests_for(3))
    proof = tree.proof_for(0)

    assert verify_proof(tree.leaves[1], proof, tree.root) is False
    assert verify_proof(tree.leaves[2], proof, tree.root) is False
    assert verify_proof(leaf_hash(tree.leaves[0]), proof, tree.root) is False


def test_a_tampered_sibling_does_not_verify() -> None:
    """A proof read back from storage is data, so a step can come back
    altered.  One bit in a sibling is enough: the walk still runs, it just
    lands on a root nobody anchored."""
    tree = build_tree(_digests_for(3))
    proof = tree.proof_for(0)
    flipped = bytes([proof[0].sibling[0] ^ 0x01]) + proof[0].sibling[1:]

    assert verify_proof(tree.leaves[0], (ProofStep(flipped, False),)
                        + proof[1:], tree.root) is False


def test_a_proof_that_is_too_long_or_too_short_does_not_verify() -> None:
    """A path is a path: adding a step to it, or dropping one, lands
    somewhere else.  This is why the shorter path for a promoted leaf has
    to be a *shorter proof* and not the full one with a filler step."""
    tree = build_tree(_digests_for(3))
    proof = tree.proof_for(0)
    filler = ProofStep(tree.leaves[2], False)

    assert verify_proof(tree.leaves[0], proof + (filler,), tree.root) is False
    assert verify_proof(tree.leaves[0], proof[:-1], tree.root) is False


@pytest.mark.parametrize("sibling", [b"", b"\x00" * 31, b"\x00" * 33])
def test_a_sibling_that_is_not_a_digest_answers_false(sibling: bytes) -> None:
    """A step whose sibling is the wrong width is refused by the walk as
    ``False``, not raised: ``node_hash`` would raise on it, and a verifier
    that raised on a bad proof could not answer 9.17's ``altered``."""
    tree = build_tree(_digests_for(3))

    with pytest.raises(MerkleError):
        node_hash(sibling, tree.leaves[0])
    assert verify_proof(tree.leaves[0], (ProofStep(sibling, False),),
                        tree.root) is False


@pytest.mark.parametrize("step", [None, "step", (b"\x00" * 32, False), 42])
def test_a_step_that_is_not_a_step_does_not_verify(step: Any) -> None:
    """``verify_proof`` is handed whatever a column read back, so a step
    that is not a ``ProofStep`` answers ``False`` rather than raising on
    the attribute that is missing."""
    tree = build_tree(_digests_for(3))

    assert verify_proof(tree.leaves[0], (step,), tree.root) is False


@pytest.mark.parametrize(
    "root",
    [b"", b"\x00" * 31, b"\x00" * 33, b"short", "root", None, 32, []],
)
def test_a_root_that_is_not_a_digest_verifies_nothing(root: Any) -> None:
    """The other end of the walk, and the shape 9.8 left open: a root that
    is not a digest cannot be what a walk lands on, so the answer is
    ``False`` -- including a root that is not bytes at all, which the
    final ``==`` would otherwise try to widen and raise on.  ``MerkleTree``
    refuses one at the other end too, pinned below; this is the walk
    answering for a root that arrived from storage instead."""
    tree = build_tree(_digests_for(3))
    proof = tree.proof_for(0)

    assert verify_proof(tree.leaves[0], proof, root) is False


def test_a_hand_built_tree_with_a_bad_root_is_refused() -> None:
    """The production change this task makes, closing what 9.8 left open.
    ``MerkleTree`` is public and frozen, so ``root=b"short"`` was buildable
    by hand and could hand ``verify_proof`` a root over no digest at all.
    Refused where the tree is made, with the same ``MerkleError`` the
    empty shape uses, and the good widths still build."""
    leaf = leaf_hash(_digests_for(1)[0])

    with pytest.raises(MerkleError) as refused:
        MerkleTree(leaves=(leaf,), root=b"short")
    assert isinstance(refused.value, ValueError)
    assert "32-byte digest" in str(refused.value)
    assert MerkleTree(leaves=(leaf,), root=leaf) == build_tree(_digests_for(1))


def test_a_tree_with_a_root_that_is_not_a_digest_does_not_verify() -> None:
    """A short root on a real leaf is refused by the type, so a
    hand-built tree can never be the source of a walk that starts from
    something other than a digest."""
    leaf = leaf_hash(_digests_for(1)[0])

    with pytest.raises(MerkleError):
        MerkleTree(leaves=(leaf, leaf), root=b"\x00" * 16)


@pytest.mark.parametrize("index", [-1, -2, 3, 99])
def test_a_leaf_index_outside_the_tree_is_refused(index: int) -> None:
    """An index is a position, not a Python index: ``-1`` is *not* the last
    leaf.  A negative one that wrapped would quietly hand back a different
    leaf's proof and the caller would never know which one it had."""
    tree = build_tree(_digests_for(3))

    with pytest.raises(MerkleError) as refused:
        tree.proof_for(index)
    assert "indexes 0 to 2" in str(refused.value)


@pytest.mark.parametrize("index", ["0", None, 1.0, (0,)])
def test_a_leaf_index_that_is_not_an_int_is_refused(index: Any) -> None:
    """A non-integer index is a caller mistake, not a missing leaf, so it
    raises ``TypeError`` and not the ``MerkleError`` the bounds check
    raises -- the same split the two hashes make."""
    tree = build_tree(_digests_for(3))

    with pytest.raises(TypeError):
        tree.proof_for(index)


def test_a_leaf_index_is_refused_even_when_it_would_otherwise_fit() -> None:
    """``1.0`` and ``True`` compare equal to a real index, so the bounds
    check alone would let them through.  The type check runs first."""
    tree = build_tree(_digests_for(3))

    with pytest.raises(TypeError):
        tree.proof_for(1.0)
    with pytest.raises(TypeError):
        tree.proof_for(True)


def test_a_proof_is_a_frozen_tuple_of_frozen_steps() -> None:
    """A proof travels to storage and back, so it has to be a value and
    not something a holder can edit in place: a tuple of frozen steps
    answers the same on every read, and a changed step is a new proof."""
    tree = build_tree(_digests_for(3))
    proof = tree.proof_for(0)

    assert isinstance(proof, tuple)
    assert all(isinstance(step, ProofStep) for step in proof)
    with pytest.raises(Exception):
        proof[0].sibling_on_left = True
    assert tree.proof_for(0) == proof


def test_the_same_leaf_gets_the_same_proof_every_time() -> None:
    """9.18's reproducibility claim, at the level it starts: asking twice
    for one leaf's path answers the same steps, so a proof written once
    and read twice is not a re-derivation that could drift."""
    tree = build_tree(_digests_for(5))

    for index in range(5):
        assert tree.proof_for(index) == tree.proof_for(index)


def test_a_proof_costs_the_hashes_of_the_siblings_it_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What building a path spends: the sibling subtrees are re-derived,
    and nothing else is.  A proof of ``k`` steps over ``n`` leaves runs
    exactly ``n - 1 - k`` node hashes -- every internal node except the
    ``k`` on the leaf's own path -- so it never re-hashes the leaf and
    never rebuilds the whole tree."""
    joined: list[tuple[bytes, bytes]] = []
    hashing = merkle.node_hash

    def counting(left: bytes, right: bytes) -> bytes:
        joined.append((left, right))
        return hashing(left, right)

    monkeypatch.setattr(merkle, "node_hash", counting)
    costs = []
    for count in (1, 2, 3, 4, 5, 8):
        digests = _digests_for(count)
        for index in range(count):
            joined.clear()
            tree = build_tree(digests)
            joined.clear()
            steps = len(tree.proof_for(index))
            costs.append((count, index, steps, len(joined)))

    assert costs == [
        (1, 0, 0, 0),
        (2, 0, 1, 0), (2, 1, 1, 0),
        (3, 0, 2, 0), (3, 1, 2, 0), (3, 2, 1, 1),
        (4, 0, 2, 1), (4, 1, 2, 1), (4, 2, 2, 1), (4, 3, 2, 1),
        (5, 0, 3, 1), (5, 1, 3, 1), (5, 2, 3, 1), (5, 3, 3, 1),
        (5, 4, 1, 3),
        (8, 0, 3, 4), (8, 1, 3, 4), (8, 2, 3, 4), (8, 3, 3, 4),
        (8, 4, 3, 4), (8, 5, 3, 4), (8, 6, 3, 4), (8, 7, 3, 4),
    ]


def test_a_proof_never_hashes_the_leaf_it_was_cut_from() -> None:
    """The leaf that starts the walk is the tree's own, handed over
    unchanged: no ``leaf_hash`` pass and no ``node_hash`` over it on the
    way out, which is the same promotion 9.7 pinned seen from the other
    end."""
    hashed: list[bytes] = []
    leafing = merkle.leaf_hash

    def counting(data: bytes) -> bytes:
        hashed.append(data)
        return leafing(data)

    tree = build_tree(_digests_for(3))
    digests = _digests_for(3)
    hashed.clear()
    merkle.leaf_hash = counting
    try:
        proof = tree.proof_for(0)
    finally:
        merkle.leaf_hash = leafing

    assert hashed == []
    assert verify_proof(tree.leaves[0], proof, tree.root) is True
    assert tree.leaves[0] == leafing(digests[0])


# --- the sweep: every leaf of a sixteen-leaf tree -------------------------


def _altered(digest: bytes) -> bytes:
    """``digest`` with one bit of its first byte flipped: still a digest,
    still 32 bytes, and equal to nothing else in the tree."""
    return bytes([digest[0] ^ 0x01]) + digest[1:]


def test_every_leaf_of_a_sixteen_leaf_tree_carries_its_own_proof_to_the_root(
) -> None:
    """Each index's own leaf walks its own proof up to the root.  The
    sixteen answers are listed rather than ``all(...)``, so a sweep over an
    empty range cannot pass, and the root is 9.6's pinned sixteen-leaf
    answer rather than the builder's reply to the same question."""
    tree = build_tree(_digests_for(16))

    answers = [
        verify_proof(tree.leaves[index], tree.proof_for(index), tree.root)
        for index in range(len(tree))
    ]

    assert len(tree) == 16
    assert answers == [True] * 16
    assert tree.root.hex() == (
        "cc6e692ad24b6d105fa005c1028345bd7fd47c0221444ae3e6b9aa3708cacfc2"
    )


def test_mutating_any_leaf_of_a_sixteen_leaf_tree_fails_verification() -> None:
    """One bit flipped in any of the sixteen leaves verifies against none of
    the sixteen proofs -- 256 checks, every one refused.  The untouched
    walk is run first in the same test, so the refusals are the mutation's
    doing and not a root nothing could have reached."""
    tree = build_tree(_digests_for(16))
    unaltered = verify_proof(
        tree.leaves[0], tree.proof_for(0), tree.root
    )
    accepted = [
        (mutated, cut_for)
        for mutated in range(len(tree))
        for cut_for in range(len(tree))
        if verify_proof(
            _altered(tree.leaves[mutated]),
            tree.proof_for(cut_for),
            tree.root,
        )
    ]

    assert unaltered is True
    assert accepted == []


def test_a_record_changed_after_its_proof_was_cut_no_longer_verifies() -> None:
    """The mutation where a ledger meets it: one record digest is changed
    before the builder, and the leaf that comes out is run against the
    proof and the root cut before the change."""
    digests = _digests_for(16)
    tree = build_tree(digests)
    changed = list(digests)
    changed[7] = bytes.fromhex(_sha256(bytes([7]) + b"altered"))
    rebuilt = build_tree(changed)

    assert rebuilt.leaves[7] != tree.leaves[7]
    assert verify_proof(
        rebuilt.leaves[7], tree.proof_for(7), tree.root
    ) is False


def test_a_stored_digest_reads_back_to_the_bytes_it_was_written_from() -> None:
    """The round trip a column makes: 32 raw bytes, 64 hex characters, and
    the same 32 bytes again -- for a record digest and for a root, which are
    the two columns 9.16 and 9.17 read."""
    digest = bytes.fromhex(hash_record(RECORD, SALT))
    root = build_tree(_digests_for(4)).root

    assert digest.hex().isascii() and len(digest.hex()) == 2 * DIGEST_BYTES
    assert read_digest(digest.hex()) == digest
    assert read_digest(root.hex()) == root


@pytest.mark.parametrize(
    "text",
    [
        "not a digest",
        "",
        "9f86d081",  # four bytes, not thirty-two
        "9f86d081884c7d65a8fcb49ca7fbeabd",  # sixteen bytes
        "ab" * 33,  # thirty-three bytes
        "zz" * DIGEST_BYTES,  # hex in length, not in characters
        "-" * 2 * DIGEST_BYTES,
    ],
)
def test_a_column_carrying_something_else_than_a_digest_is_refused(
    text: str,
) -> None:
    """Whatever wrote prose, a truncated value or a digest with a stray
    character in it, a leaf cannot be read from it."""
    with pytest.raises(MerkleError):
        read_digest(text)


@pytest.mark.parametrize(
    "value", [b"\x9f" * DIGEST_BYTES, DIGEST_BYTES, None, ["9f"]]
)
def test_a_stored_digest_that_is_not_text_is_refused(value: Any) -> None:
    """The column carries text, so raw bytes are refused by name rather than
    widened -- ``bytes.fromhex`` alone would not have raised."""
    with pytest.raises(TypeError):
        read_digest(value)


def test_reading_a_digest_re_reads_it_rather_than_agreeing_with_itself() -> None:
    """The answer is the column's bytes, not a copy of them: a digest spelled
    in upper case decodes to the digest it spelled."""
    digest = bytes.fromhex(hash_record(RECORD, SALT))

    assert read_digest(digest.hex().upper()) == digest
    assert read_digest(digest.hex().upper()) == read_digest(digest.hex())
