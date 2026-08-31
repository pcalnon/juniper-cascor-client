"""Dated deprecation of the legacy ``auto_pong=False`` posture.

Defect-register ``APD-ECO-007``, which owns the removal-date half of
``APD-CCLIENT-012``. ``APD-CCLIENT-012`` closed the *boolean-trap* half by making
``auto_pong`` keyword-only; the *removal-date* half was deliberately deferred to
``APD-ECO-007`` and is closed here.

Why dated rather than kept
--------------------------

``auto_pong=False`` shipped as a **silent** opt-out: no warning either way, and no
removal stated. The source primer names the consequence precisely -- "the risk is
that the flag never goes away: nothing tells you who still sets it" -- and contrasts
it with the ``juniper-data-client`` generator-alias deprecation, which is "warned,
dated, loud" and whose "dated window turns a deprecation from a permanent tax into
a plan".

A fleet census answered the "who still sets it" question: **zero** production users.
Every occurrence across juniper-canopy / cascor / cascor-worker / data / recurrence
/ ml is absent, and all eleven inside this repo are its own tests. With no consumer
to strand, the posture is dated rather than carried indefinitely.

What these tests pin
--------------------

* the warning fires on ``auto_pong=False`` for **both** real stream classes and
  the fake, and does **not** fire on the default;
* it is a ``DeprecationWarning`` and names the removal version, so the message is
  actionable rather than a bare "deprecated";
* **the warning is attributed to the caller, not to library code.** This is the
  arm that matters and the one that is easy to get wrong: the two call chains
  differ in depth (production goes through ``_init_liveness``, the fake does not),
  so a single shared ``stacklevel`` would be right for one and wrong for the other.
  The primer is explicit that walking the frames is "the only reliable check".
"""

import warnings

import pytest

from juniper_cascor_client.constants import AUTO_PONG_REMOVAL_VERSION
from juniper_cascor_client.testing.fake_ws_client import FakeCascorTrainingStream
from juniper_cascor_client.ws_client import CascorControlStream, CascorTrainingStream


def _construct(factory):
    """Build a stream under warning capture; return the records."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        factory()
    return caught


CONSTRUCTORS = [
    pytest.param(lambda: CascorTrainingStream(auto_pong=False), id="training"),
    pytest.param(lambda: CascorControlStream(auto_pong=False), id="control"),
    pytest.param(lambda: FakeCascorTrainingStream(auto_pong=False), id="fake"),
]

# The classes themselves, not ``lambda: Cls()`` wrappers around them: with no
# arguments to bind, the lambda adds a frame and nothing else (CodeQL
# "Unnecessary lambda", raised on this file and correct). The ``CONSTRUCTORS``
# list above legitimately keeps its lambdas -- those bind ``auto_pong=False``.
DEFAULT_CONSTRUCTORS = [
    pytest.param(CascorTrainingStream, id="training"),
    pytest.param(CascorControlStream, id="control"),
    pytest.param(FakeCascorTrainingStream, id="fake"),
]


class TestLegacyPostureIsDeprecated:
    @pytest.mark.parametrize("factory", CONSTRUCTORS)
    def test_warns_on_legacy_posture(self, factory):
        caught = _construct(factory)
        assert len(caught) == 1, [str(c.message) for c in caught]
        assert issubclass(caught[0].category, DeprecationWarning)

    @pytest.mark.parametrize("factory", CONSTRUCTORS)
    def test_message_names_the_removal_version(self, factory):
        """A deprecation without a date is the defect; the version IS the fix."""
        message = str(_construct(factory)[0].message)
        assert AUTO_PONG_REMOVAL_VERSION in message
        assert "auto_pong=False" in message

    @pytest.mark.parametrize("factory", DEFAULT_CONSTRUCTORS)
    def test_default_posture_is_silent(self, factory):
        """The default is not deprecated -- warning on it would train callers to
        filter the category, which would hide the real one."""
        assert _construct(factory) == []


class TestWarningIsAttributedToTheCaller:
    """The decisive arms.

    ``stacklevel`` off by one attributes the warning to library code, so the caller
    who passed the flag never sees their own file and cannot find the line to change.

    **These constructions are deliberately inline rather than routed through the
    ``_construct`` helper above.** With a helper plus a lambda, the frames one and
    two levels out are *both* inside this test file, so ``filename == __file__``
    holds for a right and a wrong ``stacklevel`` alike -- the arm looks green and
    pins nothing. A mutation (fake ``3 -> 4``) is what exposed that: it passed.
    Constructing inline puts pytest's own module at the next frame out, so an
    off-by-one now escapes this file and the assertion bites.

    Production is ``stacklevel=4`` (warn <- ``_init_liveness`` <- ``__init__`` <-
    caller); the fake is ``3`` (warn <- ``__init__`` <- caller).
    """

    def test_training_stream_attributes_to_caller(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            CascorTrainingStream(auto_pong=False)
        assert caught[0].filename == __file__, f"attributed to {caught[0].filename}, not the caller"

    def test_control_stream_attributes_to_caller(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            CascorControlStream(auto_pong=False)
        assert caught[0].filename == __file__, f"attributed to {caught[0].filename}, not the caller"

    def test_fake_stream_attributes_to_caller(self):
        """The fake's chain is one frame shorter than production's; this arm is
        what fails if it is given production's ``stacklevel``."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            FakeCascorTrainingStream(auto_pong=False)
        assert caught[0].filename == __file__, f"attributed to {caught[0].filename}, not the caller"

    def test_library_module_is_never_the_reported_origin(self):
        """Stated positively too: no construction may report a package file."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            CascorTrainingStream(auto_pong=False)
            CascorControlStream(auto_pong=False)
            FakeCascorTrainingStream(auto_pong=False)
        assert len(caught) == 3
        for record in caught:
            assert "juniper_cascor_client" not in record.filename
