import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from selected_analysis import measure_original_sight
from sight_measurement import ASSIGNMENT, DIRECTIONS, STATIONS_M


class SelectedAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.case = ASSIGNMENT + "__distance_reference"
        frames = [{"frame": n + 10, "time_s": n / 20} for n in range(900)]
        motion = [dict(row, yaw_deg=0 if n < 101 else 180,
                       turn_active=n in (100, 101)) for n, row in enumerate(frames)]
        rays = []
        for row in frames[100:102]:
            for direction in DIRECTIONS:
                for station in STATIONS_M:
                    blocked = direction == "ahead_opposing" and station == 152.4
                    rays.append({"frame": row["frame"], "time_s": row["time_s"],
                                 "direction": direction, "station_distance_m": station,
                                 "observer_height_m": 1.4,
                                 "observer_lane_source": "diagnostic lane",
                                 "target_vehicle_id": "diagnostic-ego",
                                 "body_point_clear": [not blocked] * 9,
                                 "terrain_hit_id": "diagnostic-hill" if blocked else None})
        packets = {
            "frame_map": {"frames": frames},
            "ego_motion": {"case_id": self.case, "source_kind": "original_native",
                           "samples": motion},
            "sight_rays": {"case_id": self.case, "source_kind": "original_native",
                           "samples": rays},
            "road_geometry": {"source_kind": "original_native_geometry",
                              "highway_source": "diagnostic road",
                              "location_kind": "curve", "ego_vehicle_id": "diagnostic-ego"},
        }
        inventory = {"case_id": self.case, "source_kind": "original_native",
                     "sources": {}}
        for name, packet in packets.items():
            path = self.root / (name + ".json")
            path.write_text(json.dumps(packet))
            inventory["sources"][name] = {"path": path.name,
                                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        (self.root / "inventory.json").write_text(json.dumps(inventory))

    def test_source_shaped_positive_has_specific_measurements(self):
        report = measure_original_sight(self.root, self.case)
        values = {key: row["value"] for key, row in report["measurements"].items()}
        self.assertEqual(values["heading_change_deg"], 180)
        self.assertEqual(values["turn_frame_count"], 2)
        self.assertEqual(values["opposing_blocked_ray_count"], 2)
        self.assertEqual(values["following_blocked_ray_count"], 0)
        self.assertEqual(values["two_direction_ray_count"], 20)
        self.assertEqual(report["original_sight"]["driver_visibility_judgment"], "unresolved")
        contract = json.loads((PACKAGE / "selected-measurement-contract.draft.json").read_text())
        plan = json.loads((PACKAGE / "case-plan.json").read_text())
        self.assertEqual({r["disposition_index"] for r in contract["requirements"]},
                         set(range(len(plan["requirement_dispositions"]))))
        for row in contract["requirements"]:
            item = report["measurements"][row["output_key"]]
            self.assertEqual(item["method"], row["method"])
            self.assertEqual(set(item["sources"]), set(row["inputs"]))
            for source, digest in item["sources"].items():
                self.assertEqual(hashlib.sha256((self.root / source).read_bytes()).hexdigest(), digest)

    def test_missing_case_source_and_stale_packet_fail(self):
        (self.root / "sight_rays.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: sight_rays.json"):
            measure_original_sight(self.root, self.case)
        (self.root / "sight_rays.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "original sight source hash mismatch"):
            measure_original_sight(self.root, self.case)

    def test_cli_emits_canonical_native_result_with_unverified_physics(self):
        construction = json.loads((PACKAGE / "construction-distance_reference.json").read_text())
        self.assertEqual(construction["case_id"], self.case)
        (self.root / "construction.json").write_text(json.dumps(construction))
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        (self.root / "config.json").write_text(json.dumps(config))
        repository = PACKAGE.parents[1]
        runtime = repository / "runtime" / "scenario_pipeline"
        env = dict(os.environ)
        env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(repository / ".runtime-work" /
                                                    "c129731-selected-analysis-test-output")
        env["PYTHONPATH"] = os.pathsep.join((str(runtime), str(PACKAGE),
                                              env.get("PYTHONPATH", "")))
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        output = self.root / "analysis-report.json"
        subprocess.run([sys.executable, str(PACKAGE / "selected_analysis.py"),
                        "--attempt", str(self.root), "--output", str(output)],
                       env=env, check=True, capture_output=True, text=True)
        result = json.loads((self.root / "result.json").read_text())
        report = json.loads(output.read_text())
        self.assertEqual(result["case_id"], self.case)
        self.assertEqual(result["measured_values"]["heading_change_deg"], 180)
        self.assertFalse(result["maneuver_completed"])
        self.assertEqual(result["physical_checks"]["maneuver"]["status"], "unverified")
        self.assertIn("measurements", report)


if __name__ == "__main__":
    unittest.main()
