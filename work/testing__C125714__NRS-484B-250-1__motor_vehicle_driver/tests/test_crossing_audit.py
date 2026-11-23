import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "crossing_audit.py"
spec = importlib.util.spec_from_file_location("crossing_audit", SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
sys.modules["crossing_audit"] = audit
CONTROL_SOURCE = SOURCE.parent / "crossing_control.py"
control_spec = importlib.util.spec_from_file_location("crossing_control", CONTROL_SOURCE)
control = importlib.util.module_from_spec(control_spec)
control_spec.loader.exec_module(control)


def trace(other_frames=(1, 2, 3, 4), ego_frames=(3, 4, 5, 6)):
    def samples(frames):
        enter, leave = frames[1], frames[3]
        return [{"frame": f, "body_vertices_xy_m":
                 [[-.2, y-.2], [.2, y-.2], [.2, y+.2], [-.2, y+.2]]}
                for f in range(9)
                for y in [-2 if f < enter else (0 if f < leave else 2)]]
    return {
        "context": {
            "map_source": "OpenDRIVE map hash", "ego_highway": "A",
            "other_highway": "B", "public_access_source": "road inventory hash",
            "device_inventory_source": "map inspection hash", "driver_scope_source": "actor blueprint hash",
            "public_access": True, "human_driver": True, "devices": [],
            "approach_relation": "crossing", "left_turn_intent": False,
            "left_turn_realized": False,
        },
        "crossing": {"crossing_id": "A-B-west", "roadway_id": "A-west", "bounds_xy_m": [-1, -1, 1, 1]},
        "other_samples": samples(other_frames), "ego_samples": samples(ego_frames),
    }


class CrossingAuditTests(unittest.TestCase):
    def test_opposite_geometry_requires_same_highway_and_reversed_heading(self):
        scene = {
            "crossing": {"crossing_id": "A-median", "map_source_sha256": "a" * 64,
                         "bounds_xy_m": [-1, -1, 1, 1]},
            "approach_relation": "opposite", "ego_highway": "A", "other_highway": "A",
            "ego_route_xy_m": [[-3, 0], [0, 0], [3, 0]],
            "other_route_xy_m": [[3, 0], [0, 0], [-3, 0]],
        }
        self.assertEqual(control.validate_routes(scene)["crossing_id"], "A-median")
        scene["other_route_xy_m"] = [[0, -3], [0, 0], [0, 3]]
        with self.assertRaisesRegex(ValueError, "opposite approach"):
            control.validate_routes(scene)
        scene["other_route_xy_m"] = [[3, 0], [0, 0], [-3, 0]]
        scene["other_highway"] = "B"
        with self.assertRaisesRegex(ValueError, "one highway identity"):
            control.validate_routes(scene)

    def test_map_binding_rejects_hash_and_road_mismatch(self):
        class Waypoint:
            def __init__(self, road_id, is_junction, x, y):
                self.road_id, self.is_junction = road_id, is_junction
                self.lane_id = -1
                self.transform = type("Transform", (), {"location": type("Location", (), {"x": x, "y": y})()})()
                self.following = []

            def next(self, distance):
                return self.following

        class Map:
            def __init__(self):
                self.nodes = {(x,y): Waypoint(10 if abs(x) >= abs(y) else 20,
                                              x == 0 and y == 0, x, y)
                              for x,y in ((-3,0),(0,0),(3,0),(0,-3),(0,3))}
                for route in (((-3,0),(0,0),(3,0)),((0,-3),(0,0),(0,3))):
                    for start,end in zip(route,route[1:]):
                        self.nodes[start].following.append(self.nodes[end])
            def to_opendrive(self):
                return "inspected OpenDRIVE"

            def get_waypoint(self, point, project_to_road=False):
                return self.nodes.get(point)

        scene = {
            "crossing": {"crossing_id": "A-B-west",
                         "map_source_sha256": hashlib.sha256(b"inspected OpenDRIVE").hexdigest(),
                         "bounds_xy_m": [-1, -1, 1, 1]},
            "ego_highway": "A", "other_highway": "B",
            "ego_approach_road_id": 10, "other_approach_road_id": 20,
            "ego_route_xy_m": [[-3, 0], [0, 0], [3, 0]],
            "other_route_xy_m": [[0, -3], [0, 0], [0, 3]],
        }
        self.assertEqual(len(control.bind_map(Map(), scene, lambda x, y: (x, y))["ego"]), 3)
        scene["crossing"]["map_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "map hash"):
            control.bind_map(Map(), scene, lambda x, y: (x, y))
        scene["crossing"]["map_source_sha256"] = hashlib.sha256(b"inspected OpenDRIVE").hexdigest()
        scene["other_approach_road_id"] = 99
        with self.assertRaisesRegex(ValueError, "road ID"):
            control.bind_map(Map(), scene, lambda x, y: (x, y))

    def test_saved_trace_hash_and_missing_source(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.json"
            raw = json.dumps(trace()).encode()
            path.write_bytes(raw)
            self.assertTrue(audit.load_and_measure(path, hashlib.sha256(raw).hexdigest()))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                audit.load_and_measure(path, "0" * 64)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                audit.load_and_measure(path, hashlib.sha256(raw).hexdigest())

    def test_route_geometry_and_control(self):
        scene = {
            "crossing": {"crossing_id": "A-B-west", "map_source_sha256": "a" * 64,
                         "bounds_xy_m": [-1, -1, 1, 1]},
            "ego_highway": "A", "other_highway": "B",
            "ego_route_xy_m": [[-3, 0], [0, 0], [3, 0]],
            "other_route_xy_m": [[0, -3], [0, 0], [0, 3]],
        }
        self.assertEqual(control.validate_routes(scene)["crossing_id"], "A-B-west")
        self.assertEqual(control.ego_request(True, True, False, True), "brake")
        self.assertEqual(control.ego_request(True, False, False, False), "brake")
        self.assertEqual(control.ego_request(True, False, False, True), "brake")
        self.assertEqual(control.ego_request(True, False, False, True, require_other_first=False), "proceed")
        self.assertEqual(control.ego_request(True, True, True, True), "proceed")
        scene["other_route_xy_m"] = [[-3, 0], [0, 0], [3, 0]]
        with self.assertRaisesRegex(ValueError, "crossing approach"):
            control.validate_routes(scene)

    def test_entry_order_and_clearance_are_separate(self):
        result = audit.measure(trace())
        self.assertTrue(result["other_entered_before_ego"])
        self.assertFalse(result["other_cleared_before_ego_entry"])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_reentry_cannot_be_counted_as_final_clearance(self):
        t = trace()
        t["other_samples"][5]["body_vertices_xy_m"] = [
            [-.2, -.2], [.2, -.2], [.2, .2], [-.2, .2]]
        with self.assertRaisesRegex(ValueError, "reentered the crossing"):
            audit.measure(t)

    def test_reverse_order(self):
        result = audit.measure(trace(other_frames=(4, 5, 6, 7), ego_frames=(1, 2, 3, 4)))
        self.assertFalse(result["other_entered_before_ego"])

    def test_exclusions_reported_without_verdict(self):
        t = trace()
        t["context"].update(approach_relation="opposite", left_turn_intent=True,
                            other_highway=t["context"]["ego_highway"], devices=["stop_sign"])
        result = audit.measure(t)
        self.assertTrue(result["official_device_exclusion"])
        self.assertTrue(result["opposite_left_exclusion"])
        self.assertEqual(result["subsection_4_qualification"], "unresolved_source_review")

    def test_declared_actual_left_turn_requires_original_body_motion(self):
        t = trace()
        t["context"].update(approach_relation="opposite",
                            other_highway=t["context"]["ego_highway"],
                            left_turn_intent=True, left_turn_realized=True)
        with self.assertRaisesRegex(ValueError, "realization differs"):
            audit.measure(t)

    def test_short_final_sideways_jitter_is_not_an_actual_left_turn(self):
        def samples(centers):
            return [{"body_vertices_xy_m": [[x-.2, y-.2], [x+.2, y-.2],
                                             [x+.2, y+.2], [x-.2, y+.2]]}
                    for x, y in centers]
        straight_with_jitter = samples([(5, 0), (3, 0), (1, 0), (-1, 0),
                                        (-3, 0), (-5, 0), (-5, -.5)])
        self.assertFalse(audit._observed_left_turn(straight_with_jitter))
        sustained_left = samples([(5, 0), (3, 0), (1, 0), (-1, 0),
                                  (-3, 0), (-3, -2), (-3, -4)])
        self.assertTrue(audit._observed_left_turn(sustained_left))

    def test_missing_source_and_unobserved_entry_rejected(self):
        t = trace()
        del t["context"]["map_source"]
        with self.assertRaisesRegex(ValueError, "map_source"):
            audit.measure(t)
        t = trace()
        t["other_samples"][0]["body_vertices_xy_m"] = [[-.2,-.2],[.2,-.2],[.2,.2],[-.2,.2]]
        with self.assertRaisesRegex(ValueError, "entry unobserved"):
            audit.measure(t)

    def test_body_contact_counts_before_center_entry(self):
        t = trace()
        t["other_samples"][0]["body_vertices_xy_m"] = [[-.2,-1.2],[.2,-1.2],[.2,-.8],[-.2,-.8]]
        with self.assertRaisesRegex(ValueError, "entry unobserved"):
            audit.measure(t)

    def test_gapped_or_misaligned_original_frames_rejected(self):
        t = trace()
        t["other_samples"].pop(3)
        with self.assertRaisesRegex(ValueError, "windows do not match"):
            audit.measure(t)
        t = trace()
        t["other_samples"].pop(3)
        t["ego_samples"].pop(3)
        with self.assertRaisesRegex(ValueError, "gap in original frame"):
            audit.measure(t)

    def test_rotated_body_box_overlap_is_not_physical_entry(self):
        rotated = [[1.15,.95],[1.55,1.35],[1.35,1.55],[.95,1.15]]
        self.assertFalse(audit._body_overlaps(rotated, [-1,-1,1,1]))

    def test_same_highway_rejected(self):
        t = trace()
        t["context"]["other_highway"] = "A"
        with self.assertRaisesRegex(ValueError, "different highway"):
            audit.measure(t)

    def test_comparison_rejects_undeclared_context_change(self):
        a, b = trace(), trace()
        b["context"]["devices"] = ["traffic_light"]
        with self.assertRaisesRegex(ValueError, "undeclared difference"):
            audit.audit_comparison(a, b, ["entry_order"])
        self.assertTrue(audit.audit_comparison(a, b, ["devices"]))

    def test_comparison_rejects_different_crossing(self):
        a, b = trace(), trace()
        b["crossing"]["crossing_id"] = "A-B-east"
        with self.assertRaisesRegex(ValueError, "fixed crossing"):
            audit.audit_comparison(a, b, ["entry_order"])

    def test_comparison_requires_realized_difference(self):
        with self.assertRaisesRegex(ValueError, "did not differ"):
            audit.audit_comparison(trace(), trace(), ["entry_order"])


if __name__ == "__main__":
    unittest.main()
