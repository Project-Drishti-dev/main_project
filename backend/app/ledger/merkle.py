"""The tree's two hashes, kept apart by the byte in front of them.

RFC 6962 separates the domains so no leaf can be read as a node or the
reverse: a leaf is SHA-256 over ``0x00 || data``, a node over
``0x01 || left || right``.  :func:`build_tree` puts a sequence of record
digests together under those two hashes, splitting at the largest power of
two.  :meth:`MerkleTree.proof_for` answers the sibling path from one leaf to
that root, and :func:`verify_proof` walks one.

:func:`read_digest` is the one reader of the stored spelling -- the 64 hex
characters a text column carries a digest in -- and both 9.16 and 9.17 read
through it rather than widening hex of their own.
"""

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Tuple

__all__ = [
    "DIGEST_BYTES",
    "LEAF_PREFIX",
    "MerkleError",
    "MerkleTree",
    "NODE_PREFIX",
    "ProofStep",
    "build_tree",
    "leaf_hash",
    "node_hash",
    "read_digest",
    "verify_proof",
]


#: The domain-separation byte a leaf hash carries, per RFC 6962 section 2.
LEAF_PREFIX = b"\x00"

#: The domain-separation byte an internal node hash carries, per section 2.
NODE_PREFIX = b"\x01"

#: SHA-256's width, and so the width of every hash this module returns and
#: of every child ``node_hash`` accepts.
DIGEST_BYTES = 32


class MerkleError(ValueError):
    """Raised when a value cannot be a child of a node.

    A ``ValueError``, so a caller already catching one around a tree keeps
    catching it.
    """


#: The one refusal both the builder and the tree itself make, so an empty
#: batch fails the same way whichever of the two is reached.
_NO_LEAVES = (
    "a tree needs at least one leaf, and none were given: no value is shown"
)

#: The refusal a hand-built root makes, so a root that is not a digest cannot
#: reach a proof walk from outside the builder.
_NOT_A_ROOT = (
    "a root is a {width}-byte digest, and this one is {given}: "
    "no value is shown"
)

#: The two refusals reading a stored digest back makes, so a column that
#: carries prose or a truncated value is refused where it is read rather than
#: at each caller.
_NOT_STORED_HEX = (
    "a stored digest is 64 hex characters, and this column is not: "
    "no value is shown"
)
_NOT_STORED_DIGEST = (
    "a stored digest is a {width}-byte digest, and this column is {given}: "
    "no value is shown"
)


def _digest(value: Any, what: str) -> bytes:
    """``value`` as the bytes to be hashed, refusing anything else."""
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError(
            f"{what} is a {type(value).__name__}, and only bytes may be "
            f"hashed: no value is shown"
        )
    return bytes(value)


def _child(value: Any, what: str) -> bytes:
    """``value`` as a node's child, which is a digest and nothing else."""
    digest = _digest(value, what)
    if len(digest) != DIGEST_BYTES:
        raise MerkleError(
            f"{what} is {len(digest)} bytes, and only a {DIGEST_BYTES}-byte "
            f"digest is a child of a node: no value is shown"
        )
    return digest


def _is_digest(value: Any) -> bool:
    """Whether ``value`` is exactly one digest, the shape a node takes."""
    return isinstance(value, (bytes, bytearray)) and len(value) == DIGEST_BYTES


def leaf_hash(data: bytes) -> bytes:
    """SHA-256 over ``0x00 || data``, as 32 raw bytes.

    :param data: the bytes the leaf commits to -- in this ledger a record's
        digest from 9.3, never the record itself.  Any length is accepted:
        this is the only place arbitrary-length data enters the tree, which
        is why it is the hash that carries the prefix.
    :returns: 32 bytes, the leaf hash, unwidened from the one hex spelling
        ``audit_events.record_hash`` uses.
    :raises TypeError: when ``data`` is not bytes.  The message names the
        type alone, so nothing of a record reaches a log.
    """
    return hashlib.sha256(LEAF_PREFIX + _digest(data, "data")).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    """SHA-256 over ``0x01 || left || right``, as 32 raw bytes.

    :param left: the left child's digest, 32 bytes.
    :param right: the right child's digest, 32 bytes.  The order is the
        tree's, so a proof that swaps the two does not verify.
    :returns: 32 bytes, the node hash, unwidened.
    :raises TypeError: when either child is not bytes.
    :raises MerkleError: when either child is not exactly
        ``DIGEST_BYTES``.  A child of any other width is a truncated or
        unhashed value, and a tree built on one cannot be walked by 9.10.
    """
    return hashlib.sha256(
        NODE_PREFIX + _child(left, "left") + _child(right, "right")
    ).digest()


