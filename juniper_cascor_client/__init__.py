"""JuniperCascor Client - Python client library for the JuniperCascor REST/WebSocket API.

This package provides HTTP and WebSocket clients for interacting with the
JuniperCascor cascade correlation neural network training service.
"""

from juniper_cascor_client.client import JuniperCascorClient
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorServiceUnavailableError, JuniperCascorTimeoutError, JuniperCascorValidationError
from juniper_cascor_client.ws_client import CascorControlStream, CascorTrainingStream

__version__ = "0.3.0"

__all__ = [
    "JuniperCascorClient",
    "CascorTrainingStream",
    "CascorControlStream",
    "JuniperCascorClientError",
    "JuniperCascorConflictError",
    "JuniperCascorConnectionError",
    "JuniperCascorNotFoundError",
    "JuniperCascorServiceUnavailableError",
    "JuniperCascorTimeoutError",
    "JuniperCascorValidationError",
    "__version__",
]
