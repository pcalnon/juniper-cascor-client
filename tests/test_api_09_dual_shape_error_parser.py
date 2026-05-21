"""API-09 PR 2: regression coverage for ``_handle_response`` dual-shape parser.

Background
----------

The API-09 migration plan (juniper-cascor PR #291 design doc;
juniper-cascor PR #293 = PR 1/3) converges cascor's two error response
shapes onto a single envelope. During the migration window cascor emits
a **dual-shape** response: the new
``{"status":"error","error":{"code","message","detail"},"meta":...}``
envelope **plus** a top-level ``"detail"`` deprecation alias for
backward compatibility with pre-PR-2 cascor-client releases.

Investigation while preparing this PR (juniper-cascor-client PR 2/3 of
the migration) surfaced that the dual-shape parser was **already
shipped** in ``client.py:_handle_response`` by Paul on 2026-02-21
(commit b0a636a3), months before the API-09 design doc was written.
The existing parser at lines 393-402 reads either shape correctly:

  * if ``body["error"]`` is a ``dict`` -> use ``body["error"]["message"]``
    (preferred — the envelope shape; future post-PR-3 cascor responses)
  * else -> fall back to ``body.get("detail", response.text)``
    (legacy — pre-PR-1 cascor responses, or hand-rolled non-cascor
    JSON error bodies that follow the FastAPI default ``{"detail": ...}``
    convention)

What this file adds
-------------------

The existing ``tests/test_client.py`` covers the **envelope-shape**
path implicitly (via the ``_error_response()`` helper that mocks
``{"status":"error","error":{"code","message"},"meta":...}``) but has
**no explicit pinning** for either of the two other shapes the parser
must handle during the API-09 deprecation window:

  1. the **legacy** ``{"detail": ...}`` shape (pre-PR-1 cascor servers)
  2. the **dual-shape** ``{"status":"error","error":{...},"meta":...,"detail":...}``
     (cascor PR 1 ↔ PR 3 deprecation window output)

Without explicit tests, a future refactor of ``_handle_response`` could
accidentally drop one of the branches and the change would go
unnoticed until a deployment surfaced degraded error messages. This
file pins all three shapes (legacy, envelope-only, dual) so the parser
contract is locked.

PR 3 of the API-09 migration will drop the top-level ``"detail"``
alias on the cascor side, at which point only the envelope-only and
legacy shapes remain in the wild. The legacy-shape tests here stay
valid (some third-party services may still emit FastAPI-default error
bodies); the dual-shape tests document the historical deprecation
window.
"""

import pytest
import responses
from requests.adapters import HTTPAdapter

from juniper_cascor_client import (
    JuniperCascorClient,
    JuniperCascorClientError,
    JuniperCascorConflictError,
    JuniperCascorNotFoundError,
    JuniperCascorServiceUnavailableError,
    JuniperCascorValidationError,
)

BASE_URL = "http://localhost:8200"
API_URL = f"{BASE_URL}/v1"


# -- Three response-shape mocks the parser must handle -------------------------


def _legacy_detail_only(message: str) -> dict:
    """Pre-PR-1 cascor (and any vanilla FastAPI HTTPException) shape."""
    return {"detail": message}


def _envelope_only(code: str, message: str) -> dict:
    """Post-PR-3 cascor (and pre-PR-1 cascor's ValueError/Exception
    handlers, which already emitted this shape).
    """
    return {
        "status": "error",
        "error": {"code": code, "message": message, "detail": None},
        "meta": {"timestamp": 1234567890.0, "version": "0.4.0"},
    }


def _dual_shape(code: str, message: str) -> dict:
    """Cascor PR 1 ↔ PR 3 deprecation-window output — envelope plus
    the top-level ``"detail"`` alias that keeps pre-PR-2 cascor-client
    releases working.

    The parser must prefer ``error.message`` over the alias when both
    are present so the alias can eventually be dropped server-side
    without changing client-side error messages.
    """
    return {
        "status": "error",
        "error": {"code": code, "message": message, "detail": None},
        "meta": {"timestamp": 1234567890.0, "version": "0.4.0"},
        "detail": message,
    }


# -- Status-code -> exception-class mapping pinned by ``_handle_response`` -----

STATUS_TO_EXCEPTION = [
    (400, JuniperCascorValidationError),
    (404, JuniperCascorNotFoundError),
    (409, JuniperCascorConflictError),
    (422, JuniperCascorValidationError),
    (503, JuniperCascorServiceUnavailableError),
]


@pytest.fixture
def client():
    """Build a JuniperCascorClient with retries disabled.

    The default client retries on 502/503/504/etc. (XREPO-02 / CC-02)
    so a plain ``responses.add(..., status=503)`` mock would surface
    as a ``Max retries exceeded`` ConnectionError rather than as the
    expected typed ``JuniperCascor*Error``. Swap the adapter for a
    no-retry one — same pattern used by ``test_client.py``'s
    ``test_service_unavailable_503``.
    """
    c = JuniperCascorClient(BASE_URL)
    no_retry = HTTPAdapter(max_retries=0)
    c.session.mount("http://", no_retry)
    c.session.mount("https://", no_retry)
    yield c
    c.close()


