import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import _read_setup
from runner import capture_original, seal_authored_setup
from test_native_scene import PLAN, packet


class RunnerTests(unittest.TestCase):
    def test_original_output_root_enforced_before_native_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "under .runtime-work"):
                capture_original(Path(directory) / "attempt", Path(directory) / "site.json",
                                 HERE / "case-plan.json", PLAN["cases"][0]["case_id"])

    def test_authored_setup_sealed_from_exact_source_packet(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "site.json"
            source.write_text(json.dumps(packet()))
            case_id = PLAN["cases"][0]["case_id"]
            seal = seal_authored_setup(root, source, HERE / "case-plan.json", case_id)
            document, digest = _read_setup(root, case_id)
            self.assertEqual(seal["sha256"], digest)
            self.assertEqual(document["opendrive_sha256"], packet()["map_sha256"])
            self.assertEqual(document["duration_frames"], 900)
            with self.assertRaisesRegex(ValueError, "retain previous authored setup"):
                seal_authored_setup(root, source, HERE / "case-plan.json", case_id)


if __name__ == "__main__":
    unittest.main()
