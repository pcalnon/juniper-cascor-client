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
