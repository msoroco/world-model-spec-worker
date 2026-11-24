import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("saved_comparison_audit", HERE / "saved_comparison_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.roots = [Path(self.temporary.name) / name for name in ("left", "right")]
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.pair = next(row["case_ids"] for row in plan["comparisons"]
                         if row["comparison_id"] == "unmarked_overtake")
        self.recomputed = []
        for index, root in enumerate(self.roots):
            root.mkdir()
            for name in ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json"):
                (root / name).write_text("{}\n")
            measured = {"frame_count": 900, "crosswalk_kind": "unmarked",
                        "stopped_vehicle_purpose_claim": "permit_pedestrian",
                        "rear_approach_frames": [100], "lead_stopped_frames": [200],
                        "pedestrian_crosswalk_frames": [400],
                        "ego_ahead_frames": [] if index == 0 else [800]}
            media = {"videos": {name: {"frames": 900} for name in
                                ("overview", "approach", "reference_corner", "driver_reference")}}
            context = {"map_sha256": "a" * 64, "junction_kind": "road_intersection",
                       "layout": "intersection", "road_axis": {"origin": [0, 0], "forward": [1, 0]},
                       "crosswalk": {"kind": "unmarked", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]},
                       "stopped_vehicle_purpose": {"claim": "permit_pedestrian", "source_ref": "observer"}}
            trace = [{"lead_center": [5, 0], "pedestrian_center": [7, 0]}]
            self.recomputed.append((measured, media, context, trace))
            report = {"assignment_id": module.ASSIGNMENT_ID, "case_id": self.pair[index],
                      "physical_acceptance": "unverified", "legal_verdict_claimed": False,
                      "measured_values": measured, "media": media,
                      "observed": {"rear_approach_sampled": True, "lead_stop_sampled": True,
                                   "pedestrian_in_polygon_sampled": True,
                                   "ego_full_pass_sampled": index == 1},
                      "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                        for name in ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json")}}
            (root / "crosswalk-measurement.json").write_text(json.dumps(report) + "\n")

    def test_exact_saved_pair_and_changed_fixed_source(self):
        with patch.object(module, "_recompute", side_effect=self.recomputed):
            result = module.audit(left_dir=self.roots[0], right_dir=self.roots[1],
                                  comparison_id="unmarked_overtake")
        self.assertEqual(result["case_ids"], self.pair)
        self.assertEqual(result["declared_difference"], "ego_full_pass")
        self.assertEqual(result["physical_acceptance"], "unverified")
        self.assertTrue(module._close_xy([5, 0], [5.2, 0]))
        self.assertFalse(module._close_xy([5, 0], [5.3, 0]))
        changed = list(self.recomputed)
        m, v, c, trace = changed[1]
        changed[1] = (m, v, c, [{"lead_center": [6, 0], "pedestrian_center": [7, 0]}])
        with patch.object(module, "_recompute", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "lead or pedestrian trajectory"):
                module.audit(left_dir=self.roots[0], right_dir=self.roots[1],
                             comparison_id="unmarked_overtake")

    def test_rejects_stale_saved_report_and_wrong_difference(self):
        (self.roots[1] / "trace.jsonl").write_text("changed\n")
        with patch.object(module, "_recompute", side_effect=self.recomputed):
            with self.assertRaisesRegex(ValueError, "original source hash differs"):
                module.audit(left_dir=self.roots[0], right_dir=self.roots[1],
                             comparison_id="unmarked_overtake")
        (self.roots[1] / "trace.jsonl").write_text("{}\n")
        changed = list(self.recomputed)
        m, v, c, trace = changed[1]
        changed[1] = ({**m, "ego_ahead_frames": []}, v, c, trace)
        with patch.object(module, "_recompute", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "saved report differs"):
                module.audit(left_dir=self.roots[0], right_dir=self.roots[1],
                             comparison_id="unmarked_overtake")


if __name__ == "__main__":
    unittest.main()
