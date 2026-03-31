"""Tests for FakeCascorClient worker methods.

Tests cover list_workers, get_worker, and get_worker_stats methods
including envelope format, known/unknown worker IDs, closed-state
behavior, and error-prone scenario injection.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: FakeCascorClient Worker Tests
Author: Paul Calnon
Version: 0.1.0
License: MIT License
"""

import random

import pytest

from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConnectionError, JuniperCascorNotFoundError, JuniperCascorServiceUnavailableError
from juniper_cascor_client.testing import FakeCascorClient

# ─── list_workers Tests ────────────────────────────────────────────────────


class TestListWorkers:
    """Tests for list_workers method."""

    @pytest.mark.unit
    def test_list_workers_returns_envelope(self, fake_idle):
        """list_workers returns a ResponseEnvelope with 'workers' list and 'count'."""
        result = fake_idle.list_workers()
        assert result["status"] == "success"
        assert "data" in result
        data = result["data"]
        assert "workers" in data
        assert "count" in data
        assert isinstance(data["workers"], list)
        assert data["count"] == len(data["workers"])

    @pytest.mark.unit
    def test_list_workers_returns_two_demo_workers(self, fake_training):
        """list_workers returns two demo workers with expected IDs."""
        result = fake_training.list_workers()
        data = result["data"]
        assert data["count"] == 2
        worker_ids = [w["worker_id"] for w in data["workers"]]
        assert "worker-demo-01" in worker_ids
        assert "worker-demo-02" in worker_ids

    @pytest.mark.unit
    def test_list_workers_worker_fields(self, fake_idle):
        """Each worker in list_workers has all expected fields."""
        result = fake_idle.list_workers()
        expected_fields = {
            "worker_id",
            "capabilities",
            "connected_at",
            "last_heartbeat",
            "tasks_completed",
            "tasks_failed",
            "active_task_id",
            "health_score",
            "idle",
        }
        for worker in result["data"]["workers"]:
            assert set(worker.keys()) == expected_fields, f"Worker {worker['worker_id']} is missing fields"

    @pytest.mark.unit
    def test_list_workers_idle_worker_details(self, fake_idle):
        """Worker-demo-01 is idle with no active task and perfect health."""
        result = fake_idle.list_workers()
        workers = {w["worker_id"]: w for w in result["data"]["workers"]}
        w1 = workers["worker-demo-01"]
        assert w1["idle"] is True
        assert w1["active_task_id"] is None
        assert w1["health_score"] == 1.0
        assert w1["tasks_completed"] == 12
        assert w1["tasks_failed"] == 0
        assert w1["capabilities"]["cpu_cores"] == 8
        assert w1["capabilities"]["gpu"] is False

    @pytest.mark.unit
    def test_list_workers_busy_worker_details(self, fake_idle):
        """Worker-demo-02 is busy with an active task and has GPU."""
        result = fake_idle.list_workers()
        workers = {w["worker_id"]: w for w in result["data"]["workers"]}
        w2 = workers["worker-demo-02"]
        assert w2["idle"] is False
        assert w2["active_task_id"] == "task-abc"
        assert w2["health_score"] == 0.8889
        assert w2["tasks_completed"] == 8
        assert w2["tasks_failed"] == 1
        assert w2["capabilities"]["cpu_cores"] == 4
        assert w2["capabilities"]["gpu"] is True

    @pytest.mark.unit
    def test_list_workers_raises_when_closed(self):
        """list_workers raises JuniperCascorClientError when client is closed."""
        client = FakeCascorClient(scenario="idle")
        client.close()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.list_workers()

    @pytest.mark.unit
    def test_list_workers_works_across_scenarios(self, fake_converged):
        """list_workers returns workers regardless of training state."""
        result = fake_converged.list_workers()
        assert result["status"] == "success"
        assert result["data"]["count"] == 2


# ─── get_worker Tests ──────────────────────────────────────────────────────


class TestGetWorker:
    """Tests for get_worker method."""

    @pytest.mark.unit
    def test_get_worker_known_id_returns_envelope(self, fake_idle):
        """get_worker returns a ResponseEnvelope for a known worker ID."""
        result = fake_idle.get_worker("worker-demo-01")
        assert result["status"] == "success"
        assert "data" in result
        assert result["data"]["worker_id"] == "worker-demo-01"

    @pytest.mark.unit
    def test_get_worker_demo_01_details(self, fake_training):
        """get_worker returns correct details for worker-demo-01."""
        result = fake_training.get_worker("worker-demo-01")
        data = result["data"]
        assert data["worker_id"] == "worker-demo-01"
        assert data["capabilities"]["cpu_cores"] == 8
        assert data["capabilities"]["gpu"] is False
        assert data["capabilities"]["python"] == "3.13"
        assert data["tasks_completed"] == 12
        assert data["tasks_failed"] == 0
        assert data["active_task_id"] is None
        assert data["health_score"] == 1.0
        assert data["idle"] is True

    @pytest.mark.unit
    def test_get_worker_demo_02_details(self, fake_training):
        """get_worker returns correct details for worker-demo-02."""
        result = fake_training.get_worker("worker-demo-02")
        data = result["data"]
        assert data["worker_id"] == "worker-demo-02"
        assert data["capabilities"]["cpu_cores"] == 4
        assert data["capabilities"]["gpu"] is True
        assert data["capabilities"]["python"] == "3.13"
        assert data["tasks_completed"] == 8
        assert data["tasks_failed"] == 1
        assert data["active_task_id"] == "task-abc"
        assert data["health_score"] == 0.8889
        assert data["idle"] is False

    @pytest.mark.unit
    def test_get_worker_unknown_id_raises_not_found(self, fake_idle):
        """get_worker raises JuniperCascorNotFoundError for unknown worker ID."""
        with pytest.raises(JuniperCascorNotFoundError, match="Worker 'nonexistent' not found"):
            fake_idle.get_worker("nonexistent")

    @pytest.mark.unit
    def test_get_worker_empty_id_raises_not_found(self, fake_idle):
        """get_worker raises JuniperCascorNotFoundError for empty worker ID."""
        with pytest.raises(JuniperCascorNotFoundError, match="not found"):
            fake_idle.get_worker("")

    @pytest.mark.unit
    def test_get_worker_raises_when_closed(self):
        """get_worker raises JuniperCascorClientError when client is closed."""
        client = FakeCascorClient(scenario="two_spiral_training")
        client.close()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.get_worker("worker-demo-01")

    @pytest.mark.unit
    def test_get_worker_has_all_fields(self, fake_idle):
        """get_worker response has all expected worker detail fields."""
        result = fake_idle.get_worker("worker-demo-01")
        expected_fields = {
            "worker_id",
            "capabilities",
            "connected_at",
            "last_heartbeat",
            "tasks_completed",
            "tasks_failed",
            "active_task_id",
            "health_score",
            "idle",
        }
        assert set(result["data"].keys()) == expected_fields


