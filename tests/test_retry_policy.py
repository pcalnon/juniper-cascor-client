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
        with JuniperCascorClient(base_url="http://localhost:8200", backoff_factor=2.5) as client:
            adapter = client.session.get_adapter("http://localhost:8200/")
            assert adapter.max_retries.backoff_factor == 2.5
            assert client.backoff_factor == 2.5

    def test_backoff_factor_defaults_to_constant(self) -> None:
        with JuniperCascorClient(base_url="http://localhost:8200") as client:
            adapter = client.session.get_adapter("http://localhost:8200/")
            assert adapter.max_retries.backoff_factor == constants.DEFAULT_BACKOFF_FACTOR

    def test_adapter_sets_both_pool_knobs(self) -> None:
        # APD-CCLIENT-009: pool_connections was omitted while both siblings set
        # it alongside pool_maxsize — silent sibling drift, not a decision.
        with JuniperCascorClient(base_url="http://localhost:8200") as client:
            for scheme_probe in ("http://localhost:8200/", "https://localhost:8200/"):
                adapter = client.session.get_adapter(scheme_probe)
                assert adapter._pool_connections == constants.DEFAULT_POOL_CONNECTIONS
                assert adapter._pool_maxsize == constants.DEFAULT_POOL_MAXSIZE

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

        source = pathlib.Path(inspect.getfile(JuniperCascorClient)).read_text(encoding="utf-8")
        adapter_calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "HTTPAdapter"]
        assert adapter_calls, "expected at least one HTTPAdapter(...) construction in client.py"
        for call in adapter_calls:
            kwargs = {kw.arg for kw in call.keywords}
            assert {"pool_connections", "pool_maxsize"} <= kwargs, f"HTTPAdapter call at line {call.lineno} must pass pool_connections AND pool_maxsize explicitly; got {sorted(kwargs)}"


class TestRetryBackoffJitter:
    """APD-ECO-002: retry schedules must be decorrelated across client instances.

    urllib3 applies jitter as an ABSOLUTE additive term --
    ``backoff_value += random.random() * backoff_jitter`` -- so without it every
    client that trips the same transient outage retries on an identical
    schedule, and a service that is already failing is hit by a synchronised
    herd. The parameter arrived in urllib3 2.0.0, which is the floor this
    package already pins.
    """

    def test_jitter_constant_is_positive(self) -> None:
        # Pin the VALUE, not merely the kwarg's presence: setting it to 0.0
        # leaves the call site looking correct while silently restoring the herd.
        assert constants.DEFAULT_BACKOFF_JITTER > 0

    def test_retry_adapter_carries_the_jitter(self) -> None:
        with JuniperCascorClient(base_url="http://localhost:8200") as client:
            adapter = client.session.get_adapter("http://localhost:8200/")
            assert adapter.max_retries.backoff_jitter == constants.DEFAULT_BACKOFF_JITTER

    def test_backoff_schedule_actually_varies(self) -> None:
        """The decisive arm -- a stored constant proves nothing if urllib3 ignores it."""
        with JuniperCascorClient(base_url="http://localhost:8200", retries=5) as client:
            retry = client.session.get_adapter("http://localhost:8200/").max_retries

        # get_backoff_time() returns 0 until at least two consecutive errors.
        for _ in range(2):
            retry = retry.increment(method="GET", url="/x", error=Exception("transient"))

        observed = {retry.get_backoff_time() for _ in range(200)}
        assert len(observed) > 1, "backoff is constant across 200 samples -- jitter is not being applied"

        # Bounds follow urllib3's documented formula for two consecutive errors:
        # backoff_factor * 2 ** (n - 1), then + uniform(0, backoff_jitter).
        base = constants.DEFAULT_BACKOFF_FACTOR * 2
        assert min(observed) >= base
        assert max(observed) <= base + constants.DEFAULT_BACKOFF_JITTER


class TestRetryAllowedMethods:
    """APD-CCLIENT-001: only idempotent methods may be replayed by the adapter.

    urllib3 replays inside the HTTP adapter, where the caller never learns it
    happened, and the stack has no idempotency key (APD-ECO-001). A transient
    502 on ``POST /v1/snapshots`` therefore wrote a duplicate snapshot row.
    """

    # RFC 9110 §9.2.2 — PUT and DELETE are idempotent and the safe methods are
    # too, but this client additionally excludes DELETE (its one call site
    # destroys a trained network) and PUT (never issued). See constants.py.
    NON_RETRYABLE = ("POST", "PATCH", "DELETE", "PUT")

    @pytest.mark.parametrize("method", NON_RETRYABLE)
    def test_mutating_method_is_not_in_allow_list(self, method: str) -> None:
        assert method not in constants.RETRY_ALLOWED_METHODS, f"{method} is auto-retried with no idempotency key -- a transient 5xx " f"silently repeats the mutation (APD-CCLIENT-001). Got {constants.RETRY_ALLOWED_METHODS}"

    @pytest.mark.parametrize("method", ["GET", "HEAD"])
    def test_safe_method_is_still_retried(self, method: str) -> None:
        # Negative control: the fix must not disable retry altogether. Dropping
        # GET would turn every transient restart back into a hard failure,
        # which is the outage XREPO-02 exists to prevent.
        assert method in constants.RETRY_ALLOWED_METHODS

    def test_adapter_allow_list_matches_constants(self) -> None:
        with JuniperCascorClient(base_url="http://localhost:8200", retries=3) as client:
            retry = client.session.get_adapter("http://localhost:8200/").max_retries
            assert set(retry.allowed_methods or ()) == set(constants.RETRY_ALLOWED_METHODS)

    @pytest.mark.parametrize("method", NON_RETRYABLE)
    def test_urllib3_refuses_to_replay_mutation(self, method: str) -> None:
        """The decisive arm: ask urllib3's own decision function, not the constant.

        The structural pins above pass if the list is right but never reaches
        urllib3 -- e.g. a future refactor that builds Retry() without
        ``allowed_methods``, which silently restores urllib3's default (and its
        default DOES include DELETE and PUT). Only ``is_retry`` proves the
        policy is the one actually in force on the mounted adapter.
        """
        with JuniperCascorClient(base_url="http://localhost:8200", retries=3) as client:
            retry = client.session.get_adapter("http://localhost:8200/").max_retries
        for code in constants.RETRYABLE_STATUS_CODES:
            assert not retry.is_retry(method, code), f"{method} would be replayed on HTTP {code}"

    @pytest.mark.parametrize("code", [429, 502, 503, 504])
    def test_urllib3_still_replays_get(self, code: int) -> None:
        with JuniperCascorClient(base_url="http://localhost:8200", retries=3) as client:
            retry = client.session.get_adapter("http://localhost:8200/").max_retries
        assert retry.is_retry("GET", code), f"GET must still retry on transient HTTP {code}"
