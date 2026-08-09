#!/usr/bin/env python3
"""Verify that judge-facing public artifacts are anonymously reachable."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_API = "https://api.github.com/repos/Oxygen56/reflexedge-arm-physical-ai"
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
        status, _, body = fetch(LICENSE_URL)
        checks["license"] = {"status": status, "mit_visible": b"MIT License" in body}
        if status != 200 or b"MIT License" not in body:
            failures.append("public repository does not expose the MIT license")
    except Exception as error:
        failures.append(f"license check failed: {error}")

    try:
        status, content_type, body = fetch(VIDEO_URL)
        checks["video"] = {
            "status": status,
            "content_type": content_type,
            "size_bytes": len(body),
        }
        if status != 200 or len(body) < 1_000_000:
            failures.append("public evidence video is missing or unexpectedly small")
    except Exception as error:
        failures.append(f"video check failed: {error}")

    try:
        status, content_type, body = fetch(DEMO_URL)
        checks["demo"] = {
            "status": status,
            "content_type": content_type,
            "reflexedge_marker": b"ReflexEdge" in body,
        }
        if status != 200 or b"ReflexEdge" not in body:
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
