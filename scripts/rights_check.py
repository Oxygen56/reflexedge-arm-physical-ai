#!/usr/bin/env python3
"""Fail closed on submission-rights and sensitive-data prerequisites."""

from __future__ import annotations

import json
import re
from pathlib import Path


REQUIRED = [
    Path("LICENSE"),
    Path("THIRD_PARTY_NOTICES.md"),
    Path("reports/rights-ledger.md"),
    Path("README.md"),
]
TEXT_SUFFIXES = {".md", ".py", ".cpp", ".h", ".sh", ".yaml", ".yml", ".json", ".txt"}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "hardware_uuid_value": re.compile(
        r"\b[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\b", re.I
    ),
    "provisioning_udid_value": re.compile(r"\b000081[0-9A-F-]{20,}\b", re.I),
}


def main() -> None:
    failures: list[str] = []
    for path in REQUIRED:
        if not path.is_file():
            failures.append(f"missing required rights artifact: {path}")
    if Path("LICENSE").is_file() and "MIT License" not in Path("LICENSE").read_text(encoding="utf-8"):
        failures.append("LICENSE is not visibly MIT")
    hardware_path = Path("reports/hardware.json")
    if hardware_path.is_file():
        hardware_keys = {key.lower() for key in json.loads(hardware_path.read_text(encoding="utf-8"))}
        forbidden = {key for key in hardware_keys if any(word in key for word in ("serial", "uuid", "udid"))}
        if forbidden:
            failures.append(f"hardware evidence contains forbidden identifier keys: {sorted(forbidden)}")

    scanned = 0
    ignored_roots = {
        ".git",
        ".competition",
        ".next",
        ".wrangler",
        "build",
        "dist",
        "node_modules",
        "frames",
    }
    for path in Path(".").rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in ignored_roots for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        scanned += 1
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                if path == Path("scripts/rights_check.py"):
                    continue
                failures.append(f"{name} pattern in {path}")

    result = {"scanned_text_files": scanned, "failures": failures, "ok": not failures}
    Path("reports/rights_check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
