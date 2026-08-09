from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_dataset", PROJECT / "src/generate_dataset.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class PipelineTests(unittest.TestCase):
    def test_generator_is_deterministic(self) -> None:
        generator = load_generator()
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.csv"
            second = Path(directory) / "second.csv"
            meta_a = generator.write_split(first, "test", 40, 77)
            meta_b = generator.write_split(second, "test", 40, 77)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(meta_a["sha256_rows_without_header"], meta_b["sha256_rows_without_header"])

    def test_generated_schema_and_bounds(self) -> None:
        path = PROJECT / "data/raw/train.csv"
        if not path.exists():
            self.skipTest("dataset not generated yet")
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        distances = [float(row[f"d{index:03d}"]) for index in range(64)]
        velocities = [float(row[f"v{index:03d}"]) for index in range(64)]
        features = [float(row[f"f{index:03d}"]) for index in range(144)]
        self.assertTrue(all(0.0 <= value <= 20.0 for value in distances))
        self.assertTrue(all(-6.1 <= value <= 1.0 for value in velocities))
        self.assertTrue(all(0.0 <= value <= 1.0 for value in features))
        self.assertIn(int(row["label"]), (0, 1))

    def test_model_validation_contract(self) -> None:
        path = PROJECT / "artifacts/model.json"
        if not path.exists():
            self.skipTest("model not trained yet")
        model = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(model["feature_count"], 144)
        self.assertEqual(len(model["weights_float"]), 144)
        self.assertEqual(len(model["weights_int8"]), 144)
        self.assertGreaterEqual(model["validation"]["int8"]["recall"], 0.98)
        self.assertGreaterEqual(model["validation"]["int8"]["accuracy"], 0.95)

    def test_binaries_report_actions(self) -> None:
        binary = PROJECT / "build/reflexedge_neon"
        dataset = PROJECT / "data/processed/test.csv"
        if not binary.exists() or not dataset.exists():
            self.skipTest("binary or dataset not built yet")
        output = subprocess.check_output(
            [str(binary), "--dataset", str(dataset), "--demo", "3"], text=True
        )
        events = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(len(events), 3)
        self.assertTrue(all(event["action"] in {"GO", "HOLD", "BRAKE"} for event in events))

    def test_benchmark_covers_raw_sensor_to_action(self) -> None:
        binary = PROJECT / "build/reflexedge_neon"
        dataset = PROJECT / "data/processed/test.csv"
        if not binary.exists() or not dataset.exists():
            self.skipTest("binary or dataset not built yet")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "benchmark.json"
            subprocess.run(
                [
                    str(binary),
                    "--dataset",
                    str(dataset),
                    "--repeat",
                    "2",
                    "--output",
                    str(output),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("raw 64-beam distance and velocity", report["end_to_end"]["scope"])
        self.assertGreater(report["end_to_end"]["inferences"], 0)
        self.assertGreater(report["end_to_end"]["latency_ns"]["p95"], 0)

    def test_non_arm_evidence_is_rejected(self) -> None:
        comparison = PROJECT / "reports/comparison.json"
        rights = PROJECT / "reports/rights_check.json"
        if not comparison.exists() or not rights.exists():
            self.skipTest("evidence checks not generated yet")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_hardware = temp / "hardware.json"
            fake_output = temp / "validation.json"
            fake_hardware.write_text('{"architecture":"x86_64"}\n', encoding="utf-8")
            process = subprocess.run(
                [
                    "python3",
                    str(PROJECT / "scripts/validate_buidl.py"),
                    "--comparison",
                    str(comparison),
                    "--rights",
                    str(rights),
                    "--hardware",
                    str(fake_hardware),
                    "--output",
                    str(fake_output),
                ],
                cwd=PROJECT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 5)
            self.assertIn("hardware evidence is not Arm64", fake_output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
