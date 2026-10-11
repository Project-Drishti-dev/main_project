"""26.3: the Cloud Run settings are one file, and they are the three the task names.

`backend/cloudrun.yaml` is that file: a v2 Service definition whose concurrency,
instance ceiling and request timeout are the deployed values because
`gcloud run services replace` applies it as written. These cases read it, so the
settings are decidable on a machine with no gcloud, no project and no deployed
revision -- the same split as D214's Dockerfile cases.

What is asserted, and why each refusal matters:

* the file is a v2 ``Service``, so the field names below are the ones the Admin
  API reads rather than v1 spellings that would be silently ignored;
* concurrency is 1 -- the cascade is CPU- and model-bound and the rate-limit and
  Merkle batching budgets are counted per process, so a second concurrent
  request makes both per-instance (D78);
* the instance ceiling is small and non-zero, because an unauthenticated public
  endpoint on a shared project is a cost and abuse bound;
* the timeout is a duration Cloud Run accepts, longer than the cascade's own
  worst case and below the platform maximum, so a cold start is not cut off and
  a hung request cannot hold an instance for an hour.

The cascade's budget is read out of `app.config` rather than retyped, so this
cannot drift from the summariser timeout the service actually applies.
"""

import re

import pytest
import yaml

from app.config import BACKEND_DIR, DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS


CLOUDRUN_CONFIG = BACKEND_DIR / "cloudrun.yaml"

#: Cloud Run's documented request-timeout bounds: 5 minutes by default, up to 60
#: minutes. A value outside this is not a tuning mistake, it is a rejected
#: deploy. Verified against the request-timeout documentation and the quotas
#: page, not recalled.
MIN_REQUEST_TIMEOUT_SECONDS = 60
MAX_REQUEST_TIMEOUT_SECONDS = 3600

#: The tier budgets the abstract states, in seconds: Tier 0 under 0.3, Tier 1 at
#: 0.5-1, Tier 2 at 1-2. The timeout has to clear the whole cascade on the
#: hardware those targets assume, before any allowance for a cold start.
TIER_TARGET_SECONDS = 0.3 + 1.0 + 2.0

#: A `google-duration` string: a number with an optional `s`, `m` or `h` unit.
#: Cloud Run rejects a bare number in the YAML even though the gcloud flag
#: assumes seconds, which is why the file carries the unit.
DURATION = re.compile(r"^(\d+)([smh])$")

UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}


def _config() -> dict:
    """The service definition, parsed."""
    return yaml.safe_load(CLOUDRUN_CONFIG.read_text(encoding="utf-8"))


def _template() -> dict:
    """`spec.template`, where all three settings live."""
    return _config()["spec"]["template"]


def _duration_seconds(value: object) -> int:
    """A duration string as seconds.

    :raises ValueError: when the value is not a `google-duration` Cloud Run
        would accept, naming it rather than parsing it leniently.
    """
    if not isinstance(value, str):
        raise ValueError(f"a duration must be a string, got {type(value).__name__}")
    match = DURATION.match(value.strip())
    if not match:
        raise ValueError(
            f"{value!r} is not a google-duration; Cloud Run wants a number and "
            "a unit, such as '600s', '10m' or '1h'"
        )
    return int(match.group(1)) * UNIT_SECONDS[match.group(2)]


def test_the_config_is_a_v2_cloud_run_service():
    """v1 spellings parse as YAML and are then ignored by the Admin API.

    `containerConcurrency` and `spec.template.spec.maxInstanceCount` are the
    v1/knative names; under apiVersion v2 the fields below are the ones read. A
    file carrying the wrong apiVersion is a deploy that succeeds and silently
    keeps its previous concurrency, so the version is asserted rather than
    assumed.
    """
    config = _config()

    assert config.get("apiVersion") == "run.googleapis.com/v2"
    assert config.get("kind") == "Service"


def test_concurrency_is_one_request_per_instance():
    """The task's setting, and the reason is per-process state.

    The rate-limit budget (D78) and the Merkle batching window are counted in
    one process, so a second concurrent request does not share them. Concurrency
    is also left unset-able to the platform default of 80, which the cascade's
    CPU and model load cannot serve.
    """
    concurrency = _template().get("maxInstanceRequestConcurrency")

    assert concurrency == 1, f"concurrency is {concurrency!r}, not 1"


