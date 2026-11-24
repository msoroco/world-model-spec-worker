import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_delivery import ASSIGNMENT, audit_saved

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__intersection_vehicle_near"
        self.site_path = self.root / "site.json"
        self.site = {"case_id": self.case, "map_sha256": "map-seal",
            "route_sha256": "route-seal", "district_source_sha256": "district-seal",
            "intersection_boundary": {"source_sha256": "boundary-seal",
                "polygon_xy_m": [[.5, -1], [1.5, -1], [1.5, 1], [.5, 1]]}}
        self.site_path.write_text(json.dumps(self.site) + "\n")
        self.native_path = self.root / "native.json"
        frames = []
        for i, yaw in enumerate((0.0, 90.0, 180.0)):
            x = float(i)
            frames.append({"frame": 100 + i, "time_s": i * .05,
                "ego": {"id": "ego", "road_id": 7, "lane_id": 1 if i < 2 else -1,
                    "junction_id": 4 if i == 1 else None, "x": x, "y": 0.0,
                    "yaw_deg": yaw, "body_corners_xy_m": [[x-.1,-.1],[x+.1,-.1],
                                                          [x+.1,.1],[x-.1,.1]]},
                "other_vehicle": {"id": "other", "road_id": 7, "lane_id": -1,
                                  "x": 5.0, "y": 0.0}})
        self.native = {"case_id": self.case, "actor": "motor_vehicle_driver",
            "site_sha256": sha(self.site_path), "map_sha256": "map-seal",
            "route_sha256": "route-seal",
            "district_basis": {"source_sha256": "district-seal"},
            "intersection_boundary": self.site["intersection_boundary"],
            "ego_id": "ego", "other_id": "other", "frames": frames}
        self.native_path.write_text(json.dumps(self.native) + "\n")
        self.manifest_path = self.root / "camera-manifest.json"
        views = {}
        for name in VIEWS:
            rows = []
            for i in range(3):
                path = self.root / f"{name}-{100+i}.png"
                Image.new("RGB", (3, 2), (i+1, 10, 20)).save(path)
                rows.append({"frame": 100+i, "time_s": i*.05,
                             "path": str(path), "sha256": sha(path)})
            views[name] = rows
        self.manifest = {"case_id": self.case, "native_sha256": sha(self.native_path),
                         "frame_count": 3, "fps": 20, "views": views}
        self.manifest_path.write_text(json.dumps(self.manifest) + "\n")

    def audit(self):
        return audit_saved(self.native_path, self.manifest_path, self.site_path,
                           self.case, diagnostic=True,
                           expected_views={name: (3, 2) for name in VIEWS})

    def test_joins_exact_location_motion_and_all_camera_sources(self):
        receipt = self.audit()
        self.assertEqual(receipt["whole_body_inside_intersection_frames"], [101])
        self.assertEqual(receipt["measured_reversal_deg"], 180)
        self.assertEqual(sum(v["decoded_original_pngs"] for v in
                             receipt["decoded_camera_sources"].values()), 12)
        self.assertFalse(receipt["checks"]["physical_completion"])

    def test_rejects_changed_site_and_location_label(self):
        self.site["district_source_sha256"] = "changed"
        self.site_path.write_text(json.dumps(self.site) + "\n")
        with self.assertRaisesRegex(ValueError, "site source binding"):
            self.audit()
        self.site["district_source_sha256"] = "district-seal"
        self.site_path.write_text(json.dumps(self.site) + "\n")
        self.native["site_sha256"] = sha(self.site_path)
        self.native_path.write_text(json.dumps(self.native) + "\n")
        self.case = ASSIGNMENT + "__approach_before_intersection"
        self.site["case_id"] = self.case
        self.site_path.write_text(json.dumps(self.site) + "\n")
        self.native["case_id"] = self.case
        self.native["site_sha256"] = sha(self.site_path)
        self.native_path.write_text(json.dumps(self.native) + "\n")
        with self.assertRaisesRegex(ValueError, "measured U-turn location"):
            self.audit()

    def test_rejects_stale_camera_source(self):
        source = Path(self.manifest["views"]["overview"][0]["path"])
        source.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "original hash"):
            self.audit()

    def test_original_mode_rejects_diagnostic_packet(self):
        with self.assertRaisesRegex(ValueError, "original reviewed Native site"):
            audit_saved(self.native_path, self.manifest_path, self.site_path,
                        self.case, expected_views={name: (3, 2) for name in VIEWS})


if __name__ == "__main__":
    unittest.main()
