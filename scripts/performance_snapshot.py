#!/usr/bin/env python3
"""Build the exact performance contract rendered by the judge-facing demo video."""

from __future__ import annotations

import math


SCHEMA = "reflexedge.video-performance.v1"


def build_performance_snapshot(
    comparison: dict,
    baseline: dict,
    optimized: dict,
    trials: dict,
) -> dict:
    """Return every performance value visibly claimed by the generated video."""

    return {
        "schema": SCHEMA,
        "headline": {
            "paired_trial_count": int(trials["trials"]),
            "pipeline_p95_speedup_median": comparison["independent_trials"][
                "pipeline_p95_speedup"
            ]["median"],
        },
        "final_run": {
            "inferences_per_engine": int(baseline["end_to_end"]["inferences"]),
            "baseline_pipeline_p95_ns": baseline["end_to_end"]["latency_ns"]["p95"],
            "optimized_pipeline_p95_ns": optimized["end_to_end"]["latency_ns"]["p95"],
            "pipeline_p95_speedup": comparison["pipeline_speedup_p95"],
            "baseline_throughput_per_second": baseline["end_to_end"][
                "throughput_per_second"
            ],
            "optimized_throughput_per_second": optimized["end_to_end"][
                "throughput_per_second"
            ],
            "pipeline_throughput_gain_percent": comparison[
                "pipeline_throughput_gain_percent"
            ],
            "baseline_model_bytes": int(baseline["model_bytes"]),
            "optimized_model_bytes": int(optimized["model_bytes"]),
            "model_size_reduction_percent": comparison["model_size_reduction_percent"],
            "baseline_cpu_proxy_ns_per_inference": baseline["end_to_end"][
                "cpu_ns_per_inference_energy_proxy"
            ],
            "optimized_cpu_proxy_ns_per_inference": optimized["end_to_end"][
                "cpu_ns_per_inference_energy_proxy"
            ],
            "pipeline_cpu_time_proxy_reduction_percent": comparison[
                "pipeline_cpu_time_proxy_reduction_percent"
            ],
            "peak_rss_change_percent": comparison["peak_rss_change_percent"],
            "baseline_accuracy": comparison["baseline_quality"]["accuracy"],
            "optimized_accuracy": comparison["optimized_quality"]["accuracy"],
            "accuracy_delta_percentage_points": comparison[
                "accuracy_delta_percentage_points"
            ],
        },
    }


def _close(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)


def source_alignment_failures(
    comparison: dict,
    baseline: dict,
    optimized: dict,
    trials: dict,
) -> list[str]:
    """Fail closed when the sources behind a displayed value disagree."""

    failures: list[str] = []
    if comparison.get("independent_trials") != trials.get("summary"):
        failures.append("comparison and paired-trial performance summaries disagree")

    if comparison.get("baseline_quality") != baseline.get("quality"):
        failures.append("comparison and baseline quality metrics disagree")
    if comparison.get("optimized_quality") != optimized.get("quality"):
        failures.append("comparison and optimized quality metrics disagree")

    for label, report in (("baseline", baseline), ("optimized", optimized)):
        if report.get("rows") != comparison.get("rows"):
            failures.append(f"comparison and {label} row counts disagree")
        if report.get("repeats") != comparison.get("repeats"):
            failures.append(f"comparison and {label} repeat counts disagree")
        if report.get("end_to_end", {}).get("inferences") != baseline.get(
            "end_to_end", {}
        ).get("inferences"):
            failures.append("baseline and optimized final-run inference counts disagree")
            break

    derived = {
        "pipeline p95 speedup": (
            baseline["end_to_end"]["latency_ns"]["p95"]
            / optimized["end_to_end"]["latency_ns"]["p95"],
            comparison["pipeline_speedup_p95"],
        ),
        "pipeline throughput gain": (
            (
                optimized["end_to_end"]["throughput_per_second"]
                / baseline["end_to_end"]["throughput_per_second"]
                - 1.0
            )
            * 100.0,
            comparison["pipeline_throughput_gain_percent"],
        ),
        "model-size reduction": (
            (baseline["model_bytes"] - optimized["model_bytes"])
            / baseline["model_bytes"]
            * 100.0,
            comparison["model_size_reduction_percent"],
        ),
        "pipeline CPU-time proxy reduction": (
            (
                baseline["end_to_end"]["cpu_ns_per_inference_energy_proxy"]
                - optimized["end_to_end"]["cpu_ns_per_inference_energy_proxy"]
            )
            / baseline["end_to_end"]["cpu_ns_per_inference_energy_proxy"]
            * 100.0,
            comparison["pipeline_cpu_time_proxy_reduction_percent"],
        ),
        "peak RSS change": (
            (optimized["peak_rss_bytes"] - baseline["peak_rss_bytes"])
            / baseline["peak_rss_bytes"]
            * 100.0,
            comparison["peak_rss_change_percent"],
        ),
        "accuracy delta": (
            (optimized["quality"]["accuracy"] - baseline["quality"]["accuracy"])
            * 100.0,
            comparison["accuracy_delta_percentage_points"],
        ),
    }
    for label, (calculated, reported) in derived.items():
        if not _close(calculated, reported):
            failures.append(f"comparison {label} does not match final-run evidence")

    return failures
