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
from juniper_cascor_client.client import _render_error_detail

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


class TestExceptionContext:
    """Every branch of ``_handle_response`` must attach the response context.

    Regression coverage for defect-register ``APD-CCLIENT-004``, which absorbed
    the retired ``APD-CCLIENT-003``. ``_handle_response`` computed ``status``
    and then dropped it on four of its five branches, so a 400 and a 422 both
    raised ``JuniperCascorValidationError(error_msg)`` and were byte-identical.
    Those are one defect: the branches were indistinguishable *because* the
    exception type carried no status.

    Ported from ``juniper-data-client`` (juniper-data-client#158). The three
    clients are separately released packages with no shared code, so nothing
    mechanical keeps them aligned -- these tests are the alignment.
    """

    #: A real FastAPI 422 body: ``detail`` is a list of error objects.
    FASTAPI_422_DETAIL = [
        {"type": "missing", "loc": ["body", "input_size"], "msg": "Field required"},
        {"type": "int_parsing", "loc": ["body", "output_size"], "msg": "Input should be a valid integer"},
    ]

    @pytest.mark.parametrize("status,exc_class", STATUS_TO_EXCEPTION)
    @responses.activate
    def test_every_branch_carries_its_status(self, client, status, exc_class):
        """All five branches, not just the generic one that formatted it in."""
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": "nope"}, status=status)

        with pytest.raises(exc_class) as excinfo:
            client.get_network()

        assert excinfo.value.status_code == status
        assert excinfo.value.detail == "nope"
        assert excinfo.value.response is not None

    @responses.activate
    def test_400_and_422_are_no_longer_byte_identical(self, client):
        """The retired APD-CCLIENT-003 half: same type, same text, no way to tell."""
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": "bad"}, status=400)
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": "bad"}, status=422)

        with pytest.raises(JuniperCascorValidationError) as first:
            client.get_network()
        with pytest.raises(JuniperCascorValidationError) as second:
            client.get_network()

        assert {first.value.status_code, second.value.status_code} == {400, 422}

    @responses.activate
    def test_422_detail_list_is_preserved_as_structure(self, client):
        """A FastAPI 422 ``detail`` is a list; the caller must get the list."""
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": self.FASTAPI_422_DETAIL}, status=422)

        with pytest.raises(JuniperCascorValidationError) as excinfo:
            client.get_network()

        assert excinfo.value.detail == self.FASTAPI_422_DETAIL
        assert excinfo.value.detail[0]["loc"] == ["body", "input_size"]

    @responses.activate
    def test_422_message_is_readable_not_a_python_repr(self, client):
        """Previously the list was passed straight to the exception, so
        ``str(exc)`` was a Python repr. This is the same defect juniper-data-client
        tracks as APD-DCLIENT-003; it was never recorded against this client.
        """
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": self.FASTAPI_422_DETAIL}, status=422)

        with pytest.raises(JuniperCascorValidationError) as excinfo:
            client.get_network()

        message = str(excinfo.value)
        assert "body.input_size: Field required" in message
        assert "body.output_size: Input should be a valid integer" in message
        # Fingerprints of the old repr-of-a-list behaviour.
        assert "'type':" not in message
        assert "[{" not in message

    @responses.activate
    def test_envelope_shape_also_carries_context(self, client):
        """The ``{"error": {"message": ...}}`` envelope is the other parser arm."""
        body = {"status": "error", "error": {"code": "CONFLICT", "message": "already training", "detail": None}}
        responses.add(responses.GET, f"{API_URL}/network", json=body, status=409)

        with pytest.raises(JuniperCascorConflictError) as excinfo:
            client.get_network()

        assert excinfo.value.status_code == 409
        assert excinfo.value.detail == "already training"

    def test_locally_raised_errors_have_no_status_code(self):
        """Backward compatibility: no response means the fields stay None."""
        error = JuniperCascorClientError("connection refused")

        assert error.status_code is None
        assert error.detail is None
        assert error.response is None
        assert str(error) == "connection refused"

    def test_positional_message_construction_still_works(self):
        """The added parameters are keyword-only, so every existing call site
        -- including ``FakeCascorClient``'s 29 raises -- keeps working."""
        for factory in (JuniperCascorClientError, JuniperCascorNotFoundError, JuniperCascorValidationError):
            error = factory("plain message")
            assert str(error) == "plain message"
            assert error.status_code is None

    def test_context_survives_pickle_and_copy(self):
        """``BaseException.__reduce__`` returns ``(cls, args, self.__dict__)``
        whenever the instance dict is non-empty, so the keyword-only context
        survives on the default path (flake8-bugbear B042) -- but only while
        ``args`` stays exactly the constructor's positional parameters. This
        test pins that invariant: forwarding the keyword-only extras into
        ``super().__init__`` (B042's own remedy) puts them in ``args``, and
        the rebuild's ``cls(*args)`` then raises ``TypeError``.
        """
        import copy as copy_module

        # Bandit blacklists pickle (B403/B301) for UNTRUSTED data; the payload
        # here is produced by the ``dumps`` below, in-process, from an exception
        # this test just built. The suppressions are the trailing inline markers
        # only -- a comment line that *begins* with the marker word is itself
        # parsed as a directive, and the following prose is read as test IDs.
        import pickle  # nosec B403

        original = JuniperCascorValidationError("Validation error", status_code=422, detail=[{"msg": "Field required"}])
        round_tripped = pickle.loads(pickle.dumps(original))  # nosec B301

        for rebuilt in (round_tripped, copy_module.copy(original), copy_module.deepcopy(original)):
            assert isinstance(rebuilt, JuniperCascorValidationError)
            assert rebuilt.status_code == 422
            assert rebuilt.detail == [{"msg": "Field required"}]
            assert str(rebuilt) == str(original)


