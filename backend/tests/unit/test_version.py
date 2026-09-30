import pytest

from app import version


VERSION_NAMES = ("APP_VERSION", "RULESET_VERSION", "PROMPT_VERSION")


@pytest.mark.parametrize("name", VERSION_NAMES)
def test_version_constant_is_a_non_empty_string(name):
    value = getattr(version, name)

    assert isinstance(value, str)
    assert value.strip()


def test_version_module_exports_exactly_the_three_names():
    assert set(version.__all__) == set(VERSION_NAMES)
