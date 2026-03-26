"""Comprehensive tests for FakeCascorClient (Task 6.5).

Tests cover all public methods and all scenario presets of the in-memory
fake REST client, including health, network management, training control,
metrics, data, test helpers, context manager, and thread safety.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: FakeCascorClient Tests
Author: Paul Calnon
Version: 0.1.0
License: MIT License
"""

import random
import threading

import pytest

from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConflictError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorServiceUnavailableError, JuniperCascorValidationError
from juniper_cascor_client.testing import FakeCascorClient

# ─── Health & Readiness Tests ───────────────────────────────────────────────


class TestHealth:
    """Tests for health_check, is_alive, is_ready, and wait_for_ready."""

    @pytest.mark.unit
    def test_health_check_returns_valid_dict(self, fake_training):
        """health_check returns a dict with 'status' and 'data' keys."""
        result = fake_training.health_check()
        assert result["status"] == "success", "Top-level status should be 'success'"
        assert "data" in result, "Response must contain 'data' key"
        data = result["data"]
        assert data["service"] == "juniper-cascor"
        assert "version" in data
        assert "uptime_seconds" in data
        assert isinstance(data["network_loaded"], bool)
        assert data["training_state"] in {"idle", "training", "paused", "complete"}

    @pytest.mark.unit
    def test_health_check_reflects_network_loaded(self, fake_idle):
        """health_check reports network_loaded=False when no network exists."""
        result = fake_idle.health_check()
        assert result["data"]["network_loaded"] is False

    @pytest.mark.unit
    def test_health_check_reflects_training_state(self, fake_training):
        """health_check reports the current training state."""
        result = fake_training.health_check()
        assert result["data"]["training_state"] == "training"

    @pytest.mark.unit
    def test_is_alive_returns_true(self, fake_idle):
        """is_alive returns True when the client is open."""
        assert fake_idle.is_alive() is True

    @pytest.mark.unit
    def test_is_alive_returns_false_when_closed(self):
        """is_alive returns False after the client is closed."""
        client = FakeCascorClient(scenario="idle")
        client.close()
        assert client.is_alive() is False

    @pytest.mark.unit
    def test_is_ready_returns_true_when_network_exists(self, fake_training):
        """is_ready returns True when a network is loaded."""
        assert fake_training.is_ready() is True

    @pytest.mark.unit
    def test_is_ready_returns_false_when_no_network(self, fake_idle):
        """is_ready returns False when no network is loaded."""
        assert fake_idle.is_ready() is False

    @pytest.mark.unit
    def test_wait_for_ready_returns_true_immediately(self, fake_idle):
        """wait_for_ready returns True immediately (no actual polling)."""
        result = fake_idle.wait_for_ready(timeout=1.0)
        assert result is True


# ─── Network Management Tests ───────────────────────────────────────────────


