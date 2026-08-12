#!/usr/bin/env python3
"""Turn raw baseline and optimized logs into a guarded evidence report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def percent_change(before: float, after: float) -> float:
    return (after - before) / before * 100.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=Path("reports/baseline.json"))
    parser.add_argument("--optimized", type=Path, default=Path("reports/optimized.json"))
    parser.add_argument("--dataset", type=Path, default=Path("data/processed/test.csv"))
    parser.add_argument("--trials", type=Path, default=Path("reports/trials.json"))
    parser.add_argument("--json", type=Path, default=Path("reports/comparison.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/comparison.md"))
    args = parser.parse_args()

    baseline = load(args.baseline)
    optimized = load(args.optimized)
    dataset_sha256 = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    architecture = optimized["architecture"]
    trials = load(args.trials) if args.trials.is_file() else None
    action_metric_keys = (
        "scalar_vs_int8_action_disagreements",
        "scalar_vs_int8_brake_decision_disagreements",
        "int8_brake_false_negative_disagreements_vs_scalar",
        "int8_additional_brake_decisions_vs_scalar",
        "additional_false_negatives_vs_scalar",
    )
    action_metrics = {key: int(optimized[key]) for key in action_metric_keys}
    three_state_action_disagreements = action_metrics[
        "scalar_vs_int8_action_disagreements"
    ]
    brake_decision_disagreements = action_metrics[
        "scalar_vs_int8_brake_decision_disagreements"
    ]
    brake_false_negative_disagreements = action_metrics[
        "int8_brake_false_negative_disagreements_vs_scalar"
    ]
    additional_brake_decisions = action_metrics[
        "int8_additional_brake_decisions_vs_scalar"
    ]
    additional_false_negatives = action_metrics["additional_false_negatives_vs_scalar"]
    quality_delta_pp = (
        float(optimized["quality"]["accuracy"]) - float(baseline["quality"]["accuracy"])
    ) * 100.0
    gates = {
        "real_arm64_hardware": architecture in {"arm64", "aarch64"},
        "same_dataset_and_rows": baseline["dataset"] == optimized["dataset"]
        and baseline["rows"] == optimized["rows"],
        "cross_engine_action_metrics_match": all(
            baseline[key] == optimized[key] for key in action_metric_keys
        ),
        "action_metrics_are_consistent": three_state_action_disagreements
        >= brake_decision_disagreements
        and brake_decision_disagreements
        == brake_false_negative_disagreements + additional_brake_decisions
        and additional_false_negatives <= brake_false_negative_disagreements,
        "zero_int8_brake_false_negative_disagreements": brake_false_negative_disagreements
        == 0,
        "zero_added_safety_false_negatives": additional_false_negatives == 0,
        "accuracy_loss_within_half_point": quality_delta_pp >= -0.5,
        "optimized_p95_is_faster": optimized["latency_ns"]["p95"] < baseline["latency_ns"]["p95"],
        "optimized_model_is_smaller": optimized["model_bytes"] < baseline["model_bytes"],
        "optimized_pipeline_p95_is_faster": optimized["end_to_end"]["latency_ns"]["p95"]
        < baseline["end_to_end"]["latency_ns"]["p95"],
        "optimized_pipeline_throughput_is_higher": optimized["end_to_end"][
            "throughput_per_second"
        ]
        > baseline["end_to_end"]["throughput_per_second"],
        "independent_trials_ready": bool(trials and trials.get("ready_for_claim")),
        "direct_energy_not_fabricated": baseline["direct_energy_joules"] is None
        and optimized["direct_energy_joules"] is None,
    }
    comparison = {
        "architecture": architecture,
        "dataset_sha256": dataset_sha256,
        "rows": baseline["rows"],
        "repeats": baseline["repeats"],
        "baseline_engine": baseline["engine"],
        "optimized_engine": optimized["engine"],
        "speedup_p50": baseline["latency_ns"]["p50"] / optimized["latency_ns"]["p50"],
        "speedup_p95": baseline["latency_ns"]["p95"] / optimized["latency_ns"]["p95"],
        "pipeline_speedup_p50": baseline["end_to_end"]["latency_ns"]["p50"]
        / optimized["end_to_end"]["latency_ns"]["p50"],
        "pipeline_speedup_p95": baseline["end_to_end"]["latency_ns"]["p95"]
        / optimized["end_to_end"]["latency_ns"]["p95"],
        "pipeline_throughput_gain_percent": percent_change(
            baseline["end_to_end"]["throughput_per_second"],
            optimized["end_to_end"]["throughput_per_second"],
        ),
        "pipeline_cpu_time_proxy_reduction_percent": -percent_change(
            baseline["end_to_end"]["cpu_ns_per_inference_energy_proxy"],
            optimized["end_to_end"]["cpu_ns_per_inference_energy_proxy"],
        ),
        "throughput_gain_percent": percent_change(
            baseline["throughput_per_second"], optimized["throughput_per_second"]
        ),
        "cpu_time_proxy_reduction_percent": -percent_change(
            baseline["cpu_ns_per_inference_energy_proxy"],
            optimized["cpu_ns_per_inference_energy_proxy"],
        ),
        "model_size_reduction_percent": -percent_change(
            baseline["model_bytes"], optimized["model_bytes"]
        ),
        "peak_rss_change_percent": percent_change(
            baseline["peak_rss_bytes"], optimized["peak_rss_bytes"]
        ),
        "accuracy_delta_percentage_points": quality_delta_pp,
        "baseline_quality": baseline["quality"],
        "optimized_quality": optimized["quality"],
        **action_metrics,
        "action_disagreement_definitions": {
            "scalar_vs_int8_action_disagreements": "any different GO, HOLD, or BRAKE command",
            "scalar_vs_int8_brake_decision_disagreements": "either engine crosses the BRAKE versus non-BRAKE boundary",
            "int8_brake_false_negative_disagreements_vs_scalar": "scalar commands BRAKE while int8 commands GO or HOLD",
            "int8_additional_brake_decisions_vs_scalar": "int8 commands BRAKE while scalar commands GO or HOLD",
            "additional_false_negatives_vs_scalar": "ground-truth brake case where scalar commands BRAKE and int8 does not",
        },
        "energy_statement": "CPU time per inference is an energy proxy. Direct joules were not measured.",
        "benchmark_scope": {
            "kernel": optimized["latency_scope"],
            "pipeline": optimized["end_to_end"]["scope"],
        },
        "independent_trials": trials["summary"] if trials else None,
        "gates": gates,
        "ready_for_claim": all(gates.values()),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    status = "VERIFIED FOR LOCAL CLAIM" if comparison["ready_for_claim"] else "NOT READY FOR CLAIM"
    rows = [
        "# ReflexEdge benchmark comparison",
        "",
        f"**Evidence verdict: {status}.**",
        "",
        f"- Evidence architecture: `{architecture}`",
        f"- Frozen test rows: {comparison['rows']}",
        f"- Repeats per engine: {comparison['repeats']}",
        f"- Dataset SHA-256: `{dataset_sha256}`",
        "",
        "## Raw sensor-to-action pipeline",
        "",
        "This is the end-to-end Physical AI path: raw 64-beam distance and velocity input, feature encoding, quantization when applicable, model inference, and GO/HOLD/BRAKE policy.",
        "",
        "| Metric | Scalar FP32 | Fused int8 Arm path | Change |",
        "| --- | ---: | ---: | ---: |",
        f"| p50 latency | {baseline['end_to_end']['latency_ns']['p50']:.2f} ns | {optimized['end_to_end']['latency_ns']['p50']:.2f} ns | {comparison['pipeline_speedup_p50']:.2f}x speedup |",
        f"| p95 latency | {baseline['end_to_end']['latency_ns']['p95']:.2f} ns | {optimized['end_to_end']['latency_ns']['p95']:.2f} ns | {comparison['pipeline_speedup_p95']:.2f}x speedup |",
        f"| Throughput | {baseline['end_to_end']['throughput_per_second']:.0f}/s | {optimized['end_to_end']['throughput_per_second']:.0f}/s | {comparison['pipeline_throughput_gain_percent']:+.1f}% |",
        f"| CPU-time proxy | {baseline['end_to_end']['cpu_ns_per_inference_energy_proxy']:.2f} ns/inf | {optimized['end_to_end']['cpu_ns_per_inference_energy_proxy']:.2f} ns/inf | {comparison['pipeline_cpu_time_proxy_reduction_percent']:.1f}% lower |",
        "",
        "## Model inference kernel",
        "",
        "Features are pre-encoded for this microbenchmark; CSV loading and sensor encoding are excluded.",
        "",
        "| Metric | Scalar FP32 | Int8 Arm NEON | Change |",
        "| --- | ---: | ---: | ---: |",
        f"| p50 latency | {baseline['latency_ns']['p50']:.2f} ns | {optimized['latency_ns']['p50']:.2f} ns | {comparison['speedup_p50']:.2f}x speedup |",
        f"| p95 latency | {baseline['latency_ns']['p95']:.2f} ns | {optimized['latency_ns']['p95']:.2f} ns | {comparison['speedup_p95']:.2f}x speedup |",
        f"| Throughput | {baseline['throughput_per_second']:.0f}/s | {optimized['throughput_per_second']:.0f}/s | {comparison['throughput_gain_percent']:+.1f}% |",
        f"| CPU-time energy proxy | {baseline['cpu_ns_per_inference_energy_proxy']:.2f} ns/inf | {optimized['cpu_ns_per_inference_energy_proxy']:.2f} ns/inf | {comparison['cpu_time_proxy_reduction_percent']:.1f}% lower |",
        f"| Model bytes | {baseline['model_bytes']} | {optimized['model_bytes']} | {comparison['model_size_reduction_percent']:.1f}% lower |",
        f"| Peak RSS | {baseline['peak_rss_bytes']} | {optimized['peak_rss_bytes']} | {comparison['peak_rss_change_percent']:+.1f}% |",
        f"| Accuracy | {baseline['quality']['accuracy']:.5f} | {optimized['quality']['accuracy']:.5f} | {quality_delta_pp:+.3f} pp |",
        f"| Total ground-truth false negatives | {baseline['quality']['false_negative']} | {optimized['quality']['false_negative']} | newly introduced cases: {additional_false_negatives} |",
        "",
        "## Action agreement and BRAKE safety",
        "",
        "These counts use the same frozen test frames but answer different questions. Full action agreement compares all three commands; the safety gate is directional and asks whether int8 ever drops a scalar BRAKE.",
        "",
        "| Metric | Count | Definition |",
        "| --- | ---: | --- |",
        f"| Full three-state action disagreements | {three_state_action_disagreements} | Scalar and int8 emit different `GO` / `HOLD` / `BRAKE` commands |",
        f"| BRAKE-boundary disagreements | {brake_decision_disagreements} | One engine emits `BRAKE` and the other emits `GO` or `HOLD` |",
        f"| Int8 BRAKE false-negative disagreements vs scalar | {brake_false_negative_disagreements} | Scalar emits `BRAKE`; int8 emits `GO` or `HOLD` |",
        f"| Additional int8 BRAKE decisions vs scalar | {additional_brake_decisions} | Int8 emits `BRAKE`; scalar emits `GO` or `HOLD` |",
        f"| Added ground-truth false negatives vs scalar | {additional_false_negatives} | True brake label, scalar emits `BRAKE`, and int8 emits `GO` or `HOLD` |",
        "",
        "## Independent process trials",
        "",
        f"Across {trials['trials'] if trials else 0} alternating-order paired trials, the median raw sensor-to-action speedups were {trials['summary']['pipeline_p50_speedup']['median']:.2f}x p50, {trials['summary']['pipeline_p95_speedup']['median']:.2f}x p95, and {trials['summary']['pipeline_throughput_speedup']['median']:.2f}x throughput." if trials else "Independent trials are missing.",
        "",
        "## Claim boundaries",
        "",
        "- These are local measurements on the hardware recorded in `reports/hardware.json`, not a cross-device benchmark.",
        "- End-to-end latency starts from in-memory raw distance/velocity arrays and ends after action-policy evaluation; physical sensor I/O and actuator transport are outside the timed region.",
        "- CPU time per inference is an energy proxy. Direct energy in joules remains unmeasured and is not claimed.",
        "- Peak RSS measures the full benchmark process; small model-size savings may not materially change process RSS.",
        "- Synthetic sensor frames enable deterministic safety regression testing; they do not establish field safety certification.",
        "",
        "## Gates",
        "",
    ]
    rows.extend(f"- [{'x' if passed else ' '}] {name}" for name, passed in gates.items())
    args.markdown.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps(comparison, indent=2, sort_keys=True))
    if not comparison["ready_for_claim"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
