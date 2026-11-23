import copy
import importlib.util
import sys
import hashlib
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("speed_delivery", ROOT / "speed_delivery.py")
speed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(speed)
audit_spec = importlib.util.spec_from_file_location("delivery_audit", ROOT / "delivery_audit.py")
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)
SEAL = "a" * 64


def packet(context):
    signs = []
    if context != "unposted":
        value = 25 if context == "same25" else 35
        signs = [{"sign_id": "S1", "value_mph": value, "source": "survey/sign-frame-and-map",
                  "direction": "route", "governed_start_station_m": 40.0,
                  "governed_end_station_m": 120.0, "time_conditions_source": "survey/daytime"}]
    return {"law_id": speed.LAW, "cell_id": "C150979", "map_sha256": SEAL,
            "map_name": "TownSource", "municipal_jurisdiction_source": "survey/jurisdiction",
            "covered_street_source": "survey/street", "road_kind": "street",
            "route": {"road_id": 3, "lane_id": 1, "one_way_source": "map/lane-inventory",
                      "spawn_station_m": 0.0, "end_station_m": 120.0},
            "start_xyz": [1.0, 2.0, 0.0], "sign_inventory_complete_source": "survey/complete-stretch",
            "sign_inventory_extent_m": [0.0, 120.0], "title_posting_review_source": "local-review/pending",
            "signs": signs}


def frames(context, value=25.0):
    out = []
    sign_value = 25 if context == "same25" else 35
    for i in range(500):
        f = {"frame_index": i, "time_s": i / 20, "ego_alive": True,
             "driver_role": "motor_vehicle_driver", "map_sha256": SEAL,
             "route_station_m": i * 0.22, "speed_mps": value * speed.MPH_TO_MPS}
        if context != "unposted" and f["route_station_m"] >= 40:
            f.update(sign_id="S1", sign_value_mph=sign_value)
        out.append(f)
    return out


