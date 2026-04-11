"""Scenario data generators for FakeCascorClient testing.

Provides pre-built scenario data for each scenario preset, including
metric curve generators, topology templates, and dataset metadata.

Project: Juniper
Sub-Project: juniper-cascor-client
Application: Testing Scenarios
Author: Paul Calnon
Version: 0.1.0
License: MIT License
"""

import math
from typing import Any, Dict, List

from juniper_cascor_client.testing.constants import (
    ACC_CEILING_DEFAULT,
    ACC_CEILING_EMPTY,
    ACC_CEILING_TWO_SPIRAL,
    ACC_MIDPOINT_DEFAULT,
    ACC_MIDPOINT_EMPTY,
    ACC_MIDPOINT_TWO_SPIRAL,
    ACC_STEEPNESS_DEFAULT,
    ACC_STEEPNESS_EMPTY,
    ACC_STEEPNESS_TWO_SPIRAL,
    ACC_VAL_SCALE_EMPTY,
    ACC_VAL_SCALE_TWO_SPIRAL,
    BIAS_NODE_ACTIVATION,
    BIAS_NODE_BIAS,
    BOUNDARY_RADIUS_SCALE,
    CANDIDATE_LEARNING_RATE_MULTIPLIER,
    DATASET_INPUT_AMPLITUDE,
    DATASET_INPUT_ANGLE_SCALE,
    DATASET_INPUT_FREQ_SCALE,
    DATASET_INPUT_PHASE_SHIFT,
    DATASET_SOURCE_GENERATOR,
    DECISION_BOUNDARY_MAX,
    DECISION_BOUNDARY_MIN,
    DEFAULT_CANDIDATE_EPOCHS,
    DEFAULT_CORRELATION_THRESHOLD,
    DEFAULT_GAP_FACTOR,
    DEFAULT_HIDDEN_UNIT_CAP,
    DEFAULT_HIDDEN_UNIT_INTERVAL,
    DEFAULT_INPUT_SIZE,
    DEFAULT_LEARNING_RATE,
    DEFAULT_MAX_EPOCHS,
    DEFAULT_OUTPUT_EPOCHS,
    DEFAULT_OUTPUT_SIZE,
    DEFAULT_PATIENCE,
    FSM_PHASE_CANDIDATE_TRAINING,
    FSM_PHASE_COMPLETE_LOWER,
    FSM_PHASE_OUTPUT_TRAINING,
    HIDDEN_BIAS_BASE,
    HIDDEN_BIAS_INCREMENT,
    HIDDEN_NODE_ACTIVATION,
    HIDDEN_WEIGHT_SCALE,
    HIDDEN_WEIGHTS_MEAN_SCALE,
    HIDDEN_WEIGHTS_STD_BASE,
    HIDDEN_WEIGHTS_STD_INCREMENT,
    INPUT_NODE_ACTIVATION,
    INPUT_NODE_BIAS,
    LAYER_TYPE_HIDDEN,
    LAYER_TYPE_INPUT,
    LAYER_TYPE_OUTPUT,
    LOSS_DECAY_DEFAULT,
    LOSS_DECAY_EMPTY,
    LOSS_DECAY_TWO_SPIRAL,
    LOSS_INITIAL_DEFAULT,
    LOSS_INITIAL_EMPTY,
    LOSS_INITIAL_TWO_SPIRAL,
    LOSS_MIN,
    LOSS_NOISE_DECAY,
    LOSS_NOISE_FREQ,
    LOSS_NOISE_SCALE,
    NETWORK_CONFIG_CANDIDATE_POOL_SIZE,
    NETWORK_CONFIG_MAX_HIDDEN_UNITS,
    NODE_ID_BIAS,
    NODE_ID_PREFIX_HIDDEN,
    NODE_ID_PREFIX_INPUT,
    NODE_ID_PREFIX_OUTPUT,
    NODE_TYPE_BIAS,
    NODE_TYPE_HIDDEN,
    NODE_TYPE_INPUT,
    NODE_TYPE_OUTPUT,
    OUTPUT_BIAS_SCALE,
    OUTPUT_NODE_ACTIVATION,
    OUTPUT_WEIGHT_SCALE,
    OUTPUT_WEIGHTS_BASE_PARAMS,
    OUTPUT_WEIGHTS_LAYER_NAME,
    OUTPUT_WEIGHTS_MAX,
    OUTPUT_WEIGHTS_MEAN,
    OUTPUT_WEIGHTS_MIN,
    OUTPUT_WEIGHTS_STD,
    SCENARIO_EMPTY,
    SCENARIO_ERROR_PRONE,
    SCENARIO_IDLE,
    SCENARIO_TWO_SPIRAL_TRAINING,
    SCENARIO_XOR_CONVERGED,
    STATE_COMPLETE,
    STATE_IDLE,
    STATE_TRAINING,
    TWO_SPIRAL_CLASSES,
    TWO_SPIRAL_DATASET_NAME,
    TWO_SPIRAL_FEATURES,
    TWO_SPIRAL_GENERATOR,
    TWO_SPIRAL_HIDDEN_UNIT_CAP,
    TWO_SPIRAL_HIDDEN_UNIT_INTERVAL,
    TWO_SPIRAL_N_POINTS,
    TWO_SPIRAL_NOISE,
    TWO_SPIRAL_PHASE_CYCLE_LENGTH,
    TWO_SPIRAL_PHASE_OUTPUT_PORTION,
    TWO_SPIRAL_ROTATIONS,
    TWO_SPIRAL_SPLIT_RATIO,
    TWO_SPIRAL_TEST_SAMPLES,
    TWO_SPIRAL_TOTAL_SAMPLES,
    TWO_SPIRAL_TRAIN_SAMPLES,
    VAL_NOISE_FREQ,
    VAL_NOISE_SCALE,
    WEIGHT_CENTER,
    WEIGHT_HASH_MODULO,
    XOR_CLASSES,
    XOR_CONVERGED_CORRELATION,
    XOR_CONVERGED_HIDDEN_UNITS,
    XOR_CONVERGED_TRAIN_ACCURACY,
    XOR_CONVERGED_TRAIN_LOSS,
    XOR_CONVERGED_VAL_ACCURACY,
    XOR_CONVERGED_VAL_LOSS,
    XOR_DATASET_NAME,
    XOR_FEATURES,
    XOR_GENERATOR,
    XOR_INITIAL_EPOCH,
    XOR_INITIAL_HIDDEN_UNITS,
    XOR_LEARNING_RATE,
    XOR_N_POINTS,
    XOR_NOISE,
    XOR_SPLIT_RATIO,
    XOR_TEST_SAMPLES,
    XOR_TOTAL_SAMPLES,
    XOR_TRAIN_SAMPLES,
)

