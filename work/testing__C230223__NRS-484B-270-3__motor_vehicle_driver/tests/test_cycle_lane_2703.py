"""Synthetic CPU shape tests; no original recording or legal result is claimed."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
from cycle_lane_2703 import prepare, measure_original_frames, intersects
from cycle_lane_native import control
from runner import check_config, reviewed_packet


class CycleLane2703Tests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / ".runtime-work" / "c230223-owner"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = json.loads((FOLDER / "case-plan.json").read_text())
        self.site = {"source_kind": "original_reviewed", "assignment_id": self.plan["assignment_id"],
                     "map_id": "synthetic-test-map", "facility_id": "synthetic-test-lane",
                     "designation_authority": "test-only review field",
                     "facility_designated_for": "mixed_cycle", "facility_extent_source": "test polygon",
                     "facility_polygon": [[-1,-1],[3,-1],[3,1],[-1,1]],
                     "conflict_polygon": [[0,-1],[2,-1],[2,1],[0,1]],
                     "routes": {case["case_slug"]: {
                         "ego": [[-3,0],[1,0],[4,0]], "participant": [[-1,0],[1,0],[3,0]],
                         "junction_geometry_id": "synthetic junction"}
                         for case in self.plan["cases"]}}

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value) + "\n")
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def packets(self, case):
        site = self.write("site.json", self.site)
        participant = self.write("participant.json", {
            "source_kind": "original_reviewed", "road_user_kind": case["road_user_kind"],
            "actor_blueprint_id": "synthetic-test-blueprint", "identity_review": "test only",
            "body_measurement_method": "test vertices"})
        qualified = case["road_user_kind"] == "qualified_pedestrian"
        context = self.write("context.json", {"source_kind": "original_reviewed",
            "law_id": "NRS-484B-270-3", "exception_kind": case["exception_request"],
            "exception_source_review": "test only", "junction_kind": case["exception_request"].split("_")[0],
            "nrs_484b_297_6": {name: qualified for name in
                ("sidewalk_obstruction", "adjacent_strip_impassable",
                 "immediately_adjacent_highway", "near_side_route",
                 "return_when_practicable")}})
        return site + participant + context

    def test_each_exact_case_has_source_gated_construct(self):
        self.assertEqual(22, len(self.plan["cases"]))
        for case in self.plan["cases"]:
            with self.subTest(case=case["case_slug"]):
                packet = self.packets(case)
                result = prepare(case["case_id"], *packet)
                self.assertEqual(case["case_id"], result["case_id"])
                self.assertEqual(case["road_user_kind"], result["participant_kind"])
                self.assertIsNone(result["legal_verdict"])

    def test_rejects_stale_source_and_wrong_qualifier(self):
        case = self.plan["cases"][4]
        packet = list(self.packets(case))
        with self.assertRaisesRegex(ValueError, "changed"):
            prepare(case["case_id"], *(packet[:1] + ["0" * 64] + packet[2:]))
        value = json.loads(packet[4].read_text())
        value["nrs_484b_297_6"]["adjacent_strip_impassable"] = False
        packet[4:6] = self.write("context.json", value)
        with self.assertRaisesRegex(ValueError, "pedestrian statutory qualification"):
            prepare(case["case_id"], *packet)

    def test_polygon_crossing_not_center_only(self):
        a = [[-2,-0.1],[2,-0.1],[2,0.1],[-2,0.1]]
        b = [[-0.1,-2],[0.1,-2],[0.1,2],[-0.1,2]]
        self.assertTrue(intersects(a,b))

    def test_original_frame_measurement_recomputes_precedence(self):
        facility = [[-1,-1],[3,-1],[3,1],[-1,1]]
        conflict = [[0,-1],[2,-1],[2,1],[0,1]]
        def body(x):
            return [[x,-0.2],[x+0.2,-0.2],[x+0.2,0.2],[x,0.2]]
        rows = [{"frame": 1000+i, "time_s": i/20,
                 "ego_actor_id": 1, "participant_actor_id": 2,
                 "ego_body_polygon": body(-2 if i < 200 else 1),
                 "participant_body_polygon": body(-2 if i < 100 else 1)}
                for i in range(900)]
        report = measure_original_frames(rows,facility,conflict,1,2)
        self.assertEqual("participant_first",report["observed_precedence"])
        self.assertEqual(1100,report["participant_conflict_entry_frame"])
        self.assertEqual(1200,report["ego_conflict_entry_frame"])
        rows[3]["time_s"] += 0.1
        with self.assertRaisesRegex(ValueError, "frame join"):
            measure_original_frames(rows,facility,conflict,1,2)

    def test_controller_and_exact_config(self):
        cfg = json.loads((FOLDER / "config.json").read_text())
        self.assertTrue(check_config(cfg))
        request = control((-3,0),0,0,[[-3,0],[1,0],[4,0]])
        self.assertGreater(request["throttle"],0)
        self.assertEqual(1.0,control((-3,0),0,0,[[-3,0],[1,0]],hold=True)["brake"])
        self.assertTrue(control((-3,0),0,0,[[-3,0],[1,0]],park=True)["hand_brake"])
        cfg["duration_s"] = 10
        with self.assertRaisesRegex(ValueError,"config differs"):
            check_config(cfg)

    def test_independent_packet_hashes(self):
        case = self.plan["cases"][0]
        packet = self.packets(case)
        values = {name:{"path":path.name,"sha256":digest} for name,(path,digest) in
                  zip(("site","participant","context"),
                      ((packet[0],packet[1]),(packet[2],packet[3]),(packet[4],packet[5])))}
        path=self.root/"reviewed-packet.json"
        path.write_text(json.dumps({"format":"cycle-lane-2703-reviewed-packet-v1",
                                    "sources":values})+"\n")
        paths,hashes=reviewed_packet(path)
        self.assertEqual(set(values),set(paths))
        self.assertEqual(values["site"]["sha256"],hashes["site"])
        packet[0].write_text("{}\n")
        with self.assertRaisesRegex(ValueError,"changed"):
            reviewed_packet(path)


if __name__ == "__main__":
    unittest.main()
