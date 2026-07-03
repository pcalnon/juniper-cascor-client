"""Targeted HTTP-path coverage for JuniperCascorClient.

Complements ``test_client.py`` by exercising the REST surfaces and error
branches that the primary suite does not reach: the readiness-polling helpers
(``is_ready`` error swallow + ``wait_for_ready`` loop), the snapshot/worker
endpoints, the ``start_training`` dataset/params body branches, and the
``_request`` transport-error mapping for timeouts and generic request
failures. Uses the same ``responses`` HTTP-mock idiom as ``test_client.py``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import requests
import responses

from juniper_cascor_client import JuniperCascorClient, JuniperCascorNotFoundError
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorTimeoutError

BASE_URL = "http://localhost:8200"
API_URL = f"{BASE_URL}/v1"


def _envelope(data):
    """Standard success envelope, mirroring ``test_client.py``."""
    return {"status": "success", "data": data, "meta": {"timestamp": 1234567890.0, "version": "0.4.0"}}


def _error_response(code, message):
    """Standard error envelope, mirroring ``test_client.py``."""
    return {"status": "error", "error": {"code": code, "message": message}, "meta": {"timestamp": 1234567890.0, "version": "0.4.0"}}


class TestReadinessHelpers:
    """``is_ready`` swallows client errors; ``wait_for_ready`` loops on them."""

    @responses.activate
    def test_is_ready_false_on_client_error(self):
        """A 404 from /health/ready surfaces as a typed client error inside
        ``is_ready``, which must catch it and report not-ready (client.py:121-122)."""
        responses.add(responses.GET, f"{API_URL}/health/ready", json=_error_response("NOT_FOUND", "no network"), status=404)
        with JuniperCascorClient(BASE_URL) as client:
            assert client.is_ready() is False

    def test_wait_for_ready_returns_true_after_transient_error(self):
        """``wait_for_ready`` tolerates a transient ``JuniperCascorClientError``
        from ``is_ready`` and returns True once readiness flips (client.py:126-133)."""
        with JuniperCascorClient(BASE_URL) as client:
            calls = {"n": 0}

            def flaky_is_ready():
                calls["n"] += 1
                if calls["n"] == 1:
                    raise JuniperCascorClientError("transient")
                return True

            client.is_ready = flaky_is_ready  # type: ignore[method-assign]
            with patch("juniper_cascor_client.client.time.sleep") as mock_sleep:
                assert client.wait_for_ready(timeout=5.0, poll_interval=0.01) is True
            # The transient error forced exactly one retry sleep.
            assert mock_sleep.call_count == 1

    def test_wait_for_ready_times_out_returns_false(self):
        """When readiness never arrives, ``wait_for_ready`` exits the loop and
        returns False without ever sleeping for real (client.py:134)."""
        with JuniperCascorClient(BASE_URL) as client:
            client.is_ready = lambda: False  # type: ignore[method-assign]
            with patch("juniper_cascor_client.client.time.sleep"):
                assert client.wait_for_ready(timeout=0.02, poll_interval=0.01) is False


class TestStartTrainingBodyBranches:
    """``start_training`` conditionally assembles the request body."""

    @responses.activate
    def test_start_training_with_dataset_and_params(self):
        """dataset= and params= populate their body keys (client.py:193, 197)."""
        import json as _json

        responses.add(responses.POST, f"{API_URL}/training/start", json=_envelope({"training_started": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.start_training(dataset={"source": "generator", "generator": "two_spiral"}, params={"learning_rate": 0.01})
            assert result["data"]["training_started"] is True
        sent = _json.loads(responses.calls[0].request.body)
        assert sent["dataset"] == {"source": "generator", "generator": "two_spiral"}
        assert sent["params"] == {"learning_rate": 0.01}


class TestMetricsHistoryNoCount:
    @responses.activate
    def test_get_metrics_history_without_count_omits_param(self):
        """Calling ``get_metrics_history()`` with no count takes the
        empty-params branch (client.py:253->255)."""
        responses.add(responses.GET, f"{API_URL}/metrics/history", json=_envelope([{"epoch": 1}]))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_metrics_history()
            assert result["data"] == [{"epoch": 1}]
        # No ``count`` query string was appended.
        assert "count" not in (responses.calls[0].request.url.split("?", 1)[1] if "?" in responses.calls[0].request.url else "")


class TestSnapshotEndpoints:
    @responses.activate
    def test_list_snapshots(self):
        responses.add(responses.GET, f"{API_URL}/snapshots", json=_envelope({"snapshots": [{"id": "s-1"}]}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.list_snapshots()
            assert result["data"]["snapshots"][0]["id"] == "s-1"

    @responses.activate
    def test_get_snapshot(self):
        responses.add(responses.GET, f"{API_URL}/snapshots/s-42", json=_envelope({"id": "s-42", "description": "checkpoint"}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_snapshot("s-42")
            assert result["data"]["id"] == "s-42"

    @responses.activate
    def test_save_snapshot(self):
        responses.add(responses.POST, f"{API_URL}/snapshots", json=_envelope({"id": "s-new", "saved": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.save_snapshot(description="my checkpoint")
            assert result["data"]["saved"] is True

    @responses.activate
    def test_load_snapshot(self):
        responses.add(responses.POST, f"{API_URL}/snapshots/s-7/restore", json=_envelope({"restored": True}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.load_snapshot("s-7")
            assert result["data"]["restored"] is True


class TestWorkerEndpoints:
    @responses.activate
    def test_list_workers(self):
        responses.add(responses.GET, f"{API_URL}/workers", json=_envelope({"workers": [{"id": "w-1", "status": "idle"}]}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.list_workers()
            assert result["data"]["workers"][0]["id"] == "w-1"

    @responses.activate
    def test_get_worker(self):
        responses.add(responses.GET, f"{API_URL}/workers/w-9", json=_envelope({"id": "w-9", "status": "busy"}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_worker("w-9")
            assert result["data"]["status"] == "busy"

    @responses.activate
    def test_get_worker_stats(self):
        responses.add(responses.GET, f"{API_URL}/workers/stats", json=_envelope({"total": 3, "idle": 2}))
        with JuniperCascorClient(BASE_URL) as client:
            result = client.get_worker_stats()
            assert result["data"]["total"] == 3


class TestRequestTransportErrors:
    """``_request`` maps ``requests`` transport failures onto typed errors."""

    @responses.activate
    def test_timeout_maps_to_timeout_error(self):
        """A ``requests.Timeout`` becomes ``JuniperCascorTimeoutError`` (client.py:369-370)."""
        responses.add(responses.GET, f"{API_URL}/health", body=requests.exceptions.ReadTimeout("read timed out"))
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorTimeoutError, match="timed out"):
                client.health_check()

    @responses.activate
    def test_generic_request_exception_maps_to_client_error(self):
        """A non-connection, non-timeout ``requests.RequestException`` becomes a
        base ``JuniperCascorClientError`` (client.py:371-372)."""
        responses.add(responses.GET, f"{API_URL}/health", body=requests.exceptions.RequestException("boom"))
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorClientError, match="failed"):
                client.health_check()

    @responses.activate
    def test_not_found_is_still_typed(self):
        """Sanity anchor: a real 404 status still maps to the not-found type
        (guards against the transport-error tests masking status mapping)."""
        responses.add(responses.GET, f"{API_URL}/network", json=_error_response("NOT_FOUND", "no network"), status=404)
        with JuniperCascorClient(BASE_URL) as client:
            with pytest.raises(JuniperCascorNotFoundError):
                client.get_network()
