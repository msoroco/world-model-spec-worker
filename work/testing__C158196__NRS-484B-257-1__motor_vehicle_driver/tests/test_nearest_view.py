import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "nearest_view.py"
spec = importlib.util.spec_from_file_location("nearest_view_c158196", MODULE)
nearest_view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nearest_view)
construction_spec = importlib.util.spec_from_file_location("construction_c158196", MODULE.parents[0] / "construction.py")
construction = importlib.util.module_from_spec(construction_spec)
construction_spec.loader.exec_module(construction)
native_spec = importlib.util.spec_from_file_location("native_observation_c158196", MODULE.parents[0] / "native_observation.py")
native_observation = importlib.util.module_from_spec(native_spec)
native_spec.loader.exec_module(native_observation)
comparison_spec = importlib.util.spec_from_file_location("saved_comparison_c158196", MODULE.parents[0] / "saved_comparison.py")
saved_comparison = importlib.util.module_from_spec(comparison_spec)
comparison_spec.loader.exec_module(saved_comparison)


def packet():
    sources = {name: {"path": f"native/{name}.json", "sha256": "a" * 64}
               for name in nearest_view.REQUIRED_SOURCES}
    context = {"cell_id": "C158196", "law_id": "NRS-484B-257-1",
               "proper_yield_sign": True, "through_highway": True, "connected_approach": True,
               "marked_stop_line": False, "near_side_crosswalk": False,
               "sidewalk_derived_crosswalk": False, "officer_controlling": False,
               "signal_controlling": False, "nearest_view_station_m": 2.0,
               "intersection_entry_station_m": 4.0}
    positions = [0, 1, 2, 3, 4, 5, 6]
    frames = [{"frame": 100 + i, "time_s": 5 + i / 20,
               "ego_front_station_m": x, "ego_speed_mps": 2.0 if i < 3 else 0.4,
               "through_center_station_m": 20 - i,
               "view_clear": i >= 2, "through_occupied": i >= 4,
               "ego_within_intersection": 4 <= i <= 6}
              for i, x in enumerate(positions)]
    return {"sources": sources, "context": context, "frames": frames}


def site():
    return {"native_cell_id": "C158196", "layout": "one_way_to_two_way_intersection",
            "route_connected": True, "through_highway_confirmed": True,
            "marked_stop_line": False, "near_side_crosswalk": False,
            "sidewalk_derived_crosswalk": False, "officer_controlling": False,
            "proper_yield_sign": True, "yield_sign_governs": True,
            "signal_controlling": False, "nearest_view_station_m": 2.0,
            "intersection_entry_station_m": 4.0,
            "map_hash": "a" * 64, "device_hash": "b" * 64,
            "raycast_hash": "c" * 64, "camera_plan_hash": "d" * 64}


def native_tick():
    geometry = {"ego_route_origin_xy_m": [0, 0], "ego_route_axis_xy": [1, 0],
                "through_route_origin_xy_m": [0, 0], "through_route_axis_xy": [0, 1],
                "intersection_polygon_xy_m": [[4, -2], [8, -2], [8, 2], [4, 2]]}
    raw = {"frame": 100, "time_s": 5.0,
           "ego_body_xy_m": [[1, -0.5], [2, -0.5], [2, 0.5], [1, 0.5]],
           "through_body_xy_m": [[5, -0.5], [6, -0.5], [6, 0.5], [5, 0.5]],
           "ego_velocity_xy_mps": [3, 0], "through_center_xy_m": [5.5, 0],
           "native_view_raycast": {"source": "native_raycast", "occluded": False,
                                   "origin_xy_m": [1.5, 0], "target_xy_m": [5.5, 0]},
           "yield_sign_readback": True, "signal_controlling": False,
           "officer_controlling": False}
    return raw, geometry


