import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("parked_activity", ROOT / "parked_activity.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CASE_ID = "testing__C227890__NRS-484B-410__motor_vehicle_driver__rear_wait"


class ParkedActivityTests(unittest.TestCase):
    def rows(self):
        return [{
            "source_kind": "synthetic_fixture", "case_id": CASE_ID, "frame": i,
            "time_s": i / 20, "ego_center_xy_m": [i / 10, -6],
            "other_center_xy_m": [20 - i, -2],
            "ego_speed_mps": 0 if i < 4 else 2,
            "other_speed_mps": 2,
            "ego_in_reviewed_parking_bay": i < 4,
            "ego_on_public_highway": True,
            "parking_permitted_at_time": True,
            "driver_in_control": True,
            "other_approaching": i < 5,
            "paths_overlap": i == 4,
            "passenger_exchange": False, "goods_exchange": False,
        } for i in range(9)]

    def measure(self, rows):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="c227890-activity-", dir=scratch))
        history, seal = root / "activity.jsonl", root / "seal.json"
        raw = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
        history.write_bytes(raw)
        seal.write_text(json.dumps({"format": "diagnostic-parked-activity-seal",
                                    "case_id": CASE_ID, "frame_count": 9, "rate_hz": 20,
                                    "history_sha256": hashlib.sha256(raw).hexdigest()}))
        return module.measure_original_activity(history, seal, CASE_ID, diagnostic=True)

    def test_measurement_tracks_original_not_requested_outcome(self):
        result = self.measure(self.rows())
        self.assertEqual(result["intervals_s"]["parked"], [[0, 0.2]])
        self.assertEqual(result["intervals_s"]["moving"], [[0.2, 0.45]])
        self.assertEqual(result["legal_safety_conclusion"], "unreviewed")

    def test_missing_parking_or_exchange_fails_closed(self):
        rows = self.rows()
        rows[3]["parking_permitted_at_time"] = False
        with self.assertRaisesRegex(ValueError, "parking basis absent"):
            self.measure(rows)
        rows = self.rows()
        rows[3]["passenger_exchange"] = True
        with self.assertRaisesRegex(ValueError, "exchange changes selected branch"):
            self.measure(rows)


if __name__ == "__main__":
    unittest.main()
