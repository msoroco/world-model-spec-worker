"""Check source-indication alternatives preserve controlled comparisons."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest

from audit_capture import audit as audit_capture
from branch_variants import RESPONSES, VARIANTS, check_pair, variant_request
from from_original import process as process_original
from runner import branch_actors, branch_indication, check as check_runner
from test_indication_actors import Carla, Walker


class BranchVariants(unittest.TestCase):
    def test_four_distinct_requests(self):
        cases = [variant_request(variant, response)
                 for variant in VARIANTS for response in RESPONSES]
        self.assertEqual(len({case["case_id"] for case in cases}), 4)
        for case in cases:
            self.assertEqual((case["frames"], case["rate_hz"], case["duration_s"]),
                             (600, 20, 30))
            self.assertEqual(len(case["cameras"]), 4)
            self.assertFalse(case["physical_acceptance_claimed"])
            self.assertTrue(check_runner(case["variant"] + "__" + case["requested_setting"])["passed"])

    def test_stopped_source_hand_signal_is_a_distinct_branch(self):
        first, second = check_pair("visible_driver_hand_signal")
        self.assertIsNotNone(first["source_driver_proxy"])
        self.assertIsNone(first["officer_actor"])
        self.assertGreater(first["emergency_motion_start_frame"],
                           first["source_driver_proxy"]["signal_frames"][1])
        self.assertNotEqual(first["ego_response_policy"], second["ego_response_policy"])

    def test_officer_direction_has_source_actor(self):
        first, second = check_pair("officer_directed_otherwise")
        self.assertIsNotNone(first["officer_actor"])
        self.assertIsNone(first["source_driver_proxy"])
        self.assertNotEqual(first["ego_response_policy"], second["ego_response_policy"])

    def test_unknown_variant_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown exact"):
            variant_request("unreviewed", RESPONSES[0])

    def test_fixed_source_mutation_rejected(self):
        first, second = check_pair("visible_driver_hand_signal")
        changed = copy.deepcopy(second)
        changed["source_driver_proxy"]["spawn_xyz_m"][0] += 1
        self.assertNotEqual(first["source_driver_proxy"], changed["source_driver_proxy"])

    def test_native_branch_actor_lifecycle(self):
        for variant in VARIANTS:
            item = variant_request(variant, RESPONSES[0])
            walkers = []
            def spawn(blueprint, pose):
                actor = Walker()
                actor.id = 100 + len(walkers)
                actor.hide_pose = lambda: actor.calls.append(("hide_pose", None))
                walkers.append(actor)
                return actor
            world = types.SimpleNamespace(
                get_blueprint_library=lambda: types.SimpleNamespace(find=lambda name: name),
                try_spawn_actor=spawn)
            source = types.SimpleNamespace(get_location=lambda: types.SimpleNamespace(x=15, y=5))
            built = branch_actors(Carla, world, item, source)
            self.assertEqual(len(built), 1)
            field = "source_driver_proxy" if variant == VARIANTS[0] else "officer_actor"
            self.assertEqual(branch_indication(Carla, item, built, 149), {})
            self.assertTrue(branch_indication(Carla, item, built, 150)[field]["native_bones_read_back"])
            self.assertTrue(branch_indication(Carla, item, built, 199)[field]["native_bones_read_back"])
            self.assertTrue(branch_indication(Carla, item, built, 200)[field]["pose_hidden"])
            self.assertEqual([call[0] for call in walkers[0].calls],
                             ["set_bones", "show_pose", "hide_pose"])

    def test_missing_native_pose_readback_rejected(self):
        item = variant_request(VARIANTS[0], RESPONSES[0])
        actor = Walker(drop_hand=True)
        actor.id = 101
        with self.assertRaisesRegex(ValueError, "bones absent"):
            branch_indication(Carla, item, {"source_driver_proxy": actor}, 150)

    def test_original_branch_capture_audit_checks_pose_and_stationarity(self):
        scratch_root = Path(__file__).resolve().parent.parents[2] / ".runtime-work"
        scratch_root.mkdir(exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="c405647-branch-capture-", dir=scratch_root))
        try:
            for variant in VARIANTS:
                condition = variant + "__" + RESPONSES[0]
                exact = variant_request(variant, RESPONSES[0])
                field = "source_driver_proxy" if variant == VARIANTS[0] else "officer_actor"
                (scratch / "native-request.json").write_text(json.dumps(exact) + "\n")
                (scratch / "scene.xodr").write_text(exact["source_map"] + "\n")
                digest = hashlib.sha256(exact["source_map"].encode()).hexdigest()
                (scratch / "native-map-readback.json").write_text(json.dumps({
                    "requested_map_sha256": digest, "original_opendrive_sha256": digest,
                    "initial_road_id": exact["road_id"]}) + "\n")
                (scratch / "native-capture-report.json").write_text(json.dumps({
                    "case_id": exact["case_id"], "frames": 600, "expected_frames": 600,
                    "error": None, "accepted": False, "restoration": {"restored": True}}) + "\n")
                body = [[-1, -1], [1, -1], [1, 1], [-1, 1]]
                rows, frames = [], []
                for index in range(600):
                    evidence = ({"native_bones_read_back": True, "native_actor_id": 101}
                                if 150 <= index <= 199 else
                                {"pose_hidden": True, "native_actor_id": 101}
                                if index == 200 else {})
                    actor = {"native_center_xy_m": [0, 0], "native_body_xy_m": body,
                             "native_speed_mps": 0.0}
                    rows.append({"frame": index, "native_frame": index + 30,
                                 "time_s": index / 20, "source_kind": "original_native_motion",
                                 "actors": {"ego": actor, "emergency": copy.deepcopy(actor)},
                                 "ego_brake_observed": 0.0, "ego_brake_request": 0.0,
                                 "lamp_request": True, "lamp_state_observed": True,
                                 "indication_native_readback": {field: evidence}})
                    frames.append({"video_frame": index, "native_frame": index + 30,
                                   "time_s": index / 20})
                actor_path = scratch / "observed-actors.jsonl"
                actor_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                (scratch / "video_frames.jsonl").write_text(
                    "".join(json.dumps(row) + "\n" for row in frames))
                self.assertEqual(audit_capture(scratch, condition)["sample_count"], 600)
                review = {"assignment_id": exact["assignment_id"],
                          "review_kind": "original_source_review",
                          "reviewer": "cpu_test_fixture_only",
                          "indication_actor_native_id": 101,
                          "frame_annotations": [
                              {"video_frame": index, "source_native_frame": index + 30,
                               "source_camera": "approach",
                               "emergency_flashing_visible": True,
                               "emergency_motion_visible": variant == VARIANTS[1] and index >= 150,
                               "hand_signal_visible": variant == VARIANTS[0] and 150 <= index <= 199,
                               "officer_direction_visible": variant == VARIANTS[1] and 150 <= index <= 199}
                              for index in range(600)]}
                if variant == VARIANTS[0]:
                    review.update({"source_driver_identity": "same_emergency_vehicle_driver",
                                   "source_driver_identity_source": "cpu_test_fixture_only",
                                   "hand_signal_source": "cpu_test_fixture_only"})
                else:
                    review.update({"officer_identity": "law_enforcement_officer",
                                   "officer_identity_source": "cpu_test_fixture_only",
                                   "officer_direction_source": "cpu_test_fixture_only",
                                   "officer_direction_present": True,
                                   "officer_direction_applies_to_ego": True})
                (scratch / "emergency_review.json").write_text(json.dumps(review) + "\n")
                self.assertEqual(process_original(scratch)["rows"], 600)
                (scratch / "approach_trace.jsonl").unlink()
                missing_review = copy.deepcopy(review)
                missing_review["indication_actor_native_id"] = 999
                (scratch / "emergency_review.json").write_text(json.dumps(missing_review) + "\n")
                with self.assertRaisesRegex(ValueError, "bind original Native actor"):
                    process_original(scratch)
                (scratch / "emergency_review.json").write_text(json.dumps(review) + "\n")
                missing_authority = copy.deepcopy(review)
                missing_authority.pop("source_driver_identity_source" if variant == VARIANTS[0]
                                      else "officer_identity_source")
                (scratch / "emergency_review.json").write_text(json.dumps(missing_authority) + "\n")
                with self.assertRaisesRegex(ValueError, "identity review missing|direction review missing"):
                    process_original(scratch)
                no_visible = copy.deepcopy(review)
                visibility_key = ("hand_signal_visible" if variant == VARIANTS[0]
                                  else "officer_direction_visible")
                for note in no_visible["frame_annotations"]:
                    note[visibility_key] = False
                (scratch / "emergency_review.json").write_text(json.dumps(no_visible) + "\n")
                with self.assertRaisesRegex(ValueError, "No frame-bound visible"):
                    process_original(scratch)
                (scratch / "emergency_review.json").write_text(json.dumps(review) + "\n")
                rows[175]["indication_native_readback"][field] = {}
                actor_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                with self.assertRaisesRegex(ValueError, "pose readback missing"):
                    audit_capture(scratch, condition)
                rows[175]["indication_native_readback"][field] = {
                    "native_bones_read_back": True, "native_actor_id": 101}
                rows[200]["indication_native_readback"][field] = {}
                actor_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                with self.assertRaisesRegex(ValueError, "pose was not hidden"):
                    audit_capture(scratch, condition)
                if field == "source_driver_proxy":
                    rows[200]["indication_native_readback"][field] = {
                        "pose_hidden": True, "native_actor_id": 101}
                    rows[175]["actors"]["emergency"]["native_speed_mps"] = 1.0
                    actor_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                    with self.assertRaisesRegex(ValueError, "source moved"):
                        audit_capture(scratch, condition)
        finally:
            shutil.rmtree(scratch)


if __name__ == "__main__":
    unittest.main()
