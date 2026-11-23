import importlib.util
import json
import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "native_witness.py"
spec = importlib.util.spec_from_file_location("c158196_native_witness", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def body(x, y):
    return [[x - .4, y - .4], [x + .4, y - .4], [x + .4, y + .4], [x - .4, y + .4]]


def packet(control="stop_sign"):
    frames = []
    for i in range(900):
        x = -5 if i < 100 else (0 if i < 160 else 5)
        frames.append({
            "native_frame": i, "camera_frame": i, "time_s": i / 20,
            "control_context": control,
            "ego": {"body_vertices_xy": body(x, 0), "speed_mps": 0 if i == 90 else 2,
                    "applied_controls": {"throttle": .2, "brake": 0}},
            "counterpart": {"body_vertices_xy": body(0, 0), "obligated_to_stop_or_yield": False},
        })
    return {"sources": {x: f"native/{x}.jsonl" for x in
                         ("native_world", "native_devices", "native_ego", "native_counterpart", "camera_sync")},
            "intersection_rectangle_xy": [-2, -2, 2, 2], "frames": frames}


class WitnessTest(unittest.TestCase):
    def test_every_case_spec_has_source_gated_controls(self):
        specs = json.loads((MODULE.parent / "case-specs.json").read_text())["cases"]
        self.assertEqual(len(specs), 6)
        self.assertEqual({s["counterpart_relation"] for s in specs}, {"within", "approaching"})
        for s in specs:
            self.assertTrue(s["ego_spawn"]["resolve_from_native_map"])
            self.assertTrue(s["counterpart_spawn"]["resolve_from_native_map"])
            self.assertEqual((s["capture"]["fps"], s["capture"]["frames"]), (20, 900))
            self.assertEqual(len(s["capture"]["cameras"]), 4)

    def test_source_gated_construction(self):
        class Adapter:
            def __init__(self):
                self.spawned = []
                self.device = {"source": "native/devices.jsonl", "context": "stop_sign", "signal_controlling": False}

            def inspect_intersection(self):
                return {"layout": "one_way_to_two_way_intersection", "through_highway": False,
                        "intersection_rectangle_xy": [-2, -2, 2, 2], "source": "native/map.json"}

            def inspect_devices(self):
                return self.device

            def spawn_vehicle(self, role, spawn):
                self.spawned.append((role, spawn))
                return role + "-id"

            def set_target_speed(self, actor, speed):
                self.spawned.append((actor, speed))

        spec = {"cell_id": "C158196", "law_id": "NRS-484B-257-2", "control_context": "stop_sign",
                "counterpart_start_m": 10, "ego_spawn": "west-entry", "counterpart_spawn": "cross-lane",
                "ego_target_mps": 2, "counterpart_target_mps": 3}
        adapter = Adapter()
        receipt = mod.build_case(adapter, spec)
        self.assertEqual(receipt["ego_id"], "ego-id")
        self.assertEqual(len(adapter.spawned), 4)
        adapter.device["signal_controlling"] = True
        with self.assertRaisesRegex(ValueError, "defeats sign"):
            mod.build_case(adapter, spec)
        self.assertEqual(len(adapter.spawned), 4)

    def test_original_within_and_stop(self):
        result = mod.measure(packet(), "stop_sign")
        self.assertEqual((result["entry_frame"], result["clearance_frame"]), (100, 160))
        self.assertEqual(result["legal_hazard_judgment"], "unresolved")
        self.assertEqual(len(result["counterpart_within_frames"]), 60)

    def test_no_stopped_history_rejected(self):
        p = packet()
        p["frames"][90]["ego"]["speed_mps"] = 2
        with self.assertRaisesRegex(ValueError, "no observed stop"):
            mod.measure(p, "stop_sign")

    def test_yield_sign_does_not_impose_stop(self):
        p = packet("yield_sign")
        p["frames"][90]["ego"]["speed_mps"] = 2
        self.assertEqual(mod.measure(p, "yield_sign")["entry_frame"], 100)

    def test_incomplete_or_unsynced_source_rejected(self):
        p = packet()
        del p["sources"]["camera_sync"]
        with self.assertRaisesRegex(ValueError, "source inventory"):
            mod.measure(p, "stop_sign")
        p = packet()
        p["frames"][150]["camera_frame"] = 149
        with self.assertRaisesRegex(ValueError, "frame maps"):
            mod.measure(p, "stop_sign")
        p = packet()
        p["frames"][200]["time_s"] = 10.01
        with self.assertRaisesRegex(ValueError, "20Hz"):
            mod.measure(p, "stop_sign")

    def test_crossing_and_priority_required(self):
        p = packet()
        p["frames"][100]["counterpart"]["obligated_to_stop_or_yield"] = None
        with self.assertRaisesRegex(ValueError, "priority"):
            mod.measure(p, "stop_sign")
        p = packet()
        for f in p["frames"]:
            f["counterpart"]["body_vertices_xy"] = body(9, 9)
        with self.assertRaisesRegex(ValueError, "no counterpart"):
            mod.measure(p, "stop_sign")

    def test_active_control_context_is_separate(self):
        p = packet("signal_exception")
        self.assertEqual(mod.measure(p, "signal_exception")["entry_frame"], 100)
        with self.assertRaisesRegex(ValueError, "context changed"):
            mod.measure(p, "stop_sign")

    def test_approaching_counterpart_has_original_motion(self):
        p = packet()
        for i, frame in enumerate(p["frames"]):
            frame["counterpart"]["body_vertices_xy"] = body(0, max(3, 14 - i * .04))
        self.assertEqual(mod.measure(p, "stop_sign", "approaching")["counterpart_relation_observed"], "approaching")
        with self.assertRaisesRegex(ValueError, "no counterpart fully within"):
            mod.measure(p, "stop_sign", "within")
        for frame in p["frames"]:
            frame["counterpart"]["body_vertices_xy"] = body(0, 10)
        with self.assertRaisesRegex(ValueError, "approach not observed"):
            mod.measure(p, "stop_sign", "approaching")

    def test_comparison_isolation(self):
        a = {"map_sha256": "map", "intersection_rectangle_xy": [-2, -2, 2, 2],
             "ego_blueprint": "car", "counterpart_blueprint": "car", "weather": "clear",
             "fps": 20, "camera_policy": "four cameras", "counterpart_start_m": 10}
        b = dict(a, counterpart_start_m=20)
        self.assertTrue(mod.compare(a, b, ["counterpart_start_m"]))
        with self.assertRaisesRegex(ValueError, "fixed condition"):
            mod.compare(a, dict(b, weather="rain"), ["counterpart_start_m"])
        with self.assertRaisesRegex(ValueError, "not realized"):
            mod.compare(a, dict(a), ["counterpart_start_m"])


if __name__ == "__main__":
    unittest.main()