# ─── get_worker_stats Tests ───────────────────────────────────────────────


class TestGetWorkerStats:
    """Tests for get_worker_stats method."""

    @pytest.mark.unit
    def test_get_worker_stats_returns_envelope(self, fake_idle):
        """get_worker_stats returns a ResponseEnvelope with aggregate stats."""
        result = fake_idle.get_worker_stats()
        assert result["status"] == "success"
        assert "data" in result
        assert "meta" in result

    @pytest.mark.unit
    def test_get_worker_stats_aggregate_fields(self, fake_training):
        """get_worker_stats data contains all expected aggregate fields."""
        result = fake_training.get_worker_stats()
        data = result["data"]
        assert "total" in data
        assert "idle" in data
        assert "busy" in data
        assert "stale" in data
        assert "total_tasks_completed" in data
        assert "total_tasks_failed" in data
        assert "average_health_score" in data
        assert "timestamp" in data

    @pytest.mark.unit
    def test_get_worker_stats_values(self, fake_idle):
        """get_worker_stats returns correct aggregate values."""
        result = fake_idle.get_worker_stats()
        data = result["data"]
        assert data["total"] == 2
        assert data["idle"] == 1
        assert data["busy"] == 1
        assert data["stale"] == 0
        assert data["total_tasks_completed"] == 20
        assert data["total_tasks_failed"] == 1
        assert data["average_health_score"] == 0.9444

    @pytest.mark.unit
    def test_get_worker_stats_has_timestamp(self, fake_idle):
        """get_worker_stats includes a numeric timestamp."""
        result = fake_idle.get_worker_stats()
        assert isinstance(result["data"]["timestamp"], float)

    @pytest.mark.unit
    def test_get_worker_stats_raises_when_closed(self):
        """get_worker_stats raises JuniperCascorClientError when client is closed."""
        client = FakeCascorClient(scenario="idle")
        client.close()
        with pytest.raises(JuniperCascorClientError, match="Client is closed"):
            client.get_worker_stats()

    @pytest.mark.unit
    def test_get_worker_stats_works_across_scenarios(self, fake_converged):
        """get_worker_stats returns stats regardless of training state."""
        result = fake_converged.get_worker_stats()
        assert result["status"] == "success"
        assert result["data"]["total"] == 2


# ─── Error-Prone Scenario Tests ──────────────────────────────────────────


class TestWorkerErrorProne:
    """Tests for worker methods under the error_prone scenario."""

    @pytest.mark.unit
    def test_list_workers_error_prone_raises_sometimes(self, fake_error):
        """list_workers raises exceptions on ~10% of calls in error_prone scenario."""
        random.seed(42)
        errors_caught = 0
        for _ in range(200):
            try:
                fake_error.list_workers()
            except (
                JuniperCascorConnectionError,
                JuniperCascorClientError,
                JuniperCascorServiceUnavailableError,
            ):
                errors_caught += 1

        assert errors_caught > 0, "Expected at least one error in 200 calls with the error_prone scenario, " f"but caught {errors_caught}"

    @pytest.mark.unit
    def test_get_worker_error_prone_raises_sometimes(self, fake_error):
        """get_worker raises exceptions on ~10% of calls in error_prone scenario."""
        random.seed(99)
        errors_caught = 0
        for _ in range(200):
            try:
                fake_error.get_worker("worker-demo-01")
            except (
                JuniperCascorConnectionError,
                JuniperCascorClientError,
                JuniperCascorServiceUnavailableError,
            ):
                errors_caught += 1

        assert errors_caught > 0, "Expected at least one error in 200 calls with the error_prone scenario, " f"but caught {errors_caught}"

    @pytest.mark.unit
    def test_get_worker_stats_error_prone_raises_sometimes(self, fake_error):
        """get_worker_stats raises exceptions on ~10% of calls in error_prone scenario."""
        random.seed(77)
        errors_caught = 0
        for _ in range(200):
            try:
                fake_error.get_worker_stats()
            except (
                JuniperCascorConnectionError,
                JuniperCascorClientError,
                JuniperCascorServiceUnavailableError,
            ):
                errors_caught += 1

        assert errors_caught > 0, "Expected at least one error in 200 calls with the error_prone scenario, " f"but caught {errors_caught}"