# ─── Metric Curve Generators ────────────────────────────────────────────────


def generate_loss_curve(epoch: int, initial_loss: float = LOSS_INITIAL_DEFAULT, decay_rate: float = LOSS_DECAY_DEFAULT, noise_scale: float = LOSS_NOISE_SCALE) -> float:
    """Generate a realistic training loss value using exponential decay.

    Args:
        epoch: Current epoch number (0-based).
        initial_loss: Starting loss value.
        decay_rate: Exponential decay rate (higher = faster convergence).
        noise_scale: Scale of sinusoidal noise added for realism.

    Returns:
        Loss value at the given epoch.
    """
    base_loss = initial_loss * math.exp(-decay_rate * epoch)
    noise = noise_scale * math.sin(epoch * LOSS_NOISE_FREQ) * math.exp(-LOSS_NOISE_DECAY * epoch)
    return max(base_loss + noise, LOSS_MIN)


def generate_accuracy_curve(epoch: int, midpoint: float = ACC_MIDPOINT_DEFAULT, steepness: float = ACC_STEEPNESS_DEFAULT, ceiling: float = ACC_CEILING_DEFAULT) -> float:
    """Generate a realistic training accuracy value using a sigmoid curve.

    Args:
        epoch: Current epoch number (0-based).
        midpoint: Epoch at which accuracy reaches ~50% of its ceiling.
        steepness: Controls how quickly accuracy rises.
        ceiling: Maximum achievable accuracy.

    Returns:
        Accuracy value at the given epoch (0.0 to ceiling).
    """
    return ceiling / (1.0 + math.exp(-steepness * (epoch - midpoint)))