class TestNetworkManagement:
    """Tests for create_network, get_network, delete_network, get_topology, get_statistics."""

    @pytest.mark.unit
    def test_create_network_from_idle(self, fake_idle):
        """Creating a network from idle state succeeds and returns config."""
        result = fake_idle.create_network(input_size=4, output_size=2, learning_rate=0.05)
        assert result["status"] == "success"
        assert "config" in result["data"]
        config = result["data"]["config"]
        assert config["input_size"] == 4
        assert config["output_size"] == 2
        assert config["learning_rate"] == 0.05

    @pytest.mark.unit
    def test_create_network_when_already_exists_raises_conflict(self, fake_training):
        """Creating a network when one already exists raises ConflictError."""
        with pytest.raises(JuniperCascorConflictError, match="Network already exists"):
            fake_training.create_network(input_size=2, output_size=1, learning_rate=0.01)

    @pytest.mark.unit
    def test_create_network_missing_required_fields_raises_validation(self, fake_idle):
        """Creating a network without required fields raises ValidationError."""
        with pytest.raises(JuniperCascorValidationError, match="Missing required fields"):
            fake_idle.create_network(input_size=2)

    @pytest.mark.unit
    def test_create_network_sets_network_loaded(self, fake_idle):
        """After creating a network, is_ready returns True."""
        fake_idle.create_network(input_size=2, output_size=1, learning_rate=0.01)
        assert fake_idle.is_ready() is True

    @pytest.mark.unit
    def test_get_network_returns_config(self, fake_training):
        """get_network returns current network configuration and state."""
        result = fake_training.get_network()
        assert result["status"] == "success"
        data = result["data"]
        assert "config" in data
        assert data["state"] == "training"
        assert data["network_loaded"] is True
        assert isinstance(data["epoch"], int)

    @pytest.mark.unit
    def test_get_network_when_none_raises_not_found(self, fake_idle):
        """get_network raises NotFoundError when no network is loaded."""
        with pytest.raises(JuniperCascorNotFoundError, match="No network loaded"):
            fake_idle.get_network()

    @pytest.mark.unit
    def test_delete_network_succeeds(self, fake_converged):
        """Deleting a network in 'complete' state succeeds."""
        result = fake_converged.delete_network()
        assert result["status"] == "success"
        assert fake_converged.is_ready() is False

    @pytest.mark.unit
    def test_delete_network_when_none_raises_not_found(self, fake_idle):
        """Deleting when no network exists raises NotFoundError."""
        with pytest.raises(JuniperCascorNotFoundError, match="No network loaded"):
            fake_idle.delete_network()

    @pytest.mark.unit
    def test_delete_network_while_training_raises_conflict(self, fake_training):
        """Deleting a network during active training raises ConflictError."""
        with pytest.raises(JuniperCascorConflictError, match="Cannot delete network while training"):
            fake_training.delete_network()

    @pytest.mark.unit
    def test_get_topology_returns_nodes_and_connections(self, fake_training):
        """get_topology returns a dict with layers, nodes, and connections."""
        result = fake_training.get_topology()
        assert result["status"] == "success"
        data = result["data"]
        assert "layers" in data
        assert "nodes" in data
        assert "connections" in data
        assert isinstance(data["total_nodes"], int)
        assert isinstance(data["total_connections"], int)

    @pytest.mark.unit
    def test_get_topology_no_network_raises(self, fake_idle):
        """get_topology raises NotFoundError when no network is loaded."""
        with pytest.raises(JuniperCascorNotFoundError):
            fake_idle.get_topology()

    @pytest.mark.unit
    def test_get_statistics_returns_dict(self, fake_training):
        """get_statistics returns weight statistics for the loaded network."""
        result = fake_training.get_statistics()
        assert result["status"] == "success"
        data = result["data"]
        assert "total_parameters" in data
        assert "layers" in data
        assert isinstance(data["layers"], list)

    @pytest.mark.unit
    def test_get_statistics_no_network_raises(self, fake_idle):
        """get_statistics raises NotFoundError when no network is loaded."""
        with pytest.raises(JuniperCascorNotFoundError):
            fake_idle.get_statistics()


# ─── Training Control Tests (State Machine) ─────────────────────────────────


