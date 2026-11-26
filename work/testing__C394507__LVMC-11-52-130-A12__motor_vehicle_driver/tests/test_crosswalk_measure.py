"""Source-shaped saved measurements retain arithmetic and legal uncertainty."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import crosswalk_measure as measure
import crosswalk_site as site


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case_id = site.ASSIGNMENT_ID + "__destination_inside_20ft"
        self.site = {"requested_activity": "destination_stop",
                     "requested_exception": "none", "crosswalk_marked": True,
                     "road_id": 1, "lane_id": -1,
                     "crossing_polygon_xy_m": [[0, -2], [2, -2], [2, 2], [0, 2]]}
        (self.root / "original-site.json").write_text(json.dumps(self.site) + "\n")
        for view in ("overview", "approach", "reference_corner", "driver_reference"):
            (self.root / (view + ".mkv")).write_text("diagnostic video placeholder\n")
        self.rows = [{"frame": 100 + i, "time_s": i / 20,
                      "road_id": 1, "lane_id": -1,
                      "activity_readback": "destination_stop",
                      "exception_readback": "none",
                      "ego_speed_mps": 0 if i >= 4 else 1,
                      "ego_body_polygon_xy_m": [[7.9, -1], [9.9, -1],
                                                 [9.9, 1], [7.9, 1]],
                      "camera_frames": {view: {"member": f"{100+i:08d}.png",
                                               "sha256": "a" * 64}
                                        for view in ("overview", "approach",
                                                     "reference_corner", "driver_reference")}}
                     for i in range(9)]
        self.refresh()

    def refresh(self):
        packet = {"source_kind": "diagnostic_fixture", "diagnostic_fixture": True,
                  "assignment_id": site.ASSIGNMENT_ID, "case_id": self.case_id,
                  "site_sha256": hashlib.sha256((self.root / "original-site.json").read_bytes()).hexdigest(),
                  "fps": 20, "frame_count": len(self.rows), "samples": self.rows,
                  "camera_archives": {view: {"path": view + ".mkv"}
                                      for view in ("overview", "approach",
                                                   "reference_corner", "driver_reference")}}
        (self.root / "original-crosswalk-history.json").write_text(json.dumps(packet) + "\n")

    def test_distance_preserves_legal_uncertainty(self):
        result = measure.measure(self.root, self.case_id, diagnostic=True)
        self.assertAlmostEqual(result["body_clearance_min_m"], 5.9)
        self.assertEqual(result["twenty_feet_m_arithmetic_reference"], 6.096)
        self.assertEqual(result["stop_stand_park_judgment"], "unresolved")
        self.assertEqual(result["stationary_sample_frames"], list(range(104, 109)))

    def test_missing_original_history_rejected(self):
        (self.root / "original-crosswalk-history.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            measure.measure(self.root, self.case_id, diagnostic=True)

    def test_stale_activity_rejected(self):
        self.rows[2]["activity_readback"] = "destination_park"
        self.refresh()
        with self.assertRaisesRegex(ValueError, "activity or exception"):
            measure.measure(self.root, self.case_id, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
