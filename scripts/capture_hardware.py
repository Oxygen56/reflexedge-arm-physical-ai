#!/usr/bin/env python3
"""Capture a privacy-safe hardware fingerprint for benchmark evidence."""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path


def command(*args: str) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    evidence = {
        "architecture": platform.machine(),
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "chip": command("sysctl", "-n", "machdep.cpu.brand_string"),
        "logical_cpu_count": command("sysctl", "-n", "hw.logicalcpu"),
        "memory_bytes": command("sysctl", "-n", "hw.memsize"),
        "neon_available": command("sysctl", "-n", "hw.optional.neon"),
        "dot_product_available": command("sysctl", "-n", "hw.optional.arm.FEAT_DotProd"),
        "compiler": command("clang++", "--version").splitlines()[0],
        "privacy": "Serial number, UUID, provisioning identifier, user name, and account data intentionally excluded.",
    }
    output = Path("reports/hardware.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
