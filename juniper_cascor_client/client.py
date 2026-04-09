"""REST API client for JuniperCascor neural network training service.

Provides network lifecycle management, training control, metrics retrieval,
and visualization data access for JuniperCascor consumers.
"""

import os
import time
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from juniper_cascor_client.constants import (
    API_KEY_ENV_VAR,
    API_KEY_HEADER_NAME,
    API_VERSION_PATH,
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_BASE_URL,
    DEFAULT_DECISION_BOUNDARY_RESOLUTION,
    DEFAULT_POOL_MAXSIZE,
    DEFAULT_READY_POLL_INTERVAL,
    DEFAULT_READY_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    ENDPOINT_DATASET,
    ENDPOINT_DATASET_DATA,
    ENDPOINT_DECISION_BOUNDARY,
    ENDPOINT_HEALTH,
    ENDPOINT_HEALTH_LIVE,
    ENDPOINT_HEALTH_READY,
    ENDPOINT_METRICS,
    ENDPOINT_METRICS_HISTORY,
    ENDPOINT_NETWORK,
    ENDPOINT_NETWORK_STATS,
    ENDPOINT_NETWORK_TOPOLOGY,
    ENDPOINT_SNAPSHOT_BY_ID_TEMPLATE,
    ENDPOINT_SNAPSHOT_RESTORE_TEMPLATE,
    ENDPOINT_SNAPSHOTS,
    ENDPOINT_TRAINING_PARAMS,
    ENDPOINT_TRAINING_PAUSE,
    ENDPOINT_TRAINING_RESET,
    ENDPOINT_TRAINING_RESUME,
    ENDPOINT_TRAINING_START,
    ENDPOINT_TRAINING_STATUS,
    ENDPOINT_TRAINING_STOP,
    ENDPOINT_WORKER_BY_ID_TEMPLATE,
    ENDPOINT_WORKERS,
    ENDPOINT_WORKERS_STATS,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_503_SERVICE_UNAVAILABLE,
    RETRY_ALLOWED_METHODS,
    RETRYABLE_STATUS_CODES,
)
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorServiceUnavailableError, JuniperCascorTimeoutError, JuniperCascorValidationError