def read_digest(text: str) -> bytes:
    """One stored digest read back from the text column that carries it.

    :param text: 64 hex characters -- ``D49``'s spelling, which is the one
        ``audit_events.record_hash`` and ``ledger_entries.merkle_root`` are
        both written in.  Nothing here re-encodes or case-folds it.
    :returns: the ``DIGEST_BYTES`` raw bytes a leaf or a root is built from.
    :raises TypeError: when ``text`` is not a ``str``.  The message names the
        type and never the value.
    :raises MerkleError: when the text is not hex, or is hex of another width
        than ``DIGEST_BYTES``.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"a stored digest is a {type(text).__name__}, and the column "
            f"carrying it holds text: no value is shown"
        )
    try:
        digest = bytes.fromhex(text)
    except ValueError as error:
        raise MerkleError(_NOT_STORED_HEX) from error
    if len(digest) != DIGEST_BYTES:
        raise MerkleError(
            _NOT_STORED_DIGEST.format(
                given=f"{len(digest)} bytes", width=DIGEST_BYTES
            )
        )
    return digest


@dataclass(frozen=True)
class ProofStep:
    """One level of a sibling path: the other child, and which side it was on.

    Frozen, because a proof travels to storage and must not be edited on the
    way: a step that could change under the walker's feet would let a proof
    verify against a tree nobody built.

    :param sibling: the other child's digest at this level, 32 bytes.
    :param sibling_on_left: ``True`` when ``sibling`` was the *left* child,
        so the hash being walked is the node's right one.
    """

    sibling: bytes
    sibling_on_left: bool


@dataclass(frozen=True)
class MerkleTree:
    """A built tree: the leaf hashes in order, and the root over them.

    Frozen, so a caller cannot swap a leaf after the root was taken over
    it.  :func:`build_tree` is the only way one is meant to be made, and
    the two shapes it refuses are a tree over no leaves and a root that is
    not a digest.

    :param leaves: the leaf hashes, one per leaf, in tree order.
    :param root: the tree's root, 32 raw bytes.
    :raises MerkleError: when ``leaves`` is empty, so the one spelling of
        "no tree" is the builder's rather than a directly-built one's.
    :raises MerkleError: when ``root`` is not ``DIGEST_BYTES`` wide, so a
        root a walk cannot start from is refused where it was made.
    """

    leaves: Tuple[bytes, ...]
    root: bytes

    def __post_init__(self) -> None:
        """Refuse the two shapes a root cannot commit to: no leaves, and a
        root that is not itself a digest."""
        if not self.leaves:
            raise MerkleError(_NO_LEAVES)
        root = _digest(self.root, "root")
        if len(root) != DIGEST_BYTES:
            raise MerkleError(
                _NOT_A_ROOT.format(
                    given=f"{len(root)} bytes", width=DIGEST_BYTES
                )
            )

    def __len__(self) -> int:
        """The number of leaves the root commits to."""
        return len(self.leaves)

    def proof_for(self, index: int) -> Tuple[ProofStep, ...]:
        """The sibling path from the leaf at ``index`` up to this root.

        Leaf-first, which is the order :func:`verify_proof` walks, and one
        step per internal node above the leaf -- so a lone leaf answers the
        empty proof and a promoted leaf one step short of its neighbours.

        :param index: the leaf's position, 0 to ``len(tree) - 1``.  Not a
            Python index: a negative one is refused, never wrapped, and a
            ``bool`` is refused though it is an ``int``.
        :returns: the steps, nearest the leaf first.
        :raises TypeError: when ``index`` is not an ``int`` (a ``bool``
            included).
        :raises MerkleError: when no leaf carries ``index``.
        """
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(
                f"index is a {type(index).__name__}, and a leaf index is an "
                f"int: no value is shown"
            )
        if not 0 <= index < len(self.leaves):
            raise MerkleError(
                f"index {index} is not a leaf of a {len(self)}-leaf tree, "
                f"which indexes 0 to {len(self.leaves) - 1}: "
                f"no value is shown"
            )
        steps: list[ProofStep] = []
        # Read from the root down: the subtree spans `leaves[start:start +
        # count]`, and the sibling is the half of it the index is not in.
        start, count = 0, len(self.leaves)
        while count > 1:
            split = 1 << ((count - 1).bit_length() - 1)
            if index < start + split:
                steps.append(
                    ProofStep(
                        sibling=_root_of(
                            self.leaves[start + split : start + count]
                        ),
                        sibling_on_left=False,
                    )
                )
                count = split
            else:
                steps.append(
                    ProofStep(
                        sibling=_root_of(self.leaves[start : start + split]),
                        sibling_on_left=True,
                    )
                )
                start, count = start + split, count - split
        # The walk above starts at the root; the verifier starts at the leaf.
        return tuple(reversed(steps))


def _root_of(leaves: Tuple[bytes, ...]) -> bytes:
    """The root over ``leaves`` by RFC 6962's split rule.

    :param leaves: one or more leaf hashes, already hashed.
    :returns: the subtree's root.  One leaf is its own root -- a lone
        subtree is promoted unchanged, never hashed a second time under
        ``0x01`` (which 9.7 pins on its own).
    :raises MerkleError: when ``leaves`` is empty.
    """
    if not leaves:
        raise MerkleError(_NO_LEAVES)
    if len(leaves) == 1:
        return leaves[0]
    # The largest power of two strictly below the leaf count (RFC 6962
    # section 2.1): 3 splits 2|1, 5 splits 4|1, 6 splits 4|2.  The
    # parentheses are the whole expression -- `<<` binds looser than `-`.
    split = 1 << ((len(leaves) - 1).bit_length() - 1)
    return node_hash(_root_of(leaves[:split]), _root_of(leaves[split:]))


def build_tree(leaves: Iterable[bytes]) -> MerkleTree:
    """A :class:`MerkleTree` over ``leaves``, splitting at the largest
    power of two.

    :param leaves: the record digests to commit to, in order -- 9.3's
        32-byte answers, unwidened.  Each is hashed with
        :func:`leaf_hash` *here*, so the leaf prefix cannot be skipped by a
        caller and a record's payload never reaches the tree.
    :returns: the tree, holding its leaf hashes and the root over them.
    :raises TypeError: when a leaf is not bytes.
    :raises MerkleError: when a leaf is not a ``DIGEST_BYTES`` digest, or
        when ``leaves`` is empty.
    """
    hashed = tuple(
        leaf_hash(_child(leaf, f"leaf {index}"))
        for index, leaf in enumerate(leaves)
    )
    return MerkleTree(leaves=hashed, root=_root_of(hashed))


def verify_proof(
    leaf: bytes, proof: Iterable[ProofStep], root: bytes
) -> bool:
    """Whether ``proof`` carries ``leaf`` up to ``root``.

    A verifier, so a proof it cannot use is a proof that failed: a leaf, a
    sibling or a root that is not a digest answers ``False`` rather than
    raising, which is what a stored proof that was tampered with is.

    :param leaf: the leaf's own hash -- :func:`leaf_hash` over a record
        digest, not the digest and not the record.
    :param proof: the steps from :meth:`MerkleTree.proof_for`, nearest the
        leaf first.  Any iterable of steps.
    :param root: the anchored root, 32 raw bytes.
    :returns: whether the walk ends at ``root``.
    :raises TypeError: when ``leaf`` is not bytes.
    """
    running = _digest(leaf, "leaf")
    if not _is_digest(running) or not _is_digest(root):
        return False
    for step in proof:
        if not isinstance(step, ProofStep) or not _is_digest(step.sibling):
            return False
        running = (
            node_hash(step.sibling, running)
            if step.sibling_on_left
            else node_hash(running, step.sibling)
        )
    return running == bytes(root)
