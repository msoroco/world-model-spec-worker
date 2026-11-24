"""Original-shaped synthetic tests only; no CARLA or legal acceptance."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c125763_saved_crossing", ROOT/"saved_crossing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def body(x, y):
    return [[x-.4,y-.4],[x+.4,y-.4],[x+.4,y+.4],[x-.4,y+.4]]


class CrossingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = {"assignment_id": module.ASSIGNMENT, "cell_id": "C125763",
                     "case_id": module.ASSIGNMENT+"__precedence", "reviewer": "fixture only",
                     "map_source_citation": "fixture map", "highway_source_citation": "fixture roads",
                     "device_source_citation": "fixture yield sign", "crossing_id": "crossing A",
                     "roadway_id": "roadway A", "ego_highway": "west highway",
                     "other_highway": "north highway", "approach_relation": "crossing",
                     "ego_side": "left", "other_side": "right",
                     "official_yield_sign_present": True, "yield_sign_controls_intersection": True,
                     "subsection_4_reviewed": False, "ego_actor_id": 11, "other_actor_id": 22,
                     "intersection_polygon_xy_m": [[-1,-1],[1,-1],[1,1],[-1,1]]}
        self.ego = self.rows(11, 6, 8, "x")
        self.other = self.rows(22, 2, 4, "y")
        self.write()

    @staticmethod
    def rows(actor, entry, exit_index, direction):
        result = []
        for i in range(10):
            coordinate = -4 if i < entry else (0 if i < exit_index else 4)
            x, y = (coordinate, 0) if direction == "x" else (0, coordinate)
            result.append({"frame": 100+i, "time_s": i*.05, "actor_id": actor,
                           "body_vertices_xy_m": body(x,y)})
        return result

    def write(self):
        (self.root/"road.xodr").write_text("<OpenDRIVE fixture='true'/>")
        self.site["map_sha256"] = module.sha(self.root/"road.xodr")
        (self.root/"site-context.json").write_text(json.dumps(self.site))
        for key, rows in (("ego",self.ego),("other",self.other)):
            (self.root/f"{key}-body-history.jsonl").write_text(
                "".join(json.dumps(row)+"\n" for row in rows))
        (self.root/"source-manifest.json").write_text(json.dumps({name:{
            "kind":"original_native","sha256":module.sha(self.root/name)}
            for name in module.SOURCES}))

    def test_original_entry_clearance_and_exception_uncertainty(self):
        result = module.measure(self.root)
        self.assertEqual(result["other_entry"]["upper_frame"], 102)
        self.assertEqual(result["ego_entry"]["upper_frame"], 106)
        self.assertTrue(result["other_entered_before_ego"])
        self.assertTrue(result["other_cleared_before_ego_entry"])
        self.assertEqual(result["simultaneous_body_overlap_frames"], [])
        self.assertIn("unresolved", result["legal_applicability"])
        self.assertFalse(result["legal_verdict_claimed"])

    def test_pair_isolates_ego_response(self):
        waiting = module.measure(self.root)
        self.site["case_id"] = module.ASSIGNMENT+"__advance"
        self.ego = self.rows(11, 3, 8, "x")
        self.write()
        advancing = module.measure(self.root)
        self.assertEqual(advancing["simultaneous_body_overlap_frames"], [103])
        self.assertEqual(module.compare(waiting, advancing)["declared_difference"],
                         "ego_response_clearance_order")
        changed = copy.deepcopy(advancing)
        changed["yield_sign_controls_intersection"] = False
        with self.assertRaisesRegex(ValueError, "fixed comparison condition"):
            module.compare(waiting, changed)
        with self.assertRaisesRegex(ValueError, "did not change"):
            module.compare(waiting, waiting | {"case_id":"other"})

    def test_missing_tampered_and_wrong_scope_rejected(self):
        (self.root/"other-body-history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "missing or stale original"):
            module.measure(self.root)
        self.write()
        (self.root/"road.xodr").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "missing or stale original"):
            module.measure(self.root)
        self.write()
        self.site["official_yield_sign_present"] = False
        self.write()
        with self.assertRaisesRegex(ValueError, "yield-sign identity"):
            module.measure(self.root)

    def test_frame_join_gap_identity_and_late_missing_body_rejected(self):
        self.other[3]["frame"] += 1
        self.write()
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            module.measure(self.root)
        self.other[3]["frame"] -= 1
        self.other[5]["actor_id"] = 99
        self.write()
        with self.assertRaisesRegex(ValueError, "actor identity"):
            module.measure(self.root)
        self.other[5]["actor_id"] = 22
        self.other[-1]["body_vertices_xy_m"] = None
        self.write()
        with self.assertRaisesRegex(ValueError, "missing original polygon"):
            module.measure(self.root)

    def test_missing_exit_and_highway_relation_rejected(self):
        self.other = self.rows(22, 2, 11, "y")
        self.write()
        with self.assertRaisesRegex(ValueError, "exit not captured"):
            module.measure(self.root)
        self.other = self.rows(22, 2, 4, "y")
        self.site["other_highway"] = self.site["ego_highway"]
        self.write()
        with self.assertRaisesRegex(ValueError, "different highways"):
            module.measure(self.root)


if __name__ == "__main__":
    unittest.main()
