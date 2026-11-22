"""Native runner accepts only the selected untouched materialized attempt."""
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_runner import check_materialized_package


class MaterializedRunnerTests(unittest.TestCase):
    def test_selected_package_and_replay_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scene = {"case_id": "exact-case", "source": "retained"}
            (root / "scene.json").write_text(json.dumps(scene))
            (root / "config.json").write_text(json.dumps({"selected_case_id": "exact-case"}))
            (root / "construction.json").write_text(json.dumps({"case_id": "exact-case"}))
            (root / "runner.py").write_text("# selected wrapper\n")
            check_materialized_package(root, scene)
            (root / "trace.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "already started"):
                check_materialized_package(root, scene)
            (root / "trace.jsonl").unlink()
            (root / "scene.json").write_text(json.dumps({"case_id": "other"}))
            with self.assertRaisesRegex(ValueError, "scene differs"):
                check_materialized_package(root, scene)


if __name__ == "__main__":
    unittest.main()
