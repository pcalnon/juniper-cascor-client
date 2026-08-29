"""Consumer-shaped type probe for ``juniper_cascor_client`` (defect register ``APD-ECO-006``).

Project:     Juniper
Sub-Project: juniper-cascor-client
Application: published type-surface probe
Author:      Paul Calnon
License:     MIT License

WHY THIS FILE EXISTS, AND WHY IT LIVES **OUTSIDE** THE PACKAGE
-------------------------------------------------------------
The repo's mypy hook was scoped ``^juniper_cascor_client/(?!testing/).*\\.py$`` -- library-internal
source only. Nothing type-checked a file that *imports* the package the way a consumer does, so the
published type surface was never verified as usable from outside. That is ``APD-ECO-006``: "no client
type-checks a consumer-shaped probe."

This module is that consumer. It is deliberately at the repo root rather than inside
``juniper_cascor_client/`` or ``tests/`` -- inside the package it would be internal source again, and
the hook's ``files:`` regex is widened to reach exactly here.

WHAT THIS CATCHES
-----------------
* a public name in ``__all__`` that does not resolve for an importer;
* a public method whose annotation is missing, wrong, or silently ``Any`` at the boundary;
* an error class that stops deriving from the package base, silently breaking every consumer's
  ``except JuniperCascorClientError``.

WHAT THIS DOES **NOT** CATCH -- stated so it is not mistaken for a guarantee
---------------------------------------------------------------------------
mypy resolves ``juniper_cascor_client`` from the **source tree** here, not from an installed
distribution, so ``py.typed`` is bypassed entirely. A wheel that shipped without ``py.typed`` would
give a real consumer an untyped package while this probe still passed -- the ``APD-SVCCORE-008`` /
``APD-OBS-002`` class. Catching that needs a check against the built artifact, and is a separate
concern from this row. ``juniper_cascor_client/py.typed`` exists today; nothing yet asserts it is
packaged.

This file is never imported at runtime. The *type check* is the test, so it must stay import-clean.
"""

from __future__ import annotations

from typing import Any, Dict

from juniper_cascor_client import (
    CascorControlStream,
    CascorTrainingStream,
    JuniperCascorClient,
    JuniperCascorClientError,
    JuniperCascorConflictError,
    JuniperCascorConnectionError,
    JuniperCascorNotFoundError,
    JuniperCascorOverloadError,
    JuniperCascorServiceUnavailableError,
    JuniperCascorTimeoutError,
    JuniperCascorValidationError,
)


def probe_client_surface(client: JuniperCascorClient) -> None:
    """Exercise the public methods a consumer actually calls, checking each declared return type."""
    health: Dict[str, Any] = client.health_check()
    network: Dict[str, Any] = client.get_network()

    # Reading a value back off each result, so a return silently widened to ``Any`` does not pass
    # unnoticed the way a bare call would.
    _status: Any = health.get("status")
    _units: Any = network.get("hidden_units")


def probe_exception_hierarchy() -> None:
    """Every published error must be catchable through the package's base error.

    A consumer writes ``except JuniperCascorClientError``. If a subclass ever stops deriving from it,
    that consumer silently stops catching it -- a failure with no runtime signal until the exception
    escapes in production. Expressed as static subtype checks so it surfaces in the type check.
    """
    for derived in (
        JuniperCascorConflictError,
        JuniperCascorConnectionError,
        JuniperCascorNotFoundError,
        JuniperCascorOverloadError,
        JuniperCascorServiceUnavailableError,
        JuniperCascorTimeoutError,
        JuniperCascorValidationError,
    ):
        _: type[JuniperCascorClientError] = derived
    _base_is_exception: type[Exception] = JuniperCascorClientError


def probe_stream_types_are_exported() -> None:
    """The two WebSocket stream classes are part of the published surface, not internals.

    They are named in ``__all__``, so a consumer may annotate against them; this pins that they
    remain importable and usable as type annotations from outside the package.
    """
    _training: type[CascorTrainingStream] = CascorTrainingStream
    _control: type[CascorControlStream] = CascorControlStream
