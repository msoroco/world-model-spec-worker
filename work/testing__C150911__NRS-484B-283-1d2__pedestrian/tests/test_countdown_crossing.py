import importlib.util
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "countdown_crossing.py"
SPEC = importlib.util.spec_from_file_location("countdown_crossing", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def site():
    value = {"cell_id": "C150911", "actor": "pedestrian",
        "layout": "one_way_road", "highway_public_vehicular_access": True,
        "signal_facing_pedestrian": True, "signal_facing_direction": "both",
        "highway_polygon_xy": [[-1, -1], [1, -1], [1, 1], [-1, 1]],
        "crossing_routes": {
            "forward": {"source_sha256": "f", "waypoints_xy": [[-2, 0], [0, 0], [2, 0]]},
            "reverse": {"source_sha256": "r", "waypoints_xy": [[2, 0], [0, 0], [-2, 0]]}}}
    for name in ("opendrive", "highway", "crossing", "sidewalk", "signal",
                 "signal_facing", "one_way_direction", "exception_context"):
        value[name + "_source_sha256"] = name
    return value


class Adapter:
    def __init__(self):
        self.calls = []

    def spawn_pedestrian(self, point):
        self.calls.append(("spawn", point))
        return "pedestrian-1"

    def request_pedestrian_signal(self, **kwargs):
        self.calls.append(("signal", kwargs))

    def set_pedestrian_route(self, *args, **kwargs):
        self.calls.append(("route", args, kwargs))

    def destroy(self, actor):
        self.calls.append(("destroy", actor))


def rows(case, completion_index=5):
    source = site()
    route = source["crossing_routes"][case.direction]["waypoints_xy"]
    result = []
    for i in range(8):
        value = 2 if i < 3 else 1 if i < 5 else 0
        pos = route[0] if i < 2 else route[1] if i < completion_index else route[-1]
        result.append({"original_frame": 100 + i, "time_s": i / 20,
            "source_sha256": "row", "signal_readback_sha256": "signal",
            "pedestrian_pose_sha256": "pose", "site_source_sha256": "signal",
            "signal_facing_direction": case.direction, "signal_form": case.signal_form,
            "pedestrian_id": "pedestrian-1", "illuminated": True,
            "flashing": i < 5, "countdown_present": True,
            "countdown_value": value, "pedestrian_xy": pos})
    return result


class CountdownCrossing(unittest.TestCase):
    def test_constructs_both_directions_and_forms(self):
        for case in MODULE.CASES:
            adapter = Adapter()
            built = MODULE.construct(adapter, site(), case)
            self.assertEqual(built["route_xy"][0], site()["crossing_routes"][case.direction]["waypoints_xy"][0])
            self.assertEqual(adapter.calls[1][1]["signal_form"], case.signal_form)
            self.assertEqual(adapter.calls[2][2]["requested_completion_s"],
                {"before_zero": 14.0, "at_zero": 15.0,
                 "after_zero": 16.0}[case.completion])

    def test_statutory_zero_boundary_and_missing_readback(self):
        before, at, after = MODULE.CASES[:3]
        for case, completion in ((before, 4), (at, 5), (after, 6)):
            measured = MODULE.measure_original(rows(case, completion), site(), case)
            self.assertEqual(measured["completion_relation"], case.completion)
            self.assertIsNone(measured["legal_judgment"])
        incomplete = rows(before, 4)
        del incomplete[2]["countdown_value"]
        with self.assertRaisesRegex(ValueError, "legible original countdown"):
            MODULE.measure_original(incomplete, site(), before)

    def test_rejects_wrong_direction_and_missing_source(self):
        case = MODULE.CASES[-1]
        original = rows(case, 4)
        original[2]["signal_facing_direction"] = "forward"
        with self.assertRaisesRegex(ValueError, "facing signal"):
            MODULE.measure_original(original, site(), case)
        bad = site()
        bad["highway_source_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "original source missing"):
            MODULE.construct(Adapter(), bad, case)


if __name__ == "__main__":
    unittest.main()
