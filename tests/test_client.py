"""Tests for JuniperCascorClient REST client."""

import pytest
import responses
from responses import matchers

from juniper_cascor_client import JuniperCascorClient, JuniperCascorConfigurationError, JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorServiceUnavailableError, JuniperCascorValidationError
from juniper_cascor_client.exceptions import JuniperCascorClientError

BASE_URL = "http://localhost:8200"
API_URL = f"{BASE_URL}/v1"


def _envelope(data):
    """Create a standard response envelope."""
    return {"status": "success", "data": data, "meta": {"timestamp": 1234567890.0, "version": "0.4.0"}}


def _error_response(code, message, status=400):
    """Create a standard error response."""
    return {"status": "error", "error": {"code": code, "message": message}, "meta": {"timestamp": 1234567890.0, "version": "0.4.0"}}


class TestClientInit:
    def test_default_url(self):
        client = JuniperCascorClient()
        assert client.base_url == "http://localhost:8200"
        assert client.api_url == "http://localhost:8200/v1"
        client.close()

    def test_custom_url(self):
        client = JuniperCascorClient("http://example.com:9000")
        assert client.base_url == "http://example.com:9000"
        client.close()

    def test_trailing_slash_stripped(self):
        client = JuniperCascorClient("http://example.com:9000/")
        assert client.base_url == "http://example.com:9000"
        client.close()

    def test_normalize_url_without_scheme(self):
        """A schemeless host gets the http:// default (APD-CCLIENT-005)."""
        client = JuniperCascorClient("example.com:9000")
        assert client.base_url == "http://example.com:9000"
        client.close()

    def test_normalize_url_with_v1_suffix(self):
        """A /v1-suffixed base no longer produces a double /v1 api_url."""
        client = JuniperCascorClient("http://example.com:9000/v1")
        assert client.base_url == "http://example.com:9000"
        assert client.api_url == "http://example.com:9000/v1"
        client.close()

    def test_normalize_url_with_whitespace(self):
        client = JuniperCascorClient("  http://example.com:9000  ")
        assert client.base_url == "http://example.com:9000"
        client.close()

    def test_normalize_https_preserved(self):
        client = JuniperCascorClient("https://example.com:9000")
        assert client.base_url == "https://example.com:9000"
        client.close()

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("HTTP://example.com:9000", "http://example.com:9000"),
            ("HTTPS://example.com:9000", "https://example.com:9000"),
            ("Http://example.com:9000", "http://example.com:9000"),
            ("Https://example.com:9000", "https://example.com:9000"),
            ("HTTPS://example.com:9000/v1", "https://example.com:9000"),
        ],
    )
    def test_normalize_url_scheme_is_case_insensitive(self, raw, expected):
        """RFC 3986 schemes are case-insensitive; do not prefix http:// onto HTTP(S)://.

        A case-sensitive startswith treated these as schemeless, producing
        ``http://HTTPS://host`` with netloc ``HTTPS:``. Construction succeeded
        and every request targeted the wrong host.
        """
        client = JuniperCascorClient(raw)
        assert client.base_url == expected
        assert client.api_url == f"{expected}/v1"
        client.close()

    @pytest.mark.parametrize("hostless", ["", "   ", "http://", "https://", "/v1", "http:///v1"])
    def test_normalize_hostless_url_raises_configuration_error(self, hostless):
        """A base URL with no host must fail at construction with the typed
        error, not opaquely on the first request (APD-CCLIENT-005)."""
        with pytest.raises(JuniperCascorConfigurationError, match="must include a host"):
            JuniperCascorClient(hostless)

    def test_hostless_url_error_is_catchable_as_the_base_error(self):
        with pytest.raises(JuniperCascorClientError):
            JuniperCascorClient("http://")

    def test_api_key_set_in_headers(self):
        client = JuniperCascorClient(api_key="test-key-123")
        assert client.session.headers["X-API-Key"] == "test-key-123"
        client.close()

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CASCOR_API_KEY", "env-key-456")
        client = JuniperCascorClient()
        assert client.api_key == "env-key-456"
        assert client.session.headers["X-API-Key"] == "env-key-456"
        client.close()

    def test_explicit_api_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CASCOR_API_KEY", "env-key-456")
        client = JuniperCascorClient(api_key="explicit-key-789")
        assert client.api_key == "explicit-key-789"
        assert client.session.headers["X-API-Key"] == "explicit-key-789"
        client.close()

    def test_context_manager(self):
        with JuniperCascorClient() as client:
            assert client is not None


