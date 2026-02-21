"""Custom exceptions for the JuniperCascor client library."""


class JuniperCascorClientError(Exception):
    """Base exception for all JuniperCascor client errors."""

    pass


class JuniperCascorConnectionError(JuniperCascorClientError):
    """Raised when connection to JuniperCascor service fails."""

    pass


class JuniperCascorTimeoutError(JuniperCascorClientError):
    """Raised when a request to JuniperCascor times out."""

    pass


class JuniperCascorNotFoundError(JuniperCascorClientError):
    """Raised when a requested resource is not found (404)."""

    pass


class JuniperCascorConflictError(JuniperCascorClientError):
    """Raised when a request conflicts with current state (409)."""

    pass


class JuniperCascorValidationError(JuniperCascorClientError):
    """Raised when request parameters fail validation (400/422)."""

    pass


class JuniperCascorServiceUnavailableError(JuniperCascorClientError):
    """Raised when the service is not ready (503)."""

    pass
