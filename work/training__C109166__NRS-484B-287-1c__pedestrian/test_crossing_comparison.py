"""Independent comparison audit mutations against complete synthetic source rows."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native" / "crossing"))
from test_original_saved import build
from audit_crossing_comparison import audit


class ComparisonTests(unittest.TestCase):
    def test_only_crossing_location_differs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marked, unmarked = root / "marked", root / "unmarked"
            marked.mkdir()
            unmarked.mkdir()
            build(marked, "marked_crosswalk")
            build(unmarked, "unmarked_midblock")
            receipt = audit(marked, unmarked)
            self.assertEqual(receipt["observed_x_separation_m"], [20.0, 20.0])
            self.assertFalse(receipt["legal_verdict_claimed"])
            path = unmarked / "controls-original.jsonl"
            original = path.read_text()
            rows = original.splitlines()
            changed = json.loads(rows[259])
            changed["controls"][0]["native_state"] = "Red"
            rows[259] = json.dumps(changed)
            path.write_text("\n".join(rows) + "\n")
            with self.assertRaisesRegex(ValueError, "control state differs"):
                audit(marked, unmarked)
            path.write_text(original)
            config = unmarked / "config.json"
            value = json.loads(config.read_text())
            value["detail_camera_height_m"] = 3.0
            config.write_text(json.dumps(value) + "\n")
            with self.assertRaisesRegex(ValueError, "fixed condition differs"):
                audit(marked, unmarked)


if __name__ == "__main__":
    unittest.main()
