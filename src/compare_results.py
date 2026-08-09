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
    parser.add_argument("--json", type=Path, default=Path("reports/comparison.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/comparison.md"))
    args = parser.parse_args()

    baseline = load(args.baseline)
    optimized = load(args.optimized)
    dataset_sha256 = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    architecture = optimized["architecture"]
    quality_delta_pp = (
        float(optimized["quality"]["accuracy"]) - float(baseline["quality"]["accuracy"])
    ) * 100.0
    gates = {
        "real_arm64_hardware": architecture in {"arm64", "aarch64"},
        "same_dataset_and_rows": baseline["dataset"] == optimized["dataset"]
        and baseline["rows"] == optimized["rows"],
        "zero_added_safety_false_negatives": optimized["additional_false_negatives_vs_scalar"] == 0,
        "accuracy_loss_within_half_point": quality_delta_pp >= -0.5,
        "optimized_p95_is_faster": optimized["latency_ns"]["p95"] < baseline["latency_ns"]["p95"],
        "optimized_model_is_smaller": optimized["model_bytes"] < baseline["model_bytes"],
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
        "action_disagreements": optimized["scalar_vs_int8_action_disagreements"],
        "additional_false_negatives": optimized["additional_false_negatives_vs_scalar"],
        "energy_statement": "CPU time per inference is an energy proxy. Direct joules were not measured.",
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
        "| Metric | Scalar FP32 | Int8 Arm NEON | Change |",
        "| --- | ---: | ---: | ---: |",
        f"| p50 latency | {baseline['latency_ns']['p50']:.2f} ns | {optimized['latency_ns']['p50']:.2f} ns | {comparison['speedup_p50']:.2f}x speedup |",
        f"| p95 latency | {baseline['latency_ns']['p95']:.2f} ns | {optimized['latency_ns']['p95']:.2f} ns | {comparison['speedup_p95']:.2f}x speedup |",
        f"| Throughput | {baseline['throughput_per_second']:.0f}/s | {optimized['throughput_per_second']:.0f}/s | {comparison['throughput_gain_percent']:+.1f}% |",
        f"| CPU-time energy proxy | {baseline['cpu_ns_per_inference_energy_proxy']:.2f} ns/inf | {optimized['cpu_ns_per_inference_energy_proxy']:.2f} ns/inf | {comparison['cpu_time_proxy_reduction_percent']:.1f}% lower |",
        f"| Model bytes | {baseline['model_bytes']} | {optimized['model_bytes']} | {comparison['model_size_reduction_percent']:.1f}% lower |",
        f"| Peak RSS | {baseline['peak_rss_bytes']} | {optimized['peak_rss_bytes']} | {comparison['peak_rss_change_percent']:+.1f}% |",
        f"| Accuracy | {baseline['quality']['accuracy']:.5f} | {optimized['quality']['accuracy']:.5f} | {quality_delta_pp:+.3f} pp |",
        f"| False negatives | {baseline['quality']['false_negative']} | {optimized['quality']['false_negative']} | added: {comparison['additional_false_negatives']} |",
        "",
        "## Claim boundaries",
        "",
        "- These are local measurements on the hardware recorded in `reports/hardware.json`, not a cross-device benchmark.",
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
