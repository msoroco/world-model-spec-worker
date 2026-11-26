"""CPU-only tests of source seals, scene construction and exception controls."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("crosswalk_site", ROOT / "crosswalk_site.py")
SITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SITE)


class FakeVehicle:
    pass


class FakeOperator:
    def __init__(self):
        self.calls = []
        self.vehicle = FakeVehicle()

    def spawn_vehicle(self, point):
        self.calls.append(("spawn", point))
        return self.vehicle

    def set_crosswalk(self, polygon, marked):
        self.calls.append(("crosswalk", marked))

    def set_vehicle_route(self, vehicle, route, clearance):
        self.calls.append(("route", clearance))

    def set_activity(self, vehicle, activity):
        self.calls.append(("activity", activity))

    def set_exception_context(self, exception, site):
        self.calls.append(("exception", exception))

    def destroy(self, vehicle):
        self.calls.append(("destroy",))


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site_path = self.root / "site.json"
        self.site = {
            "source_kind": "reviewed_original_native_crosswalk_site",
            "assignment_id": SITE.ASSIGNMENT_ID,
            "case_ids": [SITE.ASSIGNMENT_ID + "__" + name for name in SITE.CASE_CONTROLS],
            "cell_id": "C394507", "actor": "motor_vehicle_driver",
            "driver_id": "source-bound-driver", "vehicle_id": "source-bound-vehicle",
            "vehicle_route_xy_m": [[-10.0, 0.0], [15.0, 0.0]],
            "crossing_polygon_xy_m": [[0.0, -2.0], [2.0, -2.0], [2.0, 2.0], [0.0, 2.0]],
            "crosswalk_marked": True,
            "requested_activity": "destination_stop", "requested_exception": "none",
            "requested_body_clearance_m": 5.9,
            "map_sha256": "a" * 64,
            "source_records": {},
        }
        for name in SITE.SOURCE_NAMES:
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"source": name}) + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.site["source_records"][name] = {"path": path.name, "sha256": digest}
            self.site[name + "_source_sha256"] = digest

    def load(self, name="destination_inside_20ft"):
        self.site_path.write_text(json.dumps(self.site, sort_keys=True) + "\n")
        digest = hashlib.sha256(self.site_path.read_bytes()).hexdigest()
        return SITE.load_site(self.site_path, digest, SITE.ASSIGNMENT_ID + "__" + name)

    def test_all_nine_case_controls(self):
        for name, (distance, activity, exception, marked) in SITE.CASE_CONTROLS.items():
            self.site.update(requested_body_clearance_m=distance,
                             requested_activity=activity, requested_exception=exception,
                             crosswalk_marked=marked)
            loaded = self.load(name)
            operator = FakeOperator()
            self.assertIs(SITE.construct(operator, loaded), operator.vehicle)
            self.assertEqual(operator.calls[1:], [("crosswalk", marked),
                                                   ("route", distance),
                                                   ("activity", activity),
                                                   ("exception", exception)])

    def test_changed_independent_source_rejected(self):
        self.load()
        (self.root / "crosswalk_marking.json").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source changed"):
            SITE.load_site(self.site_path, hashlib.sha256(self.site_path.read_bytes()).hexdigest(),
                           SITE.ASSIGNMENT_ID + "__destination_inside_20ft")

    def test_mismatched_activity_rejected(self):
        self.site["requested_activity"] = "destination_park"
        with self.assertRaisesRegex(ValueError, "control changed"):
            self.load()

    def test_unreviewed_map_rejected(self):
        loaded = self.load()
        operator = FakeOperator()
        operator.map_bytes = lambda world: b"other map"
        operator.site_readback = lambda world, site: site
        operator.control = lambda *args: None
        operator.observe = lambda *args: None
        operator.cameras = lambda *args: None
        operator.start_pipeline_capture = lambda *args: None
        operator.capture_pipeline_tick = lambda *args: None
        operator.close_pipeline_capture = lambda *args: None
        with self.assertRaisesRegex(ValueError, "loaded Native map"):
            SITE.check_live_readback(operator, object(), loaded)


if __name__ == "__main__":
    unittest.main()
