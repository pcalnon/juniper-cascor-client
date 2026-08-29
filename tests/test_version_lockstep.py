#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   juniper-cascor-client
# Application:   juniper_cascor_client
# File Name:     test_version_lockstep.py
# Author:        Paul Calnon
# Version:       0.7.0
#
# Date Created:  2026-08-28
# Last Modified: 2026-08-28
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Pins [project].version in pyproject.toml to juniper_cascor_client.__version__
#    (defect register APD-ECO-005). The two are maintained by hand in separate
#    files and nothing checked that they agree.
#####################################################################################################################################################################################################

"""The pyproject/dunder version-lockstep gate (defect register ``APD-ECO-005``).

``[project].version`` and ``juniper_cascor_client.__version__`` are two
hand-maintained literals in two files. Nothing checked that they agree, and the
failure is silent in the direction that matters: the static release path bumps
``pyproject.toml``, so a wheel ships whose ``__version__`` lies about what it is. A
consumer pinning on the dunder, logging it, or quoting it in a bug report then
reports the wrong version.

This package is the one that actually drifted. ``APD-CCLIENT-F01`` in the register
records ``__version__`` left at ``0.4.0`` while the package shipped ``0.5.x`` /
``0.6.x``; a tombstone comment at ``__init__.py`` marks the incident. The literals
were corrected, but the *guard* was never added -- so nothing prevented a
recurrence. The register entry says so in as many words: "The *guard* is still
absent -- see ``APD-ECO-005``."

The mechanism exists one level up -- ``juniper-ml``'s
``tests/test_release_train_registry.py::VersionDunderLockstepTest``, whose docstring
names the incident that motivated it ("service-core 0.5.0, silent for five days
because no gate existed") -- but it scans only packages **in that repository**. The
standalone client repos live outside its reach, which is precisely why the drift
happened here and not there.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

import juniper_cascor_client

# The package root is the parent of ``tests/``. Resolved from this file rather
# than the process CWD: pytest can be invoked from anywhere, and reading
# "pyproject.toml" relatively would silently pick up a DIFFERENT project's file
# when run from a parent directory -- a green test asserting nothing about this
# package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _declared_version() -> str:
    return str(tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["version"])


@pytest.mark.unit
def test_pyproject_and_dunder_agree() -> None:
    assert _declared_version() == juniper_cascor_client.__version__, f"pyproject.toml [project].version is {_declared_version()!r} but " f"juniper_cascor_client.__version__ is {juniper_cascor_client.__version__!r}. " "These are two hand-maintained literals; bump both (APD-ECO-005). This package " "already drifted once this way -- see APD-CCLIENT-F01."


@pytest.mark.unit
def test_lockstep_gate_reads_this_package() -> None:
    """Negative control: prove the gate is anchored on THIS repo, not the CWD.

    The assertion above passes vacuously if ``_PYPROJECT`` resolves to some other
    project's file that happens to agree with this dunder, or to a file whose
    ``[project]`` table simply lacks the key. Pin the anchor itself.
    """
    assert _PYPROJECT.is_file(), f"{_PYPROJECT} does not exist -- the lockstep gate is reading nothing"
    parsed = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    assert parsed["project"]["name"] == "juniper-cascor-client"
    # The imported package must be the one in this checkout, or the dunder above
    # belongs to a different copy than the pyproject we just parsed.
    assert Path(juniper_cascor_client.__file__).resolve().is_relative_to(_REPO_ROOT)


@pytest.mark.unit
def test_version_is_statically_declared() -> None:
    """Dynamic packages are exempt from lockstep -- their dunder IS the source.

    juniper-recurrence-client is exactly that case and correctly has no such gate.
    If this package ever moves to ``dynamic = ["version"]`` the assertion above
    becomes tautological rather than false, so it would keep passing while guarding
    nothing. Fail here instead, so the move is a deliberate decision to delete this
    module rather than a silent downgrade to a vacuous test.
    """
    parsed = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    assert "version" not in parsed["project"].get("dynamic", []), "version is now dynamic; this lockstep gate no longer guards anything and should be removed deliberately (APD-ECO-005)"


@pytest.mark.unit
def test_tomllib_is_available() -> None:
    # tomllib is stdlib from 3.11; this package requires >=3.12, so a missing
    # tomllib means the floor slipped rather than the test being unsupported.
    assert sys.version_info >= (3, 12)
