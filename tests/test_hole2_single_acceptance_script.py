import subprocess
import unittest
from pathlib import Path


class Hole2SingleAcceptanceScriptTests(unittest.TestCase):
    def test_script_has_valid_shell_and_documents_required_arguments(self):
        script = Path("scripts/run_hole2_single_acceptance.sh")
        completed = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        help_result = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        for name in (
            "REFERENCE_ANNOTATION", "REFERENCE_IMAGE", "TARGET_IMAGE",
            "LATEST_TRUTH_JSON", "OUTPUT_DIRECTORY",
        ):
            self.assertIn(name, help_result.stdout)
        source = script.read_text(encoding="utf-8")
        self.assertNotIn("/home/ubuntu", source)
        for artifact in (
            "stdout.log", "stderr.log", "exit-code.txt", "algorithm-result.json",
            "acceptance-report.json", "key-metrics.json", "key-metrics.txt",
        ):
            self.assertIn(artifact, source)

    def test_script_rejects_worktree_output_before_creating_logs(self):
        output = Path("single-acceptance-output-must-not-exist")
        completed = subprocess.run(
            [
                "bash", "scripts/run_hole2_single_acceptance.sh",
                "/external/reference.json", "/external/reference.bmp",
                "/external/target.bmp", "/external/latest-truth.json", str(output),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("outside the Git worktree", completed.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
