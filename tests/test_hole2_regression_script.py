import subprocess
import unittest
from pathlib import Path


class Hole2RegressionScriptTests(unittest.TestCase):
    def test_script_has_valid_shell_and_documents_required_arguments(self):
        script = Path("scripts/run_hole2_full_regression.sh")
        completed = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        help_result = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
        self.assertEqual(0, help_result.returncode, help_result.stderr)
        for name in (
            "REFERENCE_ANNOTATION", "REFERENCE_IMAGE",
            "NORMAL_DIRECTORY", "DEFECTIVE_DIRECTORY", "OUTPUT_DIRECTORY",
        ):
            self.assertIn(name, help_result.stdout)

    def test_script_rejects_worktree_output_before_creating_logs(self):
        output = Path("regression-output-must-not-exist")
        completed = subprocess.run(
            [
                "bash", "scripts/run_hole2_full_regression.sh",
                "/external/reference.json", "/external/reference.bmp",
                "/external/normal", "/external/defective", str(output),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("outside the Git worktree", completed.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
