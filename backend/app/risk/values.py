"""The one gate from a flag's value into the number the engine scores it with.

The engine's sum is ``R = sum(w_i * F_i)``, so 7.3's
:func:`~app.risk.weightsets.lookup.weight_for` answers the ``w`` and this
module answers the ``F``.  **Every term of that sum is a ``float`` in the
closed unit interval, or the call is refused**, so 7.5 writes its arithmetic
against one promise rather than re-checking a value per term.

**The map is the identity, and the interval is where it comes from.**  A
flag's :attr:`~app.risk.flags.EvidenceFlag.value` is already in ``[0, 1]``
(``D6``), which is the range the engine sums in, so nothing is rescaled and
nothing is ever clipped into the range.  What this module owns is the other
half of that sentence: whether a value is one of the numbers the sum may carry
at all.  **The range is not written down here.**  It is
:func:`app.risk.flags._check_unit_interval`, the check 5.2 already put in the
record's own constructor, so the engine's gate and the record's own cannot
drift apart.

**A ``None`` value is refused, and so is a boolean.**  A rule that measured
nothing is silence rather than a finding of no strength, and a boolean says
that a rule fired rather than how strongly it fired.  7.3 refused an id
carrying no weight for the same reason: a value nobody measured must not reach
the sum as a zero, and a screening must not be answered ``low`` on it.  A
boolean is inside ``[0, 1]`` in Python's own arithmetic, so the record's own
check accepts one where a number belongs; **the shape check and the engine's
gate are two questions, and this module is the second one.**

**The refusals raise :exc:`~app.risk.flags.FlagValueError`**, the risk
package's own error and a ``ValueError``, so a caller already catching
``ValueError`` around the code that scores a screening keeps catching it.
**A message names the field and the type and never the value**, on ``D6``'s
grounds: a value is exactly where something read off a document arrives.

**Nothing here reads a weightset, and normalising a flag does not amend it.**
7.3 is the one way out of a weightset and this is the one way out of a value.
"""

from app.risk.flags import FlagValueError, _check_unit_interval

__all__ = ["normalise_value"]


def _value_off(flag: object) -> object:
    """The value ``flag`` carries, or a refusal naming the field it lacks."""
    try:
        return flag.value
    except AttributeError:
        raise FlagValueError(
            "a flag must carry a 'value' for it to be normalised"
        ) from None


def normalise_value(flag: object) -> float:
    """The value ``flag`` carries, as the ``float`` the engine may sum.

    The answer is the value unchanged, as a ``float``, and never a rescaled,
    rounded or clipped one: a value already inside the closed unit interval is
    already inside the engine's range, and ``5.2`` holds that interval rather
    than this function.

    :param flag: any record carrying a ``value``.  An
        :class:`~app.risk.flags.EvidenceFlag` is the one this is written for,
        and the refusals are for the records this package does not build: a
        rule's own finding before it became a flag, and a flag read back from
        storage, where ``null`` is a legal value.  Typed ``object`` for that
        reason, since typing it as the record would say the gate is
        unreachable.
    :returns: ``flag``'s own value, as a ``float``.
    :raises FlagValueError: when ``flag`` carries no ``value`` at all, or
        carries one that is ``None``, a boolean, or not a real number inside
        ``[0, 1]``.  Nothing is defaulted and nothing is coerced.
    """
    value = _value_off(flag)

    if value is None:
        raise FlagValueError(
            "value must not be None: a rule that measured nothing is not a "
            "strength of zero"
        )

    if isinstance(value, bool):
        raise FlagValueError(
            "value must not be a boolean: a boolean says a rule fired, not "
            "how strongly it fired"
        )

    _check_unit_interval("value", value)
    return float(value)
