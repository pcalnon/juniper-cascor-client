"""Fake REST client for JuniperCascor — fully in-memory, no network calls.

Implements every public method of JuniperCascorClient with scenario-driven
state management, configurable presets, and test helper utilities.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: FakeCascorClient
Author: Paul Calnon
Version: 0.2.0
License: MIT License
"""

import copy
import random
import threading
import time
from typing import Any, Dict, List, Optional

from juniper_cascor_client.constants import DEFAULT_READY_POLL_INTERVAL, DEFAULT_READY_TIMEOUT
from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorServiceUnavailableError, JuniperCascorValidationError
from juniper_cascor_client.testing.constants import (
    DATASET_NAME_INLINE,
    DATASET_SOURCE_INLINE,
    DEFAULT_CORRELATION_THRESHOLD,
    DEFAULT_DATASET_CLASSES,
    DEFAULT_DATASET_FEATURES,
    DEFAULT_DATASET_TRAIN_SAMPLES,
    DEFAULT_INPUT_SIZE,
    DEFAULT_LEARNING_RATE,
    DEFAULT_MAX_EPOCHS,
    DEFAULT_OUTPUT_SIZE,
    DEFAULT_PATIENCE,
    ENVELOPE_STATUS_SUCCESS,
    ERROR_PRONE_ERROR_RATE,
    FAKE_BASE_URL,
    FAKE_DEFAULT_UPTIME_SECONDS,
    FAKE_SERVICE_NAME,
    FAKE_SERVICE_VERSION,
    FAKE_SNAPSHOT_1_AGE_SECONDS,
    FAKE_SNAPSHOT_1_DESCRIPTION,
    FAKE_SNAPSHOT_1_EPOCH_OFFSET,
    FAKE_SNAPSHOT_1_HIDDEN_UNITS,
    FAKE_SNAPSHOT_1_ID,
    FAKE_SNAPSHOT_2_AGE_SECONDS,
    FAKE_SNAPSHOT_2_DESCRIPTION,
    FAKE_SNAPSHOT_2_HIDDEN_UNITS,
    FAKE_SNAPSHOT_2_ID,
    FAKE_WORKER_1_CONNECTED_AGO_SECONDS,
    FAKE_WORKER_1_CPU_CORES,
    FAKE_WORKER_1_GPU,
    FAKE_WORKER_1_HEALTH_SCORE,
    FAKE_WORKER_1_HEARTBEAT_AGO_SECONDS,
    FAKE_WORKER_1_ID,
    FAKE_WORKER_1_PYTHON_VERSION,
    FAKE_WORKER_1_TASKS_COMPLETED,
    FAKE_WORKER_1_TASKS_FAILED,
    FAKE_WORKER_2_ACTIVE_TASK_ID,
    FAKE_WORKER_2_CONNECTED_AGO_SECONDS,
    FAKE_WORKER_2_CPU_CORES,
    FAKE_WORKER_2_GPU,
    FAKE_WORKER_2_HEALTH_SCORE,
    FAKE_WORKER_2_HEARTBEAT_AGO_SECONDS,
    FAKE_WORKER_2_ID,
    FAKE_WORKER_2_PYTHON_VERSION,
    FAKE_WORKER_2_TASKS_COMPLETED,
    FAKE_WORKER_2_TASKS_FAILED,
    FAKE_WORKERS_AVG_HEALTH_SCORE,
    FAKE_WORKERS_BUSY,
    FAKE_WORKERS_IDLE,
    FAKE_WORKERS_STALE,
    FAKE_WORKERS_TOTAL,
    FAKE_WORKERS_TOTAL_TASKS_COMPLETED,
    FAKE_WORKERS_TOTAL_TASKS_FAILED,
    FSM_PHASE_IDLE_LOWER,
    FSM_PHASE_IDLE_UPPER,
    FSM_PHASE_OUTPUT_LOWER,
    FSM_PHASE_OUTPUT_UPPER,
    FSM_STATUS_COMPLETED,
    FSM_STATUS_IDLE,
    FSM_STATUS_PAUSED,
    FSM_STATUS_STARTED,
    FSM_STATUS_STOPPED,
    GET_PARAMS_DEFAULT_MAX_HIDDEN_UNITS,
    NETWORK_CONFIG_CANDIDATE_POOL_SIZE,
    SCENARIO_EMPTY,
    SCENARIO_ERROR_PRONE,
    SCENARIO_IDLE,
    SNAPSHOT_ID_GENERATED_PREFIX,
    STATE_COMPLETE,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_TRAINING,
    VALID_STATES,
)
from juniper_cascor_client.testing.scenarios import SCENARIO_DEFAULTS, build_cascor_topology, build_network_config, generate_dataset_inputs, generate_dataset_targets, generate_decision_boundary, generate_metrics_snapshot, generate_weight_statistics, get_scenario_data

