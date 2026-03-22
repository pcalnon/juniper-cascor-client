"""Tests for FakeCascorClient.update_params() method."""

import pytest

from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorNotFoundError
from juniper_cascor_client.testing import FakeCascorClient


class TestFakeClientUpdateParams:
    def test_update_params_requires_network(self):
        with FakeCascorClient(scenario="idle") as client:
            with pytest.raises(JuniperCascorNotFoundError):
                client.update_params({"learning_rate": 0.01})

    def test_update_params_updates_network_config(self):
        with FakeCascorClient(scenario="two_spiral_training") as client:
            result = client.update_params({"learning_rate": 0.001})
            assert result["status"] == "ok"
            # learning_rate should be updated in the returned config
            assert result["data"]["learning_rate"] == 0.001

    def test_update_params_unknown_keys_ignored(self):
        with FakeCascorClient(scenario="two_spiral_training") as client:
            # Should not raise even with unknown params
            result = client.update_params({"nn_spiral_stuff": "ignored"})
            assert result["status"] == "ok"

    def test_update_params_multiple_params(self):
        with FakeCascorClient(scenario="two_spiral_training") as client:
            result = client.update_params({
                "learning_rate": 0.002,
                "correlation_threshold": 0.15,
                "candidate_pool_size": 12,
            })
            assert result["status"] == "ok"
            assert result["data"]["learning_rate"] == 0.002
            assert result["data"]["correlation_threshold"] == 0.15
            assert result["data"]["candidate_pool_size"] == 12

    def test_update_params_raises_after_close(self):
        client = FakeCascorClient(scenario="two_spiral_training")
        client.close()
        with pytest.raises(JuniperCascorClientError):
            client.update_params({"learning_rate": 0.01})

    def test_update_params_paused_state_works(self):
        with FakeCascorClient(scenario="two_spiral_training") as client:
            client.set_state("paused")
            result = client.update_params({"learning_rate": 0.003})
            assert result["status"] == "ok"
