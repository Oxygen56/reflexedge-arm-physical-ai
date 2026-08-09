#!/usr/bin/env python3
"""Run alternating, independent baseline/optimized benchmark processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_engine(engine: str, repeat: int, output: Path) -> dict:
    binary = ROOT / "build" / engine
    subprocess.run(
        [
            str(binary),
            "--dataset",
            "data/processed/test.csv",
            "--repeat",
            str(repeat),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def ratio(before: float, after: float) -> float:
    return before / after


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--repeat", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("reports/trials.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/trials.md"))
    args = parser.parse_args()
    if args.trials < 3:
        raise SystemExit("at least three independent trials are required")

    raw_dir = ROOT / "reports/trials"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pairs = []
    for index in range(args.trials):
        order = ["reflexedge_scalar", "reflexedge_neon"]
        if index % 2:
            order.reverse()
        results = {}
        for engine in order:
            output = raw_dir / f"trial-{index + 1:02d}-{engine}.json"
            results[engine] = run_engine(engine, args.repeat, output)
        baseline = results["reflexedge_scalar"]
        optimized = results["reflexedge_neon"]
        pairs.append(
            {
                "trial": index + 1,
                "order": order,
                "kernel_p50_speedup": ratio(
                    baseline["latency_ns"]["p50"], optimized["latency_ns"]["p50"]
                ),
                "kernel_p95_speedup": ratio(
                    baseline["latency_ns"]["p95"], optimized["latency_ns"]["p95"]
                ),
                "kernel_throughput_speedup": ratio(
                    optimized["throughput_per_second"], baseline["throughput_per_second"]
                ),
                "pipeline_p50_speedup": ratio(
                    baseline["end_to_end"]["latency_ns"]["p50"],
                    optimized["end_to_end"]["latency_ns"]["p50"],
                ),
                "pipeline_p95_speedup": ratio(
                    baseline["end_to_end"]["latency_ns"]["p95"],
                    optimized["end_to_end"]["latency_ns"]["p95"],
                ),
                "pipeline_throughput_speedup": ratio(
                    optimized["end_to_end"]["throughput_per_second"],
                    baseline["end_to_end"]["throughput_per_second"],
                ),
                "pipeline_cpu_proxy_speedup": ratio(
                    baseline["end_to_end"]["cpu_ns_per_inference_energy_proxy"],
                    optimized["end_to_end"]["cpu_ns_per_inference_energy_proxy"],
                ),
                "additional_false_negatives": optimized[
                    "additional_false_negatives_vs_scalar"
                ],
            }
        )

    metrics = {
        name: summarize([float(pair[name]) for pair in pairs])
        for name in (
            "kernel_p50_speedup",
            "kernel_p95_speedup",
            "kernel_throughput_speedup",
            "pipeline_p50_speedup",
            "pipeline_p95_speedup",
            "pipeline_throughput_speedup",
            "pipeline_cpu_proxy_speedup",
        )
    }
    gates = {
        "all_trials_kernel_p95_faster": all(pair["kernel_p95_speedup"] > 1 for pair in pairs),
        "all_trials_pipeline_p95_faster": all(
            pair["pipeline_p95_speedup"] > 1 for pair in pairs
        ),
        "all_trials_pipeline_throughput_faster": all(
            pair["pipeline_throughput_speedup"] > 1 for pair in pairs
        ),
        "all_trials_zero_added_false_negatives": all(
            pair["additional_false_negatives"] == 0 for pair in pairs
        ),
    }
    result = {
        "trials": args.trials,
        "repeat_per_trial": args.repeat,
        "inferences_per_engine_per_trial": args.repeat * 2500,
        "binary_sha256": {
            "baseline": sha256(ROOT / "build/reflexedge_scalar"),
            "optimized": sha256(ROOT / "build/reflexedge_neon"),
        },
        "dataset_sha256": sha256(ROOT / "data/processed/test.csv"),
        "model_sha256": sha256(ROOT / "artifacts/model.json"),
        "pairs": pairs,
        "summary": metrics,
        "gates": gates,
        "ready_for_claim": all(gates.values()),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Independent paired benchmark trials",
        "",
        f"{args.trials} independent processes per engine, {args.repeat * 2500:,} raw sensor frames per process. Execution order alternates to reduce order and thermal bias.",
        "",
        "| Metric | Median speedup | Minimum | Maximum |",
        "| --- | ---: | ---: | ---: |",
    ]
    labels = {
        "kernel_p50_speedup": "Model kernel p50",
        "kernel_p95_speedup": "Model kernel p95",
        "kernel_throughput_speedup": "Model kernel throughput",
        "pipeline_p50_speedup": "Raw sensor → action p50",
        "pipeline_p95_speedup": "Raw sensor → action p95",
        "pipeline_throughput_speedup": "Raw sensor → action throughput",
        "pipeline_cpu_proxy_speedup": "Raw sensor → action CPU-time proxy",
    }
    for key, label in labels.items():
        metric = metrics[key]
        lines.append(
            f"| {label} | {metric['median']:.2f}× | {metric['minimum']:.2f}× | {metric['maximum']:.2f}× |"
        )
    lines.extend(["", "## Gates", ""])
    lines.extend(f"- [{'x' if value else ' '}] {key}" for key, value in gates.items())
    args.markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ready_for_claim"]:
        raise SystemExit(7)


if __name__ == "__main__":
    main()
