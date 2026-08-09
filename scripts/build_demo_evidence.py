#!/usr/bin/env python3
"""Generate the public demo's sanitized evidence module from raw local artifacts."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sigmoid(value: float) -> float:
    value = max(-60.0, min(60.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def probability(row: dict[str, str], model: dict, optimized: bool) -> float:
    names = [f"f{index:03d}" for index in range(model["feature_count"])]
    values = [float(row[name]) for name in names]
    if optimized:
        quantized = [max(0, min(127, round(value * 127.0))) for value in values]
        dot = sum(weight * value for weight, value in zip(model["weights_int8"], quantized))
        logit = (
            model["bias"]
            + dot * model["weight_scale"] / 127.0
            + model["int8_safety_bias"]
        )
    else:
        logit = model["bias"] + sum(
            weight * value for weight, value in zip(model["weights_float"], values)
        )
    return sigmoid(logit)


def action(risk: float, threshold: float) -> str:
    if risk >= threshold:
        return "BRAKE"
    if risk >= threshold * 0.62:
        return "HOLD"
    return "GO"


def main() -> None:
    comparison = json.loads((ROOT / "reports/comparison.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "reports/baseline.json").read_text(encoding="utf-8"))
    optimized = json.loads((ROOT / "reports/optimized.json").read_text(encoding="utf-8"))
    hardware = json.loads((ROOT / "reports/hardware.json").read_text(encoding="utf-8"))
    model = json.loads((ROOT / "artifacts/model.json").read_text(encoding="utf-8"))
    metadata = json.loads((ROOT / "data/raw/dataset_metadata.json").read_text(encoding="utf-8"))
    trials = json.loads((ROOT / "reports/trials.json").read_text(encoding="utf-8"))

    with (ROOT / "data/raw/test.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    scenarios = ["safe", "crossing", "frontal_approach", "sudden_intrusion", "dropout"]
    selected: list[dict[str, str]] = []
    for scenario in scenarios:
        candidates = [row for row in rows if row["scenario"] == scenario]
        candidates.sort(key=lambda row: probability(row, model, True))
        indexes = [0, len(candidates) // 3, (2 * len(candidates)) // 3, len(candidates) - 1]
        selected.extend(candidates[index] for index in indexes)

    frames = []
    for row in selected:
        optimized_risk = probability(row, model, True)
        baseline_risk = probability(row, model, False)
        frames.append(
            {
                "id": row["sample_id"],
                "scenario": row["scenario"].replace("_", " "),
                "truthBrake": bool(int(row["label"])),
                "baselineRisk": round(baseline_risk, 6),
                "optimizedRisk": round(optimized_risk, 6),
                "action": action(optimized_risk, model["threshold"]),
                "danger": [round(float(row[f"f{index:03d}"]), 4) for index in range(64)],
                "proximity": [round(float(row[f"f{index:03d}"]), 4) for index in range(64, 128)],
            }
        )

    public = {
        "benchmark": {
            "p50Speedup": comparison["pipeline_speedup_p50"],
            "p95Speedup": comparison["pipeline_speedup_p95"],
            "throughputGainPercent": comparison["pipeline_throughput_gain_percent"],
            "cpuProxyReductionPercent": comparison["pipeline_cpu_time_proxy_reduction_percent"],
            "modelReductionPercent": comparison["model_size_reduction_percent"],
            "accuracyDeltaPoints": comparison["accuracy_delta_percentage_points"],
            "actionDisagreements": comparison["action_disagreements"],
            "additionalFalseNegatives": comparison["additional_false_negatives"],
            "datasetSha256": comparison["dataset_sha256"],
            "rows": comparison["rows"],
            "repeats": comparison["repeats"],
            "trialCount": trials["trials"],
            "inferencesPerEnginePerTrial": trials["inferences_per_engine_per_trial"],
            "pairedTrialMedian": {
                "p50Speedup": trials["summary"]["pipeline_p50_speedup"]["median"],
                "p95Speedup": trials["summary"]["pipeline_p95_speedup"]["median"],
                "throughputSpeedup": trials["summary"]["pipeline_throughput_speedup"]["median"],
                "cpuProxySpeedup": trials["summary"]["pipeline_cpu_proxy_speedup"]["median"],
            },
            "baseline": {
                "p50Ns": baseline["end_to_end"]["latency_ns"]["p50"],
                "p95Ns": baseline["end_to_end"]["latency_ns"]["p95"],
                "throughput": baseline["end_to_end"]["throughput_per_second"],
                "modelBytes": baseline["model_bytes"],
                "accuracy": comparison["baseline_quality"]["accuracy"],
                "recall": comparison["baseline_quality"]["recall"],
                "falseNegatives": comparison["baseline_quality"]["false_negative"],
            },
            "optimized": {
                "p50Ns": optimized["end_to_end"]["latency_ns"]["p50"],
                "p95Ns": optimized["end_to_end"]["latency_ns"]["p95"],
                "throughput": optimized["end_to_end"]["throughput_per_second"],
                "modelBytes": optimized["model_bytes"],
                "accuracy": comparison["optimized_quality"]["accuracy"],
                "recall": comparison["optimized_quality"]["recall"],
                "falseNegatives": comparison["optimized_quality"]["false_negative"],
            },
        },
        "hardware": {
            "architecture": hardware["architecture"],
            "chip": hardware["chip"],
            "neon": hardware["neon_available"] == "1",
            "dotProduct": hardware["dot_product_available"] == "1",
            "compiler": hardware["compiler"],
        },
        "dataset": {
            "title": metadata["title"],
            "license": metadata["license"],
            "provenance": metadata["provenance"],
            "testRows": metadata["splits"]["test"]["rows"],
        },
        "threshold": model["threshold"],
        "frames": frames,
    }
    destination = ROOT / "demo/site/app/evidence.ts"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "// Generated by scripts/build_demo_evidence.py. Do not hand-edit.\n"
        f"export const evidence = {json.dumps(public, indent=2, sort_keys=True)} as const;\n",
        encoding="utf-8",
    )
    print(f"wrote {destination} with {len(frames)} sanitized replay frames")


if __name__ == "__main__":
    main()