# State transitions allowed by FakeCascorClient. Keys reference the same
# canonical STATE_* identifiers used everywhere else in this module.
STATE_TRANSITIONS = {
    STATE_IDLE: {STATE_TRAINING},
    STATE_TRAINING: {STATE_PAUSED, STATE_COMPLETE, STATE_IDLE},
    STATE_PAUSED: {STATE_TRAINING, STATE_IDLE},
    STATE_COMPLETE: {STATE_IDLE},
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
        scenario: str = SCENARIO_IDLE,
        base_url: str = FAKE_BASE_URL,
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
        if self._state in (STATE_TRAINING, STATE_PAUSED):
            self._training_params = {
                "epochs": self._network_config.get("epochs_max", DEFAULT_MAX_EPOCHS) if self._network_config else DEFAULT_MAX_EPOCHS,
                "dataset": self._dataset,
                "params": copy.deepcopy(self._network_config) if self._network_config else {},
            }
            self._training_start_time = time.time() - (self._epoch * 0.5)

    # ─── Error Injection ─────────────────────────────────────────────────

    def _maybe_raise_error(self, method_name: str) -> None:
        """Conditionally raise an exception for the error_prone scenario.

        Uses ``random.random() < ERROR_PRONE_ERROR_RATE`` to decide. Cycles
        through different exception types based on a hash of the method name
        for variety.
        """
        if self._scenario != SCENARIO_ERROR_PRONE:
            return
        if random.random() >= ERROR_PRONE_ERROR_RATE:
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

    @staticmethod
    def _success_envelope(data: Any) -> Dict[str, Any]:
        """Build a ResponseEnvelope matching the real cascor server format."""
        return {
            "status": ENVELOPE_STATUS_SUCCESS,
            "data": data,
            "meta": {"timestamp": time.time(), "version": FAKE_SERVICE_VERSION},
        }

    # ─── Health ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Check service health."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("health_check")
            return self._success_envelope(
                {
                    "service": FAKE_SERVICE_NAME,
                    "version": FAKE_SERVICE_VERSION,
                    "uptime_seconds": FAKE_DEFAULT_UPTIME_SECONDS,
                    "network_loaded": self._network_loaded,
                    "training_state": self._state,
                }
            )

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

    def wait_for_ready(self, timeout: float = DEFAULT_READY_TIMEOUT, poll_interval: float = DEFAULT_READY_POLL_INTERVAL) -> bool:
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
            if missing and self._scenario != SCENARIO_EMPTY:
                raise JuniperCascorValidationError(f"Missing required fields: {', '.join(missing)}")

            input_size = kwargs.get("input_size", DEFAULT_INPUT_SIZE)
            output_size = kwargs.get("output_size", DEFAULT_OUTPUT_SIZE)
            learning_rate = kwargs.get("learning_rate", DEFAULT_LEARNING_RATE)

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
            self._state = STATE_IDLE
            self._epoch = 0
            self._metrics_history = []

            return self._success_envelope(
                {
                    "config": copy.deepcopy(self._network_config),
                    "message": "Network created successfully.",
                }
            )

    def get_network(self) -> Dict[str, Any]:
        """Get current network state and configuration."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_network")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            return self._success_envelope(
                {
                    "config": copy.deepcopy(self._network_config),
                    "state": self._state,
                    "epoch": self._epoch,
                    "network_loaded": True,
                }
            )

    def delete_network(self) -> Dict[str, Any]:
        """Destroy the current network."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("delete_network")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            if self._state == STATE_TRAINING:
                raise JuniperCascorConflictError("Cannot delete network while training is active. Stop training first.")

            self._network_config = None
            self._topology = None
            self._dataset = None
            self._network_loaded = False
            self._state = STATE_IDLE
            self._epoch = 0
            self._metrics_history = []
            self._training_params = None
            self._training_start_time = None

            return self._success_envelope({"message": "Network deleted."})

    def get_topology(self) -> Dict[str, Any]:
        """Get network topology for visualization."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_topology")

            if not self._network_loaded or self._topology is None:
                raise JuniperCascorNotFoundError("No network loaded.")

            return self._success_envelope(copy.deepcopy(self._topology))

    def get_statistics(self) -> Dict[str, Any]:
        """Get network weight statistics."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_statistics")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            hidden_units = self._topology.get("hidden_units", 0) if self._topology else 0
            stats = generate_weight_statistics(hidden_units)

            return self._success_envelope(stats)

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

            if self._state == STATE_TRAINING:
                raise JuniperCascorConflictError("Training is already in progress.")

            if self._state == STATE_PAUSED:
                raise JuniperCascorConflictError("Training is paused. Resume or reset before starting new training.")

            # Store training params
            self._training_params = {
                "epochs": epochs or (self._network_config.get("epochs_max", DEFAULT_MAX_EPOCHS) if self._network_config else DEFAULT_MAX_EPOCHS),
                "dataset": dataset or inline_data or self._dataset,
                "params": params or {},
            }

            # Update dataset if provided
            if dataset is not None:
                self._dataset = copy.deepcopy(dataset)
            elif inline_data is not None:
                self._dataset = {
                    "name": DATASET_NAME_INLINE,
                    "source": DATASET_SOURCE_INLINE,
                    "samples": len(inline_data.get("train_x", [])),
                    "features": len(inline_data.get("train_x", [[]])[0]) if inline_data.get("train_x") else 0,
                }

            self._state = STATE_TRAINING
            self._epoch = 0
            self._metrics_history = []
            self._training_start_time = time.time()

            return self._success_envelope(
                {
                    "state": STATE_TRAINING,
                    "epochs": self._training_params["epochs"],
                    "message": "Training started.",
                }
            )

    def stop_training(self) -> Dict[str, Any]:
        """Request graceful training stop."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("stop_training")

            if self._state not in (STATE_TRAINING, STATE_PAUSED):
                raise JuniperCascorConflictError(f"Cannot stop training in state '{self._state}'.")

            self._state = STATE_IDLE

            return self._success_envelope(
                {
                    "state": STATE_IDLE,
                    "final_epoch": self._epoch,
                    "message": "Training stopped.",
                }
            )

    def pause_training(self) -> Dict[str, Any]:
        """Pause training after current epoch."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("pause_training")

            if self._state != STATE_TRAINING:
                raise JuniperCascorConflictError(f"Cannot pause training in state '{self._state}'.")

            self._state = STATE_PAUSED

            return self._success_envelope(
                {
                    "state": STATE_PAUSED,
                    "epoch": self._epoch,
                    "message": "Training paused.",
                }
            )

    def resume_training(self) -> Dict[str, Any]:
        """Resume paused training."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("resume_training")

            if self._state != STATE_PAUSED:
                raise JuniperCascorConflictError(f"Cannot resume training in state '{self._state}'.")

            self._state = STATE_TRAINING

            return self._success_envelope(
                {
                    "state": STATE_TRAINING,
                    "epoch": self._epoch,
                    "message": "Training resumed.",
                }
            )

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
                    input_size=self._network_config.get("input_size", DEFAULT_INPUT_SIZE),
                    output_size=self._network_config.get("output_size", DEFAULT_OUTPUT_SIZE),
                    hidden_units=0,
                )

            self._state = STATE_IDLE
            self._epoch = 0
            self._metrics_history = []
            self._training_params = None
            self._training_start_time = None

            return self._success_envelope(
                {
                    "state": STATE_IDLE,
                    "message": "Training reset.",
                }
            )

    # FSM state mapping: internal state -> cascor state_machine.status
    _STATE_TO_FSM = {
        STATE_IDLE: FSM_STATUS_STOPPED,
        STATE_TRAINING: FSM_STATUS_STARTED,
        STATE_PAUSED: FSM_STATUS_PAUSED,
        STATE_COMPLETE: FSM_STATUS_COMPLETED,
    }

    # Phase mapping: internal state -> cascor state_machine.phase
    _STATE_TO_PHASE = {
        STATE_IDLE: FSM_PHASE_IDLE_UPPER,
        STATE_TRAINING: FSM_PHASE_OUTPUT_UPPER,
        STATE_PAUSED: FSM_PHASE_OUTPUT_UPPER,
        STATE_COMPLETE: FSM_PHASE_IDLE_UPPER,
    }

    def get_training_status(self) -> Dict[str, Any]:
        """Get current training status.

        Returns ResponseEnvelope matching the real cascor server format:
        nested state_machine, monitor, and training_state dicts.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_training_status")

            elapsed = 0.0
            if self._training_start_time is not None:
                elapsed = round(time.time() - self._training_start_time, 2)

            max_epochs = DEFAULT_MAX_EPOCHS
            if self._training_params:
                max_epochs = self._training_params.get("epochs", DEFAULT_MAX_EPOCHS)

            progress = round(self._epoch / max_epochs, 4) if max_epochs > 0 else 0.0

            config = self._network_config or {}

            # Map internal state to cascor server state machine status
            status_map = {
                STATE_TRAINING: FSM_STATUS_STARTED,
                STATE_PAUSED: FSM_STATUS_PAUSED,
                STATE_COMPLETE: FSM_STATUS_COMPLETED,
                STATE_IDLE: FSM_STATUS_IDLE,
            }
            phase = FSM_PHASE_OUTPUT_LOWER if self._state == STATE_TRAINING else FSM_PHASE_IDLE_LOWER
            hidden_units = self._topology.get("hidden_units", 0) if self._topology else 0

            return self._success_envelope(
                {
                    "state_machine": {
                        "status": status_map.get(self._state, FSM_STATUS_IDLE),
                        "phase": phase,
                    },
                    "monitor": {
                        "is_training": self._state == STATE_TRAINING,
                        "current_epoch": self._epoch,
                        "current_hidden_units": hidden_units,
                        "total_metrics": len(self._metrics_history),
                    },
                    "training_state": {
                        "learning_rate": config.get("learning_rate", DEFAULT_LEARNING_RATE),
                        "max_hidden_units": config.get("max_hidden_units", GET_PARAMS_DEFAULT_MAX_HIDDEN_UNITS),
                        "max_epochs": max_epochs,
                        "progress": min(progress, 1.0),
                        "elapsed_seconds": elapsed,
                    },
                    "training_active": self._state == STATE_TRAINING,
                    "network_loaded": self._network_loaded,
                }
            )

    def get_training_params(self) -> Dict[str, Any]:
        """Get current training parameters.

        Returns ResponseEnvelope with flat param dict in data (matching real server).
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_training_params")

            config = self._network_config or {}
            if self._training_params and self._training_params.get("params"):
                config = {**config, **self._training_params["params"]}

            return self._success_envelope(
                {
                    "learning_rate": config.get("learning_rate", DEFAULT_LEARNING_RATE),
                    "max_hidden_units": config.get("max_hidden_units", GET_PARAMS_DEFAULT_MAX_HIDDEN_UNITS),
                    "epochs_max": config.get("epochs_max", DEFAULT_MAX_EPOCHS),
                    "patience": config.get("patience", DEFAULT_PATIENCE),
                    "candidate_pool_size": config.get("candidate_pool_size", NETWORK_CONFIG_CANDIDATE_POOL_SIZE),
                    "correlation_threshold": config.get("correlation_threshold", DEFAULT_CORRELATION_THRESHOLD),
                }
            )

    def update_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update runtime-modifiable training parameters.

        Args:
            params: Dict of parameter names and new values.

        Raises:
            JuniperCascorNotFoundError: If no network is loaded.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("update_params")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            # Update the network config with the provided params
            updatable_keys = {
                "learning_rate",
                "candidate_learning_rate",
                "correlation_threshold",
                "candidate_pool_size",
                "max_hidden_units",
                "epochs_max",
                "patience",
            }
            if self._network_config is not None:
                for key, value in params.items():
                    if key in updatable_keys:
                        self._network_config[key] = value

            return self._success_envelope(copy.deepcopy(self._network_config) if self._network_config else {})

    # ─── Metrics ─────────────────────────────────────────────────────────

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_metrics")

            if self._epoch == 0 and not self._metrics_history:
                return self._success_envelope(
                    {
                        "epoch": 0,
                        "train_loss": None,
                        "val_loss": None,
                        "train_accuracy": None,
                        "val_accuracy": None,
                        "hidden_units": 0,
                        "phase": None,
                        "timestamp": time.time(),
                    }
                )

            if self._metrics_history:
                current = copy.deepcopy(self._metrics_history[-1])
            else:
                current = generate_metrics_snapshot(self._epoch, self._scenario)
            current["timestamp"] = time.time()

            current.pop("correlation", None)
            current.setdefault("timestamp", time.time())

            return self._success_envelope(current)

    def get_metrics_history(self, count: Optional[int] = None) -> Dict[str, Any]:
        """Get training metrics history.

        Returns ResponseEnvelope with data as a bare list (matching real server).

        Args:
            count: Number of recent entries to return. If None, returns all.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_metrics_history")

            history = copy.deepcopy(self._metrics_history)
            if count is not None and count > 0:
                history = history[-count:]

            return self._success_envelope(history)

    # ─── Data ────────────────────────────────────────────────────────────

    def get_dataset(self) -> Dict[str, Any]:
        """Get current dataset metadata."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_dataset")

            if self._dataset is None:
                return self._success_envelope({})

            return self._success_envelope(copy.deepcopy(self._dataset))

    def get_dataset_data(self) -> Dict[str, Any]:
        """Get dataset arrays for visualization.

        Generates synthetic train_x/train_y arrays from scenario metadata
        (samples, features, classes) for visualization and testing.

        Raises:
            JuniperCascorNotFoundError: If no dataset is loaded.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_dataset_data")

            if self._dataset is None:
                raise JuniperCascorNotFoundError("No dataset loaded.")

            samples = self._dataset.get("train_samples", DEFAULT_DATASET_TRAIN_SAMPLES)
            features = self._dataset.get("features", DEFAULT_DATASET_FEATURES)
            classes = self._dataset.get("classes", DEFAULT_DATASET_CLASSES)
            train_x = generate_dataset_inputs(samples, features)
            train_y = generate_dataset_targets(samples, classes)
            return self._success_envelope({"train_x": train_x, "train_y": train_y})

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

            input_size = self._network_config.get("input_size", DEFAULT_INPUT_SIZE) if self._network_config else DEFAULT_INPUT_SIZE
            hidden_units = self._topology.get("hidden_units", 0) if self._topology else 0
            boundary = generate_decision_boundary(
                input_size=input_size,
                resolution=resolution,
                hidden_units=hidden_units,
            )

            return self._success_envelope(boundary)

    # ─── Snapshots ───────────────────────────────────────────────────────

    def list_snapshots(self) -> Dict[str, Any]:
        """List available network snapshots."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("list_snapshots")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            snapshots: List[Dict[str, Any]] = []
            if self._state in (STATE_TRAINING, STATE_PAUSED, STATE_COMPLETE):
                snapshots = [
                    {
                        "snapshot_id": FAKE_SNAPSHOT_1_ID,
                        "description": FAKE_SNAPSHOT_1_DESCRIPTION,
                        "epoch": max(0, self._epoch - FAKE_SNAPSHOT_1_EPOCH_OFFSET),
                        "hidden_units": FAKE_SNAPSHOT_1_HIDDEN_UNITS,
                        "created_at": time.time() - FAKE_SNAPSHOT_1_AGE_SECONDS,
                    },
                    {
                        "snapshot_id": FAKE_SNAPSHOT_2_ID,
                        "description": FAKE_SNAPSHOT_2_DESCRIPTION,
                        "epoch": self._epoch,
                        "hidden_units": FAKE_SNAPSHOT_2_HIDDEN_UNITS,
                        "created_at": time.time() - FAKE_SNAPSHOT_2_AGE_SECONDS,
                    },
                ]

            return self._success_envelope({"snapshots": snapshots, "count": len(snapshots)})

    def get_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Get metadata for a specific snapshot.

        Args:
            snapshot_id: Snapshot identifier.

        Raises:
            JuniperCascorNotFoundError: If no network is loaded or snapshot not found.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_snapshot")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            # Only recognize the two fake snapshot IDs
            if snapshot_id not in (FAKE_SNAPSHOT_1_ID, FAKE_SNAPSHOT_2_ID):
                raise JuniperCascorNotFoundError(f"Snapshot '{snapshot_id}' not found.")

            epoch = max(0, self._epoch - FAKE_SNAPSHOT_1_EPOCH_OFFSET) if snapshot_id == FAKE_SNAPSHOT_1_ID else self._epoch
            hidden = FAKE_SNAPSHOT_1_HIDDEN_UNITS if snapshot_id == FAKE_SNAPSHOT_1_ID else FAKE_SNAPSHOT_2_HIDDEN_UNITS
            desc = FAKE_SNAPSHOT_1_DESCRIPTION if snapshot_id == FAKE_SNAPSHOT_1_ID else FAKE_SNAPSHOT_2_DESCRIPTION

            return self._success_envelope(
                {
                    "snapshot_id": snapshot_id,
                    "description": desc,
                    "epoch": epoch,
                    "hidden_units": hidden,
                    "created_at": time.time() - (FAKE_SNAPSHOT_1_AGE_SECONDS if snapshot_id == FAKE_SNAPSHOT_1_ID else FAKE_SNAPSHOT_2_AGE_SECONDS),
                    "network_config": copy.deepcopy(self._network_config),
                }
            )

    def save_snapshot(self, description: str = "") -> Dict[str, Any]:
        """Save current network state as a snapshot.

        Args:
            description: Optional description for the snapshot.

        Raises:
            JuniperCascorNotFoundError: If no network is loaded.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("save_snapshot")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            snapshot_id = f"{SNAPSHOT_ID_GENERATED_PREFIX}{int(time.time())}"
            hidden_units = self._topology.get("hidden_units", 0) if self._topology else 0

            return self._success_envelope(
                {
                    "snapshot_id": snapshot_id,
                    "description": description,
                    "epoch": self._epoch,
                    "hidden_units": hidden_units,
                    "created_at": time.time(),
                    "message": "Snapshot saved.",
                }
            )

    def load_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Restore network state from a snapshot.

        Args:
            snapshot_id: Snapshot identifier to restore.

        Raises:
            JuniperCascorNotFoundError: If no network is loaded or snapshot not found.
            JuniperCascorConflictError: If training is active.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("load_snapshot")

            if not self._network_loaded:
                raise JuniperCascorNotFoundError("No network loaded.")

            if self._state == STATE_TRAINING:
                raise JuniperCascorConflictError("Cannot load snapshot while training is active. Stop training first.")

            if snapshot_id not in (FAKE_SNAPSHOT_1_ID, FAKE_SNAPSHOT_2_ID):
                raise JuniperCascorNotFoundError(f"Snapshot '{snapshot_id}' not found.")

            return self._success_envelope(
                {
                    "snapshot_id": snapshot_id,
                    "restored": True,
                    "message": f"Network state restored from snapshot '{snapshot_id}'.",
                }
            )

    # ─── Workers ─────────────────────────────────────────────────────────

    def list_workers(self) -> Dict[str, Any]:
        """List all registered remote workers with status."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("list_workers")

            workers = [
                {
                    "worker_id": FAKE_WORKER_1_ID,
                    "capabilities": {"cpu_cores": FAKE_WORKER_1_CPU_CORES, "gpu": FAKE_WORKER_1_GPU, "python": FAKE_WORKER_1_PYTHON_VERSION},
                    "connected_at": time.time() - FAKE_WORKER_1_CONNECTED_AGO_SECONDS,
                    "last_heartbeat": time.time() - FAKE_WORKER_1_HEARTBEAT_AGO_SECONDS,
                    "tasks_completed": FAKE_WORKER_1_TASKS_COMPLETED,
                    "tasks_failed": FAKE_WORKER_1_TASKS_FAILED,
                    "active_task_id": None,
                    "health_score": FAKE_WORKER_1_HEALTH_SCORE,
                    "idle": True,
                },
                {
                    "worker_id": FAKE_WORKER_2_ID,
                    "capabilities": {"cpu_cores": FAKE_WORKER_2_CPU_CORES, "gpu": FAKE_WORKER_2_GPU, "python": FAKE_WORKER_2_PYTHON_VERSION},
                    "connected_at": time.time() - FAKE_WORKER_2_CONNECTED_AGO_SECONDS,
                    "last_heartbeat": time.time() - FAKE_WORKER_2_HEARTBEAT_AGO_SECONDS,
                    "tasks_completed": FAKE_WORKER_2_TASKS_COMPLETED,
                    "tasks_failed": FAKE_WORKER_2_TASKS_FAILED,
                    "active_task_id": FAKE_WORKER_2_ACTIVE_TASK_ID,
                    "health_score": FAKE_WORKER_2_HEALTH_SCORE,
                    "idle": False,
                },
            ]
            return self._success_envelope({"workers": workers, "count": len(workers)})

    def get_worker(self, worker_id: str) -> Dict[str, Any]:
        """Get details for a specific worker.

        Args:
            worker_id: Worker identifier.

        Raises:
            JuniperCascorNotFoundError: If worker not found.
        """
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_worker")

            known = {FAKE_WORKER_1_ID, FAKE_WORKER_2_ID}
            if worker_id not in known:
                raise JuniperCascorNotFoundError(f"Worker '{worker_id}' not found")

            is_first = worker_id == FAKE_WORKER_1_ID
            return self._success_envelope(
                {
                    "worker_id": worker_id,
                    "capabilities": {
                        "cpu_cores": FAKE_WORKER_1_CPU_CORES if is_first else FAKE_WORKER_2_CPU_CORES,
                        "gpu": FAKE_WORKER_1_GPU if is_first else FAKE_WORKER_2_GPU,
                        "python": FAKE_WORKER_1_PYTHON_VERSION if is_first else FAKE_WORKER_2_PYTHON_VERSION,
                    },
                    "connected_at": time.time() - (FAKE_WORKER_1_CONNECTED_AGO_SECONDS if is_first else FAKE_WORKER_2_CONNECTED_AGO_SECONDS),
                    "last_heartbeat": time.time() - (FAKE_WORKER_1_HEARTBEAT_AGO_SECONDS if is_first else FAKE_WORKER_2_HEARTBEAT_AGO_SECONDS),
                    "tasks_completed": FAKE_WORKER_1_TASKS_COMPLETED if is_first else FAKE_WORKER_2_TASKS_COMPLETED,
                    "tasks_failed": FAKE_WORKER_1_TASKS_FAILED if is_first else FAKE_WORKER_2_TASKS_FAILED,
                    "active_task_id": None if is_first else FAKE_WORKER_2_ACTIVE_TASK_ID,
                    "health_score": FAKE_WORKER_1_HEALTH_SCORE if is_first else FAKE_WORKER_2_HEALTH_SCORE,
                    "idle": is_first,
                }
            )

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get aggregate worker statistics."""
        with self._lock:
            self._check_closed()
            self._maybe_raise_error("get_worker_stats")

            return self._success_envelope(
                {
                    "total": FAKE_WORKERS_TOTAL,
                    "idle": FAKE_WORKERS_IDLE,
                    "busy": FAKE_WORKERS_BUSY,
                    "stale": FAKE_WORKERS_STALE,
                    "total_tasks_completed": FAKE_WORKERS_TOTAL_TASKS_COMPLETED,
                    "total_tasks_failed": FAKE_WORKERS_TOTAL_TASKS_FAILED,
                    "average_health_score": FAKE_WORKERS_AVG_HEALTH_SCORE,
                    "timestamp": time.time(),
                }
            )

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
            if self._state not in (STATE_TRAINING, STATE_PAUSED):
                raise JuniperCascorConflictError(f"Cannot advance epoch in state '{self._state}'. Must be 'training' or 'paused'.")

            max_epochs = DEFAULT_MAX_EPOCHS
            if self._training_params:
                max_epochs = self._training_params.get("epochs", DEFAULT_MAX_EPOCHS)

            for _ in range(n):
                self._epoch += 1
                snapshot = generate_metrics_snapshot(self._epoch, self._scenario)
                self._metrics_history.append(snapshot)

                # Update topology when hidden units increase
                new_hidden = snapshot.get("hidden_units", 0)
                if self._topology and new_hidden > self._topology.get("hidden_units", 0):
                    input_size = self._network_config.get("input_size", DEFAULT_INPUT_SIZE) if self._network_config else DEFAULT_INPUT_SIZE
                    output_size = self._network_config.get("output_size", DEFAULT_OUTPUT_SIZE) if self._network_config else DEFAULT_OUTPUT_SIZE
                    self._topology = build_cascor_topology(
                        input_size=input_size,
                        output_size=output_size,
                        hidden_units=new_hidden,
                    )

                # Check if training is complete
                if self._epoch >= max_epochs:
                    self._state = STATE_COMPLETE
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
