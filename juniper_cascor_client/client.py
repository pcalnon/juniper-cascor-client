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
        base_url: str = "http://localhost:8200",
        timeout: int = 30,
        retries: int = 3,
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/v1"
        self.timeout = timeout
        self.api_key = api_key or os.environ.get("JUNIPER_CASCOR_API_KEY")

        self.session = requests.Session()

        retry_strategy = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=[502, 504],
            allowed_methods=["GET", "POST", "DELETE", "PUT", "PATCH"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        if self.api_key:
            self.session.headers["X-API-Key"] = self.api_key

    # ─── Health ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        return self._get("/health")

    def is_alive(self) -> bool:
        """Check if service is alive (liveness probe)."""
        try:
            self._get("/health/live")
            return True
        except (JuniperCascorClientError, ConnectionError):
            return False

    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        try:
            result = self._get("/health/ready")
            return result.get("details", {}).get("network_loaded", False)
        except JuniperCascorClientError:
            return False

    def wait_for_ready(self, timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
        """Wait until service is ready or timeout expires."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.is_alive():
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
        return self._post("/network", json=kwargs)

    def get_network(self) -> Dict[str, Any]:
        """Get current network state and configuration."""
        return self._get("/network")

    def delete_network(self) -> Dict[str, Any]:
        """Destroy the current network."""
        return self._delete("/network")

    def get_topology(self) -> Dict[str, Any]:
        """Get network topology for visualization."""
        return self._get("/network/topology")

    def get_statistics(self) -> Dict[str, Any]:
        """Get network weight statistics."""
        return self._get("/network/stats")

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
        return self._post("/training/start", json=body)

    def stop_training(self) -> Dict[str, Any]:
        """Request graceful training stop."""
        return self._post("/training/stop")

    def pause_training(self) -> Dict[str, Any]:
        """Pause training after current epoch."""
        return self._post("/training/pause")

    def resume_training(self) -> Dict[str, Any]:
        """Resume paused training."""
        return self._post("/training/resume")

    def reset_training(self) -> Dict[str, Any]:
        """Reset network and training state."""
        return self._post("/training/reset")

    def get_training_status(self) -> Dict[str, Any]:
        """Get current training status."""
        return self._get("/training/status")

    def get_training_params(self) -> Dict[str, Any]:
        """Get current training parameters."""
        return self._get("/training/params")

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
        return self._patch("/training/params", json=params)

    # ─── Metrics ─────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        return self._get("/metrics")

    def get_metrics_history(self, count: Optional[int] = None) -> Dict[str, Any]:
        """Get training metrics history.

        Args:
            count: Number of recent entries to return.
        """
        params = {}
        if count is not None:
            params["count"] = count
        return self._get("/metrics/history", params=params)

    # ─── Data ────────────────────────────────────────────────────────────

    def get_dataset(self) -> Dict[str, Any]:
        """Get current dataset metadata."""
        return self._get("/dataset")

    def get_dataset_data(self) -> Dict[str, Any]:
        """Get dataset arrays (train_x, train_y, optionally val_x, val_y) for visualization."""
        return self._get("/dataset/data")

    def get_decision_boundary(self, resolution: int = 50) -> Dict[str, Any]:
        """Get decision boundary grid data for 2D visualization.

        Args:
            resolution: Grid resolution (5-200, default 50).
        """
        return self._get("/decision-boundary", params={"resolution": resolution})

    # ─── Snapshots ───────────────────────────────────────────────────────

    def list_snapshots(self) -> Dict[str, Any]:
        """List available network snapshots."""
        return self._get("/snapshots")

    def get_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Get metadata for a specific snapshot.

        Args:
            snapshot_id: Snapshot identifier.
        """
        return self._get(f"/snapshots/{snapshot_id}")

    def save_snapshot(self, description: str = "") -> Dict[str, Any]:
        """Save current network state as a snapshot.

        Args:
            description: Optional description for the snapshot.
        """
        return self._post("/snapshots", json={"description": description})

    def load_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Restore network state from a snapshot.

        Args:
            snapshot_id: Snapshot identifier to restore.
        """
        return self._post(f"/snapshots/{snapshot_id}/restore")

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
        if status == 400 or status == 422:
            raise JuniperCascorValidationError(error_msg)
        elif status == 404:
            raise JuniperCascorNotFoundError(error_msg)
        elif status == 409:
            raise JuniperCascorConflictError(error_msg)
        elif status == 503:
            raise JuniperCascorServiceUnavailableError(error_msg)
        else:
            raise JuniperCascorClientError(f"HTTP {status}: {error_msg}")
