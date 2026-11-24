import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("device_saved_delivery", ROOT / "saved_delivery.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
CASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__prohibited_attempt"


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.attempt = Path(self.tmp.name)
        device = {"device_id": 77, "authority_source_sha256": "authority",
                  "legal_consistency_source_sha256": "legal",
                  "display_source_sha256": "display", "governed_approach": "A",
                  "prohibits_u_turn": True}
        frames = []
        for i in range(900):
            frames.append({"frame": 100 + i, "time_s": i / 20.0,
                           "ego": {"id": 42, "road_id": 1, "lane_id": -1 if i == 899 else 1,
                                   "x": i / 20.0, "y": 0, "yaw_deg": 180 if i == 899 else 0,
                                   "approach_id": "A", "u_turn_in_progress": i == 600},
                           "device_readback": {"device_id": 77, "prohibits_u_turn": True,
                                               "visible_to_ego": i >= 1},
                           "cameras": {name: 100 + i for name in mod.CAMERAS}})
        self.native = {"case_id": CASE, "actor": "motor_vehicle_driver",
                       "map_sha256": "map", "route_sha256": "route", "ego_id": 42,
                       "highway_status": {"source_sha256": "highway"},
                       "device": device, "duration_s": 45.0, "diagnostic": False,
                       "frames": frames}
        self.write_native()
        media = {}
        for name in mod.CAMERAS:
            path = self.attempt / (name + ".txt")
            path.write_text("original-camera-source-" + name)
            media[name] = {"path": path.name, "sha256": mod.sha_file(path)}
        self.manifest = {"case_id": CASE, "attempt_id": "attempt-1",
                         "recording_id": "recording-1", "acquisition_kind": "original_native",
                         "native": {"path": "native.json", "sha256": mod.sha_file(self.path)},
                         "media": media}
        self.write_manifest()

    def write_native(self):
        self.path = self.attempt / "native.json"
        self.path.write_text(json.dumps(self.native))

    def write_manifest(self):
        (self.attempt / "saved-sources.json").write_text(json.dumps(self.manifest))

    def test_900_frame_source_join(self):
        out = mod.audit(self.attempt, case_id=CASE)
        self.assertEqual(out["frame_count"], 900)
        self.assertTrue(out["time_join"])
        self.assertFalse(out["actual_pixels"])
        self.assertFalse(out["physical_completion"])

    def test_reject_diagnostic_and_short_capture(self):
        self.native["diagnostic"] = True
        self.write_native()
        self.manifest["native"]["sha256"] = mod.sha_file(self.path)
        self.write_manifest()
        with self.assertRaisesRegex(mod.DeliverySourceError, "diagnostic"):
            mod.audit(self.attempt, case_id=CASE)
        self.native["diagnostic"] = False
        self.native["frames"].pop()
        self.native["frames"][-1]["ego"]["lane_id"] = -1
        self.native["frames"][-1]["ego"]["yaw_deg"] = 180
        self.write_native()
        self.manifest["native"]["sha256"] = mod.sha_file(self.path)
        self.write_manifest()
        with self.assertRaisesRegex(mod.DeliverySourceError, "900 original"):
            mod.audit(self.attempt, case_id=CASE)

    def test_reject_media_hash_and_escape(self):
        (self.attempt / "detail_left.txt").write_text("tampered")
        with self.assertRaisesRegex(mod.DeliverySourceError, "media hash"):
            mod.audit(self.attempt, case_id=CASE)
        self.manifest["media"]["detail_left"]["path"] = "../outside.txt"
        self.write_manifest()
        with self.assertRaisesRegex(mod.DeliverySourceError, "escapes attempt"):
            mod.audit(self.attempt, case_id=CASE)

    def test_reject_frame_join_and_case(self):
        self.native["frames"][400]["cameras"]["detail_right"] = 999
        self.write_native()
        self.manifest["native"]["sha256"] = mod.sha_file(self.path)
        self.write_manifest()
        with self.assertRaisesRegex(mod.DeliverySourceError, "frame identities"):
            mod.audit(self.attempt, case_id=CASE)
        self.manifest["case_id"] = "foreign"
        self.write_manifest()
        with self.assertRaisesRegex(mod.DeliverySourceError, "saved case"):
            mod.audit(self.attempt, case_id=CASE)
