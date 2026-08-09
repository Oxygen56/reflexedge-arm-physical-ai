#!/usr/bin/env python3
"""Validate the local judge package before any external submission."""

from __future__ import annotations

import json
import argparse
from pathlib import Path


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
    "reports/video_validation.json",
    "demo/video/reflexedge-evidence-demo.mp4",
    "scripts/reproduce.sh",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, default=Path("reports/comparison.json"))
    parser.add_argument("--rights", type=Path, default=Path("reports/rights_check.json"))
    parser.add_argument("--hardware", type=Path, default=Path("reports/hardware.json"))
    parser.add_argument("--video", type=Path, default=Path("reports/video_validation.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/buidl_validation.json"))
    args = parser.parse_args()
    failures = [f"missing {path}" for path in REQUIRED_FILES if not Path(path).is_file()]
    if args.comparison.is_file():
        comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
        if not comparison.get("ready_for_claim"):
            failures.append("benchmark comparison has not passed all claim gates")
    if args.rights.is_file():
        rights = json.loads(args.rights.read_text(encoding="utf-8"))
        if not rights.get("ok"):
            failures.append("rights check has failures")
    if args.hardware.is_file():
        hardware = json.loads(args.hardware.read_text(encoding="utf-8"))
        if hardware.get("architecture") not in {"arm64", "aarch64"}:
            failures.append("hardware evidence is not Arm64")
        if hardware.get("neon_available") != "1":
            failures.append("hardware evidence does not confirm Arm NEON")
    if args.video.is_file():
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
    result = {"failures": failures, "ok": not failures, "required_files": REQUIRED_FILES}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(5)


if __name__ == "__main__":
    main()