def generate_validation_loss(epoch: int, train_loss: float, gap_factor: float = DEFAULT_GAP_FACTOR) -> float:
    """Generate validation loss slightly above training loss.

    Args:
        epoch: Current epoch number.
        train_loss: Corresponding training loss.
        gap_factor: Multiplier for the gap between validation and training loss.

    Returns:
        Validation loss value.
    """
    gap = (gap_factor - 1.0) * train_loss
    epoch_noise = VAL_NOISE_SCALE * math.sin(epoch * VAL_NOISE_FREQ)
    return train_loss + gap + epoch_noise


def generate_metrics_snapshot(epoch: int, scenario: str = SCENARIO_TWO_SPIRAL_TRAINING) -> Dict[str, Any]:
    """Generate a complete metrics snapshot for a given epoch and scenario.

    Args:
        epoch: Current epoch number.
        scenario: Scenario name determining curve parameters.

    Returns:
        Metrics dictionary with train_loss, val_loss, train_accuracy, val_accuracy, epoch.
    """
    if scenario == SCENARIO_XOR_CONVERGED:
        return {
            "epoch": epoch,
            "train_loss": XOR_CONVERGED_TRAIN_LOSS,
            "val_loss": XOR_CONVERGED_VAL_LOSS,
            "train_accuracy": XOR_CONVERGED_TRAIN_ACCURACY,
            "val_accuracy": XOR_CONVERGED_VAL_ACCURACY,
            "correlation": XOR_CONVERGED_CORRELATION,
            "hidden_units": XOR_CONVERGED_HIDDEN_UNITS,
            "phase": FSM_PHASE_COMPLETE_LOWER,
        }

    if scenario == SCENARIO_TWO_SPIRAL_TRAINING:
        train_loss = generate_loss_curve(epoch, initial_loss=LOSS_INITIAL_TWO_SPIRAL, decay_rate=LOSS_DECAY_TWO_SPIRAL)
        val_loss = generate_validation_loss(epoch, train_loss)
        train_acc = generate_accuracy_curve(epoch, midpoint=ACC_MIDPOINT_TWO_SPIRAL, steepness=ACC_STEEPNESS_TWO_SPIRAL, ceiling=ACC_CEILING_TWO_SPIRAL)
        val_acc = train_acc * ACC_VAL_SCALE_TWO_SPIRAL
        hidden_units = min(epoch // TWO_SPIRAL_HIDDEN_UNIT_INTERVAL, TWO_SPIRAL_HIDDEN_UNIT_CAP)
        phase = FSM_PHASE_OUTPUT_TRAINING if epoch % TWO_SPIRAL_PHASE_CYCLE_LENGTH < TWO_SPIRAL_PHASE_OUTPUT_PORTION else FSM_PHASE_CANDIDATE_TRAINING
    else:
        train_loss = generate_loss_curve(epoch, initial_loss=LOSS_INITIAL_EMPTY, decay_rate=LOSS_DECAY_EMPTY)
        val_loss = generate_validation_loss(epoch, train_loss)
        train_acc = generate_accuracy_curve(epoch, midpoint=ACC_MIDPOINT_EMPTY, steepness=ACC_STEEPNESS_EMPTY, ceiling=ACC_CEILING_EMPTY)
        val_acc = train_acc * ACC_VAL_SCALE_EMPTY
        hidden_units = min(epoch // DEFAULT_HIDDEN_UNIT_INTERVAL, DEFAULT_HIDDEN_UNIT_CAP)
        phase = FSM_PHASE_OUTPUT_TRAINING

    return {
        "epoch": epoch,
        "train_loss": round(train_loss, 6),
        "val_loss": round(val_loss, 6),
        "train_accuracy": round(train_acc, 6),
        "val_accuracy": round(val_acc, 6),
        "correlation": round(max(0.0, 1.0 - train_acc) * 0.5, 6),
        "hidden_units": hidden_units,
        "phase": phase,
    }


# ─── Topology Templates ─────────────────────────────────────────────────────


def build_cascor_topology(
    input_size: int = DEFAULT_INPUT_SIZE,
    output_size: int = DEFAULT_OUTPUT_SIZE,
    hidden_units: int = 0,
) -> Dict[str, Any]:
    """Build a CasCor network topology with the given layer sizes.

    Creates a topology dictionary representing a Cascade Correlation network
    with input nodes, output nodes, and hidden units added during cascading.

    Args:
        input_size: Number of input features.
        output_size: Number of output nodes.
        hidden_units: Number of cascade hidden units added so far.

    Returns:
        Topology dictionary with layers, nodes, and connections lists.
    """
    layers: List[Dict[str, Any]] = []
    nodes: List[Dict[str, Any]] = []
    connections: List[Dict[str, Any]] = []

    # Input layer
    input_layer_nodes = []
    for i in range(input_size):
        node_id = f"{NODE_ID_PREFIX_INPUT}{i}"
        nodes.append(
            {
                "id": node_id,
                "type": NODE_TYPE_INPUT,
                "layer": 0,
                "activation": INPUT_NODE_ACTIVATION,
                "bias": INPUT_NODE_BIAS,
            }
        )
        input_layer_nodes.append(node_id)

    # Bias node
    bias_id = NODE_ID_BIAS
    nodes.append(
        {
            "id": bias_id,
            "type": NODE_TYPE_BIAS,
            "layer": 0,
            "activation": BIAS_NODE_ACTIVATION,
            "bias": BIAS_NODE_BIAS,
        }
    )
    input_layer_nodes.append(bias_id)

    layers.append(
        {
            "index": 0,
            "type": LAYER_TYPE_INPUT,
            "nodes": input_layer_nodes,
        }
    )

    # Hidden units (cascade)
    previous_node_ids = list(input_layer_nodes)
    for h in range(hidden_units):
        hidden_id = f"{NODE_ID_PREFIX_HIDDEN}{h}"
        layer_index = h + 1
        nodes.append(
            {
                "id": hidden_id,
                "type": NODE_TYPE_HIDDEN,
                "layer": layer_index,
                "activation": HIDDEN_NODE_ACTIVATION,
                "bias": round(HIDDEN_BIAS_BASE + h * HIDDEN_BIAS_INCREMENT, 4),
            }
        )
        layers.append(
            {
                "index": layer_index,
                "type": LAYER_TYPE_HIDDEN,
                "nodes": [hidden_id],
            }
        )

        # Each hidden unit connects from ALL previous nodes (cascade property)
        for src_id in previous_node_ids:
            connections.append(
                {
                    "from": src_id,
                    "to": hidden_id,
                    "weight": round(HIDDEN_WEIGHT_SCALE * (h + 1) * (WEIGHT_CENTER - (hash(src_id + hidden_id) % WEIGHT_HASH_MODULO) / float(WEIGHT_HASH_MODULO)), 6),
                    "frozen": True,
                }
            )

        previous_node_ids.append(hidden_id)

    # Output layer
    output_layer_index = hidden_units + 1
    output_layer_nodes = []
    for o in range(output_size):
        output_id = f"{NODE_ID_PREFIX_OUTPUT}{o}"
        nodes.append(
            {
                "id": output_id,
                "type": NODE_TYPE_OUTPUT,
                "layer": output_layer_index,
                "activation": OUTPUT_NODE_ACTIVATION,
                "bias": round(OUTPUT_BIAS_SCALE * o, 4),
            }
        )
        output_layer_nodes.append(output_id)

        # Output connects from all previous nodes
        for src_id in previous_node_ids:
            connections.append(
                {
                    "from": src_id,
                    "to": output_id,
                    "weight": round(OUTPUT_WEIGHT_SCALE * (hash(src_id + output_id) % WEIGHT_HASH_MODULO - WEIGHT_HASH_MODULO // 2) / float(WEIGHT_HASH_MODULO // 2), 6),
                    "frozen": False,
                }
            )

    layers.append(
        {
            "index": output_layer_index,
            "type": LAYER_TYPE_OUTPUT,
            "nodes": output_layer_nodes,
        }
    )

    return {
        "layers": layers,
        "nodes": nodes,
        "connections": connections,
        "total_nodes": len(nodes),
        "total_connections": len(connections),
        "input_size": input_size,
        "output_size": output_size,
        "hidden_units": hidden_units,
    }


# ─── Network Configuration Templates ────────────────────────────────────────


def build_network_config(
    input_size: int = DEFAULT_INPUT_SIZE,
    output_size: int = DEFAULT_OUTPUT_SIZE,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    **overrides: Any,
) -> Dict[str, Any]:
    """Build a default network configuration dictionary.

    Args:
        input_size: Number of input features.
        output_size: Number of output nodes.
        learning_rate: Output layer learning rate.
        **overrides: Any additional overrides to merge in.

    Returns:
        Network configuration dictionary.
    """
    config = {
        "input_size": input_size,
        "output_size": output_size,
        "learning_rate": learning_rate,
        "candidate_learning_rate": learning_rate * CANDIDATE_LEARNING_RATE_MULTIPLIER,
        "max_hidden_units": NETWORK_CONFIG_MAX_HIDDEN_UNITS,
        "candidate_pool_size": NETWORK_CONFIG_CANDIDATE_POOL_SIZE,
        "correlation_threshold": DEFAULT_CORRELATION_THRESHOLD,
        "patience": DEFAULT_PATIENCE,
        "candidate_epochs": DEFAULT_CANDIDATE_EPOCHS,
        "output_epochs": DEFAULT_OUTPUT_EPOCHS,
        "epochs_max": DEFAULT_MAX_EPOCHS,
    }
    config.update(overrides)
    return config


# ─── Dataset Templates ───────────────────────────────────────────────────────

TWO_SPIRAL_DATASET: Dict[str, Any] = {
    "name": TWO_SPIRAL_DATASET_NAME,
    "source": DATASET_SOURCE_GENERATOR,
    "generator": TWO_SPIRAL_GENERATOR,
    "params": {"n_points": TWO_SPIRAL_N_POINTS, "noise": TWO_SPIRAL_NOISE, "rotations": TWO_SPIRAL_ROTATIONS},
    "samples": TWO_SPIRAL_TOTAL_SAMPLES,
    "features": TWO_SPIRAL_FEATURES,
    "classes": TWO_SPIRAL_CLASSES,
    "split_ratio": TWO_SPIRAL_SPLIT_RATIO,
    "train_samples": TWO_SPIRAL_TRAIN_SAMPLES,
    "test_samples": TWO_SPIRAL_TEST_SAMPLES,
}

XOR_DATASET: Dict[str, Any] = {
    "name": XOR_DATASET_NAME,
    "source": DATASET_SOURCE_GENERATOR,
    "generator": XOR_GENERATOR,
    "params": {"n_points": XOR_N_POINTS, "noise": XOR_NOISE},
    "samples": XOR_TOTAL_SAMPLES,
    "features": XOR_FEATURES,
    "classes": XOR_CLASSES,
    "split_ratio": XOR_SPLIT_RATIO,
    "train_samples": XOR_TRAIN_SAMPLES,
    "test_samples": XOR_TEST_SAMPLES,
}

EMPTY_DATASET: Dict[str, Any] = {}


# ─── Pre-Built Scenario Data ────────────────────────────────────────────────

SCENARIO_DEFAULTS: Dict[str, Dict[str, Any]] = {
    SCENARIO_IDLE: {
        "initial_state": STATE_IDLE,
        "network_config": None,
        "dataset": None,
        "topology": None,
        "initial_epoch": 0,
        "description": "Ready for network creation. No network loaded.",
    },
    SCENARIO_TWO_SPIRAL_TRAINING: {
        "initial_state": STATE_TRAINING,
        "network_config": build_network_config(input_size=DEFAULT_INPUT_SIZE, output_size=DEFAULT_OUTPUT_SIZE, learning_rate=DEFAULT_LEARNING_RATE),
        "dataset": TWO_SPIRAL_DATASET,
        "topology": build_cascor_topology(input_size=DEFAULT_INPUT_SIZE, output_size=DEFAULT_OUTPUT_SIZE, hidden_units=0),
        "initial_epoch": 0,
        "description": "Two-spiral dataset training in progress with realistic metric curves.",
    },
    SCENARIO_XOR_CONVERGED: {
        "initial_state": STATE_COMPLETE,
        "network_config": build_network_config(input_size=DEFAULT_INPUT_SIZE, output_size=DEFAULT_OUTPUT_SIZE, learning_rate=XOR_LEARNING_RATE),
        "dataset": XOR_DATASET,
        "topology": build_cascor_topology(input_size=DEFAULT_INPUT_SIZE, output_size=DEFAULT_OUTPUT_SIZE, hidden_units=XOR_INITIAL_HIDDEN_UNITS),
        "initial_epoch": XOR_INITIAL_EPOCH,
        "description": "Fully trained XOR network. Static converged metrics.",
    },
    SCENARIO_EMPTY: {
        "initial_state": STATE_IDLE,
        "network_config": None,
        "dataset": None,
        "topology": None,
        "initial_epoch": 0,
        "description": "Minimal responses for negative testing.",
    },
    SCENARIO_ERROR_PRONE: {
        "initial_state": STATE_IDLE,
        "network_config": build_network_config(input_size=DEFAULT_INPUT_SIZE, output_size=DEFAULT_OUTPUT_SIZE, learning_rate=DEFAULT_LEARNING_RATE),
        "dataset": TWO_SPIRAL_DATASET,
        "topology": build_cascor_topology(input_size=DEFAULT_INPUT_SIZE, output_size=DEFAULT_OUTPUT_SIZE, hidden_units=1),
        "initial_epoch": 5,
        "description": "Raises exceptions on approximately 10% of calls.",
    },
}


def get_scenario_data(scenario: str) -> Dict[str, Any]:
    """Get the pre-built scenario data for a given scenario name.

    Args:
        scenario: Scenario preset name.

    Returns:
        Dictionary of scenario defaults.

    Raises:
        ValueError: If scenario name is not recognized.
    """
    if scenario not in SCENARIO_DEFAULTS:
        valid = ", ".join(sorted(SCENARIO_DEFAULTS.keys()))
        raise ValueError(f"Unknown scenario '{scenario}'. Valid scenarios: {valid}")
    return SCENARIO_DEFAULTS[scenario]


def generate_decision_boundary(
    input_size: int = DEFAULT_INPUT_SIZE,
    resolution: int = 50,
    hidden_units: int = 0,
) -> Dict[str, Any]:
    """Generate synthetic decision boundary grid data.

    Creates a resolution x resolution grid over [-1.5, 1.5] with
    synthetic predictions based on a simple distance-based model.

    The response format matches the real juniper-cascor API
    (``/v1/decision-boundary``): 2D meshgrid arrays for ``grid_x``
    and ``grid_y``, and a 2D array of integer class predictions.

    Args:
        input_size: Number of input dimensions (must be 2 for visualization).
        resolution: Grid resolution per axis.
        hidden_units: Number of hidden units (affects decision boundary complexity).

    Returns:
        Dictionary with grid_x, grid_y (2D meshgrids), predictions (2D
        integer class indices), resolution, x_range, and y_range fields.
    """
    x_min, x_max = DECISION_BOUNDARY_MIN, DECISION_BOUNDARY_MAX
    y_min, y_max = DECISION_BOUNDARY_MIN, DECISION_BOUNDARY_MAX

    # Build 1D axis arrays
    xx = [round(x_min + i * (x_max - x_min) / (resolution - 1), 6) for i in range(resolution)]
    yy = [round(y_min + j * (y_max - y_min) / (resolution - 1), 6) for j in range(resolution)]

    # Build 2D meshgrid arrays (matching np.meshgrid(xx, yy) output)
    grid_x: List[List[float]] = []
    grid_y: List[List[float]] = []
    for j in range(resolution):
        grid_x.append(list(xx))  # each row is a copy of xx
        grid_y.append([yy[j]] * resolution)  # each row is constant y

    # Generate 2D predictions as integer class indices (matching argmax output)
    complexity = max(1, hidden_units)
    predictions: List[List[int]] = []
    for j in range(resolution):
        row: List[int] = []
        for i in range(resolution):
            x = xx[i]
            y = yy[j]
            angle = math.atan2(y, x)
            radius = math.sqrt(x * x + y * y)
            boundary = math.sin(angle * complexity + radius * BOUNDARY_RADIUS_SCALE)
            # Threshold at 0 to produce integer class index (0 or 1)
            row.append(1 if boundary > 0 else 0)
        predictions.append(row)

    return {
        "grid_x": grid_x,
        "grid_y": grid_y,
        "predictions": predictions,
        "resolution": resolution,
        "x_range": [x_min, x_max],
        "y_range": [y_min, y_max],
    }


def generate_dataset_inputs(num_samples: int, num_features: int) -> List[List[float]]:
    """Generate deterministic synthetic dataset input arrays.

    Uses sin/cos arithmetic seeded on sample index for reproducible results.
    Values are distributed in [-1.5, 1.5] matching decision boundary grid range.

    Args:
        num_samples: Number of data points to generate.
        num_features: Number of input features per sample.

    Returns:
        2D list of shape (num_samples, num_features).
    """
    inputs: List[List[float]] = []
    for i in range(num_samples):
        row: List[float] = []
        for f in range(num_features):
            angle = DATASET_INPUT_ANGLE_SCALE * math.pi * i / max(num_samples, 1) + f * DATASET_INPUT_PHASE_SHIFT
            value = DATASET_INPUT_AMPLITUDE * math.sin(angle) * math.cos(angle * DATASET_INPUT_FREQ_SCALE + f)
            row.append(round(value, 6))
        inputs.append(row)
    return inputs


def generate_dataset_targets(num_samples: int, num_classes: int) -> List[List[float]]:
    """Generate deterministic synthetic dataset target arrays.

    For binary classification (num_classes <= 2), returns single-element
    vectors [[0.0], [1.0], ...]. For multiclass, returns one-hot vectors.

    Args:
        num_samples: Number of data points.
        num_classes: Number of output classes.

    Returns:
        2D list of shape (num_samples, output_size) where output_size
        is 1 for binary or num_classes for multiclass.
    """
    targets: List[List[float]] = []
    if num_classes <= 2:
        for i in range(num_samples):
            label = 1.0 if (i % 2 == 0) else 0.0
            targets.append([label])
    else:
        for i in range(num_samples):
            one_hot = [0.0] * num_classes
            one_hot[i % num_classes] = 1.0
            targets.append(one_hot)
    return targets


def generate_weight_statistics(hidden_units: int = 0) -> Dict[str, Any]:
    """Generate synthetic network weight statistics.

    Args:
        hidden_units: Number of hidden units in the network.

    Returns:
        Dictionary with weight statistics per layer.
    """
    stats: Dict[str, Any] = {
        "total_parameters": 0,
        "layers": [],
    }

    total_params = 0

    # Input-to-output weights
    base_params = OUTPUT_WEIGHTS_BASE_PARAMS  # 2 inputs + bias -> 1 output
    total_params += base_params
    stats["layers"].append(
        {
            "name": OUTPUT_WEIGHTS_LAYER_NAME,
            "parameters": base_params,
            "mean": OUTPUT_WEIGHTS_MEAN,
            "std": OUTPUT_WEIGHTS_STD,
            "min": OUTPUT_WEIGHTS_MIN,
            "max": OUTPUT_WEIGHTS_MAX,
            "l2_norm": round(OUTPUT_WEIGHTS_STD * math.sqrt(base_params), 4),
        }
    )

    for h in range(hidden_units):
        # Each hidden unit receives from all prior nodes
        n_inputs = OUTPUT_WEIGHTS_BASE_PARAMS + h  # 2 inputs + bias + previous hidden units
        total_params += n_inputs
        std_val = round(HIDDEN_WEIGHTS_STD_BASE + HIDDEN_WEIGHTS_STD_INCREMENT * h, 4)
        stats["layers"].append(
            {
                "name": f"{NODE_ID_PREFIX_HIDDEN}{h}_weights",
                "parameters": n_inputs,
                "mean": round(HIDDEN_WEIGHTS_MEAN_SCALE * (h + 1), 4),
                "std": std_val,
                "min": round(-2.0 * std_val, 4),
                "max": round(2.0 * std_val, 4),
                "l2_norm": round(std_val * math.sqrt(n_inputs), 4),
            }
        )

    stats["total_parameters"] = total_params
    return stats
