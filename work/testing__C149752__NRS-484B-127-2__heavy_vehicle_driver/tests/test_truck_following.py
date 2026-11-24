import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("truck_following", ROOT / "truck_following.py")
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def frame(index, gap_m=152.4, phase="following", lanes=1, widths=(2.1, 2.1)):
    subject = {"identity": "subject", "vehicle_class": "truck", "route_vertex_s_m": [0, 1, 2, 3, 4, 5, 6, 7],
               "overall_width_m": widths[0], "mesh_width_verified": True}
    lead_start = 7 + gap_m
    lead = {"identity": "lead", "vehicle_class": "truck", "route_vertex_s_m": [lead_start + j for j in range(8)],
            "overall_width_m": widths[1], "mesh_width_verified": True}
    return {"frame": index, "time_s": index / 20, "bodies": [subject, lead],
            "lane_source": {"source_kind": "native_map_readback", "highway_public": True,
                            "available_same_direction_lanes": lanes,
                            "driving_lanes": [{"lane_id": f"same-{j}", "direction_dot": 1.0,
                                               "available": True, "connected": True} for j in range(lanes)] +
                                             [{"lane_id": "opposing", "direction_dot": -1.0,
                                               "available": True, "connected": True}]}, "pass_phase": phase}


class TruckFollowingTest(unittest.TestCase):
    def test_comparison_audit_rejects_missing_source_and_fixed_drift(self):
        base = {"case_id": "a", "original_source_sha256": "a" * 64, "original_frame_count": 900,
                "legal_judgment": "unresolved", "subject_width_min_m": 2.1,
                "same_direction_available_lane_count_min": 1, "steady_gap_min_m": 145.0}
        other = dict(base, case_id="b", original_source_sha256="b" * 64, steady_gap_min_m=160.0)
        proof = module.audit_comparison(base, other, fixed_fields=("subject_width_min_m", "same_direction_available_lane_count_min"),
                                        varied_field="steady_gap_min_m")
        self.assertEqual(proof["varied_field_checked"], "steady_gap_min_m")
        with self.assertRaisesRegex(module.EvidenceError, "fixed condition drift"):
            module.audit_comparison(base, dict(other, subject_width_min_m=1.9),
                                    fixed_fields=("subject_width_min_m",), varied_field="steady_gap_min_m")
        with self.assertRaisesRegex(module.EvidenceError, "source seal required"):
            module.audit_comparison(base, dict(other, original_source_sha256=""),
                                    fixed_fields=("subject_width_min_m",), varied_field="steady_gap_min_m")

    def test_adapter_receives_spawn_follow_pass_and_entry_calls(self):
        class Adapter:
            def __init__(self):
                self.calls = []
            def spawn_vehicle(self, spec, blueprint):
                self.calls.append(("spawn", spec["identity"], blueprint))
                return spec["identity"]
            def configure_following(self, subject, lead, control):
                self.calls.append(("follow", subject, lead, control["gap_target_m"]))
            def configure_pass_phase(self, subject, lead, time_s):
                self.calls.append(("pass", subject, lead, time_s))
            def spawn_entrant(self, blueprint, time_s):
                self.calls.append(("entrant", blueprint, time_s))
                return "entrant"
        lane = {"source_kind": "native_map_readback", "highway_public": True,
                "available_same_direction_lanes": 1, "straight_connected_route": True, "opposing_pass_lane": True,
                "driving_lanes": [{"lane_id": "one", "available": True, "connected": True, "direction_dot": 1.0}]}
        blue = {"source_kind": "native_blueprint_readback", "subject_overall_width_m": 2.1,
                "lead_overall_width_m": 2.1, "subject_vehicle_class": "truck", "lead_vehicle_class": "truck",
                "subject_blueprint_id": "subject-truck", "lead_blueprint_id": "lead-truck", "entrant_blueprint_id": "car"}
        adapter = Adapter()
        result = module.execute_case(adapter, module.CASES[3], lane, blue)
        self.assertEqual(result["capture_frames"], 900)
        self.assertEqual([c[0] for c in adapter.calls], ["spawn", "spawn", "follow", "pass"])
        adapter = Adapter()
        result = module.execute_case(adapter, module.CASES[4], lane, blue)
        self.assertEqual(result["entrant"], "entrant")
        self.assertEqual([c[0] for c in adapter.calls], ["spawn", "spawn", "follow", "entrant"])

    def test_owned_trucks_are_destroyed_when_pass_controller_fails(self):
        class Adapter:
            def __init__(self):
                self.destroyed = []
            def spawn_vehicle(self, spec, blueprint):
                return spec['identity']
            def configure_following(self, subject, lead, control):
                pass
            def configure_pass_phase(self, subject, lead, time_s):
                raise RuntimeError('controller failed')
            def destroy(self, actor):
                self.destroyed.append(actor)
        lane = {"source_kind": "native_map_readback", "highway_public": True,
                "available_same_direction_lanes": 1, "straight_connected_route": True,
                "opposing_pass_lane": True,
                "driving_lanes": [{"lane_id": "one", "available": True,
                                   "connected": True, "direction_dot": 1.0}]}
        blue = {"source_kind": "native_blueprint_readback", "subject_overall_width_m": 2.1,
                "lead_overall_width_m": 2.1, "subject_vehicle_class": "truck",
                "lead_vehicle_class": "truck", "subject_blueprint_id": "subject-truck",
                "lead_blueprint_id": "lead-truck"}
        adapter = Adapter()
        with self.assertRaisesRegex(RuntimeError, 'controller failed'):
            module.execute_case(adapter, module.CASES[3], lane, blue)
        self.assertEqual(adapter.destroyed, ['lead', 'subject'])

    def test_case_construction_requires_map_and_measured_blueprints(self):
        case = module.CASES[0]
        lane = {"source_kind": "native_map_readback", "highway_public": True,
                "available_same_direction_lanes": 1, "straight_connected_route": True,
                "driving_lanes": [{"lane_id": "one", "available": True, "connected": True, "direction_dot": 1.0}]}
        blue = {"source_kind": "native_blueprint_readback", "subject_overall_width_m": 2.1,
                "lead_overall_width_m": 2.1, "subject_vehicle_class": "truck", "lead_vehicle_class": "truck",
                "subject_blueprint_id": "subject-truck", "lead_blueprint_id": "lead-truck"}
        plan = module.planned_construction(case, lane, blue)
        self.assertEqual(plan["recording"], {"fps": 20, "frames": 900, "camera_count": 4})
        with self.assertRaisesRegex(module.EvidenceError, "lane count mismatch"):
            module.planned_construction(case, dict(lane, available_same_direction_lanes=2), blue)
        with self.assertRaisesRegex(module.EvidenceError, "width target mismatch"):
            module.planned_construction(case, lane, dict(blue, lead_overall_width_m=1.8))
        passing = module.CASES[3]
        with self.assertRaisesRegex(module.EvidenceError, "passing lane source"):
            module.planned_construction(passing, lane, blue)
        self.assertEqual(module.planned_construction(passing, dict(lane, opposing_pass_lane=True), blue)["physical_risk"]["status"], "physical")

    def test_original_frames_measure_without_legal_verdict(self):
        packet = {"source_kind": "sealed_native_original_frames", "case_id": "case-a",
                  "frames": [frame(i) for i in range(900)]}
        result = module.audit_original_frames(packet, case_id="case-a")
        self.assertAlmostEqual(result["steady_gap_min_ft"], 500, places=5)
        self.assertEqual(result["legal_judgment"], "unresolved")
        self.assertFalse(result["subject_pass_completed"])
        packet["frames"][480]["bodies"].append({"identity": "passing-car", "route_vertex_s_m": [20 + i for i in range(8)]})
        self.assertEqual(module.audit_original_frames(packet, case_id="case-a")["entered_gap_distinct_vehicle_count"], 1)
        packet["frames"][500]["pass_phase"] = "opposing"
        packet["frames"][600]["pass_phase"] = "ahead"
        packet["frames"][700]["pass_phase"] = "returned"
        self.assertTrue(module.audit_original_frames(packet, case_id="case-a")["subject_pass_completed"])
        packet["frames"][600]["pass_phase"] = "following"
        self.assertFalse(module.audit_original_frames(packet, case_id="case-a")["subject_pass_completed"])

    def test_original_capture_can_start_at_live_world_frame_and_time(self):
        packet = {"source_kind": "sealed_native_original_frames", "case_id": "case-a",
                  "frames": [frame(i) for i in range(900)]}
        for row in packet["frames"]:
            row["frame"] += 1000
            row["time_s"] += 65.25
        result = module.audit_original_frames(packet, case_id="case-a")
        self.assertEqual(result["first_original_frame"], 1000)
        self.assertAlmostEqual(result["first_original_time_s"], 65.25)
        self.assertAlmostEqual(result["steady_gap_min_ft"], 500, places=5)
        packet["frames"][200]["time_s"] += .02
        with self.assertRaisesRegex(module.EvidenceError, "20 Hz time mapping"):
            module.audit_original_frames(packet, case_id="case-a")

    def test_missing_original_frame_or_mesh_rejected(self):
        packet = {"source_kind": "sealed_native_original_frames", "case_id": "case-a",
                  "frames": [frame(i) for i in range(900)]}
        packet["frames"][100]["frame"] = 101
        with self.assertRaisesRegex(module.EvidenceError, "frame index"):
            module.audit_original_frames(packet, case_id="case-a")
        packet["frames"][100]["frame"] = 100
        packet["frames"][100]["bodies"][1]["mesh_width_verified"] = False
        with self.assertRaisesRegex(module.EvidenceError, "mesh width"):
            module.audit_original_frames(packet, case_id="case-a")
        packet["frames"][100]["bodies"][1]["mesh_width_verified"] = True
        packet["frames"][100]["lane_source"]["available_same_direction_lanes"] = 2
        with self.assertRaisesRegex(module.EvidenceError, "lane count disagrees"):
            module.audit_original_frames(packet, case_id="case-a")

    def test_byte_seal_and_case_binding(self):
        packet = {"source_kind": "sealed_native_original_frames", "case_id": "case-a", "frames": [frame(i) for i in range(900)]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "original.json"
            raw = json.dumps(packet).encode()
            path.write_bytes(raw)
            seal = {"source_sha256": hashlib.sha256(raw).hexdigest(), "case_id": "case-a", "frame_count": 900}
            self.assertEqual(module.audit_sealed_capture(path, seal, "case-a")["original_frame_count"], 900)
            with self.assertRaisesRegex(module.EvidenceError, "source hash mismatch"):
                module.audit_sealed_capture(path, dict(seal, source_sha256="0" * 64), "case-a")
            with self.assertRaisesRegex(module.EvidenceError, "seal case mismatch"):
                module.audit_sealed_capture(path, dict(seal, case_id="other"), "case-a")


if __name__ == "__main__":
    unittest.main()