class TestTrainingControl:
    """Tests for start/stop/pause/resume/reset training and status/params queries."""

    @pytest.mark.unit
    def test_start_training_from_idle(self, fake_idle):
        """Starting training after creating a network transitions to 'training'."""
        fake_idle.create_network(input_size=2, output_size=1, learning_rate=0.01)
        result = fake_idle.start_training(epochs=100)
        assert result["status"] == "success"
        assert result["data"]["state"] == "training"
        assert result["data"]["epochs"] == 100

    @pytest.mark.unit
    def test_start_training_without_network_raises(self, fake_idle):
        """Starting training without a network raises NotFoundError."""
        with pytest.raises(JuniperCascorNotFoundError, match="No network loaded"):
            fake_idle.start_training(epochs=50)

    @pytest.mark.unit
    def test_start_training_when_already_training_raises_conflict(self, fake_training):
        """Starting training when already in 'training' state raises ConflictError."""
        with pytest.raises(JuniperCascorConflictError, match="Training is already in progress"):
            fake_training.start_training(epochs=50)

    @pytest.mark.unit
    def test_start_training_when_paused_raises_conflict(self, fake_training):
        """Starting training when paused raises ConflictError (must resume or reset)."""
        fake_training.pause_training()
        with pytest.raises(JuniperCascorConflictError, match="Training is paused"):
            fake_training.start_training(epochs=50)

    @pytest.mark.unit
    def test_start_training_with_dataset(self, fake_idle):
        """Starting training with a dataset parameter stores it."""
        fake_idle.create_network(input_size=2, output_size=1, learning_rate=0.01)
        dataset = {"name": "test", "source": "file", "samples": 100, "features": 2}
        result = fake_idle.start_training(epochs=50, dataset=dataset)
        assert result["status"] == "success"
        ds = fake_idle.get_dataset()
        assert ds["data"]["name"] == "test"

    @pytest.mark.unit
    def test_start_training_with_inline_data(self, fake_idle):
        """Starting training with inline_data stores derived dataset info."""
        fake_idle.create_network(input_size=2, output_size=1, learning_rate=0.01)
        inline = {"train_x": [[1, 2], [3, 4]], "train_y": [[0], [1]]}
        result = fake_idle.start_training(epochs=50, inline_data=inline)
        assert result["status"] == "success"
        ds = fake_idle.get_dataset()
        assert ds["data"]["source"] == "inline"
        assert ds["data"]["samples"] == 2

    @pytest.mark.unit
    def test_stop_training(self, fake_training):
        """Stopping training transitions from 'training' to 'idle'."""
        result = fake_training.stop_training()
        assert result["status"] == "success"
        assert result["data"]["state"] == "idle"

    @pytest.mark.unit
    def test_stop_training_when_idle_raises(self, fake_idle):
        """Stopping training when not training raises ConflictError."""
        with pytest.raises(JuniperCascorConflictError, match="Cannot stop training"):
            fake_idle.stop_training()

    @pytest.mark.unit
    def test_stop_training_when_paused(self, fake_training):
        """Stopping training from 'paused' state succeeds."""
        fake_training.pause_training()
        result = fake_training.stop_training()
        assert result["data"]["state"] == "idle"

    @pytest.mark.unit
    def test_pause_training(self, fake_training):
        """Pausing active training transitions to 'paused'."""
        result = fake_training.pause_training()
        assert result["status"] == "success"
        assert result["data"]["state"] == "paused"

    @pytest.mark.unit
    def test_pause_training_when_not_training_raises(self, fake_idle):
        """Pausing when not training raises ConflictError."""
        with pytest.raises(JuniperCascorConflictError, match="Cannot pause training"):
            fake_idle.pause_training()

    @pytest.mark.unit
    def test_resume_training(self, fake_training):
        """Resuming paused training transitions back to 'training'."""
        fake_training.pause_training()
        result = fake_training.resume_training()
        assert result["status"] == "success"
        assert result["data"]["state"] == "training"

    @pytest.mark.unit
    def test_resume_training_when_not_paused_raises(self, fake_training):
        """Resuming when not paused raises ConflictError."""
        with pytest.raises(JuniperCascorConflictError, match="Cannot resume training"):
            fake_training.resume_training()

    @pytest.mark.unit
    def test_reset_training(self, fake_training):
        """Resetting training transitions to 'idle' and clears epoch."""
        fake_training.advance_epoch(5)
        result = fake_training.reset_training()
        assert result["status"] == "success"
        assert result["data"]["state"] == "idle"
        status = fake_training.get_training_status()
        assert status["data"]["monitor"]["current_epoch"] == 0

    @pytest.mark.unit
    def test_reset_training_no_network_raises(self, fake_idle):
        """Resetting without a network raises NotFoundError."""
        with pytest.raises(JuniperCascorNotFoundError, match="No network loaded"):
            fake_idle.reset_training()

    @pytest.mark.unit
    def test_get_training_status(self, fake_training):
        """get_training_status returns state_machine, monitor, training_state, and network_loaded."""
        result = fake_training.get_training_status()
        assert result["status"] == "success"
        data = result["data"]
        assert data["training_active"] is True
        assert data["state_machine"]["status"] == "STARTED"
        assert isinstance(data["monitor"]["current_epoch"], int)
        assert isinstance(data["training_state"]["max_epochs"], int)
        assert isinstance(data["monitor"]["elapsed_seconds"], float)
        assert data["network_loaded"] is True

    @pytest.mark.unit
    def test_get_training_status_idle(self, fake_idle):
        """get_training_status works even with no network loaded."""
        result = fake_idle.get_training_status()
        assert result["data"]["state_machine"]["status"] == "STOPPED"
        assert result["data"]["network_loaded"] is False

    @pytest.mark.unit
    def test_get_training_params(self, fake_training):
        """get_training_params returns flat param dict with network config fields."""
        result = fake_training.get_training_params()
        assert result["status"] == "success"
        data = result["data"]
        assert "learning_rate" in data

    @pytest.mark.unit
    def test_get_training_params_no_training(self, fake_converged):
        """get_training_params with no active training returns network config params."""
        # Reset to clear training params but keep network
        fake_converged.set_state("idle")
        fake_converged.reset_training()
        result = fake_converged.get_training_params()
        assert result["status"] == "success"
        assert "learning_rate" in result["data"]


