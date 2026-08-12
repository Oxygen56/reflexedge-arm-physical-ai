#!/usr/bin/env python3
"""Train and quantize the deterministic ReflexEdge risk model."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path


def load_dataset(path: Path) -> tuple[list[list[float]], list[int]]:
    features: list[list[float]] = []
    labels: list[int] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        feature_names = sorted(name for name in (reader.fieldnames or []) if name.startswith("f"))
        for row in reader:
            features.append([float(row[name]) for name in feature_names])
            labels.append(int(row["label"]))
    if not features:
        raise ValueError(f"empty dataset: {path}")
    return features, labels


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 60.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(value, -60.0))
    return z / (1.0 + z)


def train(features: list[list[float]], labels: list[int], seed: int) -> tuple[list[float], float]:
    width = len(features[0])
    weights = [0.0] * width
    positives = max(1, sum(labels))
    negatives = max(1, len(labels) - positives)
    positive_weight = len(labels) / (2.0 * positives)
    negative_weight = len(labels) / (2.0 * negatives)
    indices = list(range(len(labels)))
    rng = random.Random(seed)
    bias = math.log(positives / negatives)
    for epoch in range(22):
        rng.shuffle(indices)
        learning_rate = 0.12 / math.sqrt(epoch + 1.0)
        regularization = 1e-5
        for index in indices:
            row = features[index]
            label = labels[index]
            score = bias + sum(weight * value for weight, value in zip(weights, row))
            probability = sigmoid(score)
            class_weight = positive_weight if label else negative_weight
            error = (probability - label) * class_weight
            bias -= learning_rate * error
            for column, value in enumerate(row):
                weights[column] -= learning_rate * (error * value + regularization * weights[column])
    return weights, bias


def quantize(weights: list[float]) -> tuple[list[int], float]:
    maximum = max(abs(weight) for weight in weights) or 1.0
    scale = maximum / 127.0
    return [max(-127, min(127, round(weight / scale))) for weight in weights], scale


def predict_float(row: list[float], weights: list[float], bias: float) -> float:
    return sigmoid(bias + sum(weight * value for weight, value in zip(weights, row)))


def float_logit(row: list[float], weights: list[float], bias: float) -> float:
    return bias + sum(weight * value for weight, value in zip(weights, row))


def int8_logit(row: list[float], qweights: list[int], weight_scale: float, bias: float) -> float:
    qfeatures = [max(0, min(127, round(value * 127.0))) for value in row]
    dot = sum(value * weight for value, weight in zip(qfeatures, qweights))
    return bias + dot * weight_scale / 127.0


def predict_int8(
    row: list[float], qweights: list[int], weight_scale: float, bias: float, safety_bias: float
) -> float:
    return sigmoid(int8_logit(row, qweights, weight_scale, bias) + safety_bias)


def metrics(probabilities: list[float], labels: list[int], threshold: float) -> dict[str, float | int]:
    tp = fp = tn = fn = 0
    for probability, label in zip(probabilities, labels):
        prediction = int(probability >= threshold)
        tp += int(prediction == 1 and label == 1)
        fp += int(prediction == 1 and label == 0)
        tn += int(prediction == 0 and label == 0)
        fn += int(prediction == 0 and label == 1)
    accuracy = (tp + tn) / max(1, len(labels))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "rows": len(labels),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def action(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "BRAKE"
    if probability >= threshold * 0.62:
        return "HOLD"
    return "GO"


def compare_actions(
    float_probabilities: list[float],
    int8_probabilities: list[float],
    labels: list[int],
    threshold: float,
) -> dict[str, int]:
    float_actions = [action(probability, threshold) for probability in float_probabilities]
    int8_actions = [action(probability, threshold) for probability in int8_probabilities]
    float_brakes = [value == "BRAKE" for value in float_actions]
    int8_brakes = [value == "BRAKE" for value in int8_actions]
    return {
        "float_vs_int8_action_disagreements": sum(
            left != right for left, right in zip(float_actions, int8_actions)
        ),
        "float_vs_int8_brake_decision_disagreements": sum(
            left != right for left, right in zip(float_brakes, int8_brakes)
        ),
        "int8_brake_false_negative_disagreements_vs_float": sum(
            left and not right for left, right in zip(float_brakes, int8_brakes)
        ),
        "int8_additional_brake_decisions_vs_float": sum(
            not left and right for left, right in zip(float_brakes, int8_brakes)
        ),
        "additional_false_negatives_vs_float": sum(
            label == 1 and left and not right
            for label, left, right in zip(labels, float_brakes, int8_brakes)
        ),
    }


def choose_threshold(probabilities: list[float], labels: list[int]) -> tuple[float, dict[str, float | int]]:
    best_threshold = 0.5
    best_metrics = metrics(probabilities, labels, best_threshold)
    best_key = (-1.0, -1.0, -1.0)
    for step in range(120, 841, 5):
        threshold = step / 1000.0
        current = metrics(probabilities, labels, threshold)
        recall = float(current["recall"])
        precision = float(current["precision"])
        f2 = 5 * precision * recall / max(1e-12, 4 * precision + recall)
        key = (f2, recall, float(current["accuracy"]))
        if key > best_key:
            best_threshold = threshold
            best_metrics = current
            best_key = key
    return best_threshold, best_metrics


def write_header(
    path: Path,
    weights: list[float],
    qweights: list[int],
    weight_scale: float,
    bias: float,
    threshold: float,
    safety_bias: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    float_values = ",\n    ".join(f"{value:.9g}f" for value in weights)
    int_values = ",\n    ".join(str(value) for value in qweights)
    path.write_text(
        "#pragma once\n"
        "#include <cstddef>\n"
        "#include <cstdint>\n\n"
        "namespace reflexedge_model {\n"
        f"inline constexpr std::size_t kFeatureCount = {len(weights)};\n"
        f"inline constexpr float kBias = {bias:.9g}f;\n"
        f"inline constexpr float kThreshold = {threshold:.9g}f;\n"
        f"inline constexpr float kWeightScale = {weight_scale:.9g}f;\n"
        f"inline constexpr float kInt8SafetyBias = {safety_bias:.9g}f;\n"
        "alignas(64) inline constexpr float kWeightsFloat[kFeatureCount] = {\n    "
        + float_values
        + "\n};\n"
        "alignas(64) inline constexpr std::int8_t kWeightsInt8[kFeatureCount] = {\n    "
        + int_values
        + "\n};\n"
        "}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=Path("data/raw/train.csv"))
    parser.add_argument("--validation", type=Path, default=Path("data/raw/validation.csv"))
    parser.add_argument("--model-json", type=Path, default=Path("artifacts/model.json"))
    parser.add_argument("--header", type=Path, default=Path("artifacts/generated/model_weights.h"))
    parser.add_argument("--seed", type=int, default=260814)
    args = parser.parse_args()

    train_x, train_y = load_dataset(args.train)
    validation_x, validation_y = load_dataset(args.validation)
    weights, bias = train(train_x, train_y, args.seed)
    qweights, weight_scale = quantize(weights)
    float_probabilities = [predict_float(row, weights, bias) for row in validation_x]
    threshold, float_metrics = choose_threshold(float_probabilities, validation_y)
    positive_brake_errors = sorted(
        float_logit(row, weights, bias) - int8_logit(row, qweights, weight_scale, bias)
        for row, label, probability in zip(validation_x, validation_y, float_probabilities)
        if label == 1 and probability >= threshold
    )
    percentile_index = int(0.99 * max(0, len(positive_brake_errors) - 1))
    safety_bias = max(0.0, positive_brake_errors[percentile_index]) + 0.02
    int8_probabilities = [
        predict_int8(row, qweights, weight_scale, bias, safety_bias) for row in validation_x
    ]
    int8_metrics = metrics(int8_probabilities, validation_y, threshold)
    action_comparison = compare_actions(
        float_probabilities, int8_probabilities, validation_y, threshold
    )
    model = {
        "type": "logistic_collision_risk",
        "feature_count": len(weights),
        "bias": bias,
        "threshold": threshold,
        "weights_float": weights,
        "weights_int8": qweights,
        "weight_scale": weight_scale,
        "feature_scale": 1.0 / 127.0,
        "int8_safety_bias": safety_bias,
        "int8_safety_bias_method": "99th percentile scalar-minus-int8 logit error among validation true-positive brake decisions plus 0.02 margin",
        "training": {"seed": args.seed, "rows": len(train_y), "epochs": 22},
        "validation": {
            "float": float_metrics,
            "int8": int8_metrics,
            "action_disagreement_scope": "full three-state GO/HOLD/BRAKE command equality",
            **action_comparison,
            "accuracy_delta": float(int8_metrics["accuracy"]) - float(float_metrics["accuracy"]),
        },
    }
    args.model_json.parent.mkdir(parents=True, exist_ok=True)
    args.model_json.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_header(args.header, weights, qweights, weight_scale, bias, threshold, safety_bias)
    print(json.dumps({key: value for key, value in model.items() if key != "weights_float" and key != "weights_int8"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
