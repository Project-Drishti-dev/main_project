"""15.1 -- Tier 2 goes through one interface, and an empty registry still answers.

The claim pinned first is the verification the task names: the shipped
registry holds no module at all, and a run over it is a valid answer rather
than a refusal.  The rest pins that every module that ran left a result, that
the registry is read-only, and that the interface refuses a subclass that did
not write ``run`` -- why the registry is empty, why a module that raises is
not caught here, and why an empty run must never read as a clean document are
D115.
"""

import types
import uuid

import pytest

from app.pipeline import orchestrator
from app.pipeline.tier2 import base

DeepModule = base.DeepModule
DeepRun = base.DeepRun

SCREENING_ID = uuid.UUID("6f1a0c2e-4b3d-4c5a-9e7f-0a1b2c3d4e5f")


def _context():
    """A context carrying what a stand-in module needs and nothing else."""
    return orchestrator.ScreeningContext(
        screening_id=SCREENING_ID,
        document_type="passport",
        image=object(),
        reference_date=None,
        depth_mode=orchestrator.STANDARD,
    )


class _Answers(DeepModule):
    """A stand-in module that answers one object per context it is handed."""

    def __init__(self, answer):
        self.name = type(self).__name__
        self.answer = answer
        self.seen = []

    def run(self, context):
        self.seen.append(context)
        return self.answer


class _NoRun(DeepModule):
    """A subclass that never wrote ``run``, which the interface must refuse."""

    name = "no_run"


def test_an_empty_registry_still_answers_a_valid_result():
    """The task's own verification: zero modules is an answer, not a refusal."""
    run = base.run_deep_modules(_context())

    assert isinstance(run, DeepRun)
    assert run.ran == ()
    assert run.results == ()


def test_the_shipped_registry_holds_no_module_yet():
    """15.1 is the seam; the first module behind it is 15.3, not this task."""
    assert base.MODULE_NAMES == ()
    assert dict(base.DEEP_MODULES) == {}


def test_every_module_that_ran_left_a_result():
    """One row per module, in registry order, so a name sits beside its answer."""
    first, second = _Answers("ela"), _Answers("residual")
    registry = {"tamper_ela": first, "tamper_noise": second}

    run = base.run_deep_modules(_context(), modules=registry)

    assert run.ran == ("tamper_ela", "tamper_noise")
    assert run.results == ("ela", "residual")


def test_a_module_is_handed_the_context_it_was_run_with():
    """``run`` is given the record, so a module reads one screening in hand."""
    module = _Answers("ela")

    base.run_deep_modules(_context(), modules={"tamper_ela": module})

    assert len(module.seen) == 1
    assert isinstance(module.seen[0], orchestrator.ScreeningContext)


def test_the_registry_cannot_be_edited_by_a_caller():
    """Behind a proxy, so the set a screening draws from is fixed at import."""
    assert isinstance(base.DEEP_MODULES, types.MappingProxyType)

    with pytest.raises(TypeError):
        base.DEEP_MODULES["tamper_ela"] = _Answers("ela")


def test_module_names_spell_the_registry_in_its_own_order():
    """The names are one value a test holds the registry against."""
    registry = {"tamper_ela": _Answers("ela"), "tamper_noise": _Answers("x")}

    assert tuple(registry) == ("tamper_ela", "tamper_noise")


def test_a_module_that_never_wrote_run_cannot_be_built():
    """Wired wrongly fails at construction, not on the first document."""
    with pytest.raises(TypeError):
        _NoRun()


def test_a_module_that_raises_reaches_the_caller():
    """D114 isolates a broken stage in ``run_cascade``; catching twice would
    hide the failure from the trace row that records it."""
    module = _Answers("ela")
    module.run = _raiser()

    with pytest.raises(RuntimeError):
        base.run_deep_modules(_context(), modules={"tamper_ela": module})


def _raiser():
    def run(context):
        raise RuntimeError("the encoder returned no direction")

    return run