# ─── Metrics Tests ───────────────────────────────────────────────────────────


class TestMetrics:
    """Tests for get_metrics and get_metrics_history."""

    @pytest.mark.unit
    def test_get_metrics_returns_current_snapshot(self, fake_training):
        """get_metrics returns a metrics snapshot with standard fields."""
        fake_training.advance_epoch(5)
        result = fake_training.get_metrics()
        assert result["status"] == "success"
        data = result["data"]
        assert "epoch" in data
        assert "train_loss" in data
        assert "val_loss" in data
        assert "train_accuracy" in data
        assert "val_accuracy" in data
        assert "hidden_units" in data

    @pytest.mark.unit
    def test_get_metrics_at_epoch_zero(self, fake_training):
        """get_metrics at epoch 0 returns null/None metric values."""
        # The two_spiral_training scenario starts at epoch 0
        result = fake_training.get_metrics()
        data = result["data"]
        assert data["epoch"] == 0
        assert data["train_loss"] is None

    @pytest.mark.unit
    def test_get_metrics_history_returns_list(self, fake_training):
        """get_metrics_history returns a bare list of metric snapshots."""
        fake_training.advance_epoch(10)
        result = fake_training.get_metrics_history()
        assert result["status"] == "success"
        data = result["data"]
        assert isinstance(data, list)
        assert len(data) == 10

    @pytest.mark.unit
    def test_get_metrics_history_with_count(self, fake_training):
        """get_metrics_history with count returns only the last N entries."""
        fake_training.advance_epoch(20)
        result = fake_training.get_metrics_history(count=5)
        data = result["data"]
        assert isinstance(data, list)
        assert len(data) == 5
        # Verify we got the most recent 5
        epochs = [entry["epoch"] for entry in data]
        assert epochs == [16, 17, 18, 19, 20]

    @pytest.mark.unit
    def test_get_metrics_history_empty(self, fake_idle):
        """get_metrics_history with no training returns empty list."""
        result = fake_idle.get_metrics_history()
        assert result["data"] == []

    @pytest.mark.unit
    def test_get_metrics_converged_scenario(self, fake_converged):
        """get_metrics for xor_converged returns static converged values."""
        result = fake_converged.get_metrics()
        data = result["data"]
        assert data["train_loss"] == 0.003
        assert data["train_accuracy"] == 0.999
        assert data["phase"] == "complete"


