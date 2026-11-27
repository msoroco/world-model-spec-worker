import importlib.util
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


construction = module("driveway_construction")
controller = module("driveway_controller")
measurement = module("driveway_measurement")
acquisition = module("native_acquisition")
delivery = module("delivery_audit")
CASES = json.loads((ROOT / "case-plan.json").read_text())["cases"]


def source_packet():
    return {
        "source_kind": "original_native_geometry",
        "map_sha256": "a" * 64,
        "district_source": "reviewed district parcel record",
        "frontage_source": "reviewed residential frontage survey",
        "private_driveway_source": "reviewed ownership and permitted use packet",
        "sidewalk_source": "original native sidewalk survey",
        "roadway_source": "original native lane survey",
        "connection_source": "original route continuity survey",
        "ego_vehicle_id": "ego-1",
        "district": "residence", "business_district": False,
        "access": "private_driveway", "road_connection": True,
        "crosswalk_assumed": False, "controlled_access_assumed": False,
        "driveway_polygon_m": [[-12, -3], [-1, -3], [-1, 3], [-12, 3]],
        "sidewalk_polygon_m": [[-2, -3], [2, -3], [2, 3], [-2, 3]],
        "roadway_polygon_m": [[3, -7], [13, -7], [13, 7], [3, 7]],
        "ego_route_xy_m": [[-11, 0], [-6, 0], [-3, 0], [0, 0], [2, 0], [4, 0], [8, 0]],
        "pedestrian_route_xy_m": [[0, -2], [0, 2]],
        "roadway_approaches": {
            "left": {"lane_source": "native left approach", "route_xy_m": [[4, -6], [4, 0]]},
            "right": {"lane_source": "native right approach", "route_xy_m": [[8, 6], [8, 0]]},
        },
    }