class SpeedDeliveryTest(unittest.TestCase):
    def test_each_context_and_observed_speed(self):
        for key, (context, target) in speed.TARGETS.items():
            report = speed.measure(packet(context), key, SEAL, frames(context, target))
            self.assertEqual(report["original_frame_count"], 500)
            self.assertAlmostEqual(report["observed_speed_mph_min"], target)
            self.assertEqual(report["legal_status"], "unresolved_prima_facie_and_title_posting_review")

    def test_reject_incomplete_posting_or_changed_map(self):
        site = packet("same25")
        site["signs"][0].pop("time_conditions_source")
        with self.assertRaisesRegex(ValueError, "sign time conditions"):
            speed.validate_site(site, "same25_at", SEAL)
        with self.assertRaisesRegex(ValueError, "map seal"):
            speed.validate_site(packet("unposted"), "unposted_at", "b" * 64)
        with self.assertRaisesRegex(ValueError, "unposted case has sign"):
            speed.validate_site(packet("same25"), "unposted_at", SEAL)

    def test_reject_original_gap_and_sign_readback(self):
        bad = frames("same25")
        bad[101]["frame_index"] = 102
        with self.assertRaisesRegex(ValueError, "frame gap"):
            speed.measure(packet("same25"), "same25_at", SEAL, bad)
        bad = frames("same25")
        bad[300]["sign_value_mph"] = 35
        with self.assertRaisesRegex(ValueError, "sign Native readback"):
            speed.measure(packet("same25"), "same25_at", SEAL, bad)

    def test_comparison_requires_exact_members(self):
        keys = ["unposted_below", "unposted_at", "unposted_above"]
        reports = [speed.measure(packet("unposted"), k, SEAL, frames("unposted", speed.TARGETS[k][1])) for k in keys]
        self.assertEqual(len(speed.compare(reports, keys)["case_ids"]), 3)
        with self.assertRaisesRegex(ValueError, "member missing"):
            speed.compare(reports[:-1], keys)
        changed = copy.deepcopy(reports)
        changed[1]["posting_context"] = "same25"
        with self.assertRaisesRegex(ValueError, "posting context"):
            speed.compare(changed, keys)
        contrast = [speed.measure(packet("same25"), "same25_above", SEAL, frames("same25", 30)),
                    speed.measure(packet("different35"), "different35", SEAL, frames("different35", 30))]
        self.assertEqual(len(speed.compare(contrast, ["same25_above", "different35"], varying_posting=True)["case_ids"]), 2)
        changed = copy.deepcopy(contrast)
        changed[1]["route"]["lane_id"] = 2
        with self.assertRaisesRegex(ValueError, "map or route"):
            speed.compare(changed, ["same25_above", "different35"], varying_posting=True)

    def test_native_spawn_checks_actual_lane(self):
        class Location:
            def __init__(self, *xyz): self.xyz = xyz
        class Map:
            name = "TownSource"
            def __init__(self, lane): self.lane = lane
            def get_waypoint(self, loc, project_to_road=False):
                self.loc = loc
                return type("Waypoint", (), {"road_id": 3, "lane_id": self.lane, "transform": "native-transform"})()
        class Library:
            def find(self, key): return key
        class World:
            def __init__(self, lane): self.map = Map(lane)
            def get_map(self): return self.map
            def get_blueprint_library(self): return Library()
            def try_spawn_actor(self, blueprint, transform):
                self.spawn = (blueprint, transform)
                return object()
        previous = sys.modules.get("carla")
        sys.modules["carla"] = type("Carla", (), {"Location": Location})
        try:
            world = World(1)
            construction = speed.construct(world, packet("unposted"), "unposted_at", SEAL)
            self.assertEqual(world.spawn, ("vehicle.tesla.model3", "native-transform"))
            self.assertAlmostEqual(construction["target_mps"], 25 * speed.MPH_TO_MPS)
            with self.assertRaisesRegex(ValueError, "Native lane"):
                speed.construct(World(2), packet("unposted"), "unposted_at", SEAL)
        finally:
            if previous is None: sys.modules.pop("carla", None)
            else: sys.modules["carla"] = previous

    def test_controller_reads_actual_velocity(self):
        class VehicleControl:
            def __init__(self, **kwargs): self.values = kwargs
        class Actor:
            def __init__(self, speed): self.speed = speed
            def get_velocity(self): return type("V", (), {"x": self.speed, "y": 0.0, "z": 0.0})()
            def apply_control(self, control): self.control = control
        previous = sys.modules.get("carla")
        sys.modules["carla"] = type("Carla", (), {"VehicleControl": VehicleControl})
        try:
            slow = Actor(4.0)
            fast = Actor(18.0)
            self.assertGreater(speed.control_tick(slow, 10.0)["throttle"], 0)
            self.assertGreater(speed.control_tick(fast, 10.0)["brake"], 0)
            self.assertEqual(slow.control.values["brake"], 0.0)
        finally:
            if previous is None: sys.modules.pop("carla", None)
            else: sys.modules["carla"] = previous

    def test_saved_audit_rejects_missing_and_stale_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = Path(tmp) / "native.json"
            native.write_text("source", encoding="utf-8")
            seal = hashlib.sha256(native.read_bytes()).hexdigest()
            frame_map = [{"frame_index": i, "native_frame": i + 100, "time_s": i / 20} for i in range(400)]
            cameras = {}
            for name in audit.CAMERAS:
                path = Path(tmp) / f"{name}.bin"
                path.write_bytes(name.encode())
                cameras[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                 "decoded_frames": 400, "original_frame_first": 0, "original_frame_last": 399}
            sign_inventory = Path(tmp) / "signs.json"
            sign_inventory.write_text("[]", encoding="utf-8")
            title_review = Path(tmp) / "title.json"
            title_review.write_text("{}", encoding="utf-8")
            measured = {"case_id": "case", "map_sha256": SEAL, "original_frame_count": 400}
            source = {"case_id": "case", "native_result_path": str(native), "native_result_sha256": seal,
                      "map_sha256": SEAL, "frame_map": frame_map, "cameras": cameras,
                      "sign_inventory_source": {"path": str(sign_inventory), "sha256": hashlib.sha256(sign_inventory.read_bytes()).hexdigest()},
                      "title_review_source": {"path": str(title_review), "sha256": hashlib.sha256(title_review.read_bytes()).hexdigest()},
                      "physical_completion": True}
            self.assertEqual(audit.audit_saved(source, measured)["original_frame_count"], 400)
            bad = copy.deepcopy(source)
            bad["sign_inventory_source"]["sha256"] = SEAL
            with self.assertRaisesRegex(ValueError, "posting source seal"):
                audit.audit_saved(bad, measured)
            bad = copy.deepcopy(source)
            bad_measurement = dict(measured, governed_original_samples=[{"frame_index": 200, "time_s": 11.0}])
            with self.assertRaisesRegex(ValueError, "measurement time join"):
                audit.audit_saved(bad, bad_measurement)
            bad = copy.deepcopy(source)
            bad["cameras"].pop("left")
            with self.assertRaisesRegex(ValueError, "four camera"):
                audit.audit_saved(bad, measured)
            native.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "seal mismatch"):
                audit.audit_saved(source, measured)


if __name__ == "__main__":
    unittest.main()