# ─── Data Tests ──────────────────────────────────────────────────────────────


class TestData:
    """Tests for get_dataset and get_decision_boundary."""

    @pytest.mark.unit
    def test_get_dataset_returns_info(self, fake_training):
        """get_dataset returns dataset metadata for an active scenario."""
        result = fake_training.get_dataset()
        assert result["status"] == "success"
        data = result["data"]
        assert data["name"] == "two_spiral"
        assert data["samples"] == 194
        assert data["features"] == 2

    @pytest.mark.unit
    def test_get_dataset_empty(self, fake_idle):
        """get_dataset with no dataset returns empty data."""
        result = fake_idle.get_dataset()
        assert result["status"] == "success"
        assert result["data"] == {}

    @pytest.mark.unit
    def test_get_decision_boundary(self, fake_training):
        """get_decision_boundary returns 2D grid data matching real API format."""
        result = fake_training.get_decision_boundary(resolution=10)
        assert result["status"] == "success"
        data = result["data"]
        assert data["resolution"] == 10
        # grid_x and grid_y are 2D meshgrid arrays (10x10)
        assert len(data["grid_x"]) == 10
        assert len(data["grid_x"][0]) == 10
        assert len(data["grid_y"]) == 10
        assert len(data["grid_y"][0]) == 10
        # predictions is a 2D array of integer class indices (10x10)
        assert len(data["predictions"]) == 10
        assert len(data["predictions"][0]) == 10
        # All prediction values are integers (0 or 1)
        for row in data["predictions"]:
            for val in row:
                assert val in (0, 1)

    @pytest.mark.unit
    def test_get_decision_boundary_default_resolution(self, fake_training):
        """get_decision_boundary with default resolution uses 50."""
        result = fake_training.get_decision_boundary()
        assert result["data"]["resolution"] == 50

    @pytest.mark.unit
    def test_get_decision_boundary_no_network_raises(self, fake_idle):
        """get_decision_boundary without a network raises NotFoundError."""
        with pytest.raises(JuniperCascorNotFoundError):
            fake_idle.get_decision_boundary()

    @pytest.mark.unit
    def test_get_decision_boundary_invalid_resolution_raises(self, fake_training):
        """get_decision_boundary with out-of-range resolution raises ValidationError."""
        with pytest.raises(JuniperCascorValidationError, match="Resolution must be between"):
            fake_training.get_decision_boundary(resolution=3)
        with pytest.raises(JuniperCascorValidationError, match="Resolution must be between"):
            fake_training.get_decision_boundary(resolution=201)


# ─── Scenario Tests ──────────────────────────────────────────────────────────


