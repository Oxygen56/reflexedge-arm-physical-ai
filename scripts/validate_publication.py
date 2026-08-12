#!/usr/bin/env python3
"""Verify that judge-facing public artifacts are anonymously reachable."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.performance_snapshot import (
        build_performance_snapshot,
        source_alignment_failures,
    )
except ModuleNotFoundError:  # direct execution via python3 scripts/validate_publication.py
    from performance_snapshot import build_performance_snapshot, source_alignment_failures


REPOSITORY_API = "https://api.github.com/repos/Oxygen56/reflexedge-arm-physical-ai"
COMMIT_API = REPOSITORY_API + "/commits/main"
LICENSE_URL = "https://raw.githubusercontent.com/Oxygen56/reflexedge-arm-physical-ai/main/LICENSE"
VIDEO_URL = "https://raw.githubusercontent.com/Oxygen56/reflexedge-arm-physical-ai/main/demo/video/reflexedge-evidence-demo.mp4"
DEMO_URL = "https://reflexedge-arm-ai.jiangth99.chatgpt.site"
ACTION_METRIC_KEYS = (
    "scalar_vs_int8_action_disagreements",
    "scalar_vs_int8_brake_decision_disagreements",
    "int8_brake_false_negative_disagreements_vs_scalar",
    "int8_additional_brake_decisions_vs_scalar",
    "additional_false_negatives_vs_scalar",
)


def fetch(url: str) -> tuple[int, str, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "ReflexEdge-publication-validator/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def demo_performance_checks(body: bytes, snapshot: dict) -> dict[str, bool]:
    """Match displayed values in their labeled HTML positions, not anywhere on the page."""

    normalized = re.sub(br"<!--\s*-->", b"", body)
    headline = snapshot["headline"]
    final_run = snapshot["final_run"]

    def matches(pattern: str) -> bool:
        return re.search(pattern.encode("utf-8"), normalized, re.S) is not None

    return {
        "headline_p95": matches(
            rf"<strong[^>]*>\s*{headline['pipeline_p95_speedup_median']:.2f}×\s*</strong>"
            r"\s*<p[^>]*>\s*median p95 · raw sensor → action\s*</p>"
        ),
        "final_run_p95": matches(
            r"<span[^>]*>\s*P95 · FINAL RUN\s*</span>\s*<div[^>]*>\s*"
            rf"<del[^>]*>\s*{final_run['baseline_pipeline_p95_ns']:.2f} ns\s*</del>\s*"
            rf"<strong[^>]*>\s*{final_run['optimized_pipeline_p95_ns']:.2f} ns\s*</strong>"
        ),
        "model_bytes": matches(
            r"<span[^>]*>\s*MODEL BYTES\s*</span>\s*<div[^>]*>\s*"
            rf"<del[^>]*>\s*{final_run['baseline_model_bytes']} B\s*</del>\s*"
            rf"<strong[^>]*>\s*{final_run['optimized_model_bytes']} B\s*</strong>"
        ),
        "accuracy": matches(
            r"<span[^>]*>\s*ACCURACY\s*</span>\s*<div[^>]*>\s*"
            rf"<del[^>]*>\s*{final_run['baseline_accuracy'] * 100:.2f}%\s*</del>\s*"
            rf"<strong[^>]*>\s*{final_run['optimized_accuracy'] * 100:.2f}%\s*</strong>"
        ),
    }


def main() -> None:
    failures: list[str] = []
    checks: dict[str, object] = {}
    comparison = json.loads(Path("reports/comparison.json").read_text(encoding="utf-8"))
    baseline = json.loads(Path("reports/baseline.json").read_text(encoding="utf-8"))
    optimized = json.loads(Path("reports/optimized.json").read_text(encoding="utf-8"))
    trials = json.loads(Path("reports/trials.json").read_text(encoding="utf-8"))
    failures.extend(source_alignment_failures(comparison, baseline, optimized, trials))
    performance_snapshot = build_performance_snapshot(
        comparison, baseline, optimized, trials
    )
    local_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True
    ).strip()

    try:
        status, content_type, body = fetch(REPOSITORY_API)
        repository = json.loads(body)
        checks["repository"] = {
            "status": status,
            "private": repository.get("private"),
            "default_branch": repository.get("default_branch"),
            "url": repository.get("html_url"),
        }
        if status != 200 or repository.get("private") is not False:
            failures.append("GitHub repository is not anonymously public")
    except Exception as error:  # fail closed with a useful public gate
        failures.append(f"repository check failed: {error}")

    try:
        status, _, body = fetch(COMMIT_API)
        remote_head = json.loads(body).get("sha")
        checks["commit"] = {"status": status, "local_head": local_head, "remote_head": remote_head}
        if status != 200 or remote_head != local_head:
            failures.append("public repository head does not match the validated local commit")
    except Exception as error:
        failures.append(f"commit check failed: {error}")

    try:
        status, _, body = fetch(LICENSE_URL)
        local_license = Path("LICENSE").read_bytes()
        checks["license"] = {
            "status": status,
            "mit_visible": b"MIT License" in body,
            "matches_local": body == local_license,
        }
        if status != 200 or b"MIT License" not in body or body != local_license:
            failures.append("public repository does not expose the MIT license")
    except Exception as error:
        failures.append(f"license check failed: {error}")

    try:
        status, content_type, body = fetch(VIDEO_URL)
        local_video = Path("demo/video/reflexedge-evidence-demo.mp4").read_bytes()
        checks["video"] = {
            "status": status,
            "content_type": content_type,
            "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "matches_local": body == local_video,
        }
        if status != 200 or len(body) < 1_000_000 or body != local_video:
            failures.append("public evidence video is missing or unexpectedly small")
    except Exception as error:
        failures.append(f"video check failed: {error}")

    try:
        status, content_type, body = fetch(DEMO_URL)
        metric_marker = b"median p95"
        dataset_marker = comparison["dataset_sha256"][:12].encode()
        action_markers = {
            "three_state": str(comparison["scalar_vs_int8_action_disagreements"]).encode(),
            "brake_boundary": str(
                comparison["scalar_vs_int8_brake_decision_disagreements"]
            ).encode(),
            "missed_scalar_brake": str(
                comparison["int8_brake_false_negative_disagreements_vs_scalar"]
            ).encode(),
            "additional_int8_brake": str(
                comparison["int8_additional_brake_decisions_vs_scalar"]
            ).encode(),
            "added_ground_truth_fn": str(
                comparison["additional_false_negatives_vs_scalar"]
            ).encode(),
        }
        normalized_body = re.sub(br"<!--\s*-->", b"", body)
        performance_checks = demo_performance_checks(body, performance_snapshot)
        action_checks = {
            "three_state": action_markers["three_state"] + b" full action changes"
            in normalized_body,
            "brake_boundary": action_markers["brake_boundary"] + b" BRAKE-boundary"
            in normalized_body,
            "missed_scalar_brake": action_markers["missed_scalar_brake"]
            + b" missed scalar BRAKE"
            in normalized_body,
            "additional_int8_brake": action_markers["additional_int8_brake"]
            + b" additional int8 BRAKE"
            in normalized_body,
            "added_ground_truth_fn": b"ADDED GROUND-TRUTH FALSE NEGATIVES"
            in normalized_body
            and re.search(
                br"ADDED GROUND-TRUTH FALSE NEGATIVES.*?<strong[^>]*>"
                + re.escape(action_markers["added_ground_truth_fn"])
                + br"</strong>",
                normalized_body,
                re.S,
            )
            is not None,
        }
        checks["demo"] = {
            "status": status,
            "content_type": content_type,
            "reflexedge_marker": b"ReflexEdge" in body,
            "current_metric_marker": metric_marker in normalized_body,
            "dataset_marker": dataset_marker in body,
            "action_markers": action_checks,
            "performance_markers": performance_checks,
        }
        if (
            status != 200
            or b"ReflexEdge" not in body
            or metric_marker not in normalized_body
            or dataset_marker not in body
            or not all(action_checks.values())
            or not all(performance_checks.values())
        ):
            failures.append("public evidence demo is unavailable or does not match local metrics")
    except Exception as error:
        failures.append(f"demo check failed: {error}")

    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "evidence_snapshot": {
            "video_sha256": hashlib.sha256(
                Path("demo/video/reflexedge-evidence-demo.mp4").read_bytes()
            ).hexdigest(),
            "action_metrics": {
                key: comparison[key]
                for key in ACTION_METRIC_KEYS
            },
            "performance_snapshot": performance_snapshot,
        },
        "failures": failures,
        "ok": not failures,
    }
    Path("reports/publication_validation.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(6)


if __name__ == "__main__":
    main()
