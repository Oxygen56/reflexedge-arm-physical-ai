#!/usr/bin/env python3
"""Full deterministic audit of the generated sensor corpus."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def audit(path: Path, expected_split: str) -> dict:
    identifiers: set[str] = set()
    rows = positives = missing = out_of_bounds = wrong_split = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        feature_names = sorted(name for name in (reader.fieldnames or []) if name.startswith("f"))
        for row in reader:
            rows += 1
            identifiers.add(row["sample_id"])
            positives += int(row["label"])
            wrong_split += row["split"] != expected_split
            missing += sum(value == "" for value in row.values())
            out_of_bounds += sum(not 0.0 <= float(row[name]) <= 1.0 for name in feature_names)
    return {
        "path": str(path),
        "rows": rows,
        "columns": 5 + len(feature_names),
        "feature_count": len(feature_names),
        "positive_rows": positives,
        "duplicate_ids": rows - len(identifiers),
        "missing_values": missing,
        "out_of_bounds_features": out_of_bounds,
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
        for field in ("duplicate_ids", "missing_values", "out_of_bounds_features", "wrong_split_rows"):
            if result[field] != 0:
                failures.append(f"{split} {field}={result[field]}")
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
