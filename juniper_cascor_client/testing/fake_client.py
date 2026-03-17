"""Fake REST client for JuniperCascor — fully in-memory, no network calls.

Implements every public method of JuniperCascorClient with scenario-driven
state management, configurable presets, and test helper utilities.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: FakeCascorClient
Author: Paul Calnon
Version: 0.1.0
License: MIT License
"""

import copy
import random
import threading
import time
from typing import Any, Dict, List, Optional

from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorServiceUnavailableError, JuniperCascorValidationError
from juniper_cascor_client.testing.scenarios import SCENARIO_DEFAULTS, build_cascor_topology, build_network_config, generate_decision_boundary, generate_metrics_snapshot, generate_weight_statistics, get_scenario_data

# Valid training states and allowed transitions
VALID_STATES = {"idle", "training", "paused", "complete"}

STATE_TRANSITIONS = {
    "idle": {"training"},
    "training": {"paused", "complete", "idle"},
    "paused": {"training", "idle"},
    "complete": {"idle"},
}


class FakeCascorClient:
    """In-memory fake of JuniperCascorClient for testing.

    Provides identical method signatures to JuniperCascorClient but operates
    entirely in-memory. Configured via scenario presets that determine initial
    state, network configuration, dataset, and metric generation behavior.

    Scenario presets:
        - "idle": No network loaded, ready for creation.
        - "two_spiral_training": Active training with realistic metric curves.
        - "xor_converged": Fully trained XOR network, static metrics.
        - "empty": Minimal responses for negative testing.
        - "error_prone": Raises exceptions on ~10% of calls.

    Test helpers:
        - advance_epoch(n): Advance the epoch counter and update metrics.
        - set_state(state): Force a specific training state.

    Example:
        >>> from juniper_cascor_client.testing import FakeCascorClient
        >>> with FakeCascorClient(scenario="two_spiral_training") as client:
        ...     status = client.get_training_status()
        ...     client.advance_epoch(10)
        ...     metrics = client.get_metrics()
    """

    def __init__(
        self,
        scenario: str = "idle",
        base_url: str = "http://fake-cascor:8200",
        api_key: Optional[str] = None,
    ) -> None:
        self._lock = threading.Lock()
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/v1"
        self.api_key = api_key
        self._closed = False

        # Load scenario data
        scenario_data = get_scenario_data(scenario)
        self._scenario = scenario
        self._state: str = scenario_data["initial_state"]
        self._epoch: int = scenario_data["initial_epoch"]
        self._network_config: Optional[Dict[str, Any]] = copy.deepcopy(scenario_data["network_config"]) if scenario_data["network_config"] else None
        self._dataset: Optional[Dict[str, Any]] = copy.deepcopy(scenario_data["dataset"]) if scenario_data["dataset"] else None
        self._topology: Optional[Dict[str, Any]] = copy.deepcopy(scenario_data["topology"]) if scenario_data["topology"] else None
        self._metrics_history: List[Dict[str, Any]] = []
        self._training_params: Optional[Dict[str, Any]] = None
        self._training_start_time: Optional[float] = None
        self._network_loaded: bool = self._network_config is not None

        # Populate initial metrics history for scenarios that start mid-training
        if self._epoch > 0 and self._network_config is not None:
            for e in range(self._epoch):
                self._metrics_history.append(generate_metrics_snapshot(e, self._scenario))

        # Set training params for active scenarios
        if self._state in ("training", "paused"):
            self._training_params = {
                "epochs": self._network_config.get("epochs_max", 1000) if self._network_config else 1000,
                "dataset": self._dataset,
                "params": copy.deepcopy(self._network_config) if self._network_config else {},
            }
            self._training_start_time = time.time() - (self._epoch * 0.5)

    # ─── Error Injection ─────────────────────────────────────────────────

    def _maybe_raise_error(self, method_name: str) -> None:
        """Conditionally raise an exception for the error_prone scenario.

        Uses random.random() < 0.1 to decide. Cycles through different
        exception types based on a hash of the method name for variety.
        """
        if self._scenario != "error_prone":
            return
        if random.random() >= 0.1:
            return

        # Cycle through exception types for variety
        error_types = [
            JuniperCascorConnectionError,
            JuniperCascorClientError,
            JuniperCascorServiceUnavailableError,
        ]
        idx = hash(method_name + str(random.randint(0, 99))) % len(error_types)
        exc_class = error_types[idx]
        raise exc_class(f"Simulated error in {method_name} (error_prone scenario)")

    def _check_closed(self) -> None:
        """Raise if the client has been closed."""
        if self._closed:
            raise JuniperCascorClientError("Client is closed. Cannot make requests.")

    # ─── Health ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("health_check")
            return {
                "status": "ok",
                "data": {
                    "service": "juniper-cascor",
                    "version": "0.1.0",
                    "uptime_seconds": 3600.0,
                    "network_loaded": self._network_loaded,
                    "training_state": self._state,
                },
            }

    def is_alive(self) -> bool:
        """Check if service is alive (liveness probe)."""
        with self._lock:
            if self._closed:
                return False
            try:
                self._maybe_raise_error("is_alive")
            except JuniperCascorClientError:
                return False
            return True

    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        with self._lock:
            if self._closed:
                return False
            try:
                self._maybe_raise_error("is_ready")
            except JuniperCascorClientError:
                return False
            return self._network_loaded

    def wait_for_ready(self, timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
        """Wait until service is ready or timeout expires.

        For the fake client, this returns immediately based on current state
        since there is no actual startup delay.
        """
        self._check_closed()
        self._maybe_raise_error("wait_for_ready")
        # Fake is always "alive" if not closed
        return True

    # ─── Network ─────────────────────────────────────────────────────────

    def create_network(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a new CasCor network.

        Args:
            input_size: Number of input features (required).
            output_size: Number of output classes (required).
            learning_rate: Output layer learning rate (required).
            **kwargs: Additional network configuration parameters.

        Raises:
            JuniperCascorValidationError: If required parameters are missing.
            JuniperCascorConflictError: If a network already exists.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("create_network")

            if self._network_loaded:
                raise JuniperCascorConflictError("Network already exists. Delete it first.")

            # Validate required fields
            required = ["input_size", "output_size", "learning_rate"]
            missing = [f for f in required if f not in kwargs]
            if missing and self._scenario != "empty":
                raise JuniperCascorValidationError(f"Missing required fields: {', '.join(missing)}")

            input_size = kwargs.get("input_size", 2)
            output_size = kwargs.get("output_size", 1)
            learning_rate = kwargs.get("learning_rate", 0.01)

            self._network_config = build_network_config(
                input_size=input_size,
                output_size=output_size,
                learning_rate=learning_rate,
                **{k: v for k, v in kwargs.items() if k not in ("input_size", "output_size", "learning_rate")},
            )
            self._topology = build_cascor_topology(
                input_size=input_size,
                output_size=output_size,
                hidden_units=0,
            )
            self._network_loaded = True
            self._state = "idle"
            self._epoch = 0
            self._metrics_history = []

            return {
                "status": "ok",
                "message": "Network created successfully.",
                "data": {
                    "config": copy.deepcopy(self._network_config),
                },
            }

    def get_network(self) -> Dict[str, Any]:
        """Get current network state and configuration."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_network")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            return {
                "status": "ok",
                "data": {
                    "config": copy.deepcopy(self._network_config),
                    "state": self._state,
                    "epoch": self._epoch,
                    "network_loaded": True,
                },
            }

    def delete_network(self) -> Dict[str, Any]:
        """Destroy the current network."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("delete_network")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            if self._state == "training":
                raise JuniperCascorConflictError("Cannot delete network while training is active. Stop training first.")

            self._network_config = None
            self._topology = None
            self._dataset = None
            self._network_loaded = False
            self._state = "idle"
            self._epoch = 0
            self._metrics_history = []
            self._training_params = None
            self._training_start_time = None

            return {
                "status": "ok",
                "message": "Network deleted.",
            }

    def get_topology(self) -> Dict[str, Any]:
        """Get network topology for visualization."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_topology")

            if not self._network_loaded or self._topology is None:
                raise JuniperCascorNotFoundError("No network loaded.")

            return {
                "status": "ok",
                "data": copy.deepcopy(self._topology),
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get network weight statistics."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_statistics")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            hidden_units = self._topology.get("hidden_units", 0) if self._topology else 0
            stats = generate_weight_statistics(hidden_units)

            return {
                "status": "ok",
                "data": stats,
            }

    # ─── Training Control ────────────────────────────────────────────────

    def start_training(
        self,
        epochs: Optional[int] = None,
        dataset: Optional[Dict[str, Any]] = None,
        inline_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Start training (returns immediately, training is async).

        Args:
            epochs: Max epochs override.
            dataset: Dataset source config.
            inline_data: Inline training data.
            params: Training parameter overrides.

        Raises:
            JuniperCascorNotFoundError: If no network is loaded.
            JuniperCascorConflictError: If training is already in progress.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("start_training")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded. Create a network first.")

            if self._state == "training":
                raise JuniperCascorConflictError("Training is already in progress.")

            if self._state == "paused":
                raise JuniperCascorConflictError("Training is paused. Resume or reset before starting new training.")

            # Store training params
            self._training_params = {
                "epochs": epochs or (self._network_config.get("epochs_max", 1000) if self._network_config else 1000),
                "dataset": dataset or inline_data or self._dataset,
                "params": params or {},
            }

            # Update dataset if provided
            if dataset is not None:
                self._dataset = copy.deepcopy(dataset)
            elif inline_data is not None:
                self._dataset = {
                    "name": "inline",
                    "source": "inline",
                    "samples": len(inline_data.get("train_x", [])),
                    "features": len(inline_data.get("train_x", [[]])[0]) if inline_data.get("train_x") else 0,
                }

            self._state = "training"
            self._epoch = 0
            self._metrics_history = []
            self._training_start_time = time.time()

            return {
                "status": "ok",
                "message": "Training started.",
                "data": {
                    "state": "training",
                    "epochs": self._training_params["epochs"],
                },
            }

    def stop_training(self) -> Dict[str, Any]:
        """Request graceful training stop."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("stop_training")

            if self._state not in ("training", "paused"):
                raise JuniperCascorConflictError(f"Cannot stop training in state '{self._state}'.")

            self._state = "idle"

            return {
                "status": "ok",
                "message": "Training stopped.",
                "data": {
                    "state": "idle",
                    "final_epoch": self._epoch,
                },
            }

    def pause_training(self) -> Dict[str, Any]:
        """Pause training after current epoch."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("pause_training")

            if self._state != "training":
                raise JuniperCascorConflictError(f"Cannot pause training in state '{self._state}'.")

            self._state = "paused"

            return {
                "status": "ok",
                "message": "Training paused.",
                "data": {
                    "state": "paused",
                    "epoch": self._epoch,
                },
            }

    def resume_training(self) -> Dict[str, Any]:
        """Resume paused training."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("resume_training")

            if self._state != "paused":
                raise JuniperCascorConflictError(f"Cannot resume training in state '{self._state}'.")

            self._state = "training"

            return {
                "status": "ok",
                "message": "Training resumed.",
                "data": {
                    "state": "training",
                    "epoch": self._epoch,
                },
            }

    def reset_training(self) -> Dict[str, Any]:
        """Reset network and training state."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("reset_training")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            # Reset to initial topology (no hidden units)
            if self._network_config:
                self._topology = build_cascor_topology(
                    input_size=self._network_config.get("input_size", 2),
                    output_size=self._network_config.get("output_size", 1),
                    hidden_units=0,
                )

            self._state = "idle"
            self._epoch = 0
            self._metrics_history = []
            self._training_params = None
            self._training_start_time = None

            return {
                "status": "ok",
                "message": "Training reset.",
                "data": {
                    "state": "idle",
                },
            }

    def get_training_status(self) -> Dict[str, Any]:
        """Get current training status."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_training_status")

            elapsed = 0.0
            if self._training_start_time is not None:
                elapsed = round(time.time() - self._training_start_time, 2)

            max_epochs = 1000
            if self._training_params:
                max_epochs = self._training_params.get("epochs", 1000)

            progress = round(self._epoch / max_epochs, 4) if max_epochs > 0 else 0.0

            return {
                "status": "ok",
                "is_training": self._state == "training",
                "data": {
                    "state": self._state,
                    "epoch": self._epoch,
                    "max_epochs": max_epochs,
                    "progress": min(progress, 1.0),
                    "elapsed_seconds": elapsed,
                    "network_loaded": self._network_loaded,
                },
            }

    def get_training_params(self) -> Dict[str, Any]:
        """Get current training parameters."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_training_params")

            if self._training_params is None:
                return {
                    "status": "ok",
                    "data": {
                        "params": copy.deepcopy(self._network_config) if self._network_config else {},
                        "epochs": self._network_config.get("epochs_max", 1000) if self._network_config else 0,
                    },
                }

            return {
                "status": "ok",
                "data": {
                    "epochs": self._training_params.get("epochs", 1000),
                    "params": copy.deepcopy(self._training_params.get("params", {})),
                    "dataset": copy.deepcopy(self._training_params.get("dataset")),
                },
            }

    # ─── Metrics ─────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_metrics")

            if self._epoch == 0 and not self._metrics_history:
                return {
                    "status": "ok",
                    "data": {
                        "epoch": 0,
                        "train_loss": None,
                        "val_loss": None,
                        "train_accuracy": None,
                        "val_accuracy": None,
                        "correlation": None,
                        "hidden_units": 0,
                        "phase": None,
                    },
                }

            if self._metrics_history:
                current = copy.deepcopy(self._metrics_history[-1])
            else:
                current = generate_metrics_snapshot(self._epoch, self._scenario)

            return {
                "status": "ok",
                "data": current,
            }

    def get_metrics_history(self, count: Optional[int] = None) -> Dict[str, Any]:
        """Get training metrics history.

        Args:
            count: Number of recent entries to return. If None, returns all.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_metrics_history")

            history = copy.deepcopy(self._metrics_history)
            if count is not None and count > 0:
                history = history[-count:]

            return {
                "status": "ok",
                "data": {
                    "history": history,
                    "total": len(self._metrics_history),
                    "returned": len(history),
                },
            }

    # ─── Data ────────────────────────────────────────────────────────────

    def get_dataset(self) -> Dict[str, Any]:
        """Get current dataset metadata."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_dataset")

            if self._dataset is None:
                return {
                    "status": "ok",
                    "data": {},
                }

            return {
                "status": "ok",
                "data": copy.deepcopy(self._dataset),
            }

    def get_decision_boundary(self, resolution: int = 50) -> Dict[str, Any]:
        """Get decision boundary grid data for 2D visualization.

        Args:
            resolution: Grid resolution (5-200, default 50).

        Raises:
            JuniperCascorValidationError: If resolution is out of range.
            JuniperCascorNotFoundError: If no network is loaded.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_decision_boundary")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            if resolution < 5 or resolution > 200:
                raise JuniperCascorValidationError(f"Resolution must be between 5 and 200, got {resolution}.")

            input_size = self._network_config.get("input_size", 2) if self._network_config else 2
            hidden_units = self._topology.get("hidden_units", 0) if self._topology else 0
            boundary = generate_decision_boundary(
                input_size=input_size,
                resolution=resolution,
                hidden_units=hidden_units,
            )

            return {
                "status": "success",
                "data": boundary,
            }

    # ─── Context Manager ─────────────────────────────────────────────────

    def close(self) -> None:
        """Close the fake client."""
        with self._lock:
            self._closed = True

    def __enter__(self) -> "FakeCascorClient":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ─── Test Helpers ────────────────────────────────────────────────────

    def advance_epoch(self, n: int = 1) -> None:
        """Advance the epoch counter and generate metrics for each new epoch.

        This is a test helper not present on the real client. It simulates
        the passage of training epochs by generating metrics snapshots and
        updating the topology when cascade events would occur.

        Args:
            n: Number of epochs to advance.

        Raises:
            JuniperCascorConflictError: If training is not active.
        """
        with self._lock:
            if self._state not in ("training", "paused"):
                raise JuniperCascorConflictError(f"Cannot advance epoch in state '{self._state}'. Must be 'training' or 'paused'.")

            max_epochs = 1000
            if self._training_params:
                max_epochs = self._training_params.get("epochs", 1000)

            for _ in range(n):
                self._epoch += 1
                snapshot = generate_metrics_snapshot(self._epoch, self._scenario)
                self._metrics_history.append(snapshot)

                # Update topology when hidden units increase
                new_hidden = snapshot.get("hidden_units", 0)
                if self._topology and new_hidden > self._topology.get("hidden_units", 0):
                    input_size = self._network_config.get("input_size", 2) if self._network_config else 2
                    output_size = self._network_config.get("output_size", 1) if self._network_config else 1
                    self._topology = build_cascor_topology(
                        input_size=input_size,
                        output_size=output_size,
                        hidden_units=new_hidden,
                    )

                # Check if training is complete
                if self._epoch >= max_epochs:
                    self._state = "complete"
                    break

    def set_state(self, state: str) -> None:
        """Force a specific training state.

        This is a test helper not present on the real client. It bypasses
        normal state transition rules to allow testing of specific states.

        Args:
            state: Target state ('idle', 'training', 'paused', 'complete').

        Raises:
            ValueError: If state is not a valid training state.
        """
        with self._lock:
            if state not in VALID_STATES:
                valid = ", ".join(sorted(VALID_STATES))
                raise ValueError(f"Invalid state '{state}'. Valid states: {valid}")
            self._state = state