class TestScenarios:
    """Tests verifying each scenario preset produces correct initial state."""

    @pytest.mark.unit
    def test_idle_scenario_initial_state(self, fake_idle):
        """Idle scenario: no network, state_machine.status='STOPPED', epoch=0."""
        status = fake_idle.get_training_status()
        assert status["data"]["state_machine"]["status"] == "STOPPED"
        assert status["data"]["monitor"]["current_epoch"] == 0
        assert status["data"]["network_loaded"] is False

    @pytest.mark.unit
    def test_two_spiral_training_scenario(self, fake_training):
        """Two-spiral scenario: network loaded, state_machine.status='STARTED', epoch=0."""
        status = fake_training.get_training_status()
        assert status["data"]["state_machine"]["status"] == "STARTED"
        assert status["data"]["monitor"]["current_epoch"] == 0
        assert status["data"]["network_loaded"] is True
        # Verify dataset is two_spiral
        ds = fake_training.get_dataset()
        assert ds["data"]["name"] == "two_spiral"

    @pytest.mark.unit
    def test_xor_converged_scenario(self, fake_converged):
        """XOR converged scenario: state_machine.status='COMPLETED', epoch=150, 2 hidden units."""
        status = fake_converged.get_training_status()
        assert status["data"]["state_machine"]["status"] == "COMPLETED"
        assert status["data"]["monitor"]["current_epoch"] == 150
        # Verify topology has hidden units
        topo = fake_converged.get_topology()
        assert topo["data"]["hidden_units"] == 2
        # Verify metrics history was populated
        history = fake_converged.get_metrics_history()
        assert len(history["data"]) == 150

    @pytest.mark.unit
    def test_empty_scenario(self, fake_empty):
        """Empty scenario: no network, no dataset, state_machine.status='STOPPED'."""
        status = fake_empty.get_training_status()
        assert status["data"]["state_machine"]["status"] == "STOPPED"
        assert status["data"]["network_loaded"] is False
        ds = fake_empty.get_dataset()
        assert ds["data"] == {}

    @pytest.mark.unit
    def test_error_prone_scenario_raises_sometimes(self, fake_error):
        """Error-prone scenario raises exceptions on approximately 10% of calls.

        Runs 200 calls and expects at least one exception to confirm the
        error injection mechanism is functional.
        """
        random.seed(42)  # Deterministic for reproducibility
        errors_caught = 0
        for _ in range(200):
            try:
                fake_error.health_check()
            except (
                JuniperCascorConnectionError,
                JuniperCascorClientError,
                JuniperCascorServiceUnavailableError,
            ):
                errors_caught += 1

        assert errors_caught > 0, "Expected at least one error in 200 calls with the error_prone scenario, " f"but caught {errors_caught}"

    @pytest.mark.unit
    def test_error_prone_scenario_network_is_loaded(self, fake_error):
        """Error-prone scenario has a network loaded at epoch 5."""
        status = fake_error.get_training_status()
        assert status["data"]["network_loaded"] is True
        assert status["data"]["monitor"]["current_epoch"] == 5

    @pytest.mark.unit
    def test_invalid_scenario_raises_value_error(self):
        """Using an unknown scenario name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown scenario"):
            FakeCascorClient(scenario="nonexistent_scenario")


# ─── Test Helper Tests ───────────────────────────────────────────────────────


class TestHelpers:
    """Tests for advance_epoch and set_state test helpers."""

    @pytest.mark.unit
    def test_advance_epoch_updates_state(self, fake_training):
        """advance_epoch increments the epoch counter."""
        fake_training.advance_epoch(5)
        status = fake_training.get_training_status()
        assert status["data"]["monitor"]["current_epoch"] == 5

    @pytest.mark.unit
    def test_advance_epoch_generates_metrics(self, fake_training):
        """advance_epoch populates metrics history with one entry per epoch."""
        fake_training.advance_epoch(10)
        history = fake_training.get_metrics_history()
        data = history["data"]
        assert len(data) == 10
        # Each snapshot has increasing epochs
        epochs = [entry["epoch"] for entry in data]
        assert epochs == list(range(1, 11))

    @pytest.mark.unit
    def test_advance_epoch_transitions_to_complete(self):
        """advance_epoch transitions to 'complete' when max_epochs is reached."""
        client = FakeCascorClient(scenario="idle")
        client.create_network(input_size=2, output_size=1, learning_rate=0.01)
        client.start_training(epochs=10)
        client.advance_epoch(15)  # Exceeds the 10-epoch max
        status = client.get_training_status()
        assert status["data"]["state_machine"]["status"] == "COMPLETED"
        # Epoch should cap at max_epochs (10)
        assert status["data"]["monitor"]["current_epoch"] == 10
        client.close()

    @pytest.mark.unit
    def test_advance_epoch_updates_topology_on_cascade(self, fake_training):
        """advance_epoch updates topology when hidden units increase."""
        # For two_spiral_training, hidden_units = min(epoch // 20, 8)
        # At epoch 20, hidden_units transitions from 0 to 1
        fake_training.advance_epoch(20)
        topo = fake_training.get_topology()
        assert topo["data"]["hidden_units"] >= 1

    @pytest.mark.unit
    def test_advance_epoch_when_not_training_raises(self, fake_idle):
        """advance_epoch raises ConflictError when not in training/paused state."""
        with pytest.raises(JuniperCascorConflictError, match="Cannot advance epoch"):
            fake_idle.advance_epoch(1)

    @pytest.mark.unit
    def test_advance_epoch_from_paused(self, fake_training):
        """advance_epoch works from paused state."""
        fake_training.pause_training()
        fake_training.advance_epoch(3)
        status = fake_training.get_training_status()
        assert status["data"]["monitor"]["current_epoch"] == 3

    @pytest.mark.unit
    def test_set_state_to_training(self, fake_idle):
        """set_state forces the client to 'training' state."""
        fake_idle.set_state("training")
        status = fake_idle.get_training_status()
        assert status["data"]["state_machine"]["status"] == "STARTED"

    @pytest.mark.unit
    def test_set_state_to_paused(self, fake_idle):
        """set_state forces the client to 'paused' state."""
        fake_idle.set_state("paused")
        status = fake_idle.get_training_status()
        assert status["data"]["state_machine"]["status"] == "PAUSED"

    @pytest.mark.unit
    def test_set_state_to_complete(self, fake_training):
        """set_state forces the client to 'complete' state."""
        fake_training.set_state("complete")
        status = fake_training.get_training_status()
        assert status["data"]["state_machine"]["status"] == "COMPLETED"

    @pytest.mark.unit
    def test_set_state_to_idle(self, fake_training):
        """set_state forces the client to 'idle' state."""
        fake_training.set_state("idle")
        status = fake_training.get_training_status()
        assert status["data"]["state_machine"]["status"] == "STOPPED"

    @pytest.mark.unit
    def test_set_state_invalid_raises_value_error(self, fake_idle):
        """set_state raises ValueError for an invalid state name."""
        with pytest.raises(ValueError, match="Invalid state"):
            fake_idle.set_state("running")


# ─── Context Manager Tests ──────────────────────────────────────────────────


class TestContextManager:
    """Tests for context manager usage and close behavior."""

    @pytest.mark.unit
    def test_context_manager_usage(self):
        """FakeCascorClient works as a context manager."""
        with FakeCascorClient(scenario="two_spiral_training") as client:
            result = client.health_check()
            assert result["status"] == "success"

    @pytest.mark.unit
    def test_context_manager_closes_on_exit(self):
        """Exiting the context manager closes the client."""
        with FakeCascorClient(scenario="idle") as client:
            assert client.is_alive() is True
        # After exiting, is_alive returns False
        assert client.is_alive() is False

    @pytest.mark.unit
    def test_close_makes_methods_raise(self):
        """After close(), calling any method raises JuniperCascorClientError."""
        client = FakeCascorClient(scenario="two_spiral_training")
        client.close()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.health_check()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.get_network()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.get_training_status()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.get_metrics()

    @pytest.mark.unit
    def test_close_is_idempotent(self):
        """Calling close() multiple times does not raise."""
        client = FakeCascorClient(scenario="idle")
        client.close()
        client.close()  # Should not raise
        assert client.is_alive() is False


# ─── Thread Safety Tests ────────────────────────────────────────────────────


class TestThreadSafety:
    """Tests for concurrent access to FakeCascorClient."""

    @pytest.mark.unit
    def test_concurrent_reads(self, fake_training):
        """Multiple threads can safely read training status concurrently."""
        results = []
        errors = []

        def read_status():
            try:
                for _ in range(50):
                    status = fake_training.get_training_status()
                    results.append(status["data"]["state_machine"]["status"])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=read_status) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent reads produced errors: {errors}"
        assert len(results) == 400, f"Expected 400 results, got {len(results)}"

    @pytest.mark.unit
    def test_concurrent_read_and_advance(self):
        """Concurrent reads and epoch advances do not raise or corrupt state."""
        client = FakeCascorClient(scenario="two_spiral_training")
        errors = []

        def advance_epochs():
            try:
                for _ in range(20):
                    client.advance_epoch(1)
            except Exception as exc:
                errors.append(exc)

        def read_metrics():
            try:
                for _ in range(50):
                    client.get_metrics()
            except Exception as exc:
                errors.append(exc)

        threads = []
        threads.append(threading.Thread(target=advance_epochs))
        for _ in range(4):
            threads.append(threading.Thread(target=read_metrics))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        client.close()
        assert len(errors) == 0, f"Concurrent operations produced errors: {errors}"


# ─── Miscellaneous Tests ────────────────────────────────────────────────────


class TestMiscellaneous:
    """Additional edge-case and integration tests."""

    @pytest.mark.unit
    def test_base_url_and_api_url(self):
        """Constructor sets base_url and api_url correctly."""
        client = FakeCascorClient(scenario="idle", base_url="http://myhost:9999/")
        assert client.base_url == "http://myhost:9999"
        assert client.api_url == "http://myhost:9999/v1"
        client.close()

    @pytest.mark.unit
    def test_api_key_stored(self):
        """Constructor stores the provided API key."""
        client = FakeCascorClient(scenario="idle", api_key="test-key-abc")
        assert client.api_key == "test-key-abc"
        client.close()

    @pytest.mark.unit
    def test_full_lifecycle(self):
        """End-to-end test: create -> train -> advance -> pause -> resume -> stop -> delete."""
        with FakeCascorClient(scenario="idle") as client:
            # Create
            client.create_network(input_size=2, output_size=1, learning_rate=0.01)
            assert client.is_ready() is True

            # Start training
            client.start_training(epochs=100)
            assert client.get_training_status()["data"]["state_machine"]["status"] == "STARTED"

            # Advance a few epochs
            client.advance_epoch(10)
            assert client.get_training_status()["data"]["monitor"]["current_epoch"] == 10

            # Pause
            client.pause_training()
            assert client.get_training_status()["data"]["state_machine"]["status"] == "PAUSED"

            # Resume
            client.resume_training()
            assert client.get_training_status()["data"]["state_machine"]["status"] == "STARTED"

            # Stop
            client.stop_training()
            assert client.get_training_status()["data"]["state_machine"]["status"] == "STOPPED"

            # Delete
            client.delete_network()
            assert client.is_ready() is False

    @pytest.mark.unit
    def test_create_delete_recreate(self, fake_idle):
        """A network can be deleted and recreated."""
        fake_idle.create_network(input_size=3, output_size=2, learning_rate=0.1)
        fake_idle.delete_network()
        # Recreate with different config
        result = fake_idle.create_network(input_size=5, output_size=3, learning_rate=0.001)
        assert result["data"]["config"]["input_size"] == 5
        assert result["data"]["config"]["output_size"] == 3

    @pytest.mark.unit
    def test_metrics_loss_decreases_over_epochs(self):
        """Training loss generally decreases across epochs for two_spiral scenario."""
        with FakeCascorClient(scenario="two_spiral_training") as client:
            client.advance_epoch(50)
            history = client.get_metrics_history()["data"]
            first_loss = history[0]["train_loss"]
            last_loss = history[-1]["train_loss"]
            assert last_loss < first_loss, f"Expected loss to decrease: first={first_loss}, last={last_loss}"

    @pytest.mark.unit
    def test_wait_for_ready_raises_when_closed(self):
        """wait_for_ready raises when client is closed."""
        client = FakeCascorClient(scenario="idle")
        client.close()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.wait_for_ready()
