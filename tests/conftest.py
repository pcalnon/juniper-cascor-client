"""Shared fixtures for juniper-cascor-client fake client tests.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: Test Fixtures
Author: Paul Calnon
Version: 0.1.0
License: MIT License
"""

import pytest

from juniper_cascor_client.testing import FakeCascorClient


@pytest.fixture
def fake_idle():
    """FakeCascorClient configured with the 'idle' scenario.

    No network loaded, ready for creation.
    """
    with FakeCascorClient(scenario="idle") as client:
        yield client


@pytest.fixture
def fake_training():
    """FakeCascorClient configured with the 'two_spiral_training' scenario.

    Active training on two-spiral dataset with realistic metric curves.
    """
    with FakeCascorClient(scenario="two_spiral_training") as client:
        yield client


@pytest.fixture
def fake_converged():
    """FakeCascorClient configured with the 'xor_converged' scenario.

    Fully trained XOR network at epoch 150, state 'complete'.
    """
    with FakeCascorClient(scenario="xor_converged") as client:
        yield client


@pytest.fixture
def fake_empty():
    """FakeCascorClient configured with the 'empty' scenario.

    Minimal responses for negative testing. No network loaded.
    """
    with FakeCascorClient(scenario="empty") as client:
        yield client


@pytest.fixture
def fake_error():
    """FakeCascorClient configured with the 'error_prone' scenario.

    Raises exceptions on approximately 10% of calls.
    Network loaded with one hidden unit at epoch 5.
    """
    with FakeCascorClient(scenario="error_prone") as client:
        yield client
