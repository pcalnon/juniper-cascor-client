"""Constants for the JuniperCascor testing utilities.

Centralizes hardcoded literals used by ``FakeCascorClient``,
``FakeCascorTrainingStream``, and the scenario generators in
``juniper_cascor_client.testing.scenarios``.

These are *test fixture* values: synthetic worker IDs, synthetic snapshot
identifiers, hand-tuned curve parameters, and dataset metadata used to
produce stable, deterministic responses without a running cascor service.
They are not intended to match real production values.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: FakeCascorClient / Testing Scenarios
Author: Paul Calnon
Version: 0.3.0
License: MIT License
"""

from typing import FrozenSet

# ─── Fake Service Identity ───────────────────────────────────────────────────

FAKE_BASE_URL: str = "http://fake-cascor:8200"
FAKE_WS_BASE_URL: str = "ws://fake-cascor:8200"
FAKE_SERVICE_NAME: str = "juniper-cascor"
FAKE_SERVICE_VERSION: str = "0.4.0"
FAKE_DEFAULT_UPTIME_SECONDS: float = 3600.0

# Response envelope status fields.
ENVELOPE_STATUS_SUCCESS: str = "success"

# ─── Error Injection (error_prone scenario) ──────────────────────────────────

ERROR_PRONE_ERROR_RATE: float = 0.1

# ─── Training State Names ────────────────────────────────────────────────────

STATE_IDLE: str = "idle"
STATE_TRAINING: str = "training"
STATE_PAUSED: str = "paused"
STATE_COMPLETE: str = "complete"
VALID_STATES: FrozenSet[str] = frozenset({STATE_IDLE, STATE_TRAINING, STATE_PAUSED, STATE_COMPLETE})

# ─── FSM Status Identifiers (cascor server protocol) ─────────────────────────

FSM_STATUS_STOPPED: str = "STOPPED"
FSM_STATUS_STARTED: str = "STARTED"
FSM_STATUS_PAUSED: str = "PAUSED"
FSM_STATUS_COMPLETED: str = "COMPLETED"
FSM_STATUS_IDLE: str = "IDLE"

# ─── FSM Phase Identifiers (cascor server protocol) ──────────────────────────

FSM_PHASE_IDLE_UPPER: str = "IDLE"
FSM_PHASE_OUTPUT_UPPER: str = "OUTPUT"
FSM_PHASE_IDLE_LOWER: str = "idle"
FSM_PHASE_OUTPUT_LOWER: str = "output"
FSM_PHASE_OUTPUT_TRAINING: str = "output_training"
FSM_PHASE_CANDIDATE_TRAINING: str = "candidate_training"
FSM_PHASE_COMPLETE_LOWER: str = "complete"

# ─── Scenario Identifiers ────────────────────────────────────────────────────

SCENARIO_IDLE: str = "idle"
SCENARIO_TWO_SPIRAL_TRAINING: str = "two_spiral_training"
SCENARIO_XOR_CONVERGED: str = "xor_converged"
SCENARIO_EMPTY: str = "empty"
SCENARIO_ERROR_PRONE: str = "error_prone"

# ─── Default Network Configuration ───────────────────────────────────────────

DEFAULT_INPUT_SIZE: int = 2
DEFAULT_OUTPUT_SIZE: int = 1
DEFAULT_LEARNING_RATE: float = 0.01
CANDIDATE_LEARNING_RATE_MULTIPLIER: int = 10
NETWORK_CONFIG_MAX_HIDDEN_UNITS: int = 20
NETWORK_CONFIG_CANDIDATE_POOL_SIZE: int = 8
DEFAULT_CORRELATION_THRESHOLD: float = 0.01
DEFAULT_PATIENCE: int = 10
DEFAULT_CANDIDATE_EPOCHS: int = 200
DEFAULT_OUTPUT_EPOCHS: int = 200
DEFAULT_MAX_EPOCHS: int = 1000

# get_training_status / get_training_params fall back to these when no network
# config is loaded — note these differ from the build_network_config defaults.
GET_PARAMS_DEFAULT_MAX_HIDDEN_UNITS: int = 10