class DrivewayConstructionTests(unittest.TestCase):
    def test_every_exact_case_has_sourced_order_and_approach(self):
        self.assertEqual(len(CASES), 8)
        for case in CASES:
            built = construction.construct(source_packet(), case)
            self.assertLess(built["sidewalk_entry_index"], built["roadway_entry_index"])
            self.assertEqual(built["source_kind"], "original_native_geometry")
            if "left_" in case["world_setup"]["roadway_vehicle"]:
                self.assertEqual(built["active_roadway_direction"], "left")
            if "right_" in case["world_setup"]["roadway_vehicle"]:
                self.assertEqual(built["active_roadway_direction"], "right")

    def test_rejects_wrong_order_and_missing_origins(self):
        packet = source_packet()
        packet["ego_route_xy_m"] = list(reversed(packet["ego_route_xy_m"]))
        with self.assertRaisesRegex(ValueError, "order"):
            construction.survey(packet)
        packet = source_packet()
        packet["sidewalk_source"] = ""
        with self.assertRaisesRegex(ValueError, "sidewalk_source"):
            construction.survey(packet)
        packet = source_packet()
        packet["roadway_approaches"].pop("right")
        with self.assertRaisesRegex(ValueError, "both roadway"):
            construction.survey(packet)

    def test_stop_and_yield_controller_branches(self):
        stop = construction.construct(source_packet(), CASES[0])
        control = controller.DrivewayController(stop)
        value = control.step((-3, 0), 0, 2.0, True, True)
        self.assertEqual(value["phase"], "pre_sidewalk_stop")
        self.assertEqual(value["brake"], 1.0)
        for _ in range(4):
            value = control.step((-3, 0), 0, 0, True, True)
        self.assertEqual(value["phase"], "sidewalk_crossing")
        pedestrian = construction.construct(source_packet(), CASES[2])
        control = controller.DrivewayController(pedestrian)
        for _ in range(4):
            value = control.step((-3, 0), 0, 0, False, True)
        self.assertEqual(value["phase"], "sidewalk_wait")
        self.assertEqual(value["brake"], 1.0)

    def test_measured_original_activity_and_missing_source_rejection(self):
        scratch = Path.cwd() / ".runtime-work" / "c213645-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        case = CASES[4]
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp)
            geometry = source_packet()
            geometry["case_id"] = case["case_id"]
            geometry["source_kind"] = "synthetic_fixture"
            xs = [-11, -6, -3, 0, 1, 2, 4, 6, 8]
            frames = [{"video_frame": i, "frame": 100 + i, "time_s": round(i * .05, 3)}
                      for i in range(9)]
            activity = []
            for i, x in enumerate(xs):
                activity.append({
                    "frame": 100 + i, "time_s": round(i * .05, 3),
                    "ego": {"actor_id": "ego-1", "xy_m": [x, 0],
                            "speed_mps": 0.0 if i == 2 else 2.0},
                    "pedestrian": None,
                    "roadway_vehicle": {"actor_id": "road-1", "source": "synthetic fixture",
                                        "approach_direction": "left", "xy_m": [4, -6 + i * .5]},
                })
            docs = {"frame_map": {"frames": frames},
                    "driveway_geometry": geometry, "activity": {"samples": activity}}
            inventory = {"case_id": case["case_id"], "source_kind": "synthetic_fixture",
                         "diagnostic_fixture": True, "sources": {}}
            for name, value in docs.items():
                path = root / (name + ".json")
                path.write_text(json.dumps(value) + "\n")
                inventory["sources"][name] = {"path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (root / "inventory.json").write_text(json.dumps(inventory) + "\n")
            measured = measurement.measure(root, case, diagnostic=True)
            self.assertEqual(measured["first_sidewalk_frame"], 103)
            self.assertEqual(measured["first_roadway_frame"], 106)
            self.assertEqual(measured["last_pre_sidewalk_halt_frame"], 102)
            self.assertIsNotNone(measured["minimum_roadway_vehicle_center_separation_m"])
            self.assertIsNone(measured["roadway_right_of_way_judgment"])
            (root / "activity.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: activity"):
                measurement.measure(root, case, diagnostic=True)

    def test_diagnostic_acquisition_seals_frame_join_and_cameras(self):
        from PIL import Image
        data = io.BytesIO()
        Image.new("RGB", (2, 2), (255, 0, 0)).save(data, "PNG")
        png = data.getvalue()
        road = b"<OpenDRIVE><header/></OpenDRIVE>"
        case = CASES[4]

        class Operator:
            native_attested = False
            restored = False
            closed = False

            def __init__(self):
                self.index = -1
                self.geometry = source_packet()
                self.geometry.update(case_id=case["case_id"], source_kind="synthetic_fixture",
                                     map_sha256=hashlib.sha256(road).hexdigest())

            def geometry_packet(self, case_id):
                if case_id != self.geometry["case_id"]:
                    raise ValueError("case")
                return self.geometry

            def opendrive_bytes(self):
                return road

            def start(self, plan):
                self.plan = plan

            def tick(self):
                self.index += 1
                return {"frame": 300 + self.index, "time_s": round(.05 * self.index, 3)}

            def activity(self, frame):
                i = self.index
                xs = [-11, -6, -3, 0, 1, 2, 4, 6, 8]
                return {"frame": frame, "time_s": round(.05 * i, 3),
                        "ego": {"actor_id": "ego-1", "xy_m": [xs[i], 0],
                                "speed_mps": 0 if i == 2 else 2},
                        "pedestrian": None,
                        "roadway_vehicle": {"actor_id": "road-1", "source": "synthetic fixture",
                                            "approach_direction": "left", "xy_m": [4, -6 + i * .5]}}

            def cameras(self, frame):
                return {name: {"frame": frame, "time_s": round(.05 * self.index, 3),
                               "png": png} for name in acquisition.VIEWS}

            def brake(self):
                self.braked = True

            def cleanup(self):
                self.closed = True
                self.restored = True

        scratch = Path.cwd() / ".runtime-work" / "c213645-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            original = Path(temp) / "original"
            operator = Operator()
            inventory = acquisition.capture(operator, case, original, diagnostic=True)
            self.assertTrue(operator.braked)
            self.assertTrue(operator.closed)
            self.assertEqual(inventory["source_kind"], "synthetic_fixture")
            self.assertFalse(inventory["physical_acceptance_claimed"])
            self.assertEqual(len(inventory["media"]), 4)
            result = measurement.measure(original, case, diagnostic=True)
            self.assertEqual(result["last_pre_sidewalk_halt_frame"], 302)
            self.assertEqual(result["first_roadway_frame"], 306)
            software = delivery.audit(original, case, diagnostic=True)
            self.assertTrue(software["software_checks_passed"])
            self.assertFalse(software["physical_completion_verified"])
            (original / "overview.zip").unlink()
            with self.assertRaisesRegex(ValueError, "camera source absent"):
                delivery.audit(original, case, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