def test_the_instance_ceiling_is_small_and_the_floor_is_zero():
    """A small maximum is a cost and abuse bound; a zero minimum costs nothing.

    Left unspecified, `maxInstanceCount` takes the server default of 100, which
    on an unauthenticated public endpoint is an unbounded bill, so the ceiling
    is asserted to be written down rather than merely present.
    """
    scaling = _template().get("scaling", {})

    assert "maxInstanceCount" in scaling, (
        "maxInstanceCount is unset, so the platform default of 100 applies"
    )
    maximum = scaling["maxInstanceCount"]
    assert isinstance(maximum, int) and not isinstance(maximum, bool)
    assert 1 <= maximum <= 10, f"maxInstanceCount is {maximum}, not a small ceiling"
    assert scaling.get("minInstanceCount") == 0, (
        "an idle demo should scale to zero rather than hold an instance"
    )


def test_the_timeout_is_a_duration_cloud_run_accepts():
    """A bare number is accepted by the gcloud flag and rejected in the file.

    `--timeout 600` means 600 seconds, but the YAML field is a
    `google-duration`, so the unit has to be written for the deploy to be
    accepted at all -- and a value past the platform maximum is not a slow
    request but a rejected config.
    """
    seconds = _duration_seconds(_template().get("timeout"))

    assert MIN_REQUEST_TIMEOUT_SECONDS <= seconds <= MAX_REQUEST_TIMEOUT_SECONDS, (
        f"the request timeout is {seconds}s, outside Cloud Run's documented "
        f"{MIN_REQUEST_TIMEOUT_SECONDS}-{MAX_REQUEST_TIMEOUT_SECONDS}s range"
    )


def test_the_timeout_outlasts_the_cascade_it_serves():
    """Sized for the cascade: the whole tier budget plus the summariser's own.

    Read from `app.config` and the abstract's stated targets rather than
    retyped, so this cannot drift from the timeout the service actually applies
    to its largest single step. The margin over the platform default of 300 s is
    the point of the setting: the default is close enough to a cold start plus
    a slow Tier 2 that a legitimate deep-analysis request would be cut at 504.
    """
    seconds = _duration_seconds(_template()["timeout"])
    cascade = TIER_TARGET_SECONDS + DEFAULT_LOCAL_LLM_TIMEOUT_SECONDS

    assert seconds > cascade, (
        f"the request timeout is {seconds}s and the cascade can spend "
        f"{cascade:.1f}s, so the platform would answer 504 for a request the "
        "service is still working on"
    )


def test_a_hung_request_cannot_hold_an_instance_for_the_platform_maximum():
    """The timeout is a bound on a stuck request, not only a floor for a slow one.

    Concurrency 1 means a hung request occupies the only request slot an
    instance has, so the platform's 60-minute ceiling is the worst case this
    setting exists to prevent. Requiring real headroom below it keeps the
    ceiling from becoming the de facto timeout.
    """
    seconds = _duration_seconds(_template()["timeout"])

    assert seconds < MAX_REQUEST_TIMEOUT_SECONDS, (
        "a timeout at the 60-minute maximum gives a hung request an hour to "
        "hold the single concurrency slot an instance has"
    )


def test_the_port_is_the_one_the_image_serves():
    """The revision's port and the container's must be the same 8080.

    D214's Dockerfile exposes 8080 and starts uvicorn on it, and Cloud Run sends
    traffic to whatever the container declares. A revision on a different port
    answers every request with a connection the client did not make.
    """
    containers = _template()["containers"]

    assert len(containers) == 1, "the service is expected to run one container"
    ports = containers[0].get("ports", [])

    assert [port["containerPort"] for port in ports] == [8080]


def test_the_deployed_revision_refuses_to_generate_a_production_key():
    """APP_ENV=production, so a missing key stops the service (19.1).

    Left at the `development` default, each instance would generate its own
    AES-GCM master key on start-up and evidence written by one instance would be
    undecryptable by the next -- which two instances makes likely rather than
    theoretical.
    """
    containers = _template()["containers"]
    environment = {
        entry["name"]: entry.get("value") for entry in containers[0].get("env", [])
    }

    assert environment.get("APP_ENV") == "production"


@pytest.mark.parametrize("field", ["maxInstanceRequestConcurrency", "timeout"])
def test_no_setting_is_left_to_the_platform_default(field):
    """Unset is not a decision, and these two defaults are the wrong answers.

    Concurrency defaults to 80 when CPU >= 1 and an unset timeout defaults to
    300 s; `maxInstanceCount` defaults to 100. Each is checked explicitly so a
    key deleted from the file fails here rather than deploying silently.
    """
    assert field in _template(), f"{field} is not written down in cloudrun.yaml"
