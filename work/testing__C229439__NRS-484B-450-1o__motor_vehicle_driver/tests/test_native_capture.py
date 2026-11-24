import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
spec = importlib.util.spec_from_file_location("native_capture", FOLDER / "native_capture.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        verts = [NS(x=x, y=y) for x in (0, 2) for y in (1, 3) for _ in (0, 1)]
        self.ego = NS(id=7, get_velocity=lambda: NS(length=lambda: 0.0),
                      get_transform=lambda: object(),
                      bounding_box=NS(get_world_vertices=lambda transform: verts))
        self.snapshot = NS(frame=10, timestamp=NS(elapsed_seconds=0.5))
        self.case = {"case_id": "exact", "halt_action": "park"}
        self.site = {"parking_polygon": [[0, 0], [3, 0], [3, 4]]}
        self.device = {"device_id": "sign", "exact_instruction": "NO PARKING",
                       "prohibited_actions": ["park"]}
        self.context = {"traffic_conflict": False, "police_direction": False,
                        "law_direction": False, "device_direction": False,
                        "device_effective": True, "halt_activity": "park"}

    def test_original_footprint_and_context(self):
        row = module.original_row(self.snapshot, self.ego, self.case,
                                  self.device, self.site, self.context, {})
        self.assertEqual(row["body_corners_xy"], [[0, 1], [2, 1], [2, 3], [0, 3]])
        self.assertEqual(row["device_effective"], True)

    def test_missing_independent_exception_rejected(self):
        self.context.pop("traffic_conflict")
        with self.assertRaisesRegex(ValueError, "per-frame context missing"):
            module.original_row(self.snapshot, self.ego, self.case,
                                self.device, self.site, self.context, {})


if __name__ == "__main__":
    unittest.main()
