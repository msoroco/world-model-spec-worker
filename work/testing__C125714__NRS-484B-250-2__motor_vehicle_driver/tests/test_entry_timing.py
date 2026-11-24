"""Synthetic original-shaped data tests; no physical/legal acceptance claim."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c125714_entry_timing", ROOT / "entry_timing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
finalizer_spec = importlib.util.spec_from_file_location(
    'c125714_finalizer', ROOT / 'saved_finalizer.py')
finalizer = importlib.util.module_from_spec(finalizer_spec)
finalizer_spec.loader.exec_module(finalizer)


def rectangle(x, y):
    return [[x-0.4, y-0.4], [x+0.4, y-0.4], [x+0.4, y+0.4], [x-0.4, y+0.4]]


class EntryTimingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.site = {
            "assignment_id": module.ASSIGNMENT, "cell_id": "C125714",
            "case_id": module.ASSIGNMENT + "__precedence", "reviewer": "synthetic fixture",
            "map_source_citation": "fixture map", "highway_source_citation": "fixture approaches",
            "device_source_citation": "fixture inventory", "crossing_id": "fixture crossing",
            "roadway_id": "fixture roadway", "ego_actor_id": 11, "other_actor_id": 22,
            "ego_highway": "road A", "other_highway": "road B", "ego_side": "left",
            "other_side": "right", "approach_relation": "crossing",
            "official_device_controls_intersection": False, "other_left_turn_intent": False,
            "subsection_4_context_reviewed": False,
            "intersection_polygon_xy_m": [[-1,-1],[1,-1],[1,1],[-1,1]],
        }
        self.ego = [self.row(i, 11, -4 if i < 3 else 0, 0) for i in range(6)]
        self.other = [self.row(i, 22, 0, -4 if i < 2 else 0) for i in range(6)]
        self.write()

    @staticmethod
    def row(i, actor_id, x, y):
        return {"frame": 100+i, "time_s": i*0.05, "actor_id": actor_id,
                "body_vertices_xy_m": rectangle(x, y)}

    def write(self):
        (self.root / "road.xodr").write_text("<OpenDRIVE fixture='true'/>")
        self.site["map_sha256"] = module.sha(self.root / "road.xodr")
        (self.root / "site-context.json").write_text(json.dumps(self.site))
        for name, data in (("ego", self.ego), ("other", self.other)):
            (self.root / f"{name}-body-history.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in data))
        (self.root / "source-manifest.json").write_text(json.dumps({name: {
            "kind": "original_native", "sha256": module.sha(self.root / name)}
            for name in module.SOURCES}))

    def test_entry_uses_original_footprint_and_time_brackets(self):
        result = module.measure(self.root)
        self.assertEqual(result["ego_entry"]["upper_frame"], 103)
        self.assertEqual(result["other_entry"]["upper_frame"], 102)
        self.assertAlmostEqual(result["intersection_entry_time_difference_s"], .05)
        self.assertAlmostEqual(result["difference_bracket_s"][0], 0)
        self.assertAlmostEqual(result["difference_bracket_s"][1], .1)
        self.assertEqual(result["approximately_same_time"], "unresolved_judgment")
        self.assertFalse(result["legal_verdict_claimed"])

    def test_missing_and_tampered_original_rejected(self):
        (self.root / "other-body-history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "missing or stale original"):
            module.measure(self.root)
        self.write()
        with (self.root / "road.xodr").open("a") as stream:
            stream.write("tampered")
        with self.assertRaisesRegex(ValueError, "missing or stale original"):
            module.measure(self.root)

    def test_frame_gap_and_identity_rejected_even_with_current_hash(self):
        self.other[4]["frame"] += 1
        self.ego[4]["frame"] += 1
        self.write()
        with self.assertRaisesRegex(ValueError, "20 Hz frame sequence"):
            module.measure(self.root)
        self.ego[4]["frame"] -= 1
        self.other[4]["frame"] -= 1
        self.other[0]["actor_id"] = 99
        self.write()
        with self.assertRaisesRegex(ValueError, "actor identity"):
            module.measure(self.root)

    def test_initial_overlap_or_missing_entry_rejected(self):
        self.ego[0]["body_vertices_xy_m"] = rectangle(0, 0)
        self.write()
        with self.assertRaisesRegex(ValueError, "initial frame"):
            module.measure(self.root)
        self.ego = [self.row(i, 11, -4, 0) for i in range(6)]
        self.write()
        with self.assertRaisesRegex(ValueError, "no original body entry"):
            module.measure(self.root)

    def test_site_scope_and_comparison_isolation(self):
        first = module.measure(self.root)
        self.site["case_id"] = module.ASSIGNMENT + "__other_later"
        self.other = [self.row(i, 22, 0, -4 if i < 4 else 0) for i in range(6)]
        self.write()
        second = module.measure(self.root)
        audit = module.compare(first, second, "entry_timing")
        self.assertEqual(audit["variable"], "entry_timing")
        broken = copy.deepcopy(second)
        broken["official_device_controls_intersection"] = True
        with self.assertRaisesRegex(ValueError, "undeclared difference"):
            module.compare(first, broken, "entry_timing")
        with self.assertRaisesRegex(ValueError, "undeclared difference"):
            module.compare(first, second, "ego_side")
        self.site["ego_highway"] = "road B"
        self.write()
        with self.assertRaisesRegex(ValueError, "different highways"):
            module.measure(self.root)

    def test_opposite_branch_requires_same_highway(self):
        self.site["approach_relation"] = "opposite"
        self.site["other_highway"] = "road A"
        self.write()
        result = module.measure(self.root)
        self.assertEqual(result["approach_relation"], "opposite")
        self.assertEqual(result["legal_applicability"], "unresolved_review")

    def test_selected_finalizer_positive_and_missing_source_negative(self):
        selected = module.ASSIGNMENT + '__timing_inside_training'
        self.site['case_id'] = selected
        self.site['subsection_4_context_reviewed'] = True
        self.write()
        result = finalizer.finalize(self.root, selected)
        self.assertEqual(result['measurement'], 'intersection_entry_time_difference_s')
        self.assertAlmostEqual(result['measured_value_s'], .05)
        self.assertFalse(result['legal_verdict_claimed'])
        with self.assertRaisesRegex(ValueError, 'case identity'):
            finalizer.finalize(self.root, module.ASSIGNMENT + '__timing_below_training')
        (self.root / 'other-body-history.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'missing or stale original'):
            finalizer.finalize(self.root, selected)


if __name__ == "__main__":
    unittest.main()
