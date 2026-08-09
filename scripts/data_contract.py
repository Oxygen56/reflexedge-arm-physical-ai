#!/usr/bin/env python3
"""Full deterministic audit of the generated sensor corpus."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def audit(path: Path, expected_split: str) -> dict:
    identifiers: set[str] = set()
    rows = positives = missing = out_of_bounds = raw_out_of_bounds = wrong_split = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        feature_names = sorted(name for name in fieldnames if name.startswith("f") and name[1:].isdigit())
        distance_names = sorted(name for name in fieldnames if name.startswith("d") and name[1:].isdigit())
        velocity_names = sorted(name for name in fieldnames if name.startswith("v") and name[1:].isdigit())
        schema_errors = []
        if len(feature_names) != 144:
            schema_errors.append(f"feature count {len(feature_names)} != 144")
        if len(distance_names) != 64:
            schema_errors.append(f"distance beam count {len(distance_names)} != 64")
        if len(velocity_names) != 64:
            schema_errors.append(f"velocity beam count {len(velocity_names)} != 64")
        for row in reader:
            rows += 1
            identifiers.add(row["sample_id"])
            positives += int(row["label"])
            wrong_split += row["split"] != expected_split
            missing += sum(value == "" for value in row.values())
            out_of_bounds += sum(not 0.0 <= float(row[name]) <= 1.0 for name in feature_names)
            raw_out_of_bounds += sum(not 0.0 <= float(row[name]) <= 20.0 for name in distance_names)
            raw_out_of_bounds += sum(not -6.1 <= float(row[name]) <= 1.0 for name in velocity_names)
    return {
        "path": str(path),
        "rows": rows,
        "columns": len(fieldnames),
        "feature_count": len(feature_names),
        "distance_beams": len(distance_names),
        "velocity_beams": len(velocity_names),
        "positive_rows": positives,
        "duplicate_ids": rows - len(identifiers),
        "missing_values": missing,
        "out_of_bounds_features": out_of_bounds,
        "out_of_bounds_raw_sensor_values": raw_out_of_bounds,
        "schema_errors": schema_errors,
        "wrong_split_rows": wrong_split,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    expected = {"train": 6000, "validation": 1500, "test": 2500}
    audits = {
        split: audit(Path(f"data/raw/{split}.csv"), split)
        for split in ("train", "validation", "test")
    }
    failures: list[str] = []
    all_ids: set[str] = set()
    for split, result in audits.items():
        if result["rows"] != expected[split]:
            failures.append(f"{split} row count {result['rows']} != {expected[split]}")
        for field in (
            "duplicate_ids",
            "missing_values",
            "out_of_bounds_features",
            "out_of_bounds_raw_sensor_values",
            "wrong_split_rows",
        ):
            if result[field] != 0:
                failures.append(f"{split} {field}={result[field]}")
        failures.extend(f"{split} {error}" for error in result["schema_errors"])
        with Path(f"data/raw/{split}.csv").open(newline="", encoding="utf-8") as handle:
            ids = {row["sample_id"] for row in csv.DictReader(handle)}
        if all_ids.intersection(ids):
            failures.append(f"{split} identifiers overlap another split")
        all_ids.update(ids)
    result = {"audits": audits, "failures": failures, "ok": not failures}
    Path("reports/data_contract.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(6)


if __name__ == "__main__":
    main()