class TestHealthEndpoints:
    @responses.activate
    def test_health_check(self):
        responses.add(responses.GET, f"{API_URL}/health", json=_envelope({"status": "ok", "version": "0.4.0"}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.health_check()
            assert result["data"]["status"] == "ok"

    @responses.activate
    def test_is_alive_true(self):
        responses.add(responses.GET, f"{API_URL}/health/live", json=_envelope({"status": "alive"}))
        with JuniperCascorClient(BASE_URL) as client:
            assert client.is_alive() is True

    @responses.activate
    def test_is_alive_false_on_error(self):
        responses.add(responses.GET, f"{API_URL}/health/live", body=ConnectionError("refused"))
        with JuniperCascorClient(BASE_URL) as client:
            assert client.is_alive() is False

    @responses.activate
    def test_is_ready_true(self):
        """is_ready() returns True when server reports network_loaded in flat ReadinessResponse."""
        responses.add(
            responses.GET,
            f"{API_URL}/health/ready",
            json={
                "status": "ready",
                "version": "0.4.0",
                "service": "juniper-cascor",
                "details": {"network_loaded": True, "training_state": "Started"},
            },
        )
        with JuniperCascorClient(BASE_URL) as client:
            assert client.is_ready() is True

    @responses.activate
    def test_is_ready_false(self):
        """is_ready() returns False when server reports network_loaded=False in flat ReadinessResponse."""
        responses.add(
            responses.GET,
            f"{API_URL}/health/ready",
            json={
                "status": "ready",
                "version": "0.4.0",
                "service": "juniper-cascor",
                "details": {"network_loaded": False, "training_state": "unknown"},
            },
        )
        with JuniperCascorClient(BASE_URL) as client:
            assert client.is_ready() is False


class TestNetworkEndpoints:
    @responses.activate
    def test_create_network(self):
        responses.add(responses.POST, f"{API_URL}/network", json=_envelope({"input_size": 2, "output_size": 2, "hidden_units": 0, "uuid": "net-123"}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.create_network(input_size=2, output_size=2, learning_rate=0.01)
            assert result["data"]["uuid"] == "net-123"

    @responses.activate
    def test_get_network(self):
        responses.add(responses.GET, f"{API_URL}/network", json=_envelope({"input_size": 2}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_network()
            assert result["data"]["input_size"] == 2

    @responses.activate
    def test_delete_network(self):
        responses.add(responses.DELETE, f"{API_URL}/network", json=_envelope({"deleted": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.delete_network()
            assert result["data"]["deleted"] is True

    @responses.activate
    def test_get_topology(self):
        responses.add(responses.GET, f"{API_URL}/network/topology", json=_envelope({"nodes": [], "edges": []}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_topology()
            assert "nodes" in result["data"]

    @responses.activate
    def test_get_statistics(self):
        responses.add(responses.GET, f"{API_URL}/network/stats", json=_envelope({"total_params": 10}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_statistics()
            assert result["data"]["total_params"] == 10

    @responses.activate
    def test_create_network_conflict(self):
        responses.add(responses.POST, f"{API_URL}/network", json=_error_response("CONFLICT", "Network already exists"), status=409)
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorConflictError):
                client.create_network(input_size=2, output_size=2, learning_rate=0.01)

    @responses.activate
    def test_get_network_not_found(self):
        responses.add(responses.GET, f"{API_URL}/network", json=_error_response("NOT_FOUND", "No network"), status=404)
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorNotFoundError):
                client.get_network()


class TestTrainingEndpoints:
    @responses.activate
    def test_start_training(self):
        responses.add(responses.POST, f"{API_URL}/training/start", json=_envelope({"training_started": True, "epochs": 100}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.start_training(epochs=100)
            assert result["data"]["training_started"] is True

    @responses.activate
    def test_start_training_with_inline_data(self):
        responses.add(responses.POST, f"{API_URL}/training/start", json=_envelope({"training_started": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.start_training(inline_data={"train_x": [[1, 2]], "train_y": [[1, 0]]})
            assert result["data"]["training_started"] is True

    @responses.activate
    def test_stop_training(self):
        responses.add(responses.POST, f"{API_URL}/training/stop", json=_envelope({"training_stopped": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.stop_training()
            assert result["data"]["training_stopped"] is True

    @responses.activate
    def test_pause_training(self):
        responses.add(responses.POST, f"{API_URL}/training/pause", json=_envelope({"paused": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.pause_training()
            assert result["data"]["paused"] is True

    @responses.activate
    def test_resume_training(self):
        responses.add(responses.POST, f"{API_URL}/training/resume", json=_envelope({"resumed": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.resume_training()
            assert result["data"]["resumed"] is True

    @responses.activate
    def test_reset_training(self):
        responses.add(responses.POST, f"{API_URL}/training/reset", json=_envelope({"reset": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.reset_training()
            assert result["data"]["reset"] is True

    @responses.activate
    def test_get_training_status(self):
        responses.add(responses.GET, f"{API_URL}/training/status", json=_envelope({"training_active": True, "state_machine": {}}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_training_status()
            assert result["data"]["training_active"] is True

    @responses.activate
    def test_get_training_params(self):
        responses.add(responses.GET, f"{API_URL}/training/params", json=_envelope({"learning_rate": 0.01}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_training_params()
            assert result["data"]["learning_rate"] == 0.01


class TestMetricsEndpoints:
    @responses.activate
    def test_get_metrics(self):
        responses.add(responses.GET, f"{API_URL}/metrics", json=_envelope({"epoch": 10, "train_loss": 0.05}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_metrics()
            assert result["data"]["epoch"] == 10

    @responses.activate
    def test_get_metrics_history(self):
        responses.add(responses.GET, f"{API_URL}/metrics/history", json=_envelope([{"epoch": 1}, {"epoch": 2}]))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_metrics_history(count=50)
            assert len(result["data"]) == 2

    @responses.activate
    def test_get_metrics_not_found(self):
        responses.add(responses.GET, f"{API_URL}/metrics", json=_error_response("NOT_FOUND", "No network"), status=404)
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorNotFoundError):
                client.get_metrics()


class TestDataEndpoints:
    @responses.activate
    def test_get_dataset(self):
        responses.add(responses.GET, f"{API_URL}/dataset", json=_envelope({"train_shape": [500, 2]}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_dataset()
            assert result["data"]["train_shape"] == [500, 2]

    @responses.activate
    def test_get_dataset_data(self):
        data = {"train_x": [[0.1, 0.2]], "train_y": [[1.0, 0.0]]}
        responses.add(responses.GET, f"{API_URL}/dataset/data", json=_envelope(data))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_dataset_data()
            assert result["data"]["train_x"] == [[0.1, 0.2]]
            assert result["data"]["train_y"] == [[1.0, 0.0]]

    @responses.activate
    def test_get_dataset_data_not_found(self):
        responses.add(responses.GET, f"{API_URL}/dataset/data", json=_error_response("NOT_FOUND", "No dataset loaded"), status=404)
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorNotFoundError):
                client.get_dataset_data()

    @responses.activate
    def test_get_decision_boundary(self):
        responses.add(responses.GET, f"{API_URL}/decision-boundary", json=_envelope({"resolution": 50, "predictions": []}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_decision_boundary(resolution=50)
            assert result["data"]["resolution"] == 50


class TestErrorHandling:
    @responses.activate
    def test_validation_error_400(self):
        responses.add(responses.POST, f"{API_URL}/network", json=_error_response("VALIDATION_ERROR", "Invalid"), status=400)
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorValidationError):
                client.create_network(input_size=-1)

    @responses.activate
    def test_validation_error_422(self):
        responses.add(responses.POST, f"{API_URL}/network", json=_error_response("VALIDATION_ERROR", "Invalid"), status=422)
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorValidationError):
                client.create_network()

    @responses.activate
    def test_service_unavailable_503(self):
        # XREPO-02 / CC-02 (2026-04-24): 503 is now a retryable status.
        # To exercise the server-error -> typed-exception mapping, swap
        # the session adapter for a retry-free one after construction.
        # This mirrors how integration tests that need deterministic
        # error surfacing would disable retries in practice.
        from requests.adapters import HTTPAdapter

        responses.add(responses.GET, f"{API_URL}/network", json=_error_response("SERVICE_UNAVAILABLE", "Not ready"), status=503)
        with JuniperCascorClient(BASE_URL) as client:
            no_retry = HTTPAdapter(max_retries=0)
            client.session.mount("http://", no_retry)
            client.session.mount("https://", no_retry)
            with pytest.raises(JuniperCascorServiceUnavailableError):
                client.get_network()

    def test_connection_refused(self):
        with JuniperCascorClient("http://localhost:19999") as client:
            with pytest.raises(JuniperCascorConnectionError):
                client.health_check()


class TestMalformedJsonResponse:
    """ERR-02 (Phase 4C): malformed JSON bodies should raise typed errors."""

    @responses.activate
    def test_success_status_with_invalid_json_raises_client_error(self):
        responses.add(
            responses.GET,
            f"{API_URL}/health",
            body="this is not json {",
            status=200,
            content_type="application/json",
        )
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorClientError, match="Malformed JSON response"):
                client.health_check()

    @responses.activate
    def test_error_status_with_invalid_json_uses_raw_text(self):
        responses.add(
            responses.GET,
            f"{API_URL}/network",
            body="upstream proxy error not json",
            status=502,
            content_type="text/plain",
        )
        with JuniperCascorClient(BASE_URL) as client:
            from requests.adapters import HTTPAdapter

            no_retry = HTTPAdapter(max_retries=0)
            client.session.mount("http://", no_retry)
            client.session.mount("https://", no_retry)
            with pytest.raises(JuniperCascorClientError, match="upstream proxy error not json"):
                client.get_network()


@pytest.mark.unit
class TestRetryExhaustionSurfacesTypedStatus:
    """A retryable status that outlives its retries must still be classified.

    Regression coverage for defect-register ``APD-CCLIENT-002``. urllib3
    defaults ``raise_on_status`` to True, so once the retries for a
    ``status_forcelist`` code ran out it raised ``MaxRetryError`` -- surfaced by
    requests as ``RetryError``, a plain ``RequestException`` -- which
    ``_request``'s generic handler flattened into ``JuniperCascorClientError``
    *before* ``_handle_response`` ever ran. The 503 arm there, and therefore
    ``JuniperCascorServiceUnavailableError``, was unreachable in any client
    built with retries: i.e. every production client.

    Every pre-existing test of that arm swaps in ``HTTPAdapter(max_retries=0)``
    first (see ``TestErrorHandling.test_service_unavailable_503``). That is why
    the dead branch went unnoticed -- the coverage proved the branch worked
    under a configuration production never uses. These tests deliberately use a
    **retrying** client and mount no adapter of their own.
    """

    @responses.activate
    def test_503_after_retries_raises_the_typed_error_not_the_generic_one(self) -> None:
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": "not ready"}, status=503)

        with JuniperCascorClient(BASE_URL, retries=2) as client:
            with pytest.raises(JuniperCascorServiceUnavailableError) as excinfo:
                client.get_network()

        assert excinfo.value.status_code == 503
        assert excinfo.value.detail == "not ready"

    @responses.activate
    def test_retries_are_still_performed(self) -> None:
        """The fix changes only the give-up path, never the retrying itself.

        If ``raise_on_status=False`` were mistaken for "stop retrying", this is
        the arm that catches it: a retrying client must still make
        ``retries + 1`` attempts before surfacing the error.
        """
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": "not ready"}, status=503)

        with JuniperCascorClient(BASE_URL, retries=2) as client:
            with pytest.raises(JuniperCascorServiceUnavailableError):
                client.get_network()

        assert len(responses.calls) == 3

    @responses.activate
    def test_other_retryable_statuses_keep_their_real_status_code(self) -> None:
        """429 / 502 / 504 have no dedicated type, but they had no status either."""
        responses.add(responses.GET, f"{API_URL}/network", json={"detail": "slow down"}, status=429)

        with JuniperCascorClient(BASE_URL, retries=1) as client:
            with pytest.raises(JuniperCascorClientError) as excinfo:
                client.get_network()

        assert excinfo.value.status_code == 429

    def test_transport_failures_are_untouched(self) -> None:
        """No response means no classification -- these must still be typed as transport errors.

        ``raise_on_status`` only governs the give-up path for a *status*. A
        refused connection never produces a response, so it must keep raising
        from urllib3 and keep landing on the ConnectionError arm.
        """
        with JuniperCascorClient("http://127.0.0.1:19999", retries=1) as client:
            with pytest.raises(JuniperCascorConnectionError) as excinfo:
                client.get_network()

        assert excinfo.value.status_code is None
