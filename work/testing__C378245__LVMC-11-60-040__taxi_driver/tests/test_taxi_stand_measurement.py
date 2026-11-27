"""Synthetic source-shape checks; no physical or legal result is claimed."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parents[1] / "taxi_stand_measurement.py"
SPEC = importlib.util.spec_from_file_location("taxi_stand_measurement", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SCRATCH = REPO / ".runtime-work/c378245-taxi-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


class TaxiStandMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        self.case_id = MODULE.ASSIGNMENT + "__designated_stand_park"
        self.packet = {"assignment_id": MODULE.ASSIGNMENT, "cell_id": "C378245",
                       "actor": "taxi_driver", "law_id": "LVMC-11-60-040",
                       "case_id": self.case_id, "recording_id": "synthetic-fixture"}
        self.camera = {name: ("synthetic " + name).encode() for name in MODULE.VIEWS}
        self.packet["camera_sources"] = {}
        for name, data in self.camera.items():
            self.packet["camera_sources"][name] = self.write("camera_" + name, data)
        self.add("reviewed_site", {"source_kind": "original_independent_site_review",
                                   "cell_id": "C378245", "business_district": True,
                                   "street_public_access": True, "jurisdiction_review_id": "jurisdiction-fixture",
                                   "map_sha256": "map-fixture", "designation_id": "stand-fixture",
                                   "other_regulation_review_id": "other-rules-fixture",
                                   "stand_polygon_xy_m": [[0, 0], [5, 0], [5, 4], [0, 4]],
                                   "street_polygon_xy_m": [[-10, -10], [20, -10], [20, 10], [-10, 10]]})
        self.add("stand_designation", {"designation_id": "stand-fixture", "authority_reviewed": True})
        self.add("taxi_licence", {"vehicle_id": "taxi-fixture", "operator_id": "driver-fixture"})
        self.add("other_regulations", {"review_id": "other-rules-fixture"})
        self.add("native_result", {"source_kind": "original_native", "case_id": self.case_id,
                                   "recording_id": "synthetic-fixture", "frame_count": 900,
                                   "map_sha256": "map-fixture", "taxi_vehicle_id": "taxi-fixture",
                                   "operator_id": "driver-fixture"})
        self.add("native_frames", [{"frame": i, "elapsed_s": i / 20,
                                    "taxi_center_xy_m": [2.0, 2.0],
                                    "taxi_speed_mps": 0.0} for i in range(900)])
        self.add("activity_review", {"source_kind": "original_independent_activity_review",
                                     "case_id": self.case_id, "recording_id": "synthetic-fixture",
                                     "camera_sha256": {name: hashlib.sha256(data).hexdigest()
                                                       for name, data in self.camera.items()},
                                     "halt_interval_frames": [200, 500], "activity": "park",
                                     "reviewer_id": "fixture-reviewer", "passenger_events": []})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, key, data):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        name = key + (".bin" if isinstance(data, bytes) else ".json")
        (self.root / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def add(self, key, data):
        self.packet[key] = self.write(key, data)

    def change(self, key, mutate):
        value = json.loads((self.root / (key + ".json")).read_text())
        mutate(value)
        self.add(key, value)

    def test_designated_stand_parking(self):
        value = MODULE.measure(self.packet, self.root)
        self.assertTrue(value["all_halt_centers_inside_designated_stand"])
        self.assertIsNone(value["legal_verdict"])

    def test_outside_stand_loading_event(self):
        self.packet["case_id"] = MODULE.ASSIGNMENT + "__outside_stand_load"
        self.change("native_result", lambda value: value.update(case_id=self.packet["case_id"]))
        self.change("native_frames", lambda value: [row.update(taxi_center_xy_m=[8.0, 2.0]) for row in value])
        self.change("activity_review", lambda value: value.update(
            case_id=self.packet["case_id"], activity="temporary_stop",
            passenger_events=[{"kind": "boarding", "frame": 320,
                               "passenger_actor_id": "passenger-fixture", "observed": True}]))
        value = MODULE.measure(self.packet, self.root)
        self.assertTrue(value["all_halt_centers_outside_designated_stand"])
        self.assertEqual(value["passenger_event_kinds"], ["boarding"])
        self.assertEqual(value["expeditiousness"], "requires_independent_review")

    def test_changed_camera_bytes_rejected(self):
        (self.root / "camera_overview.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            MODULE.measure(self.packet, self.root)

    def test_rehashed_frame_gap_rejected(self):
        self.change("native_frames", lambda value: value[300].update(frame=301))
        with self.assertRaisesRegex(ValueError, "frame/time gap"):
            MODULE.measure(self.packet, self.root)

    def test_activity_review_changed_video_rejected(self):
        self.change("activity_review", lambda value: value["camera_sha256"].update(overview="0" * 64))
        with self.assertRaisesRegex(ValueError, "camera bytes"):
            MODULE.measure(self.packet, self.root)

    def test_unreviewed_stand_designation_rejected(self):
        self.change("stand_designation", lambda value: value.update(authority_reviewed=False))
        with self.assertRaisesRegex(ValueError, "official stand"):
            MODULE.measure(self.packet, self.root)

    def test_moving_taxi_in_halt_interval_rejected(self):
        self.change("native_frames", lambda value: value[250].update(taxi_speed_mps=3.0))
        with self.assertRaisesRegex(ValueError, "moving taxi"):
            MODULE.measure(self.packet, self.root)


if __name__ == "__main__":
    unittest.main()
