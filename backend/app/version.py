"""Version identifiers reported by the DRISHTI API and its result payloads.

These are plain constants rather than package metadata so they can be read
without installing anything, and so a screening record can quote the exact
versions that produced it.

- ``APP_VERSION`` changes when the service itself changes.
- ``RULESET_VERSION`` changes whenever a flag, threshold, or weight changes,
  because a score is only comparable against the ruleset that produced it.
- ``PROMPT_VERSION`` changes whenever the explanation prompt template changes.
- ``MODEL_VERSIONS`` names the models the cascade runs, module to version, and
  is empty while it runs none (``D79``).

The three versions move together as semantic versions.  All four are surfaced
by ``GET /api/version``, and the first three on every result; the UI shows
them as experimental.
"""

APP_VERSION = "0.1.0"
RULESET_VERSION = "0.2.0"
PROMPT_VERSION = "0.1.0"

#: Module name to version for the models a screening can be scored by: the
#: shape ``model_versions`` already carries on a row and on the trail, so a
#: caller meets one spelling of "which models" wherever it reads one (D79).
MODEL_VERSIONS: dict[str, str] = {}

__all__ = ["APP_VERSION", "MODEL_VERSIONS", "PROMPT_VERSION", "RULESET_VERSION"]