class TestLegacyDetailOnlyShape:
    """Pre-PR-1 cascor (and any vanilla FastAPI HTTPException) shape."""

    @pytest.mark.parametrize("status,exc_class", STATUS_TO_EXCEPTION)
    @responses.activate
    def test_legacy_detail_propagates_to_exception_message(self, client, status, exc_class):
        message = f"legacy-detail-msg-{status}"
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            json=_legacy_detail_only(message),
            status=status,
        )
        with pytest.raises(exc_class) as excinfo:
            client.get_network()
        assert message in str(excinfo.value)

    @responses.activate
    def test_legacy_detail_500_raises_generic_with_http_prefix(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            json=_legacy_detail_only("server exploded"),
            status=500,
        )
        with pytest.raises(JuniperCascorClientError) as excinfo:
            client.get_network()
        assert "HTTP 500" in str(excinfo.value)
        assert "server exploded" in str(excinfo.value)


class TestEnvelopeOnlyShape:
    """Post-PR-3 cascor (envelope-only — no top-level ``detail`` alias)."""

    @pytest.mark.parametrize("status,exc_class", STATUS_TO_EXCEPTION)
    @responses.activate
    def test_envelope_message_propagates_to_exception(self, client, status, exc_class):
        message = f"envelope-msg-{status}"
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            json=_envelope_only(f"HTTP_{status}", message),
            status=status,
        )
        with pytest.raises(exc_class) as excinfo:
            client.get_network()
        assert message in str(excinfo.value)


class TestDualShapeDeprecationWindow:
    """Cascor PR 1 ↔ PR 3 dual-shape output.

    The parser must prefer ``error.message`` over the top-level
    ``"detail"`` alias so the alias can be removed server-side in PR 3
    without changing client error messages. To prove that, the mocks
    here deliberately put **different** strings in ``error.message``
    vs. ``detail`` and assert the envelope's ``error.message`` wins.
    """

    @pytest.mark.parametrize("status,exc_class", STATUS_TO_EXCEPTION)
    @responses.activate
    def test_envelope_message_wins_over_top_level_detail(self, client, status, exc_class):
        envelope_msg = f"from-envelope-{status}"
        alias_msg = f"from-alias-DIFFERENT-{status}"
        body = {
            "status": "error",
            "error": {"code": f"HTTP_{status}", "message": envelope_msg, "detail": None},
            "meta": {"timestamp": 1234567890.0, "version": "0.4.0"},
            "detail": alias_msg,
        }
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            json=body,
            status=status,
        )
        with pytest.raises(exc_class) as excinfo:
            client.get_network()
        assert envelope_msg in str(excinfo.value)
        assert alias_msg not in str(excinfo.value)

    @pytest.mark.parametrize("status,exc_class", STATUS_TO_EXCEPTION)
    @responses.activate
    def test_dual_shape_realistic_alias_equals_envelope(self, client, status, exc_class):
        """In practice cascor PR 1 sets alias == error.message. Pin
        the happy path too so we don't only test the divergent-mock
        case."""
        message = f"realistic-dual-msg-{status}"
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            json=_dual_shape(f"HTTP_{status}", message),
            status=status,
        )
        with pytest.raises(exc_class) as excinfo:
            client.get_network()
        assert message in str(excinfo.value)


class TestNonJsonAndMalformedFallback:
    """Defensive paths around the JSON/key lookup that haven't drifted."""

    @responses.activate
    def test_non_json_body_falls_back_to_text(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            body="<html>nginx 502</html>",
            content_type="text/html",
            status=502,
        )
        with pytest.raises(JuniperCascorClientError) as excinfo:
            client.get_network()
        assert "HTTP 502" in str(excinfo.value)
        assert "nginx" in str(excinfo.value)

    @responses.activate
    def test_json_with_neither_detail_nor_error_falls_back_to_text(self, client):
        # An error body shaped neither like FastAPI's default nor like
        # cascor's envelope — e.g. a passthrough from a reverse proxy or
        # a misconfigured third-party intermediary. The parser must fall
        # back to ``response.text`` (the raw JSON) rather than raise on
        # the missing keys.
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            json={"unexpected": "shape", "no_detail_or_error_key": True},
            status=502,
        )
        with pytest.raises(JuniperCascorClientError) as excinfo:
            client.get_network()
        assert "HTTP 502" in str(excinfo.value)
        # The raw text fallback contains the JSON-encoded body so at
        # least one of the literal keys appears in the error message.
        assert "unexpected" in str(excinfo.value) or "shape" in str(excinfo.value)