# Scenario-specific overrides for xor_converged and error_prone.
XOR_LEARNING_RATE: float = 0.05
XOR_INITIAL_HIDDEN_UNITS: int = 2
XOR_INITIAL_EPOCH: int = 150
ERROR_PRONE_INITIAL_HIDDEN_UNITS: int = 1
ERROR_PRONE_INITIAL_EPOCH: int = 5

# ─── Loss Curve Parameters ───────────────────────────────────────────────────

# Default ``generate_loss_curve`` arguments.
LOSS_INITIAL_DEFAULT: float = 2.5
LOSS_DECAY_DEFAULT: float = 0.05
LOSS_NOISE_SCALE: float = 0.02
LOSS_NOISE_FREQ: float = 0.7
LOSS_NOISE_DECAY: float = 0.01
LOSS_MIN: float = 0.001

# two_spiral_training scenario overrides.
LOSS_INITIAL_TWO_SPIRAL: float = 2.5
LOSS_DECAY_TWO_SPIRAL: float = 0.04

# Empty / fallback scenario overrides.
LOSS_INITIAL_EMPTY: float = 1.5
LOSS_DECAY_EMPTY: float = 0.03

# ─── Accuracy Curve Parameters ───────────────────────────────────────────────

# Default ``generate_accuracy_curve`` arguments.
ACC_MIDPOINT_DEFAULT: float = 40.0
ACC_STEEPNESS_DEFAULT: float = 0.08
ACC_CEILING_DEFAULT: float = 0.98

# two_spiral_training scenario overrides.
ACC_MIDPOINT_TWO_SPIRAL: float = 50.0
ACC_STEEPNESS_TWO_SPIRAL: float = 0.06
ACC_CEILING_TWO_SPIRAL: float = 0.96
ACC_VAL_SCALE_TWO_SPIRAL: float = 0.97

# Empty / fallback scenario overrides.
ACC_MIDPOINT_EMPTY: float = 30.0
ACC_STEEPNESS_EMPTY: float = 0.07
ACC_CEILING_EMPTY: float = 0.92
ACC_VAL_SCALE_EMPTY: float = 0.95

# ─── Validation Loss Parameters ──────────────────────────────────────────────

DEFAULT_GAP_FACTOR: float = 1.15
VAL_NOISE_SCALE: float = 0.01
VAL_NOISE_FREQ: float = 1.3

# ─── Hidden Unit Schedule (per scenario) ─────────────────────────────────────

# two_spiral_training: ``hidden_units = min(epoch // 20, 8)``
TWO_SPIRAL_HIDDEN_UNIT_INTERVAL: int = 20
TWO_SPIRAL_HIDDEN_UNIT_CAP: int = 8

# Default / empty scenario: ``hidden_units = min(epoch // 25, 5)``
DEFAULT_HIDDEN_UNIT_INTERVAL: int = 25
DEFAULT_HIDDEN_UNIT_CAP: int = 5

# Phase rotation: ``"output_training" if epoch % 20 < 15 else "candidate_training"``
TWO_SPIRAL_PHASE_CYCLE_LENGTH: int = 20
TWO_SPIRAL_PHASE_OUTPUT_PORTION: int = 15

# ─── Static Metrics for xor_converged Scenario ───────────────────────────────

XOR_CONVERGED_TRAIN_LOSS: float = 0.003
XOR_CONVERGED_VAL_LOSS: float = 0.005
XOR_CONVERGED_TRAIN_ACCURACY: float = 0.999
XOR_CONVERGED_VAL_ACCURACY: float = 0.998
XOR_CONVERGED_CORRELATION: float = 0.001
XOR_CONVERGED_HIDDEN_UNITS: int = 2

# ─── Topology Generation ─────────────────────────────────────────────────────

# Node type identifiers.
NODE_TYPE_INPUT: str = "input"
NODE_TYPE_BIAS: str = "bias"
NODE_TYPE_HIDDEN: str = "hidden"
NODE_TYPE_OUTPUT: str = "output"

# Layer type identifiers (parallel to node types).
LAYER_TYPE_INPUT: str = "input"
LAYER_TYPE_HIDDEN: str = "hidden"
LAYER_TYPE_OUTPUT: str = "output"