class JuniperCascorClient:
    """Client for interacting with the JuniperCascor REST API.

    Provides methods for network lifecycle management, training control,
    metrics retrieval, and visualization data access.

    Example:
        >>> with JuniperCascorClient("http://localhost:8200") as client:
        ...     client.create_network(input_size=2, output_size=2, learning_rate=0.01)
        ...     client.start_training(dataset={"source": "inline", ...})
        ...     status = client.get_training_status()
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        retries: int = DEFAULT_RETRY_COUNT,
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}{API_VERSION_PATH}"
        self.timeout = timeout
        self.api_key = api_key or os.environ.get(API_KEY_ENV_VAR)

        self.session = requests.Session()

        retry_strategy = Retry(
            total=retries,
            backoff_factor=DEFAULT_BACKOFF_FACTOR,
            status_forcelist=RETRYABLE_STATUS_CODES,
            allowed_methods=RETRY_ALLOWED_METHODS,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=DEFAULT_POOL_MAXSIZE)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        if self.api_key:
            self.session.headers[API_KEY_HEADER_NAME] = self.api_key

    # ─── Health ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        return self._get(ENDPOINT_HEALTH)

    def is_alive(self) -> bool:
        """Check if service is alive (liveness probe)."""
        try:
            self._get(ENDPOINT_HEALTH_LIVE)
            return True
        except (JuniperCascorClientError, ConnectionError):
            return False

    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        try:
            result = self._get(ENDPOINT_HEALTH_READY)
            return result.get("details", {}).get("network_loaded", False)
        except JuniperCascorClientError:
            return False

    def wait_for_ready(self, timeout: float = DEFAULT_READY_TIMEOUT, poll_interval: float = DEFAULT_READY_POLL_INTERVAL) -> bool:
        """Wait until service is ready or timeout expires."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.is_ready():
                    return True
            except JuniperCascorClientError:
                pass
            time.sleep(poll_interval)
        return False

    # ─── Network ─────────────────────────────────────────────────────────

    def create_network(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new CasCor network.

        Args:
            input_size: Number of input features (required).
            output_size: Number of output classes (required).
            learning_rate: Output layer learning rate (required).
            candidate_learning_rate: Candidate training learning rate.
            max_hidden_units: Maximum hidden units to add.
            candidate_pool_size: Number of candidate units per round.
            correlation_threshold: Minimum correlation to accept candidate.
            patience: Epochs without improvement before stopping.
            candidate_epochs: Max epochs per candidate training.
            output_epochs: Max epochs per output training.
            epochs_max: Global max epochs.
        """
        return self._post(ENDPOINT_NETWORK, json=kwargs)

    def get_network(self) -> Dict[str, Any]:
        """Get current network state and configuration."""
        return self._get(ENDPOINT_NETWORK)

    def delete_network(self) -> Dict[str, Any]:
        """Destroy the current network."""
        return self._delete(ENDPOINT_NETWORK)

    def get_topology(self) -> Dict[str, Any]:
        """Get network topology for visualization."""
        return self._get(ENDPOINT_NETWORK_TOPOLOGY)

    def get_statistics(self) -> Dict[str, Any]:
        """Get network weight statistics."""
        return self._get(ENDPOINT_NETWORK_STATS)

    # ─── Training Control ────────────────────────────────────────────────

    def start_training(
        self,
        epochs: Optional[int] = None,
        dataset: Optional[Dict[str, Any]] = None,
        inline_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Start training (async — returns immediately).

        Args:
            epochs: Max epochs override.
            dataset: Dataset source config (source, url, generator, params).
            inline_data: Inline training data (train_x, train_y, val_x, val_y).
            params: Training parameter overrides.
        """
        body: Dict[str, Any] = {}
        if epochs is not None:
            body["epochs"] = epochs
        if dataset is not None:
            body["dataset"] = dataset
        if inline_data is not None:
            body["inline_data"] = inline_data
        if params is not None:
            body["params"] = params
        return self._post(ENDPOINT_TRAINING_START, json=body)

    def stop_training(self) -> Dict[str, Any]:
        """Request graceful training stop."""
        return self._post(ENDPOINT_TRAINING_STOP)

    def pause_training(self) -> Dict[str, Any]:
        """Pause training after current epoch."""
        return self._post(ENDPOINT_TRAINING_PAUSE)

    def resume_training(self) -> Dict[str, Any]:
        """Resume paused training."""
        return self._post(ENDPOINT_TRAINING_RESUME)

    def reset_training(self) -> Dict[str, Any]:
        """Reset network and training state."""
        return self._post(ENDPOINT_TRAINING_RESET)

    def get_training_status(self) -> Dict[str, Any]:
        """Get current training status."""
        return self._get(ENDPOINT_TRAINING_STATUS)

    def get_training_params(self) -> Dict[str, Any]:
        """Get current training parameters."""
        return self._get(ENDPOINT_TRAINING_PARAMS)

    def update_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update runtime-modifiable training parameters.

        Updates parameters on the running network without requiring a restart.
        Parameters that are safe to update at runtime:
        - learning_rate, candidate_learning_rate, correlation_threshold,
          candidate_pool_size, max_hidden_units, epochs_max, patience.

        Args:
            params: Dict of parameter names and new values (only non-None values).

        Returns:
            Updated training parameters dict.
        """
        return self._patch(ENDPOINT_TRAINING_PARAMS, json=params)

    # ─── Metrics ─────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        return self._get(ENDPOINT_METRICS)

    def get_metrics_history(self, count: Optional[int] = None) -> Dict[str, Any]:
        """Get training metrics history.

        Args:
            count: Number of recent entries to return.
        """
        params = {}
        if count is not None:
            params["count"] = count
        return self._get(ENDPOINT_METRICS_HISTORY, params=params)

    # ─── Data ────────────────────────────────────────────────────────────

    def get_dataset(self) -> Dict[str, Any]:
        """Get current dataset metadata."""
        return self._get(ENDPOINT_DATASET)

    def get_dataset_data(self) -> Dict[str, Any]:
        """Get dataset arrays (train_x, train_y, optionally val_x, val_y) for visualization."""
        return self._get(ENDPOINT_DATASET_DATA)

    def get_decision_boundary(self, resolution: int = DEFAULT_DECISION_BOUNDARY_RESOLUTION) -> Dict[str, Any]:
        """Get decision boundary grid data for 2D visualization.

        Args:
            resolution: Grid resolution (5-200, default 50).
        """
        return self._get(ENDPOINT_DECISION_BOUNDARY, params={"resolution": resolution})

    # ─── Snapshots ───────────────────────────────────────────────────────

    def list_snapshots(self) -> Dict[str, Any]:
        """List available network snapshots."""
        return self._get(ENDPOINT_SNAPSHOTS)

    def get_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Get metadata for a specific snapshot.

        Args:
            snapshot_id: Snapshot identifier.
        """
        return self._get(ENDPOINT_SNAPSHOT_BY_ID_TEMPLATE.format(snapshot_id=snapshot_id))

    def save_snapshot(self, description: str = "") -> Dict[str, Any]:
        """Save current network state as a snapshot.

        Args:
            description: Optional description for the snapshot.
        """
        return self._post(ENDPOINT_SNAPSHOTS, json={"description": description})

    def load_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Restore network state from a snapshot.

        Args:
            snapshot_id: Snapshot identifier to restore.
        """
        return self._post(ENDPOINT_SNAPSHOT_RESTORE_TEMPLATE.format(snapshot_id=snapshot_id))

    # ─── Workers ─────────────────────────────────────────────────────────

    def list_workers(self) -> Dict[str, Any]:
        """List all registered remote workers with status."""
        return self._get(ENDPOINT_WORKERS)

    def get_worker(self, worker_id: str) -> Dict[str, Any]:
        """Get details for a specific worker.

        Args:
            worker_id: Worker identifier.
        """
        return self._get(ENDPOINT_WORKER_BY_ID_TEMPLATE.format(worker_id=worker_id))

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get aggregate worker statistics."""
        return self._get(ENDPOINT_WORKERS_STATS)

    # ─── Context Manager ─────────────────────────────────────────────────

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self) -> "JuniperCascorClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ─── Internal ────────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("POST", path, json=json)

    def _delete(self, path: str) -> Dict[str, Any]:
        return self._request("DELETE", path)

    def _patch(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("PATCH", path, json=json)

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.api_url}{path}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json,
                params=params,
                timeout=self.timeout,
            )
            self._handle_response(response)
            return response.json()
        except requests.ConnectionError as e:
            raise JuniperCascorConnectionError(f"Failed to connect to {url}: {e}") from e
        except requests.Timeout as e:
            raise JuniperCascorTimeoutError(f"Request to {url} timed out after {self.timeout}s") from e
        except requests.RequestException as e:
            raise JuniperCascorClientError(f"Request to {url} failed: {e}") from e

    def _handle_response(self, response: requests.Response) -> None:
        if response.ok:
            return

        try:
            body = response.json()
            if isinstance(body.get("error"), dict):
                error_msg = body.get("error", {}).get("message", response.text)
            else:
                error_msg = body.get("detail", response.text)
        except (ValueError, KeyError):
            error_msg = response.text

        status = response.status_code
        if status in (HTTP_400_BAD_REQUEST, HTTP_422_UNPROCESSABLE_ENTITY):
            raise JuniperCascorValidationError(error_msg)
        elif status == HTTP_404_NOT_FOUND:
            raise JuniperCascorNotFoundError(error_msg)
        elif status == HTTP_409_CONFLICT:
            raise JuniperCascorConflictError(error_msg)
        elif status == HTTP_503_SERVICE_UNAVAILABLE:
            raise JuniperCascorServiceUnavailableError(error_msg)
        else:
            raise JuniperCascorClientError(f"HTTP {status}: {error_msg}")
