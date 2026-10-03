import pytest

from app import version


VERSION_NAMES = ("APP_VERSION", "MODEL_VERSIONS", "PROMPT_VERSION", "RULESET_VERSION")
SCALAR_NAMES = ("APP_VERSION", "RULESET_VERSION", "PROMPT_VERSION")


@pytest.mark.parametrize("name", SCALAR_NAMES)
def test_version_constant_is_a_non_empty_string(name):
    value = getattr(version, name)

    assert isinstance(value, str)
    assert value.strip()


def test_the_model_versions_are_a_module_name_to_version():
    """``MODEL_VERSIONS`` is the shape a row's own column carries (``D79``)."""
    assert isinstance(version.MODEL_VERSIONS, dict)

    for module, module_version in version.MODEL_VERSIONS.items():
        assert isinstance(module, str) and module.strip()
        assert isinstance(module_version, str) and module_version.strip()


def test_version_module_exports_exactly_the_four_names():
    assert set(version.__all__) == set(VERSION_NAMES)