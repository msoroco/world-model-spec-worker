import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    obj = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj

signal = module("signal_measurement")
compare = module("comparison_audit")
SOURCE = {"path": "sealed/native.json", "sha256": "a" * 64}


def packet(entry_frame=4, count=8):
    frames = []
    for i in range(count):
        state = "green" if i < 2 else "yellow" if i < 5 else "red"
        frames.append({"frame": i, "source_frame": i, "time_s": i / 20,
                       "ego_front_signed_distance_m": i - entry_frame + 0.25,
                       "ego_geometry_source": SOURCE,
                       "signals": [{"signal_id": "head1", "route_id": "ego_route", "kind": "vehicular",
                                    "official": True, "facing_ego": True, "state": state,
                                    "flashing": False, "companion_lamps_on": [], "source": SOURCE},
                                   {"signal_id": "head2", "route_id": "other_route", "kind": "vehicular",
                                    "official": True, "facing_ego": False, "state": "red", "source": SOURCE}]})
    return {"layout": "one_way_to_two_way_intersection", "route_id": "ego_route", "signal_id": "head1",
            "intersection_polygon": SOURCE, "route_connectivity": SOURCE,
            "device_route_binding": SOURCE, "native_result": SOURCE, "frames": frames}


class SignalMeasurementTest(unittest.TestCase):
    def test_yellow_entry_and_red_entry_are_distinct(self):
        yellow = signal.measure(packet(4), 8)
        red = signal.measure(packet(6), 8)
        self.assertEqual(yellow["entry_observation"], "yellow_both_samples")
        self.assertEqual(red["entry_observation"], "red_both_samples")
        self.assertEqual(red["entry_bracket"]["after_frame"], 6)
        self.assertEqual(red["legal_judgment"], "unresolved")

    def test_already_inside_and_no_entry(self):
        already = packet(0)
        self.assertEqual(signal.measure(already, 8)["entry_observation"], "no_entry")
        stopped = packet(99)
        self.assertEqual(signal.measure(stopped, 8)["entry_observation"], "no_entry")

    def test_transition_bracket_not_assigned_a_color(self):
        p = packet(5)
        self.assertEqual(signal.measure(p, 8)["entry_observation"], "transition_bracket_unresolved")

    def test_rejects_non_steady_yellow_and_wrong_route(self):
        p = packet()
        p["frames"][2]["signals"][0]["flashing"] = True
        with self.assertRaisesRegex(signal.EvidenceError, "steady yellow alone"):
            signal.measure(p, 8)
        p = packet()
        p["frames"][3]["signals"][0]["route_id"] = "other_route"
        with self.assertRaisesRegex(signal.EvidenceError, "exactly one"):
            signal.measure(p, 8)

    def test_rejects_wrong_source_or_missing_sequence(self):
        p = packet()
        p["frames"][0]["signals"][0]["source"] = None
        with self.assertRaisesRegex(signal.EvidenceError, "source binding"):
            signal.measure(p, 8)
        p = packet()
        for f in p["frames"]:
            if f["signals"][0]["state"] == "red":
                f["signals"][0]["state"] = "yellow"
        with self.assertRaisesRegex(signal.EvidenceError, "subsequent red"):
            signal.measure(p, 8)

    def test_rejects_broken_original_join_and_incomplete_history(self):
        p = packet()
        p["frames"][3]["time_s"] = 100
        with self.assertRaisesRegex(signal.EvidenceError, "frame/time"):
            signal.measure(p, 8)
        with self.assertRaisesRegex(signal.EvidenceError, "incomplete"):
            signal.measure(packet(), 900)


def delivery(case_id, observation):
    d = {field: "fixed" for field in compare.FIXED_FIELDS}
    d.update({"format": "signal-delivery-measurement", "case_id": case_id,
              "native_result_sha256": case_id * 64, "frame_count": 900,
              "full_video_decode": True, "actual_pixels": True,
              "physical_completion": True,
              "observables": {"entry_observation": observation}})
    return d