# Activation function names assigned by the topology builder.
INPUT_NODE_ACTIVATION: str = "linear"
BIAS_NODE_ACTIVATION: str = "constant"
HIDDEN_NODE_ACTIVATION: str = "sigmoid"
OUTPUT_NODE_ACTIVATION: str = "sigmoid"

# Default bias values for input/bias nodes.
INPUT_NODE_BIAS: float = 0.0
BIAS_NODE_BIAS: float = 1.0

# Node ID prefixes used by the topology builder.
NODE_ID_PREFIX_INPUT: str = "input_"
NODE_ID_PREFIX_HIDDEN: str = "hidden_"
NODE_ID_PREFIX_OUTPUT: str = "output_"
NODE_ID_BIAS: str = "bias_0"

# Hidden unit bias formula: ``-0.5 + h * 0.1``.
HIDDEN_BIAS_BASE: float = -0.5
HIDDEN_BIAS_INCREMENT: float = 0.1

# Hidden unit weight formula: ``0.1 * (h + 1) * (0.5 - (hash(...) % 100) / 100.0)``.
HIDDEN_WEIGHT_SCALE: float = 0.1
WEIGHT_HASH_MODULO: int = 100
WEIGHT_CENTER: float = 0.5

# Output bias formula: ``0.01 * o``.
OUTPUT_BIAS_SCALE: float = 0.01

# Output weight formula: ``0.05 * (hash(...) % 100 - 50) / 50.0``.
OUTPUT_WEIGHT_SCALE: float = 0.05

# ─── Decision Boundary Generation ────────────────────────────────────────────

DECISION_BOUNDARY_MIN: float = -1.5
DECISION_BOUNDARY_MAX: float = 1.5

# ``boundary = math.sin(angle * complexity + radius * 2.0)``
BOUNDARY_RADIUS_SCALE: float = 2.0

# ─── Dataset Input Generation ────────────────────────────────────────────────

# ``angle = 2.0 * math.pi * i / num_samples + f * 0.5``
DATASET_INPUT_ANGLE_SCALE: float = 2.0
DATASET_INPUT_PHASE_SHIFT: float = 0.5
# ``value = 1.5 * math.sin(angle) * math.cos(angle * 0.3 + f)``
DATASET_INPUT_AMPLITUDE: float = 1.5
DATASET_INPUT_FREQ_SCALE: float = 0.3

# ─── Dataset Default Sizes ───────────────────────────────────────────────────

DEFAULT_DATASET_TRAIN_SAMPLES: int = 4
DEFAULT_DATASET_FEATURES: int = 2
DEFAULT_DATASET_CLASSES: int = 2

# ─── Two-Spiral Dataset Fixture ──────────────────────────────────────────────

TWO_SPIRAL_DATASET_NAME: str = "two_spiral"
TWO_SPIRAL_GENERATOR: str = "two_spiral"
TWO_SPIRAL_N_POINTS: int = 97
TWO_SPIRAL_NOISE: float = 0.0
TWO_SPIRAL_ROTATIONS: float = 1.5
TWO_SPIRAL_TOTAL_SAMPLES: int = 194
TWO_SPIRAL_FEATURES: int = 2
TWO_SPIRAL_CLASSES: int = 2
TWO_SPIRAL_SPLIT_RATIO: float = 0.8
TWO_SPIRAL_TRAIN_SAMPLES: int = 155
TWO_SPIRAL_TEST_SAMPLES: int = 39

# ─── XOR Dataset Fixture ─────────────────────────────────────────────────────

XOR_DATASET_NAME: str = "xor"
XOR_GENERATOR: str = "xor"
XOR_N_POINTS: int = 4
XOR_NOISE: float = 0.0
XOR_TOTAL_SAMPLES: int = 4
XOR_FEATURES: int = 2
XOR_CLASSES: int = 2
XOR_SPLIT_RATIO: float = 1.0
XOR_TRAIN_SAMPLES: int = 4
XOR_TEST_SAMPLES: int = 0

# ─── Dataset Source Identifiers ──────────────────────────────────────────────

DATASET_SOURCE_GENERATOR: str = "generator"
DATASET_SOURCE_INLINE: str = "inline"
DATASET_NAME_INLINE: str = "inline"

