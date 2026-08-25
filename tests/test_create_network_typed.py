"""Typed ``create_network`` surface (defect-register ``APD-CCLIENT-011``).

``create_network(**kwargs: Any)`` documented 11 parameters and typed none of
them — and its blind pass-through fed the server's silent-ignore behavior: a
typo'd hyperparameter reached a pydantic model that drops unknown keys
without a trace (the retired ``epochs_max`` did exactly this). The method now
names the server's actual ``NetworkCreateRequest`` fields as keyword-only
``Optional`` parameters (every field has a server-side default — the old
"(required)" docstring claims were wrong), sends only what the caller set,
and keeps ``**extra`` as an explicit forward-compat channel that logs a
WARNING naming its keys.
"""

import inspect
import json
import logging

import pytest
import responses

from juniper_cascor_client import JuniperCascorClient
from juniper_cascor_client.testing import FakeCascorClient

BASE_URL = "http://localhost:8200"
API_URL = f"{BASE_URL}/v1"

EXPECTED_NAMED = [
    "input_size",
    "output_size",
    "learning_rate",
    "candidate_learning_rate",
    "max_hidden_units",
    "candidate_pool_size",
    "correlation_threshold",
    "patience",
    "candidate_epochs",
    "output_epochs",
    "max_iterations",
    "init_output_weights",
    "optimizer_type",
    "activation_function_name",
]


def _envelope(data):
    return {"status": "success", "data": data, "meta": {"timestamp": 1234567890.0, "version": "0.4.0"}}


@responses.activate
def test_typed_kwargs_reach_body_and_none_is_omitted():
    responses.add(responses.POST, f"{API_URL}/network", json=_envelope({"created": True}))
    with JuniperCascorClient(BASE_URL) as client:
        client.create_network(input_size=2, output_size=2, learning_rate=0.01, optimizer_type="AdamW")
    sent = json.loads(responses.calls[0].request.body)
    assert sent == {"input_size": 2, "output_size": 2, "learning_rate": 0.01, "optimizer_type": "AdamW"}


@responses.activate
def test_zero_arg_call_posts_empty_body():
    # The server defaults every NetworkCreateRequest field, and canopy's
    # adapter calls create_network() bare for a default network — the typed
    # surface must keep that legal and send an empty body.
    responses.add(responses.POST, f"{API_URL}/network", json=_envelope({"created": True}))
    with JuniperCascorClient(BASE_URL) as client:
        client.create_network()
    assert json.loads(responses.calls[0].request.body) == {}


@responses.activate
def test_extra_keys_forward_with_warning(caplog):
    # **extra is the forward-compat channel for fields newer than this client
    # — forwarded verbatim, but LOUDLY: the server silently ignores unknown
    # keys, so without the warning a typo vanishes without a trace.
    responses.add(responses.POST, f"{API_URL}/network", json=_envelope({"created": True}))
    caplog.set_level(logging.WARNING, logger="juniper_cascor_client.client")
    with JuniperCascorClient(BASE_URL) as client:
        client.create_network(input_size=2, some_future_field=7)
    sent = json.loads(responses.calls[0].request.body)
    assert sent == {"input_size": 2, "some_future_field": 7}
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("some_future_field" in r.getMessage() for r in warning_records), f"expected a WARNING naming the extra key; got: {[r.getMessage() for r in caplog.records]}"


def test_named_params_are_keyword_only_and_match_server_fields():
    kinds = {n: p.kind for n, p in inspect.signature(JuniperCascorClient.create_network).parameters.items() if n != "self"}
    assert [n for n, k in kinds.items() if k is inspect.Parameter.KEYWORD_ONLY] == EXPECTED_NAMED
    assert [n for n, k in kinds.items() if k is inspect.Parameter.VAR_KEYWORD] == ["extra"]
    assert not [n for n, k in kinds.items() if k is inspect.Parameter.POSITIONAL_OR_KEYWORD]


def test_fake_signature_matches_real():
    real = inspect.signature(JuniperCascorClient.create_network)
    fake = inspect.signature(FakeCascorClient.create_network)
    assert [(n, p.kind, p.default) for n, p in real.parameters.items()] == [(n, p.kind, p.default) for n, p in fake.parameters.items()]


def test_fake_accepts_typed_params_and_extra():
    with FakeCascorClient() as fake:
        result = fake.create_network(input_size=2, output_size=2, learning_rate=0.01, candidate_pool_size=4, some_future_field=1)
    assert result["data"]["config"]["input_size"] == 2
    assert result["data"]["config"]["candidate_pool_size"] == 4
