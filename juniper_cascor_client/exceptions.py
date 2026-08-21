"""Custom exceptions for the JuniperCascor client library."""

from __future__ import annotations

from typing import Any


class JuniperCascorClientError(Exception):
    """Base exception for all JuniperCascor client errors.

    Carries the machine-readable context a caller needs to *act* on the error
    rather than re-parse its message (defect-register ``APD-CCLIENT-004``,
    which absorbed the retired ``APD-CCLIENT-003``). ``_handle_response``
    computed the status and then dropped it on four of its five branches, so a
    400 and a 422 both raised ``JuniperCascorValidationError(error_msg)`` and
    were byte-identical. The two halves close together because they are one
    defect: the branches are indistinguishable *because* the type carries no
    status.

    Every attribute is optional and keyword-only, so locally raised errors
    (connection, timeout, "client is closed") and existing call sites that pass
    only a message keep working unchanged.

    Attributes:
        message: The human-readable summary, also passed to ``Exception``.
        status_code: HTTP status of the originating response, when there was
            one. ``None`` for errors raised before or without a response.
        detail: The server's error payload **exactly as decoded**. This service
            answers with two envelopes (``{"error": {"message": ...}}`` and
            FastAPI's ``{"detail": ...}``), and the latter is a ``list[dict]``
            for a 422. Deliberately not stringified: the structure is the point.
        response: The originating ``requests.Response``, when available, for
            callers that need headers or the raw body.

    This mirrors ``juniper-data-client``'s hierarchy deliberately. The three
    clients are separately released packages with no shared code, so nothing
    mechanical can keep them aligned -- the alignment is a convention, and this
    is a port of its reference implementation (juniper-data-client#158).
    """

    def __init__(  # noqa: B042 — see __reduce__ below
        self,
        message: str = "",
        *,
        status_code: int | None = None,
        detail: Any = None,
        response: Any = None,
    ) -> None:
        # B042 asks that an exception's ``__init__`` forward every argument to
        # ``super().__init__()`` and take no kwargs, so pickle and copy
        # round-trip. That concern is real and is honoured by ``__reduce__``
        # below; the remedy it suggests is not available here, because "take no
        # kwargs" is precisely the defect this class is closing. Forwarding the
        # extras to ``super()`` instead would put them in ``args`` and make
        # ``str(exc)`` a tuple repr, breaking every existing error message.
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail
        self.response = response

    def __reduce__(self) -> tuple[type[JuniperCascorClientError], tuple[str], dict[str, Any]]:
        """Keep the added context across ``pickle`` and ``copy``.

        ``BaseException.__reduce__`` returns ``(cls, self.args)``, and ``args``
        holds only the message -- so a round-trip would rebuild the exception
        with ``status_code=None``. It would still *look* correct, having
        silently dropped exactly the fields this class exists to carry.
        """
        return (self.__class__, (self.message,), self.__dict__.copy())


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


class JuniperCascorOverloadError(JuniperCascorClientError):
    """Raised when too many concurrent commands are pending (bounded map full)."""

    pass