# ─── Worker Simulation: worker-demo-01 ───────────────────────────────────────

FAKE_WORKER_1_ID: str = "worker-demo-01"
FAKE_WORKER_1_CPU_CORES: int = 8
FAKE_WORKER_1_PYTHON_VERSION: str = "3.13"
FAKE_WORKER_1_GPU: bool = False
FAKE_WORKER_1_CONNECTED_AGO_SECONDS: int = 600
FAKE_WORKER_1_HEARTBEAT_AGO_SECONDS: int = 2
FAKE_WORKER_1_TASKS_COMPLETED: int = 12
FAKE_WORKER_1_TASKS_FAILED: int = 0
FAKE_WORKER_1_HEALTH_SCORE: float = 1.0

# ─── Worker Simulation: worker-demo-02 ───────────────────────────────────────

FAKE_WORKER_2_ID: str = "worker-demo-02"
FAKE_WORKER_2_CPU_CORES: int = 4
FAKE_WORKER_2_PYTHON_VERSION: str = "3.13"
FAKE_WORKER_2_GPU: bool = True
FAKE_WORKER_2_CONNECTED_AGO_SECONDS: int = 300
FAKE_WORKER_2_HEARTBEAT_AGO_SECONDS: int = 1
FAKE_WORKER_2_TASKS_COMPLETED: int = 8
FAKE_WORKER_2_TASKS_FAILED: int = 1
FAKE_WORKER_2_HEALTH_SCORE: float = 0.8889
FAKE_WORKER_2_ACTIVE_TASK_ID: str = "task-abc"

# ─── Worker Aggregate Statistics ─────────────────────────────────────────────

FAKE_WORKERS_TOTAL: int = 2
FAKE_WORKERS_IDLE: int = 1
FAKE_WORKERS_BUSY: int = 1
FAKE_WORKERS_STALE: int = 0
FAKE_WORKERS_TOTAL_TASKS_COMPLETED: int = 20
FAKE_WORKERS_TOTAL_TASKS_FAILED: int = 1
FAKE_WORKERS_AVG_HEALTH_SCORE: float = 0.9444

# ─── Snapshot Fixtures ───────────────────────────────────────────────────────

FAKE_SNAPSHOT_1_ID: str = "snap-001"
FAKE_SNAPSHOT_1_DESCRIPTION: str = "Before candidate installation"
FAKE_SNAPSHOT_1_AGE_SECONDS: int = 300
FAKE_SNAPSHOT_1_EPOCH_OFFSET: int = 5  # ``max(0, self._epoch - 5)``
FAKE_SNAPSHOT_1_HIDDEN_UNITS: int = 0

FAKE_SNAPSHOT_2_ID: str = "snap-002"
FAKE_SNAPSHOT_2_DESCRIPTION: str = "After first hidden unit"
FAKE_SNAPSHOT_2_AGE_SECONDS: int = 60
FAKE_SNAPSHOT_2_HIDDEN_UNITS: int = 1

# ``snapshot_id = f"snap-{int(time.time())}"``
SNAPSHOT_ID_GENERATED_PREFIX: str = "snap-"

# ─── Weight Statistics Fixtures ──────────────────────────────────────────────

# Output layer parameters: 2 inputs + bias -> 1 output.
OUTPUT_WEIGHTS_BASE_PARAMS: int = 3
OUTPUT_WEIGHTS_LAYER_NAME: str = "output_weights"
OUTPUT_WEIGHTS_MEAN: float = 0.012
OUTPUT_WEIGHTS_STD: float = 0.45
OUTPUT_WEIGHTS_MIN: float = -0.89
OUTPUT_WEIGHTS_MAX: float = 0.91

# Hidden weight stat formulas.
HIDDEN_WEIGHTS_MEAN_SCALE: float = 0.01  # ``0.01 * (h + 1)``
HIDDEN_WEIGHTS_STD_BASE: float = 0.3
HIDDEN_WEIGHTS_STD_INCREMENT: float = 0.05  # ``0.3 + 0.05 * h``

# ─── Fake Async WebSocket Stream ─────────────────────────────────────────────

FAKE_WS_DEFAULT_DELAY_SECONDS: float = 0.1
