"""Tests for JuniperCascorClient.update_params() method."""

import pytest
import responses as responses_lib

from juniper_cascor_client import JuniperCascorClient

BASE_URL = "http://localhost:8200"


@pytest.fixture
def client():
    with JuniperCascorClient(BASE_URL) as c:
        yield c


class TestUpdateParams:
    @responses_lib.activate
    def test_update_params_sends_patch_request(self, client):
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE_URL}/v1/training/params",
            json={"status": "ok", "data": {"learning_rate": 0.005}},
            status=200,
        )
        result = client.update_params({"learning_rate": 0.005})
        assert result["data"] == {"learning_rate": 0.005}
        assert len(responses_lib.calls) == 1
        assert responses_lib.calls[0].request.method == "PATCH"

    @responses_lib.activate
    def test_update_params_sends_correct_path(self, client):
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE_URL}/v1/training/params",
            json={"status": "ok", "data": {}},
            status=200,
        )
        client.update_params({"max_hidden_units": 15})
        assert "/v1/training/params" in responses_lib.calls[0].request.url

    @responses_lib.activate
    def test_update_params_sends_json_body(self, client):
        import json

        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE_URL}/v1/training/params",
            json={"status": "ok", "data": {}},
            status=200,
        )
        params = {"learning_rate": 0.01, "correlation_threshold": 0.2}
        client.update_params(params)
        body = json.loads(responses_lib.calls[0].request.body)
        assert body == params

    @responses_lib.activate
    def test_update_params_handles_404(self, client):
        from juniper_cascor_client.exceptions import JuniperCascorNotFoundError

        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE_URL}/v1/training/params",
            json={"detail": "No network loaded"},
            status=404,
        )
        with pytest.raises(JuniperCascorNotFoundError):
            client.update_params({"learning_rate": 0.01})
