#!/usr/bin/env python3
"""Verify that judge-facing public artifacts are anonymously reachable."""

from __future__ import annotations

import json
import hashlib
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_API = "https://api.github.com/repos/Oxygen56/reflexedge-arm-physical-ai"
COMMIT_API = REPOSITORY_API + "/commits/main"
LICENSE_URL = "https://raw.githubusercontent.com/Oxygen56/reflexedge-arm-physical-ai/main/LICENSE"
VIDEO_URL = "https://raw.githubusercontent.com/Oxygen56/reflexedge-arm-physical-ai/main/demo/video/reflexedge-evidence-demo.mp4"
DEMO_URL = "https://reflexedge-arm-ai.jiangth99.chatgpt.site"


def fetch(url: str) -> tuple[int, str, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "ReflexEdge-publication-validator/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read()


def main() -> None:
    failures: list[str] = []
    checks: dict[str, object] = {}
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
        marker = b"median p95"
        dataset_marker = json.loads(Path("reports/comparison.json").read_text(encoding="utf-8"))[
            "dataset_sha256"
        ][:12].encode()
        checks["demo"] = {
            "status": status,
            "content_type": content_type,
            "reflexedge_marker": b"ReflexEdge" in body,
            "current_metric_marker": marker in body,
            "dataset_marker": dataset_marker in body,
        }
        if (
            status != 200
            or b"ReflexEdge" not in body
            or marker not in body
            or dataset_marker not in body
        ):
            failures.append("public evidence demo is not anonymously reachable")
    except Exception as error:
        failures.append(f"demo check failed: {error}")

    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
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
