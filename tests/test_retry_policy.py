"""Regression tests for the HTTP retry policy.

Guards XREPO-02 / CC-02: `RETRYABLE_STATUS_CODES` must include 503 and
429 so transient service restarts / rate-limited responses are retried
instead of bubbling up as immediate failures.
"""

from __future__ import annotations

import pytest

from juniper_cascor_client import constants
from juniper_cascor_client.client import JuniperCascorClient


class TestRetryableStatusCodes:
    """The retry-forcelist must cover every canonical transient status."""

    @pytest.mark.parametrize("code", [429, 502, 503, 504])
    def test_canonical_transient_code_is_retryable(self, code: int) -> None:
        assert code in constants.RETRYABLE_STATUS_CODES, f"HTTP {code} is a canonical transient error and MUST be in " f"RETRYABLE_STATUS_CODES (got {constants.RETRYABLE_STATUS_CODES})"

    @pytest.mark.parametrize("code", [200, 400, 401, 403, 404, 409, 422, 500, 501])
    def test_non_transient_code_is_not_retryable(self, code: int) -> None:
        assert code not in constants.RETRYABLE_STATUS_CODES, f"HTTP {code} is not transient and must NOT auto-retry " f"(got {constants.RETRYABLE_STATUS_CODES})"


class TestClientRetryConfiguration:
    """The retry strategy attached to the session must honor the constants."""

    def test_retry_forcelist_matches_constants(self) -> None:
        client = JuniperCascorClient(base_url="http://localhost:8200", retries=3)
        try:
            adapter = client.session.get_adapter("http://localhost:8200/")
            forcelist = set(adapter.max_retries.status_forcelist or [])
            assert forcelist == set(constants.RETRYABLE_STATUS_CODES)
            assert 503 in forcelist
            assert 429 in forcelist
        finally:
            client.close()

    def test_backoff_factor_is_constructor_configurable(self) -> None:
        # APD-CCLIENT-013: the value was hardcoded to DEFAULT_BACKOFF_FACTOR at
        # session build; both siblings expose it as a constructor parameter.
        # Asserted where it takes effect — the mounted adapter's Retry.
        client = JuniperCascorClient(base_url="http://localhost:8200", backoff_factor=2.5)
        try:
            adapter = client.session.get_adapter("http://localhost:8200/")
            assert adapter.max_retries.backoff_factor == 2.5
            assert client.backoff_factor == 2.5
        finally:
            client.close()

    def test_backoff_factor_defaults_to_constant(self) -> None:
        client = JuniperCascorClient(base_url="http://localhost:8200")
        try:
            adapter = client.session.get_adapter("http://localhost:8200/")
            assert adapter.max_retries.backoff_factor == constants.DEFAULT_BACKOFF_FACTOR
        finally:
            client.close()

    def test_adapter_sets_both_pool_knobs(self) -> None:
        # APD-CCLIENT-009: pool_connections was omitted while both siblings set
        # it alongside pool_maxsize — silent sibling drift, not a decision.
        client = JuniperCascorClient(base_url="http://localhost:8200")
        try:
            for scheme_probe in ("http://localhost:8200/", "https://localhost:8200/"):
                adapter = client.session.get_adapter(scheme_probe)
                assert adapter._pool_connections == constants.DEFAULT_POOL_CONNECTIONS
                assert adapter._pool_maxsize == constants.DEFAULT_POOL_MAXSIZE
        finally:
            client.close()

    def test_adapter_call_passes_both_pool_knobs_explicitly(self) -> None:
        # The runtime arm above is blind to the original omission: requests'
        # own pool_connections default is also 10, so dropping the explicit
        # kwarg changes nothing observable today — it only re-introduces the
        # silent dependence on urllib3's default that APD-CCLIENT-009 filed.
        # Pin the call site itself: every HTTPAdapter(...) in client.py must
        # pass both knobs by keyword.
        import ast
        import inspect
        import pathlib

        import juniper_cascor_client.client as client_module

        source = pathlib.Path(inspect.getfile(client_module)).read_text(encoding="utf-8")
        adapter_calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "HTTPAdapter"]
        assert adapter_calls, "expected at least one HTTPAdapter(...) construction in client.py"
        for call in adapter_calls:
            kwargs = {kw.arg for kw in call.keywords}
            assert {"pool_connections", "pool_maxsize"} <= kwargs, f"HTTPAdapter call at line {call.lineno} must pass pool_connections AND pool_maxsize explicitly; got {sorted(kwargs)}"
