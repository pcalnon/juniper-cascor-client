"""Testing utilities for juniper-cascor-client.

Provides in-memory fake implementations of JuniperCascorClient and
CascorTrainingStream for use in consumer test suites without requiring
a running JuniperCascor service.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: Testing Submodule
Author: Paul Calnon
Version: 0.1.0
License: MIT License

Usage:
    >>> from juniper_cascor_client.testing import FakeCascorClient, FakeCascorTrainingStream
    >>> with FakeCascorClient(scenario="two_spiral_training") as client:
    ...     status = client.get_training_status()
    ...     client.advance_epoch(10)
    ...     metrics = client.get_metrics()
"""

from juniper_cascor_client.testing.fake_client import FakeCascorClient
from juniper_cascor_client.testing.fake_ws_client import FakeCascorTrainingStream

__all__ = [
    "FakeCascorClient",
    "FakeCascorTrainingStream",
]
