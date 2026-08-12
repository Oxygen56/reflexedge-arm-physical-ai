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


def load_demo_video_builder():
    spec = importlib.util.spec_from_file_location(
        "build_demo_video", PROJECT / "scripts/build_demo_video.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_publication_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_publication", PROJECT / "scripts/validate_publication.py"
    )
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
        validation = model["validation"]
        self.assertEqual(
            validation["action_disagreement_scope"],
            "full three-state GO/HOLD/BRAKE command equality",
        )
        self.assertGreaterEqual(
            validation["float_vs_int8_action_disagreements"],
            validation["float_vs_int8_brake_decision_disagreements"],
        )
        self.assertEqual(validation["int8_brake_false_negative_disagreements_vs_float"], 0)
        self.assertEqual(validation["additional_false_negatives_vs_float"], 0)

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

    def test_video_generator_renders_explicit_action_safety_counts(self) -> None:
        comparison_path = PROJECT / "reports/comparison.json"
        if not comparison_path.exists():
            self.skipTest("comparison evidence not generated yet")
        builder = load_demo_video_builder()
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        safety_scene = builder.safety_scene(comparison)
        social_scene = builder.social_scene(comparison)
        for label, key in (
            ("FULL GO/HOLD/BRAKE DISAGREEMENTS", "scalar_vs_int8_action_disagreements"),
            ("BRAKE-BOUNDARY DISAGREEMENTS", "scalar_vs_int8_brake_decision_disagreements"),
            ("MISSED SCALAR BRAKES", "int8_brake_false_negative_disagreements_vs_scalar"),
            ("ADDITIONAL INT8 BRAKES", "int8_additional_brake_decisions_vs_scalar"),
            ("ADDED GROUND-TRUTH FALSE NEGATIVES", "additional_false_negatives_vs_scalar"),
        ):
            self.assertIn(label, safety_scene)
            self.assertIn(f">{comparison[key]}</text>", safety_scene)
        self.assertIn(
            f"{comparison['int8_brake_false_negative_disagreements_vs_scalar']} MISSED SCALAR BRAKES",
            social_scene,
        )
        self.assertIn(
            f"{comparison['additional_false_negatives_vs_scalar']} ADDED GT FNs",
            social_scene,
        )

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

    def test_action_disagreement_metrics_distinguish_three_state_and_brake_safety(self) -> None:
        binaries = {
            "scalar": PROJECT / "build/reflexedge_scalar",
            "int8": PROJECT / "build/reflexedge_neon",
        }
        dataset = PROJECT / "data/processed/test.csv"
        if not all(path.exists() for path in (*binaries.values(), dataset)):
            self.skipTest("binaries or dataset not built yet")

        with tempfile.TemporaryDirectory() as directory:
            reports = {}
            events = {}
            for engine, binary in binaries.items():
                output = Path(directory) / f"{engine}.json"
                subprocess.run(
                    [
                        str(binary),
                        "--dataset",
                        str(dataset),
                        "--repeat",
                        "1",
                        "--output",
                        str(output),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
                reports[engine] = json.loads(output.read_text(encoding="utf-8"))
                demo = subprocess.check_output(
                    [
                        str(binary),
                        "--dataset",
                        str(dataset),
                        "--demo",
                        str(reports[engine]["rows"]),
                    ],
                    text=True,
                )
                events[engine] = [json.loads(line) for line in demo.splitlines()]

        self.assertEqual(len(events["scalar"]), len(events["int8"]))
        paired = list(zip(events["scalar"], events["int8"]))
        three_state_disagreements = sum(
            scalar["action"] != int8["action"] for scalar, int8 in paired
        )
        brake_decision_disagreements = sum(
            (scalar["action"] == "BRAKE") != (int8["action"] == "BRAKE")
            for scalar, int8 in paired
        )
        brake_false_negative_disagreements = sum(
            scalar["action"] == "BRAKE" and int8["action"] != "BRAKE"
            for scalar, int8 in paired
        )
        additional_brake_decisions = sum(
            scalar["action"] != "BRAKE" and int8["action"] == "BRAKE"
            for scalar, int8 in paired
        )
        additional_false_negatives = sum(
            scalar["truth_brake"] == 1
            and scalar["action"] == "BRAKE"
            and int8["action"] != "BRAKE"
            for scalar, int8 in paired
        )
        expected = {
            "scalar_vs_int8_action_disagreements": three_state_disagreements,
            "scalar_vs_int8_brake_decision_disagreements": brake_decision_disagreements,
            "int8_brake_false_negative_disagreements_vs_scalar": brake_false_negative_disagreements,
            "int8_additional_brake_decisions_vs_scalar": additional_brake_decisions,
            "additional_false_negatives_vs_scalar": additional_false_negatives,
        }
        for report in reports.values():
            self.assertEqual(report["action_disagreement_scope"], "full three-state GO/HOLD/BRAKE command equality")
            for key, value in expected.items():
                self.assertEqual(report[key], value)

        self.assertEqual(three_state_disagreements, 15)
        self.assertEqual(brake_decision_disagreements, 3)
        self.assertGreater(three_state_disagreements, brake_decision_disagreements)
        self.assertEqual(brake_false_negative_disagreements, 0)
        self.assertEqual(additional_brake_decisions, 3)
        self.assertEqual(additional_false_negatives, 0)

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

    def test_buidl_gate_rejects_int8_missed_scalar_brake(self) -> None:
        comparison = PROJECT / "reports/comparison.json"
        rights = PROJECT / "reports/rights_check.json"
        hardware = PROJECT / "reports/hardware.json"
        video = PROJECT / "reports/video_validation.json"
        if not all(path.exists() for path in (comparison, rights, hardware, video)):
            self.skipTest("evidence checks not generated yet")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_comparison = temp / "comparison.json"
            fake_output = temp / "validation.json"
            report = json.loads(comparison.read_text(encoding="utf-8"))
            report["scalar_vs_int8_action_disagreements"] += 1
            report["scalar_vs_int8_brake_decision_disagreements"] += 1
            report["int8_brake_false_negative_disagreements_vs_scalar"] = 1
            report["ready_for_claim"] = True
            fake_comparison.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            process = subprocess.run(
                [
                    "python3",
                    str(PROJECT / "scripts/validate_buidl.py"),
                    "--comparison",
                    str(fake_comparison),
                    "--rights",
                    str(rights),
                    "--hardware",
                    str(hardware),
                    "--video",
                    str(video),
                    "--output",
                    str(fake_output),
                ],
                cwd=PROJECT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 5)
            failures = json.loads(fake_output.read_text(encoding="utf-8"))["failures"]
            self.assertIn("int8 drops one or more scalar BRAKE decisions", failures)

    def test_buidl_gate_rejects_missing_override_evidence(self) -> None:
        rights = PROJECT / "reports/rights_check.json"
        hardware = PROJECT / "reports/hardware.json"
        video = PROJECT / "reports/video_validation.json"
        if not all(path.exists() for path in (rights, hardware, video)):
            self.skipTest("evidence checks not generated yet")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            missing_comparison = temp / "missing-comparison.json"
            fake_output = temp / "validation.json"
            process = subprocess.run(
                [
                    "python3",
                    str(PROJECT / "scripts/validate_buidl.py"),
                    "--comparison",
                    str(missing_comparison),
                    "--rights",
                    str(rights),
                    "--hardware",
                    str(hardware),
                    "--video",
                    str(video),
                    "--output",
                    str(fake_output),
                ],
                cwd=PROJECT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 5)
            failures = json.loads(fake_output.read_text(encoding="utf-8"))["failures"]
            self.assertIn(f"missing comparison evidence: {missing_comparison}", failures)

    def test_buidl_gate_rejects_added_ground_truth_false_negative(self) -> None:
        comparison = PROJECT / "reports/comparison.json"
        rights = PROJECT / "reports/rights_check.json"
        hardware = PROJECT / "reports/hardware.json"
        video = PROJECT / "reports/video_validation.json"
        if not all(path.exists() for path in (comparison, rights, hardware, video)):
            self.skipTest("evidence checks not generated yet")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_comparison = temp / "comparison.json"
            fake_output = temp / "validation.json"
            report = json.loads(comparison.read_text(encoding="utf-8"))
            report["scalar_vs_int8_action_disagreements"] += 1
            report["scalar_vs_int8_brake_decision_disagreements"] += 1
            report["int8_brake_false_negative_disagreements_vs_scalar"] = 1
            report["additional_false_negatives_vs_scalar"] = 1
            report["ready_for_claim"] = True
            fake_comparison.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            process = subprocess.run(
                [
                    "python3",
                    str(PROJECT / "scripts/validate_buidl.py"),
                    "--comparison",
                    str(fake_comparison),
                    "--rights",
                    str(rights),
                    "--hardware",
                    str(hardware),
                    "--video",
                    str(video),
                    "--output",
                    str(fake_output),
                ],
                cwd=PROJECT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 5)
            failures = json.loads(fake_output.read_text(encoding="utf-8"))["failures"]
            self.assertIn("int8 introduces one or more ground-truth false negatives", failures)

    def test_buidl_gate_rejects_stale_video_performance_snapshot(self) -> None:
        video_path = PROJECT / "reports/video_validation.json"
        if not video_path.exists():
            self.skipTest("video evidence not generated yet")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            stale_video = temp / "video.json"
            output = temp / "validation.json"
            video = json.loads(video_path.read_text(encoding="utf-8"))
            video["performance_snapshot"]["headline"][
                "pipeline_p95_speedup_median"
            ] = 3.01
            stale_video.write_text(json.dumps(video), encoding="utf-8")
            process = subprocess.run(
                [
                    "python3",
                    str(PROJECT / "scripts/validate_buidl.py"),
                    "--video",
                    str(stale_video),
                    "--output",
                    str(output),
                ],
                cwd=PROJECT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(process.returncode, 5)
            failures = json.loads(output.read_text(encoding="utf-8"))["failures"]
            self.assertIn(
                "video performance snapshot does not exactly match comparison and trial evidence",
                failures,
            )

    def test_publication_gate_rejects_old_performance_page(self) -> None:
        validator = load_publication_validator()
        from scripts.performance_snapshot import build_performance_snapshot

        load = lambda path: json.loads((PROJECT / path).read_text(encoding="utf-8"))
        snapshot = build_performance_snapshot(
            load("reports/comparison.json"),
            load("reports/baseline.json"),
            load("reports/optimized.json"),
            load("reports/trials.json"),
        )
        old_page = (
            "<strong>3.01×</strong><p>median p95 · raw sensor → action</p>"
            "<span>P95 · FINAL RUN</span><div><del>5480.60 ns</del>"
            "<strong>700.50 ns</strong></div>"
            "<span>MODEL BYTES</span><div><del>584 B</del><strong>160 B</strong></div>"
            "<span>ACCURACY</span><div><del>98.24%</del><strong>98.20%</strong></div>"
        ).encode()
        checks = validator.demo_performance_checks(old_page, snapshot)
        self.assertFalse(checks["headline_p95"])
        self.assertFalse(checks["final_run_p95"])
        self.assertTrue(checks["model_bytes"])
        self.assertTrue(checks["accuracy"])


if __name__ == "__main__":
    unittest.main()
