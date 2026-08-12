from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class ReproducibilityPortabilityTests(unittest.TestCase):
    def test_public_entrypoints_do_not_use_private_competition_tooling(self) -> None:
        for relative_path in ("Makefile", "scripts/reproduce.sh"):
            content = (PROJECT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertNotIn(".competition/bin/contestctl", content)
                self.assertNotIn("/.codex/skills/", content)
                self.assertNotIn("/Users/", content)

    def test_repository_data_audit_runs_without_dot_competition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "fresh-clone"
            (clone / "scripts").mkdir(parents=True)
            shutil.copy2(PROJECT / "scripts/data_contract.py", clone / "scripts/data_contract.py")
            shutil.copytree(PROJECT / "data/raw", clone / "data/raw")

            process = subprocess.run(
                ["python3", "scripts/data_contract.py"],
                cwd=clone,
                text=True,
                capture_output=True,
            )

            self.assertFalse((clone / ".competition").exists())
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads((clone / "reports/data_contract.json").read_text(encoding="utf-8"))
            self.assertTrue(report["ok"])
            self.assertEqual(report["failures"], [])

    def test_optional_contestctl_wrapper_accepts_portable_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake_tool = Path(directory) / "contestctl.py"
            fake_tool.write_text(
                "import json, sys\nprint(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            environment["CONTESTCTL_PY"] = str(fake_tool)

            process = subprocess.run(
                [str(PROJECT / ".competition/bin/contestctl"), "toolcheck", "--portable"],
                cwd=PROJECT,
                env=environment,
                text=True,
                capture_output=True,
            )

            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout), ["toolcheck", "--portable"])


if __name__ == "__main__":
    unittest.main()
