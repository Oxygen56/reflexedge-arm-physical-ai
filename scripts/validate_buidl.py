#!/usr/bin/env python3
"""Validate the local judge package before any external submission."""

from __future__ import annotations

import json
import argparse
import hashlib
from pathlib import Path

try:
    from scripts.performance_snapshot import (
        build_performance_snapshot,
        source_alignment_failures,
    )
except ModuleNotFoundError:  # direct execution via python3 scripts/validate_buidl.py
    from performance_snapshot import build_performance_snapshot, source_alignment_failures


REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "reports/brief.md",
    "reports/baseline_protocol.md",
    "reports/hardware.json",
    "reports/baseline.json",
    "reports/optimized.json",
    "reports/comparison.json",
    "reports/comparison.md",
    "reports/rights_check.json",
    "artifacts/model.json",
    "data/raw/dataset_metadata.json",
    "reports/data_contract.json",
    "reports/publication_validation.json",
    "reports/trials.json",
    "reports/trials.md",
    "reports/video_validation.json",
    "demo/video/reflexedge-evidence-demo.mp4",
    "scripts/reproduce.sh",
    "submissions/devpost-field-map.md",
    "submissions/devpost-writeup.md",
    "submissions/video-upload.md",
]
ACTION_METRIC_KEYS = (
    "scalar_vs_int8_action_disagreements",
    "scalar_vs_int8_brake_decision_disagreements",
    "int8_brake_false_negative_disagreements_vs_scalar",
    "int8_additional_brake_decisions_vs_scalar",
    "additional_false_negatives_vs_scalar",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, default=Path("reports/comparison.json"))
    parser.add_argument("--baseline", type=Path, default=Path("reports/baseline.json"))
    parser.add_argument("--optimized", type=Path, default=Path("reports/optimized.json"))
    parser.add_argument("--rights", type=Path, default=Path("reports/rights_check.json"))
    parser.add_argument("--hardware", type=Path, default=Path("reports/hardware.json"))
    parser.add_argument("--video", type=Path, default=Path("reports/video_validation.json"))
    parser.add_argument("--trials", type=Path, default=Path("reports/trials.json"))
    parser.add_argument(
        "--publication", type=Path, default=Path("reports/publication_validation.json")
    )
    parser.add_argument("--output", type=Path, default=Path("reports/buidl_validation.json"))
    args = parser.parse_args()
    failures = [f"missing {path}" for path in REQUIRED_FILES if not Path(path).is_file()]
    action_metrics: dict[str, int] | None = None
    comparison: dict | None = None
    baseline: dict | None = None
    optimized: dict | None = None
    trials: dict | None = None
    video: dict | None = None
    performance_snapshot: dict | None = None
    actual_video_sha256: str | None = None
    if not args.comparison.is_file():
        failures.append(f"missing comparison evidence: {args.comparison}")
    else:
        comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
        if not comparison.get("ready_for_claim"):
            failures.append("benchmark comparison has not passed all claim gates")
        action_fields = set(ACTION_METRIC_KEYS)
        missing_action_fields = sorted(action_fields - comparison.keys())
        if missing_action_fields:
            failures.append(
                f"benchmark comparison is missing explicit action safety fields: {missing_action_fields}"
            )
        else:
            action_metrics = {key: int(comparison[key]) for key in ACTION_METRIC_KEYS}
            three_state = int(comparison["scalar_vs_int8_action_disagreements"])
            brake_boundary = int(
                comparison["scalar_vs_int8_brake_decision_disagreements"]
            )
            missed_brakes = int(
                comparison["int8_brake_false_negative_disagreements_vs_scalar"]
            )
            extra_brakes = int(comparison["int8_additional_brake_decisions_vs_scalar"])
            added_false_negatives = int(
                comparison["additional_false_negatives_vs_scalar"]
            )
            if three_state < brake_boundary or brake_boundary != missed_brakes + extra_brakes:
                failures.append("action disagreement counts are internally inconsistent")
            if missed_brakes != 0:
                failures.append("int8 drops one or more scalar BRAKE decisions")
            if added_false_negatives != 0:
                failures.append("int8 introduces one or more ground-truth false negatives")
    if not args.baseline.is_file():
        failures.append(f"missing baseline evidence: {args.baseline}")
    else:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    if not args.optimized.is_file():
        failures.append(f"missing optimized evidence: {args.optimized}")
    else:
        optimized = json.loads(args.optimized.read_text(encoding="utf-8"))
    if not args.rights.is_file():
        failures.append(f"missing rights evidence: {args.rights}")
    else:
        rights = json.loads(args.rights.read_text(encoding="utf-8"))
        if not rights.get("ok"):
            failures.append("rights check has failures")
    if not args.hardware.is_file():
        failures.append(f"missing hardware evidence: {args.hardware}")
    else:
        hardware = json.loads(args.hardware.read_text(encoding="utf-8"))
        if hardware.get("architecture") not in {"arm64", "aarch64"}:
            failures.append("hardware evidence is not Arm64")
        if hardware.get("neon_available") != "1":
            failures.append("hardware evidence does not confirm Arm NEON")
    if not args.video.is_file():
        failures.append(f"missing video evidence: {args.video}")
    else:
        video = json.loads(args.video.read_text(encoding="utf-8"))
        if not 0 < float(video.get("duration_seconds", 0)) < 180:
            failures.append("demo video must be shorter than three minutes")
        streams = video.get("streams", [])
        video_streams = [stream for stream in streams if stream.get("codec_name") == "h264"]
        if not video_streams:
            failures.append("demo video does not report an H.264 stream")
        elif not any(
            stream.get("width") == 1920 and stream.get("height") == 1080
            for stream in video_streams
        ):
            failures.append("demo video is not verified at 1920x1080")
        if video.get("third_party_music") != "none":
            failures.append("demo video music rights are not cleared")
        video_path = Path(str(video.get("video", "")))
        if not video_path.is_file():
            failures.append(f"demo video artifact is missing: {video_path}")
        else:
            actual_video_sha256 = sha256(video_path)
            if video.get("sha256") != actual_video_sha256:
                failures.append("video evidence hash does not match the demo video artifact")
        thumbnail_path = Path("demo/site/public/og.png")
        if not thumbnail_path.is_file():
            failures.append(f"demo thumbnail is missing: {thumbnail_path}")
        elif video.get("thumbnail_sha256") != sha256(thumbnail_path):
            failures.append("video evidence thumbnail hash does not match the demo cover")
        if action_metrics is not None and video.get("action_metrics") != action_metrics:
            failures.append("video action metrics do not match the benchmark comparison")
    if not args.trials.is_file():
        failures.append(f"missing paired-trial evidence: {args.trials}")
    else:
        trials = json.loads(args.trials.read_text(encoding="utf-8"))
        if not trials.get("ready_for_claim"):
            failures.append("independent paired benchmark trials have not passed")
        if int(trials.get("trials", 0)) < 5:
            failures.append("fewer than five independent benchmark trials")
    if all(item is not None for item in (comparison, baseline, optimized, trials)):
        assert comparison is not None and baseline is not None
        assert optimized is not None and trials is not None
        try:
            failures.extend(
                source_alignment_failures(comparison, baseline, optimized, trials)
            )
            performance_snapshot = build_performance_snapshot(
                comparison, baseline, optimized, trials
            )
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            failures.append(f"performance evidence is incomplete or malformed: {error}")
        if (
            performance_snapshot is not None
            and video is not None
            and video.get("performance_snapshot") != performance_snapshot
        ):
            failures.append(
                "video performance snapshot does not exactly match comparison and trial evidence"
            )
    if not args.publication.is_file():
        failures.append(f"missing publication evidence: {args.publication}")
    else:
        publication = json.loads(args.publication.read_text(encoding="utf-8"))
        if not publication.get("ok"):
            failures.append("public repository, demo, or video availability gate failed")
        if (
            action_metrics is not None
            and actual_video_sha256 is not None
            and performance_snapshot is not None
        ):
            expected_snapshot = {
                "video_sha256": actual_video_sha256,
                "action_metrics": action_metrics,
                "performance_snapshot": performance_snapshot,
            }
            if publication.get("evidence_snapshot") != expected_snapshot:
                failures.append(
                    "publication validation is stale for the current performance, action metrics, or video"
                )
    result = {"failures": failures, "ok": not failures, "required_files": REQUIRED_FILES}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(5)


if __name__ == "__main__":
    main()