class ComparisonAuditTest(unittest.TestCase):
    def test_comparison_checks_realized_difference(self):
        r = compare.audit(delivery("a", "yellow_both_samples"), delivery("b", "red_both_samples"),
                          deliberate_differences=["entry_observation"])
        self.assertEqual(r["status"], "measurement_comparable_legal_judgment_unresolved")

    def test_rejects_unrealized_difference_and_changed_fixed_condition(self):
        a, b = delivery("a", "red_both_samples"), delivery("b", "red_both_samples")
        with self.assertRaisesRegex(compare.ComparisonError, "not realized"):
            compare.audit(a, b, deliberate_differences=["entry_observation"])
        b["observables"]["entry_observation"] = "no_entry"
        b["map_sha256"] = "different"
        with self.assertRaisesRegex(compare.ComparisonError, "fixed condition changed"):
            compare.audit(a, b, deliberate_differences=["entry_observation"])

    def test_rejects_missing_physical_evidence(self):
        a, b = delivery("a", "red_both_samples"), delivery("b", "no_entry")
        b["actual_pixels"] = False
        with self.assertRaisesRegex(compare.ComparisonError, "physical visibility"):
            compare.audit(a, b, deliberate_differences=["entry_observation"])
        b = delivery("b", "no_entry")
        del b["device_route_binding_sha256"]
        with self.assertRaisesRegex(compare.ComparisonError, "missing fixed condition"):
            compare.audit(a, b, deliberate_differences=["entry_observation"])


if __name__ == "__main__":
    unittest.main()

construction = module("construction")


def scene():
    return {"map_sha256": "a" * 64, "intersection_polygon_sha256": "b" * 64,
            "route_connectivity_sha256": "c" * 64, "ego_blueprint": "vehicle.tesla.model3",
            "selected_route_id": "ego_route", "selected_signal_id": "head1",
            "official_device_sha256": "d" * 64, "signal_route_binding_sha256": "e" * 64,
            "approach_spawn": [0, 0, 0], "route_waypoints": [[0, 0], [10, 0], [20, 0]],
            "layout": "one_way_to_two_way_intersection", "signal_kind": "vehicular",
            "signal_facing_route_id": "ego_route",
            "route_direction_sequence": ["one_way", "intersection", "two_way"],
            "duration_frames": 900, "rate_hz": 20, "cameras": list(construction.CAMERAS)}


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def configure_world(self, *args, **kwargs):
        self.calls.append(("configure_world", args, kwargs))

    def spawn_ego(self, *args):
        self.calls.append(("spawn_ego", args, {}))
        return "ego"

    def bind_official_signal(self, signal_id, route_id):
        self.calls.append(("bind_official_signal", (signal_id, route_id), {}))
        return {"kind": "vehicular", "facing_route_id": route_id}

    def program_signal(self, *args, **kwargs):
        self.calls.append(("program_signal", args, kwargs))

    def set_route_controller(self, *args, **kwargs):
        self.calls.append(("set_route_controller", args, kwargs))

    def attach_camera(self, *args):
        self.calls.append(("attach_camera", args, {}))


class ConstructionTest(unittest.TestCase):
    def test_constructs_every_case_with_native_device_and_cameras(self):
        for case in construction.CASE_PROFILES:
            adapter = FakeAdapter()
            result = construction.construct(adapter, scene(), case)
            self.assertEqual(result["physical_outcome"], "unverified")
            self.assertEqual([x[0] for x in adapter.calls].count("attach_camera"), 4)
            self.assertIn("bind_official_signal", [x[0] for x in adapter.calls])

    def test_rejects_wrong_route_and_capture_profile_before_side_effects(self):
        s = scene()
        s["signal_facing_route_id"] = "other_route"
        adapter = FakeAdapter()
        with self.assertRaisesRegex(construction.ConstructionError, "not bound"):
            construction.construct(adapter, s, "enters_red")
        self.assertEqual(adapter.calls, [])
        s = scene()
        s["duration_frames"] = 100
        with self.assertRaisesRegex(construction.ConstructionError, "capture profile"):
            construction.construct(adapter, s, "enters_red")
        self.assertEqual(adapter.calls, [])

class FullLengthMeasurementTest(unittest.TestCase):
    def test_900_frame_capture_contract(self):
        p = packet(entry_frame=4, count=900)
        measured = signal.measure(p)
        self.assertEqual(measured["frame_count"], 900)
        self.assertEqual(measured["entry_observation"], "yellow_both_samples")
        self.assertEqual(len(measured["phase_transitions"]), 2)
