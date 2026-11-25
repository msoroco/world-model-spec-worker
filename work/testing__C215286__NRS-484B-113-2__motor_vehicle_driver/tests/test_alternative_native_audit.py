"""The Native handoff must reject a software fixture before source review."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


class NativeAuditBoundaryTests(unittest.TestCase):
    def test_synthetic_attempt_cannot_enter_native_source_audit(self):
        scratch = REPO / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch, prefix="c215286-native-audit-test-") as temporary:
            env = dict(os.environ)
            env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(Path(temporary) / "pipeline")
            case_id = PACKAGE.name + "__reverse_into_intersection"
            command = [sys.executable, str(PACKAGE / "reverse_alternative_delivery_audit.py"),
                       "--native", temporary, case_id, str(Path(temporary) / "owner.json")]
            completed = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                                       text=True, timeout=30, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Original non-diagnostic Native provenance required", completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
