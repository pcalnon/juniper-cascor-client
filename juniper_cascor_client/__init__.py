"""JuniperCascor Client - Python client library for the JuniperCascor REST/WebSocket API.

This package provides HTTP and WebSocket clients for interacting with the
JuniperCascor cascade correlation neural network training service.
"""

from juniper_cascor_client.client import JuniperCascorClient
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorOverloadError, JuniperCascorServiceUnavailableError, JuniperCascorTimeoutError, JuniperCascorValidationError
from juniper_cascor_client.ws_client import CascorControlStream, CascorTrainingStream

# Kept in lockstep with [project].version in pyproject.toml (CL1 also fixed a
# pre-existing drift where this constant had been left at 0.4.0 while the
# package shipped 0.5.x/0.6.x).
__version__ = "0.7.0"

__all__ = [
    "JuniperCascorClient",
    "CascorTrainingStream",
    "CascorControlStream",
    "JuniperCascorClientError",
    "JuniperCascorConflictError",
    "JuniperCascorConnectionError",
    "JuniperCascorNotFoundError",
    "JuniperCascorOverloadError",
    "JuniperCascorServiceUnavailableError",
    "JuniperCascorTimeoutError",
    "JuniperCascorValidationError",
    "__version__",
]