class TestFakeClientMatchesRealExceptionContext:
    """``FakeCascorClient`` implements every public method of the real client,
    so it must populate the same context.

    A double that raises the right *type* with ``status_code=None`` lets a
    consumer's test pass against behaviour production does not have.
    """

    def test_fake_not_found_carries_404(self):
        from juniper_cascor_client.testing import FakeCascorClient

        fake = FakeCascorClient()
        with pytest.raises(JuniperCascorNotFoundError) as excinfo:
            fake.get_network()

        assert excinfo.value.status_code == 404

    def test_fake_conflict_carries_409(self):
        from juniper_cascor_client.testing import FakeCascorClient

        fake = FakeCascorClient()
        fake.create_network(input_size=2, output_size=2, learning_rate=0.1)
        with pytest.raises(JuniperCascorConflictError) as excinfo:
            fake.create_network(input_size=2, output_size=2, learning_rate=0.1)

        assert excinfo.value.status_code == 409

    def test_fake_validation_carries_422_like_pydantic(self):
        """The real service validates these with pydantic (``Field(ge=1)`` /
        ``Query(ge=, le=)``), and FastAPI answers a constraint violation 422.
        """
        from juniper_cascor_client.testing import FakeCascorClient

        fake = FakeCascorClient()
        with pytest.raises(JuniperCascorValidationError) as excinfo:
            fake.create_network(input_size=2)

        assert excinfo.value.status_code == 422


class TestRenderErrorDetailDegenerateShapes:
    """``_render_error_detail`` must not crash or emit a Python repr on shapes
    FastAPI (and proxies in front of it) actually produce besides the happy
    ``[{loc, msg}, ...]`` list pinned by ``TestExceptionContext``.

    These branches were uncovered on main (client.py:89-90, 97): a non-dict
    item, a mapping with no usable ``loc``, and the empty-list fallback.
    A refactor that assumed every element is a dict with ``loc`` would turn a
    422 into an uncaught TypeError on the caller's request path.
    """

    def test_non_dict_items_are_stringified_not_crashed(self):
        """A mixed list must keep going; the string item is not a mapping."""
        detail = ["plain string error", {"loc": ["body", "input_size"], "msg": "Field required"}]
        rendered = _render_error_detail(detail)
        assert "plain string error" in rendered
        assert "body.input_size: Field required" in rendered
        assert "'type':" not in rendered

    def test_dict_without_loc_uses_msg(self):
        """``loc`` is optional on FastAPI error objects; missing/empty/wrong-type
        all take the msg-only arm rather than raising."""
        assert _render_error_detail([{"msg": "something went wrong"}]) == "something went wrong"
        assert _render_error_detail([{"loc": [], "msg": "empty loc"}]) == "empty loc"
        assert _render_error_detail([{"loc": "not-a-sequence", "msg": "bad loc"}]) == "bad loc"

    def test_loc_tuple_is_joined_like_a_list(self):
        """Starlette stores ``loc`` as a tuple internally; join must accept it."""
        assert _render_error_detail([{"loc": ("body", "lr"), "msg": "too small"}]) == "body.lr: too small"

    def test_loc_with_empty_msg_is_just_the_location(self):
        """A present loc and blank msg must not collapse to an empty string."""
        assert _render_error_detail([{"loc": ["body", "x"], "msg": ""}]) == "body.x"

    def test_empty_list_stays_visible(self):
        """An empty list is a legal payload; ``str`` keeps it visible rather
        than collapsing to an empty exception message."""
        assert _render_error_detail([]) == "[]"

    @responses.activate
    def test_malformed_422_list_still_raises_typed_error_with_detail_preserved(self, client):
        """The consumer path: a mixed FastAPI-ish 422 must not crash inside
        ``_handle_response``, must keep the list on ``exc.detail``, and must
        render a readable message."""
        detail = ["gateway timeout fragment", {"loc": ("query", "count"), "msg": "ensure this value is greater than 0"}]
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": detail}, status=422)

        with pytest.raises(JuniperCascorValidationError) as excinfo:
            client.get_network()

        assert excinfo.value.status_code == 422
        assert excinfo.value.detail == detail
        message = str(excinfo.value)
        assert "gateway timeout fragment" in message
        assert "query.count: ensure this value is greater than 0" in message
        assert "[{" not in message
