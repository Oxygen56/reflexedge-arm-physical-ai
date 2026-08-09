#!/usr/bin/env python3
"""Generate a deterministic, rights-clean Physical AI sensor corpus."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
from pathlib import Path

BEAMS = 64
SUMMARY_FEATURES = 16
FEATURES = BEAMS * 2 + SUMMARY_FEATURES
SCENARIOS = ("safe", "frontal_approach", "crossing", "sudden_intrusion", "dropout")


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def make_frame(
    rng: random.Random, scenario: str
) -> tuple[list[float], list[float], list[float], int, float]:
    distances = [rng.uniform(5.5, 14.0) for _ in range(BEAMS)]
    velocities = [rng.uniform(-0.25, 0.25) for _ in range(BEAMS)]

    if scenario == "frontal_approach":
        center = rng.randint(27, 36)
        width = rng.randint(4, 11)
        distance = rng.uniform(0.55, 4.2)
        closing = rng.uniform(-5.8, -0.9)
        for beam in range(max(0, center - width), min(BEAMS, center + width + 1)):
            distances[beam] = max(0.12, distance + rng.uniform(-0.18, 0.18))
            velocities[beam] = closing + rng.uniform(-0.25, 0.25)
    elif scenario == "crossing":
        center = rng.choice((rng.randint(10, 25), rng.randint(39, 54)))
        width = rng.randint(3, 8)
        distance = rng.uniform(0.8, 3.8)
        closing = rng.uniform(-3.4, -0.25)
        for beam in range(max(0, center - width), min(BEAMS, center + width + 1)):
            distances[beam] = max(0.15, distance + rng.uniform(-0.25, 0.25))
            velocities[beam] = closing + rng.uniform(-0.2, 0.2)
    elif scenario == "sudden_intrusion":
        center = rng.randint(18, 45)
        width = rng.randint(2, 6)
        distance = rng.uniform(0.18, 1.15)
        closing = rng.uniform(-2.2, -0.05)
        for beam in range(max(0, center - width), min(BEAMS, center + width + 1)):
            distances[beam] = max(0.08, distance + rng.uniform(-0.08, 0.08))
            velocities[beam] = closing + rng.uniform(-0.12, 0.12)
    elif scenario == "dropout":
        start = rng.randint(5, 50)
        for beam in range(start, min(BEAMS, start + rng.randint(3, 12))):
            distances[beam] = 20.0
            velocities[beam] = 0.0

    features: list[float] = []
    danger_values: list[float] = []
    proximity_values: list[float] = []
    min_ttc = 999.0
    nearest_central = 999.0
    for beam, (distance, velocity) in enumerate(zip(distances, velocities)):
        angle = -math.pi / 2 + beam * math.pi / (BEAMS - 1)
        angular_weight = math.exp(-((angle / 0.78) ** 2))
        proximity = clamp((6.0 - distance) / 6.0)
        closing = clamp(-velocity / 6.0)
        danger = proximity * (0.25 + 0.75 * closing) * angular_weight
        danger_values.append(danger)
        proximity_values.append(proximity * angular_weight)
        if velocity < -0.05:
            min_ttc = min(min_ttc, distance / -velocity)
        if 22 <= beam <= 41:
            nearest_central = min(nearest_central, distance)

    ordered_danger = sorted(danger_values, reverse=True)
    central_danger = danger_values[22:42]
    central_proximity = proximity_values[22:42]
    summary = [
        ordered_danger[0],
        ordered_danger[1],
        sum(ordered_danger[:4]) / 4.0,
        sum(danger_values) / BEAMS,
        max(central_danger),
        max(danger_values[:32]),
        max(danger_values[32:]),
        max(proximity_values),
        max(central_proximity),
        sum(proximity_values) / BEAMS,
        sum(value >= 0.05 for value in danger_values) / BEAMS,
        sum(value >= 0.10 for value in danger_values) / BEAMS,
        sum(value >= 0.20 for value in danger_values) / BEAMS,
        sum(central_danger) / len(central_danger),
        (sum(danger_values[:12]) + sum(danger_values[-12:])) / 24.0,
        1.0,
    ]
    features.extend(danger_values)
    features.extend(proximity_values)
    features.extend(summary)
    truth_score = max(danger_values)
    label = int(truth_score >= 0.205 or nearest_central < 0.52)
    return distances, velocities, features, label, min_ttc


def split_scenario(rng: random.Random) -> str:
    value = rng.random()
    if value < 0.36:
        return "safe"
    if value < 0.58:
        return "frontal_approach"
    if value < 0.75:
        return "crossing"
    if value < 0.92:
        return "sudden_intrusion"
    return "dropout"


def write_split(path: Path, split: str, count: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    fields = (
        ["sample_id", "split", "scenario", "label", "min_ttc"]
        + [f"d{i:03d}" for i in range(BEAMS)]
        + [f"v{i:03d}" for i in range(BEAMS)]
        + [f"f{i:03d}" for i in range(FEATURES)]
    )
    label_count = 0
    scenario_counts = {name: 0 for name in SCENARIOS}
    digest = hashlib.sha256()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(fields)
        for index in range(count):
            scenario = split_scenario(rng)
            distances, velocities, features, label, min_ttc = make_frame(rng, scenario)
            label_count += label
            scenario_counts[scenario] += 1
            row = [
                f"{split}-{index:06d}",
                split,
                scenario,
                label,
                f"{min_ttc:.6f}",
                *[f"{value:.8f}" for value in distances],
                *[f"{value:.8f}" for value in velocities],
                *[f"{value:.8f}" for value in features],
            ]
            line = ",".join(map(str, row)) + "\n"
            handle.write(line)
            digest.update(line.encode("utf-8"))
    return {
        "path": str(path),
        "rows": count,
        "positive_rows": label_count,
        "positive_rate": label_count / count,
        "scenario_counts": scenario_counts,
        "sha256_rows_without_header": digest.hexdigest(),
        "seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--seed", type=int, default=260814)
    parser.add_argument("--train", type=int, default=6000)
    parser.add_argument("--validation", type=int, default=1500)
    parser.add_argument("--test", type=int, default=2500)
    args = parser.parse_args()

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.processed_dir.mkdir(parents=True, exist_ok=True)
    splits = {
        "train": write_split(args.raw_dir / "train.csv", "train", args.train, args.seed),
        "validation": write_split(
            args.raw_dir / "validation.csv", "validation", args.validation, args.seed + 1
        ),
        "test": write_split(args.raw_dir / "test.csv", "test", args.test, args.seed + 2),
    }
    shutil.copyfile(args.raw_dir / "test.csv", args.processed_dir / "test.csv")
    metadata = {
        "title": "ReflexEdge deterministic synthetic range-sensor corpus",
        "license": "MIT",
        "provenance": "Generated entirely by src/generate_dataset.py; no external data.",
        "generator_seed": args.seed,
        "beams": BEAMS,
        "features": FEATURES,
        "raw_sensor_layout": "d000-d063 distance in meters; v000-v063 radial velocity in meters per second (negative is closing)",
        "feature_layout": "f000-f063 danger; f064-f127 angular proximity; f128-f143 global safety summaries",
        "splits": splits,
    }
    (args.raw_dir / "dataset_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
