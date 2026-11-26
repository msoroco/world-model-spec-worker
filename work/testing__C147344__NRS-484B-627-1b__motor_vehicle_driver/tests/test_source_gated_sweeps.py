"""Synthetic source-shaped construction probes; no original physical authority."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reviewed_scene import ASSIGNMENT, CAMERAS, execute_native
from source_gated_sweeps import prepare
from sweep_native_adapter import SweepNativeAdapter
from sweep_runner import run
from sweep_comparison_audit import audit


SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c147344-sweep-tests"


class FakeAdapter:
    def __init__(self):
        self.spawned = []
        self.frames = []

    def open_map(self, path, sha256):
        self.map = (path, sha256)

    def spawn_vehicle(self, **spec):
        self.spawned.append(spec)
        return spec["role"]

    def attach_camera(self, **spec):
        return spec["name"]

    def tick_and_capture(self, **spec):
        self.frames.append(spec["frame"])


class SweepTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.write("map.xodr", '<OpenDRIVE><road id="21"><lanes><laneSection><right>'
                   '<lane id="-1" type="driving"/><lane id="-2" type="driving"/>'
                   '</right></laneSection></lanes></road></OpenDRIVE>\n')
        pose = {key: 0.0 for key in ("x", "y", "z", "pitch", "yaw", "roll")}
        site = {"reviewed_original_site": True, "highway": True, "one_way": True,
                "map_ref": self.ref("map.xodr"), "road_id": "21",
                "same_direction_lanes": [
                    {"id": "-1", "direction": "travel", "clearly_marked": True},
                    {"id": "-2", "direction": "travel", "clearly_marked": True}],
                "lane_roles": {"right": "-1", "middle": "-2"},
                "camera_profiles": {name: {"width": 960, "height": 540, "pose": pose}
                                    for name in CAMERAS},
                "construction_controls": {
                    "ego_speed_mps": 5.0, "follower_speed_mps": 8.0,
                    "slower_speed_mps": 3.0, "ego_start_station_m": 20.0,
                    "follower_start_station_m": 0.0, "slower_start_station_m": 50.0}}
        self.write_json("site.json", site)
        self.site_ref = self.ref("site.json")
        self.write("feasibility.txt", "synthetic feasibility source\n")
        self.control = {"reviewed_original_controls": True,
                        "site_sha256": self.site_ref["sha256"],
                        "supported_numeric_controls": [
                            {"name": "ego_speed_mps", "actor_role": "ego",
                             "original_readback_field": "ego_speed_mps"},
                            {"name": "slower_speed_mps", "actor_role": "slower_vehicle",
                             "original_readback_field": "slower_vehicle_speed_mps"}]}
        self.write_json("controls.json", self.control)
        self.ranges = {"format": "c147344-reviewed-sweep-ranges-v1",
                       "reviewed_original_ranges": True,
                       "site_sha256": self.site_ref["sha256"],
                       "control_ref": self.ref("controls.json"),
                       "evidence_refs": [self.ref("feasibility.txt")],
                       "axes": {}}
        for name, variable, minimum, maximum in (
                ("impediment", "ego_speed_mps", 4.0, 6.0),
                ("passing_necessity", "slower_speed_mps", 2.0, 4.0)):
            self.ranges["axes"][name] = {
                "variable": variable, "unit": "m/s", "minimum": minimum,
                "maximum": maximum, "spacing": 0.5,
                "range_rationale": "synthetic construction test",
                "spacing_rationale": "synthetic construction test",
                "feasibility_evidence": "synthetic construction test",
                "feasibility_source_ref": self.ref("feasibility.txt")}
        self.save_ranges()

    def write(self, name, content):
        (self.root / name).write_text(content, encoding="utf-8")

    def write_json(self, name, value):
        self.write(name, json.dumps(value, sort_keys=True) + "\n")

    def ref(self, name):
        return {"path": name,
                "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def save_ranges(self):
        self.write_json("ranges.json", self.ranges)
        self.ranges_ref = self.ref("ranges.json")

    def test_six_one_variable_scenes_execute_through_native_contract(self):
        packet = prepare(self.root, self.site_ref, self.ranges_ref)
        self.assertFalse(packet["physical_acceptance"])
        self.assertEqual(len(packet["scenes"]), 6)
        for scene in packet["scenes"]:
            self.assertEqual(set(scene["cameras"]), set(CAMERAS))
            self.assertEqual(scene["frames"], 900)
            self.assertIsNone(scene["sweep"]["legal_threshold"])
            adapter = FakeAdapter()
            receipt = execute_native(scene, adapter)
            self.assertEqual(adapter.frames, list(range(900)))
            self.assertFalse(receipt["physical_acceptance"])
            target = "ego" if scene["sweep"]["axis_id"] == "impediment" else "slower_vehicle"
            self.assertEqual(next(row["target_speed_mps"] for row in adapter.spawned
                                  if row["role"] == target), scene["sweep"]["requested_setpoint"])
        self.assertEqual([scene["sweep"]["requested_setpoint"]
                          for scene in packet["scenes"]], [4.0, 5.0, 6.0, 2.0, 3.0, 4.0])

    def test_rejects_missing_or_stale_source_and_unsupported_controls(self):
        self.ranges["reviewed_original_ranges"] = False
        self.save_ranges()
        with self.assertRaisesRegex(ValueError, "original reviewed sweep ranges"):
            prepare(self.root, self.site_ref, self.ranges_ref)
        self.ranges["reviewed_original_ranges"] = True
        self.ranges["control_ref"]["sha256"] = "0" * 64
        self.save_ranges()
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            prepare(self.root, self.site_ref, self.ranges_ref)
        self.ranges["control_ref"] = self.ref("controls.json")
        self.control["supported_numeric_controls"][1]["original_readback_field"] = "absent"
        self.write_json("controls.json", self.control)
        self.ranges["control_ref"] = self.ref("controls.json")
        self.save_ranges()
        with self.assertRaisesRegex(ValueError, "physical range/control invalid"):
            prepare(self.root, self.site_ref, self.ranges_ref)

    def test_rejects_unspaced_or_incomplete_axis(self):
        self.ranges["axes"]["impediment"]["spacing"] = 1.1
        self.save_ranges()
        with self.assertRaisesRegex(ValueError, "source-spaced construction points"):
            prepare(self.root, self.site_ref, self.ranges_ref)
        self.ranges["axes"].pop("passing_necessity")
        self.save_ranges()
        with self.assertRaisesRegex(ValueError, "both original judgment axes"):
            prepare(self.root, self.site_ref, self.ranges_ref)

    def test_rejects_unlisted_feasibility_source(self):
        self.write("other.txt", "unlisted synthetic source\n")
        self.ranges["axes"]["impediment"]["feasibility_source_ref"] = self.ref("other.txt")
        self.save_ranges()
        with self.assertRaisesRegex(ValueError, "omitted from evidence packet"):
            prepare(self.root, self.site_ref, self.ranges_ref)

    def test_sweep_adapter_records_slower_speed_in_same_motion_row(self):
        class Velocity:
            x, y, z = 3.0, 4.0, 0.0

        class Actor:
            def get_velocity(self):
                return Velocity()

        adapter = object.__new__(SweepNativeAdapter)
        adapter.motion_rows = []
        def base_tick(self, frame, hz, actors, cameras):
            self.motion_rows.append({"frame": frame, "ego_speed_mps": 5.0})
        with patch.object(SweepNativeAdapter.__bases__[0], "tick_and_capture", base_tick):
            adapter.tick_and_capture(7, 20, {"slower_vehicle": Actor()}, {})
        self.assertEqual(adapter.motion_rows[-1]["slower_vehicle_speed_mps"], 5.0)

    def test_runner_binds_one_exact_scene_before_native_attempt(self):
        output = self.root.parent / (self.root.name + "-native")
        self.addCleanup(lambda: __import__("shutil").rmtree(output, ignore_errors=True))
        case_id = ASSIGNMENT + "__passing_necessity_middle"
        with patch("sweep_runner.SweepNativeAdapter") as adapter_class, \
                patch("sweep_runner.execute_native") as execute:
            run(self.root, self.site_ref, self.ranges_ref, case_id, output, "localhost", 2000)
        scene = json.loads((output / "requested-scene.json").read_text())
        self.assertEqual(scene["case_id"], case_id)
        self.assertEqual(scene["sweep"]["original_readback_field"],
                         "slower_vehicle_speed_mps")
        self.assertEqual(execute.call_args.args[0], scene)
        self.assertEqual(adapter_class.return_value.site_road_id, "21")
        adapter_class.return_value.close.assert_called_once()
        with self.assertRaisesRegex(ValueError, "fresh sweep attempt"):
            run(self.root, self.site_ref, self.ranges_ref, case_id, output, "localhost", 2000)

    def test_original_sweep_comparison_is_source_bound_and_nonlegal(self):
        packet = prepare(self.root, self.site_ref, self.ranges_ref)
        receipts = []
        for index, scene in enumerate(packet["scenes"]):
            trace_id = "original-" + str(index)
            rows = [{"frame": frame, "time_s": frame / 20,
                     scene["sweep"]["original_readback_field"]:
                     scene["sweep"]["requested_setpoint"]}
                    for frame in range(900)]
            name = "trace-" + str(index) + ".json"
            self.write_json(name, {"case_id": scene["case_id"],
                                   "original_trace_id": trace_id, "frames": rows})
            receipts.append({"case_id": scene["case_id"],
                             "source_kind": "original_native_attempt",
                             "owner_released": True, "native_process_exit_code": 0,
                             "site_sha256": packet["site_sha256"],
                             "ranges_sha256": packet["ranges_sha256"],
                             "original_trace_id": trace_id, "trace_ref": self.ref(name)})
        result = audit(self.root, self.site_ref, self.ranges_ref, receipts)
        self.assertEqual(len(result["comparisons"]), 2)
        self.assertFalse(result["physical_acceptance"])
        self.assertEqual(result["legal_impediment_or_exception"], "unresolved")
        receipts[1]["original_trace_id"] = receipts[0]["original_trace_id"]
        with self.assertRaisesRegex(ValueError, "readback required"):
            audit(self.root, self.site_ref, self.ranges_ref, receipts)


if __name__ == "__main__":
    unittest.main()
