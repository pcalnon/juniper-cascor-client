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


# ─── Metric Curve Generators ────────────────────────────────────────────────

def generate_loss_curve(epoch: int, initial_loss: float = 2.5, decay_rate: float = 0.05, noise_scale: float = 0.02) -> float:
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
    noise = noise_scale * math.sin(epoch * 0.7) * math.exp(-0.01 * epoch)
    return max(base_loss + noise, 0.001)


def generate_accuracy_curve(epoch: int, midpoint: float = 40.0, steepness: float = 0.08, ceiling: float = 0.98) -> float:
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


def generate_validation_loss(epoch: int, train_loss: float, gap_factor: float = 1.15) -> float:
    """Generate validation loss slightly above training loss.

    Args:
        epoch: Current epoch number.
        train_loss: Corresponding training loss.
        gap_factor: Multiplier for the gap between validation and training loss.

    Returns:
        Validation loss value.
    """
    gap = (gap_factor - 1.0) * train_loss
    epoch_noise = 0.01 * math.sin(epoch * 1.3)
    return train_loss + gap + epoch_noise


def generate_metrics_snapshot(epoch: int, scenario: str = "two_spiral_training") -> Dict[str, Any]:
    """Generate a complete metrics snapshot for a given epoch and scenario.

    Args:
        epoch: Current epoch number.
        scenario: Scenario name determining curve parameters.

    Returns:
        Metrics dictionary with train_loss, val_loss, train_accuracy, val_accuracy, epoch.
    """
    if scenario == "xor_converged":
        return {
            "epoch": epoch,
            "train_loss": 0.003,
            "val_loss": 0.005,
            "train_accuracy": 0.999,
            "val_accuracy": 0.998,
            "correlation": 0.001,
            "hidden_units": 2,
            "phase": "complete",
        }

    if scenario == "two_spiral_training":
        train_loss = generate_loss_curve(epoch, initial_loss=2.5, decay_rate=0.04)
        val_loss = generate_validation_loss(epoch, train_loss)
        train_acc = generate_accuracy_curve(epoch, midpoint=50.0, steepness=0.06, ceiling=0.96)
        val_acc = train_acc * 0.97
        hidden_units = min(epoch // 20, 8)
        phase = "output_training" if epoch % 20 < 15 else "candidate_training"
    else:
        train_loss = generate_loss_curve(epoch, initial_loss=1.5, decay_rate=0.03)
        val_loss = generate_validation_loss(epoch, train_loss)
        train_acc = generate_accuracy_curve(epoch, midpoint=30.0, steepness=0.07, ceiling=0.92)
        val_acc = train_acc * 0.95
        hidden_units = min(epoch // 25, 5)
        phase = "output_training"

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
    input_size: int = 2,
    output_size: int = 1,
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
        node_id = f"input_{i}"
        nodes.append({
            "id": node_id,
            "type": "input",
            "layer": 0,
            "activation": "linear",
            "bias": 0.0,
        })
        input_layer_nodes.append(node_id)

    # Bias node
    bias_id = "bias_0"
    nodes.append({
        "id": bias_id,
        "type": "bias",
        "layer": 0,
        "activation": "constant",
        "bias": 1.0,
    })
    input_layer_nodes.append(bias_id)

    layers.append({
        "index": 0,
        "type": "input",
        "nodes": input_layer_nodes,
    })

    # Hidden units (cascade)
    previous_node_ids = list(input_layer_nodes)
    for h in range(hidden_units):
        hidden_id = f"hidden_{h}"
        layer_index = h + 1
        nodes.append({
            "id": hidden_id,
            "type": "hidden",
            "layer": layer_index,
            "activation": "sigmoid",
            "bias": round(-0.5 + h * 0.1, 4),
        })
        layers.append({
            "index": layer_index,
            "type": "hidden",
            "nodes": [hidden_id],
        })

        # Each hidden unit connects from ALL previous nodes (cascade property)
        for src_id in previous_node_ids:
            connections.append({
                "from": src_id,
                "to": hidden_id,
                "weight": round(0.1 * (h + 1) * (0.5 - (hash(src_id + hidden_id) % 100) / 100.0), 6),
                "frozen": True,
            })

        previous_node_ids.append(hidden_id)

    # Output layer
    output_layer_index = hidden_units + 1
    output_layer_nodes = []
    for o in range(output_size):
        output_id = f"output_{o}"
        nodes.append({
            "id": output_id,
            "type": "output",
            "layer": output_layer_index,
            "activation": "sigmoid",
            "bias": round(0.01 * o, 4),
        })
        output_layer_nodes.append(output_id)

        # Output connects from all previous nodes
        for src_id in previous_node_ids:
            connections.append({
                "from": src_id,
                "to": output_id,
                "weight": round(0.05 * (hash(src_id + output_id) % 100 - 50) / 50.0, 6),
                "frozen": False,
            })

    layers.append({
        "index": output_layer_index,
        "type": "output",
        "nodes": output_layer_nodes,
    })

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
    input_size: int = 2,
    output_size: int = 1,
    learning_rate: float = 0.01,
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
        "candidate_learning_rate": learning_rate * 10,
        "max_hidden_units": 20,
        "candidate_pool_size": 8,
        "correlation_threshold": 0.01,
        "patience": 10,
        "candidate_epochs": 200,
        "output_epochs": 200,
        "epochs_max": 1000,
    }
    config.update(overrides)
    return config


# ─── Dataset Templates ───────────────────────────────────────────────────────

TWO_SPIRAL_DATASET: Dict[str, Any] = {
    "name": "two_spiral",
    "source": "generator",
    "generator": "two_spiral",
    "params": {"n_points": 97, "noise": 0.0, "rotations": 1.5},
    "samples": 194,
    "features": 2,
    "classes": 2,
    "split_ratio": 0.8,
    "train_samples": 155,
    "test_samples": 39,
}

XOR_DATASET: Dict[str, Any] = {
    "name": "xor",
    "source": "generator",
    "generator": "xor",
    "params": {"n_points": 4, "noise": 0.0},
    "samples": 4,
    "features": 2,
    "classes": 2,
    "split_ratio": 1.0,
    "train_samples": 4,
    "test_samples": 0,
}

EMPTY_DATASET: Dict[str, Any] = {}


# ─── Pre-Built Scenario Data ────────────────────────────────────────────────

SCENARIO_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "idle": {
        "initial_state": "idle",
        "network_config": None,
        "dataset": None,
        "topology": None,
        "initial_epoch": 0,
        "description": "Ready for network creation. No network loaded.",
    },
    "two_spiral_training": {
        "initial_state": "training",
        "network_config": build_network_config(input_size=2, output_size=1, learning_rate=0.01),
        "dataset": TWO_SPIRAL_DATASET,
        "topology": build_cascor_topology(input_size=2, output_size=1, hidden_units=0),
        "initial_epoch": 0,
        "description": "Two-spiral dataset training in progress with realistic metric curves.",
    },
    "xor_converged": {
        "initial_state": "complete",
        "network_config": build_network_config(input_size=2, output_size=1, learning_rate=0.05),
        "dataset": XOR_DATASET,
        "topology": build_cascor_topology(input_size=2, output_size=1, hidden_units=2),
        "initial_epoch": 150,
        "description": "Fully trained XOR network. Static converged metrics.",
    },
    "empty": {
        "initial_state": "idle",
        "network_config": None,
        "dataset": None,
        "topology": None,
        "initial_epoch": 0,
        "description": "Minimal responses for negative testing.",
    },
    "error_prone": {
        "initial_state": "idle",
        "network_config": build_network_config(input_size=2, output_size=1, learning_rate=0.01),
        "dataset": TWO_SPIRAL_DATASET,
        "topology": build_cascor_topology(input_size=2, output_size=1, hidden_units=1),
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
    input_size: int = 2,
    resolution: int = 50,
    hidden_units: int = 0,
) -> Dict[str, Any]:
    """Generate synthetic decision boundary grid data.

    Creates a resolution x resolution grid over [-1.5, 1.5] with
    synthetic predictions based on a simple distance-based model.

    Args:
        input_size: Number of input dimensions (must be 2 for visualization).
        resolution: Grid resolution per axis.
        hidden_units: Number of hidden units (affects decision boundary complexity).

    Returns:
        Dictionary with x_grid, y_grid, predictions, and resolution fields.
    """
    x_min, x_max = -1.5, 1.5
    y_min, y_max = -1.5, 1.5
    x_step = (x_max - x_min) / (resolution - 1)
    y_step = (y_max - y_min) / (resolution - 1)

    x_grid: List[float] = []
    y_grid: List[float] = []
    predictions: List[float] = []

    for i in range(resolution):
        x = x_min + i * x_step
        x_grid.append(round(x, 6))

    for j in range(resolution):
        y = y_min + j * y_step
        y_grid.append(round(y, 6))

    # Generate predictions based on a synthetic nonlinear boundary
    # More hidden units -> more complex boundary
    complexity = max(1, hidden_units)
    for j in range(resolution):
        y = y_min + j * y_step
        for i in range(resolution):
            x = x_min + i * x_step
            # Spiral-inspired decision: angle + radius modulation
            angle = math.atan2(y, x)
            radius = math.sqrt(x * x + y * y)
            boundary = math.sin(angle * complexity + radius * 2.0)
            prediction = 1.0 / (1.0 + math.exp(-5.0 * boundary))
            predictions.append(round(prediction, 6))

    return {
        "x_grid": x_grid,
        "y_grid": y_grid,
        "predictions": predictions,
        "resolution": resolution,
        "x_range": [x_min, x_max],
        "y_range": [y_min, y_max],
    }


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
    base_params = 3  # 2 inputs + bias -> 1 output
    total_params += base_params
    stats["layers"].append({
        "name": "output_weights",
        "parameters": base_params,
        "mean": 0.012,
        "std": 0.45,
        "min": -0.89,
        "max": 0.91,
        "l2_norm": round(0.45 * math.sqrt(base_params), 4),
    })

    for h in range(hidden_units):
        # Each hidden unit receives from all prior nodes
        n_inputs = 3 + h  # 2 inputs + bias + previous hidden units
        total_params += n_inputs
        std_val = round(0.3 + 0.05 * h, 4)
        stats["layers"].append({
            "name": f"hidden_{h}_weights",
            "parameters": n_inputs,
            "mean": round(0.01 * (h + 1), 4),
            "std": std_val,
            "min": round(-2.0 * std_val, 4),
            "max": round(2.0 * std_val, 4),
            "l2_norm": round(std_val * math.sqrt(n_inputs), 4),
        })

    stats["total_parameters"] = total_params
    return stats