def write_attempt(base, suffix, *, policy, occupied=True, minimum_speed=0.4):
    base.mkdir(parents=True, exist_ok=True)
    value = packet()
    value["case_id"] = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__" + suffix
    value["context"]["engineering_policy"] = policy
    value["context"]["through_vehicle_initial_station_m"] = 20.0 if occupied else 80.0
    for frame in value["frames"]:
        frame["through_occupied"] = occupied and frame["frame"] >= 104
        frame["ego_speed_mps"] = minimum_speed
        frame["through_center_station_m"] += 0 if occupied else 60
    for name, item in value["sources"].items():
        path = base / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name + "\n", encoding="utf-8")
        item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    packet_path = base / "native" / "nearest_view_packet.json"
    packet_path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path


class NearestViewTests(unittest.TestCase):
    def test_measures_original_order_and_traffic(self):
        result = nearest_view.measure(packet())
        self.assertEqual(result["first_view_frame"], 102)
        self.assertEqual(result["first_entry_frame"], 104)
        self.assertEqual(result["through_center_at_view_m"], 18)
        self.assertTrue(result["through_occupied_during_crossing"])
        self.assertEqual(result["legal_immediate_hazard"], "unresolved_judgment")

    def test_rejects_active_signal_control(self):
        value = packet()
        value["context"]["signal_controlling"] = True
        with self.assertRaisesRegex(ValueError, "signal_controlling"):
            nearest_view.measure(value)

    def test_rejects_sidewalk_derived_crosswalk(self):
        value = packet()
        value["context"]["sidewalk_derived_crosswalk"] = True
        with self.assertRaisesRegex(ValueError, "sidewalk_derived_crosswalk"):
            nearest_view.measure(value)

    def test_rejects_missing_source(self):
        value = packet()
        del value["sources"]["yield_sign_readback"]
        with self.assertRaisesRegex(ValueError, "yield_sign_readback"):
            nearest_view.measure(value)

    def test_rejects_noncontiguous_or_wrong_rate(self):
        value = packet()
        value["frames"][3]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "contiguous"):
            nearest_view.measure(value)
        value = packet()
        value["frames"][3]["time_s"] += .01
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            nearest_view.measure(value)

    def test_rejects_view_after_entry(self):
        value = packet()
        for frame in value["frames"][:5]:
            frame["view_clear"] = False
        with self.assertRaisesRegex(ValueError, "view must precede"):
            nearest_view.measure(value)

    def test_rejects_unreviewed_context_change(self):
        left, right = packet(), packet()
        right["context"]["marked_stop_line"] = True
        with self.assertRaisesRegex(ValueError, "fixed-condition"):
            nearest_view.compare(left, right, differing=("nearest_view_station_m",))

    def test_declared_difference_still_must_be_valid(self):
        left, right = packet(), packet()
        right["context"]["nearest_view_station_m"] = 3.0
        result = nearest_view.compare(left, right, differing=("nearest_view_station_m",))
        self.assertEqual(result["comparison_status"], "measured_not_legal_verdict")

    def test_construction_requires_observed_governance(self):
        value = site()
        self.assertEqual(construction.validate_site(value, "nearest_view_hold")["case"], "nearest_view_hold")
        value["signal_controlling"] = True
        with self.assertRaisesRegex(ValueError, "signal exception"):
            construction.validate_site(value, "nearest_view_hold")
        self.assertEqual(construction.validate_site(value, "active_signal_exception")["case"], "active_signal_exception")

    def test_construction_rejects_unconfirmed_crosswalk(self):
        value = site()
        value["near_side_crosswalk"] = None
        with self.assertRaisesRegex(ValueError, "crosswalk"):
            construction.validate_site(value, "nearest_view_hold")

    def test_controller_response_isolated(self):
        observed = {"ego_speed_mps": 3.0, "ego_front_station_m": 2.1,
                    "through_occupied": True}
        hold = construction.controller("nearest_view_hold", site(), observed)
        go = construction.controller("nearest_view_continue", site(), observed)
        self.assertGreater(hold["brake"], go["brake"])
        self.assertGreater(go["throttle"], hold["throttle"])

    def test_clear_case_rejects_occupied_traffic(self):
        with self.assertRaisesRegex(ValueError, "clear-traffic"):
            construction.controller("nearest_view_clear", site(),
                                    {"ego_speed_mps": 3.0, "ego_front_station_m": 2.1,
                                     "through_occupied": True})

    def test_original_source_bytes_are_verified(self):
        value = packet()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for name, item in value["sources"].items():
                path = base / item["path"]
                path.parent.mkdir(exist_ok=True)
                path.write_text(name + "\n")
                item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            nearest_view.verify_source_bytes(value, base)
            (base / value["sources"]["view_raycast"]["path"]).write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                nearest_view.verify_source_bytes(value, base)

    def test_source_path_escape_rejected(self):
        value = packet()
        value["sources"]["native_map"]["path"] = "../outside"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "escapes attempt"):
                nearest_view.verify_source_bytes(value, Path(temporary))

    def test_native_original_body_derivation(self):
        raw, geometry = native_tick()
        measured = native_observation.derive(raw, geometry)
        self.assertEqual(measured["ego_front_station_m"], 2.0)
        self.assertEqual(measured["through_center_station_m"], 0.0)
        self.assertTrue(measured["view_clear"])
        self.assertTrue(measured["through_occupied"])
        self.assertFalse(measured["ego_within_intersection"])

    def test_native_raycast_must_bind_bodies(self):
        raw, geometry = native_tick()
        raw["native_view_raycast"]["target_xy_m"] = [20, 20]
        with self.assertRaisesRegex(ValueError, "endpoint differs"):
            native_observation.derive(raw, geometry)

    def test_native_signal_exception_rejected(self):
        raw, geometry = native_tick()
        raw["signal_controlling"] = True
        with self.assertRaisesRegex(ValueError, "controlling exception"):
            native_observation.derive(raw, geometry)

    def test_saved_conflict_comparison_reopens_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right = Path(temporary) / "hold", Path(temporary) / "continue"
            write_attempt(left, "nearest_view_hold", policy="hold_for_observed_traffic", minimum_speed=0.1)
            write_attempt(right, "nearest_view_continue", policy="continue_through_observed_traffic", minimum_speed=2.0)
            result = saved_comparison.audit(left, right, "nearest_view_conflict_response")
            self.assertEqual(result["status"], "source_bound_measured_not_legal_verdict")
            (left / "native" / "view_raycast.json").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                saved_comparison.audit(left, right, "nearest_view_conflict_response")

    def test_saved_occupancy_comparison_rejects_unchanged_traffic(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right = Path(temporary) / "continue", Path(temporary) / "clear"
            write_attempt(left, "nearest_view_continue", policy="continue_through_observed_traffic")
            packet_path = write_attempt(right, "nearest_view_clear", policy="continue_through_observed_traffic", occupied=False)
            self.assertEqual(saved_comparison.audit(left, right, "nearest_view_traffic_occupancy")["comparison_id"], "nearest_view_traffic_occupancy")
            value = json.loads(packet_path.read_text(encoding="utf-8"))
            for frame in value["frames"]:
                frame["through_occupied"] = frame["frame"] >= 104
            packet_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "occupancy does not differ"):
                saved_comparison.audit(left, right, "nearest_view_traffic_occupancy")

    def test_saved_comparison_rejects_fixed_context_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right = Path(temporary) / "hold", Path(temporary) / "continue"
            write_attempt(left, "nearest_view_hold", policy="hold_for_observed_traffic", minimum_speed=0.1)
            packet_path = write_attempt(right, "nearest_view_continue", policy="continue_through_observed_traffic", minimum_speed=2.0)
            value = json.loads(packet_path.read_text(encoding="utf-8"))
            value["context"]["nearest_view_station_m"] = 3.0
            packet_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixed-condition"):
                saved_comparison.audit(left, right, "nearest_view_conflict_response")


if __name__ == "__main__":
    unittest.main()
