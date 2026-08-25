"""Signature pins for the WS stream constructors (defect-register ``APD-CCLIENT-012``).

``auto_pong`` was a trailing positional-or-keyword boolean on all three
constructors — ``CascorTrainingStream("ws://h", None, None, False)`` was legal
and unreadable, and appending any future parameter before it would silently
rebind the boolean. It is now keyword-only on the two real streams and the
fake alike (the fake must fail a positional call exactly as production
would). An ecosystem census at fix time found no construction passing more
than one positional argument and every ``auto_pong`` use already by keyword,
so the boundary broke no caller.

The legacy ``auto_pong=False`` posture's missing *removal date* — the other
half of the register row — is the deprecation-machinery question tracked by
the open ``APD-ECO-007`` and is deliberately not decided here.
"""

import inspect

import pytest

from juniper_cascor_client import CascorControlStream, CascorTrainingStream
from juniper_cascor_client.testing import FakeCascorTrainingStream


@pytest.mark.parametrize("cls", [CascorTrainingStream, CascorControlStream, FakeCascorTrainingStream], ids=["training", "control", "fake"])
def test_auto_pong_is_keyword_only(cls):
    kind = inspect.signature(cls.__init__).parameters["auto_pong"].kind
    assert kind is inspect.Parameter.KEYWORD_ONLY, f"{cls.__name__}.auto_pong must be keyword-only (APD-CCLIENT-012); got {kind!r}"


# No runtime "positional call raises TypeError" arm on purpose: the KEYWORD_ONLY
# kind pinned above implies that TypeError by Python semantics, and CodeQL's
# arity check (py/call/wrong-number-class-arguments) statically flags any
# visible wrong-arity instantiation — including a literal-tuple splat — so the
# demonstration arm cannot be written without suppressions. The kind arm alone
# fails when the boundary is removed (mutation-verified).


def test_keyword_auto_pong_still_works():
    stream = CascorTrainingStream("ws://localhost:8200", auto_pong=False)
    assert stream._auto_pong is False
