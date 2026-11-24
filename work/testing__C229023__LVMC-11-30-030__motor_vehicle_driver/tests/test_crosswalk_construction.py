import json
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosswalk_construction import build, build_sourced
from case_construction import CASES, compare_constructions, construct
from crosswalk_measurements import ASSIGNMENT_ID


class CrosswalkConstructionTests(unittest.TestCase):
    def site(self):
        return {"assignment_id": ASSIGNMENT_ID, "map_id": "synthetic-only",
                "junction_kind": "road_intersection", "alley_junction": False,
                "opposite_sidewalk_lateral_lines": [[[10, -3], [14, -3]], [[10, 3], [14, 3]]],
                "curb_or_traveled_edge_source": "synthetic-curb",
                "crosswalk_marking_source": "synthetic-markings",
                "marked_crosswalk_polygon": [[10, -3], [14, -3], [14, 3], [10, 3]],
                "road_y_bounds": [-3, 5], "lead_stop_center": [7, 0],
                "ego_start_center": [-10, 0], "pass_lane_y": 3.5,
                "combined_vehicle_half_width_m": 2.4,
                "pedestrian_start": [12, -4], "pedestrian_end": [12, 6]}

    def run_build(self, site, kind="unmarked", behavior="pass"):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "site.json"
            p.write_text(json.dumps(site), encoding="utf-8")
            return build(p, crosswalk_kind=kind, ego_behavior=behavior)

    def test_unmarked_crossing_and_pass_route_constructed(self):
        r = self.run_build(self.site())
        self.assertEqual(r["crosswalk_polygon"], [[10, -3], [14, -3], [14, 3], [10, 3]])
        self.assertGreater(r["ego_route"][-1][0], 14)

    def test_wait_route_remains_behind_lead(self):
        r = self.run_build(self.site(), behavior="wait")
        self.assertLess(r["ego_route"][-1][0], r["lead_stop_center"][0])

    def test_marked_source_path(self):
        r = self.run_build(self.site(), kind="marked")
        self.assertEqual(r["crosswalk_kind"], "marked")

    def test_missing_opposite_sidewalk_rejected(self):
        s = self.site()
        s["opposite_sidewalk_lateral_lines"] = []
        with self.assertRaisesRegex(ValueError, "opposite sidewalk"):
            self.run_build(s)

    def test_alley_junction_rejected(self):
        s = self.site()
        s["alley_junction"] = True
        with self.assertRaisesRegex(ValueError, "road intersection"):
            self.run_build(s)

    def test_inadequate_lateral_clearance_rejected(self):
        s = self.site()
        s["pass_lane_y"] = 1
        with self.assertRaisesRegex(ValueError, "clearance"):
            self.run_build(s)

    def sourced_site(self, root):
        site = self.site()
        citations = {"map": "map-survey", "intersection": "intersection-survey",
                     "sidewalk": "sidewalk-survey", "curb_or_edge": "synthetic-curb",
                     "stopped_purpose": "stopped-purpose-observation", "marking": "synthetic-markings"}
        site["sources"] = {}
        for name, citation in citations.items():
            payload = (json.dumps({"source_kind": "original_observer_statement", "lead_stop_purpose": "permit_pedestrian"}) + "\n").encode() if name == "stopped_purpose" else (name + " diagnostic source\n").encode()
            (root / (name + ".txt")).write_bytes(payload)
            site["sources"][name] = {"path": name + ".txt", "sha256": hashlib.sha256(payload).hexdigest(), "citation": citation}
        site["map_sha256"] = site["sources"]["map"]["sha256"]
        (root / "site.json").write_text(json.dumps(site))
        return root / "site.json"

    def test_sourced_crossing_binds_original_bytes(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            path = self.sourced_site(Path(d))
            result = build_sourced(path, crosswalk_kind="unmarked", ego_behavior="pass")
            self.assertEqual(set(result["source_inventory"]), {"map", "intersection", "sidewalk", "curb_or_edge", "stopped_purpose"})
            self.assertIn("unreviewed", result["source_status"])
            (Path(d) / "sidewalk.txt").write_text("changed source\n")
            with self.assertRaisesRegex(ValueError, "sidewalk source hash mismatch"):
                build_sourced(path, crosswalk_kind="unmarked", ego_behavior="pass")

    def test_sourced_map_identity_required(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            path = self.sourced_site(Path(d))
            site = json.loads(path.read_text())
            site["map_sha256"] = "0" * 64
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "site map hash"):
                build_sourced(path, crosswalk_kind="unmarked", ego_behavior="pass")

    def test_sourced_marking_and_purpose_required(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            path = self.sourced_site(Path(d))
            result = build_sourced(path, crosswalk_kind="marked", ego_behavior="wait")
            self.assertIn("marking", result["source_inventory"])
            site = json.loads(path.read_text())
            del site["sources"]["stopped_purpose"]
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "complete site source inventory"):
                build_sourced(path, crosswalk_kind="marked", ego_behavior="wait")

    def test_sourced_symlink_and_citation_mismatch_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            root = Path(d)
            path = self.sourced_site(root)
            site = json.loads(path.read_text())
            (root / "linked.txt").symlink_to(root / "sidewalk.txt")
            site["sources"]["sidewalk"]["path"] = "linked.txt"
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "distinct regular source"):
                build_sourced(path, crosswalk_kind="unmarked", ego_behavior="pass")
            site["sources"]["sidewalk"]["path"] = "sidewalk.txt"
            site["sources"]["curb_or_edge"]["citation"] = "different-curb"
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "curb source citation"):
                build_sourced(path, crosswalk_kind="unmarked", ego_behavior="pass")

    def test_sourced_absolute_path_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            root = Path(d)
            path = self.sourced_site(root)
            site = json.loads(path.read_text())
            site["sources"]["map"]["path"] = str(root / "map.txt")
            path.write_text(json.dumps(site))
            with self.assertRaisesRegex(ValueError, "portable sibling filename"):
                build_sourced(path, crosswalk_kind="unmarked", ego_behavior="pass")

    def test_exact_case_construction_selects_behavior_and_purpose(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            root = Path(d)
            path = self.sourced_site(root)
            for suffix, (crossing, behavior, purpose) in CASES.items():
                payload = (json.dumps({"source_kind": "original_observer_statement", "lead_stop_purpose": purpose}) + "\n").encode()
                (root / "stopped_purpose.txt").write_bytes(payload)
                site = json.loads(path.read_text())
                site["sources"]["stopped_purpose"]["sha256"] = hashlib.sha256(payload).hexdigest()
                path.write_text(json.dumps(site))
                result = construct(path, ASSIGNMENT_ID + "__" + suffix)
                self.assertEqual((result["crosswalk_kind"], result["ego_behavior"], result["lead_stop_purpose"]),
                                 (crossing, behavior, purpose))
                self.assertEqual((result["capture_plan"]["fps"], result["capture_plan"]["frames"]), (20, 900))
                self.assertFalse(result["physical_acceptance_claimed"])

    def test_exact_case_rejects_wrong_observed_purpose(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            path = self.sourced_site(Path(d))
            with self.assertRaisesRegex(ValueError, "original lead stop purpose"):
                construct(path, ASSIGNMENT_ID + "__unmarked_other_stop_pass")

    def test_exact_comparison_preserves_fixed_sources(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            path = self.sourced_site(Path(d))
            wait = construct(path, ASSIGNMENT_ID + "__unmarked_wait")
            passed = construct(path, ASSIGNMENT_ID + "__unmarked_pass")
            receipt = compare_constructions(wait, passed, "unmarked_overtake")
            self.assertEqual(receipt["case_ids"], [wait["case_id"], passed["case_id"]])
            changed = json.loads(json.dumps(passed))
            changed["source_inventory"]["map"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "fixed map source"):
                compare_constructions(wait, changed, "unmarked_overtake")
            with self.assertRaisesRegex(ValueError, "exact ordered case pair"):
                compare_constructions(passed, wait, "unmarked_overtake")

    def test_stop_purpose_comparison_isolates_observer_source(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            root = Path(d)
            path = self.sourced_site(root)
            pedestrian = construct(path, ASSIGNMENT_ID + "__unmarked_pass")
            payload = (json.dumps({"source_kind": "original_observer_statement", "lead_stop_purpose": "other"}) + "\n").encode()
            (root / "stopped_purpose.txt").write_bytes(payload)
            site = json.loads(path.read_text())
            site["sources"]["stopped_purpose"]["sha256"] = hashlib.sha256(payload).hexdigest()
            path.write_text(json.dumps(site))
            other = construct(path, ASSIGNMENT_ID + "__unmarked_other_stop_pass")
            receipt = compare_constructions(pedestrian, other, "stop_purpose")
            self.assertNotIn("stopped_purpose", receipt["fixed_source_names_checked"])
            changed = json.loads(json.dumps(other))
            changed["pedestrian_route"] = [[12, -5], [12, 6]]
            with self.assertRaisesRegex(ValueError, "fixed pedestrian_route"):
                compare_constructions(pedestrian, changed, "stop_purpose")

    def test_all_five_declared_construction_comparisons(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            root = Path(d)
            path = self.sourced_site(root)
            proposals = {}
            for suffix in CASES:
                purpose = CASES[suffix][2]
                payload = (json.dumps({"source_kind": "original_observer_statement", "lead_stop_purpose": purpose}) + "\n").encode()
                (root / "stopped_purpose.txt").write_bytes(payload)
                site = json.loads(path.read_text())
                site["sources"]["stopped_purpose"]["sha256"] = hashlib.sha256(payload).hexdigest()
                path.write_text(json.dumps(site))
                proposals[ASSIGNMENT_ID + "__" + suffix] = construct(path, ASSIGNMENT_ID + "__" + suffix)
            plan = json.loads((Path(__file__).resolve().parents[1] / "case-plan.json").read_text())
            for comparison in plan["comparisons"]:
                left, right = [proposals[i] for i in comparison["case_ids"]]
                receipt = compare_constructions(left, right, comparison["comparison_id"])
                self.assertEqual(receipt["comparison_id"], comparison["comparison_id"])


if __name__ == "__main__":
    unittest.main()
