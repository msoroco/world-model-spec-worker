import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_uturn import ASSIGNMENT, ComparisonError, compare


def seal(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native(case, *, inside=True, other_x=5):
    frames = []
    for i in range(900):
        x = 2 * i / 899 + (0 if inside else 3)
        frames.append({"frame": 100 + i, "time_s": i * .05,
                       "ego": {"id": "ego", "road_id": 7,
                               "lane_id": 1 if i < 899 else -1,
                               "junction_id": 4 if inside and 300 <= i < 600 else None,
                               "x": x, "y": 0, "yaw_deg": 180 * i / 899,
                               "body_corners_xy_m": [[x-.1, -.1], [x+.1, -.1],
                                                     [x+.1, .1], [x-.1, .1]]},
                       "other_vehicle": {"id": "other", "road_id": 8,
                                         "lane_id": 1, "x": other_x, "y": 0}})
    return {"case_id": case, "actor": "motor_vehicle_driver", "map_sha256": "map",
            "route_sha256": "route", "district_basis": {"source_sha256": "district"},
            "intersection_boundary": {"source_sha256": "boundary",
                                      "polygon_xy_m": [[.8, -1], [1.2, -1],
                                                       [1.2, 1], [.8, 1]]},
            "ego_id": "ego", "other_id": "other", "frames": frames}


def site(case, *, ego_route="route-a", start=0):
    return {"case_id": ASSIGNMENT + "__" + case, "map_sha256": "map",
            "route_sha256": "route", "district_source_sha256": "district",
            "intersection_boundary_source_sha256": "boundary", "ego_blueprint": "vehicle.ego",
            "other_blueprint": "vehicle.other", "weather_sha256": "weather",
            "camera_policy_sha256": "camera", "other_route_sha256": "other-route",
            "ego_route_sha256": ego_route, "other_start_tick": start}


class ComparisonTest(unittest.TestCase):
    def files(self, root, *, second_site, inside):
        paths = []
        for index, (site_value, is_inside) in enumerate(((site("intersection_vehicle_near"), True),
                                                          (second_site, inside))):
            site_path = root / f"site-{index}.json"
            native_path = root / f"native-{index}.json"
            site_path.write_text(json.dumps(site_value))
            packet = native(site_value["case_id"], inside=is_inside)
            packet["site_sha256"] = seal(site_path)
            native_path.write_text(json.dumps(packet))
            paths.extend((site_path, seal(site_path), native_path, seal(native_path)))
        return paths

    def test_location_pair_is_source_bound_and_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            files = self.files(Path(directory), second_site=site("approach_before_intersection", ego_route="route-b"),
                               inside=False)
            result = compare("intersection_exception_location", *files)
            self.assertGreater(result["observed_whole_body_inside_intersection_frames"][0], 0)
            self.assertEqual(result["observed_whole_body_inside_intersection_frames"][1], 0)

    def test_timing_pair_keeps_ego_route(self):
        with tempfile.TemporaryDirectory() as directory:
            files = self.files(Path(directory), second_site=site("intersection_vehicle_far", start=80), inside=True)
            result = compare("surrounding_vehicle_context", *files)
            self.assertEqual(result["legal_interpretation"], "unresolved_review")

    def test_rejects_changed_fixed_weather(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = self.files(root, second_site=site("intersection_vehicle_far", start=80), inside=True)
            changed = json.loads(files[4].read_text())
            changed["weather_sha256"] = "other-weather"
            files[4].write_text(json.dumps(changed))
            files[5] = seal(files[4])
            packet = json.loads(files[6].read_text())
            packet["site_sha256"] = files[5]
            files[6].write_text(json.dumps(packet))
            files[7] = seal(files[6])
            with self.assertRaisesRegex(ComparisonError, "weather"):
                compare("surrounding_vehicle_context", *files)

    def test_rejects_missing_declared_timing_difference(self):
        with tempfile.TemporaryDirectory() as directory:
            files = self.files(Path(directory), second_site=site("intersection_vehicle_far", start=0), inside=True)
            with self.assertRaisesRegex(ComparisonError, "timing difference"):
                compare("surrounding_vehicle_context", *files)

    def test_rejects_wrong_exact_case_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            files = self.files(Path(directory), second_site=site("approach_before_intersection", ego_route="route-b"), inside=False)
            with self.assertRaisesRegex(ComparisonError, "exact comparison case pair"):
                compare("surrounding_vehicle_context", *files)

    def test_rejects_native_site_or_route_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            files = self.files(Path(directory), second_site=site("intersection_vehicle_far", start=80), inside=True)
            packet = json.loads(files[6].read_text())
            packet["route_sha256"] = "unreviewed-route"
            files[6].write_text(json.dumps(packet))
            files[7] = seal(files[6])
            with self.assertRaisesRegex(ComparisonError, "site/map/route source binding"):
                compare("surrounding_vehicle_context", *files)
