"""Version identifiers reported by the DRISHTI API and its result payloads.

These are plain constants rather than package metadata so they can be read
without installing anything, and so a screening record can quote the exact
versions that produced it.

- ``APP_VERSION`` changes when the service itself changes.
- ``RULESET_VERSION`` changes whenever a flag, threshold, or weight changes,
  because a score is only comparable against the ruleset that produced it.
- ``PROMPT_VERSION`` changes whenever the explanation prompt template changes.

All three move together as semantic versions. They are surfaced by
``GET /api/version`` and on every result, and the UI shows them as
experimental.
"""

APP_VERSION = "0.1.0"
RULESET_VERSION = "0.1.0"
PROMPT_VERSION = "0.1.0"

__all__ = ["APP_VERSION", "RULESET_VERSION", "PROMPT_VERSION"]
