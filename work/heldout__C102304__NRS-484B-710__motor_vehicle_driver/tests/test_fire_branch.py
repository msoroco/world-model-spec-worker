import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "fire_branch.py"
spec = importlib.util.spec_from_file_location("fire_branch", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def box(x0, x1):
    return [(x0, -1), (x1, -1), (x1, 1), (x0, 1)]


class FireBranchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.participants = Path(self.temp.name) / "participants.jsonl"
        self.states = Path(self.temp.name) / "state.jsonl"
        self.context = {"alarm_response_source": "authored alarm dispatch premise",
                        "apparatus_answered_alarm": True,
                        "subject_authorized_emergency": False,
                        "subject_official_business": False}

    def write(self, gaps, states):
        rows = []
        for frame, gap in enumerate(gaps):
            x = 4 + gap / module._distance.FEET_PER_METRE
            rows.append({"frame": frame, "time_s": frame / 20,
                         "ego_id": "ego", "apparatus_id": "apparatus",
                         "ego_corners": box(0, 4), "apparatus_corners": box(x, x + 6)})
            states[frame].update(frame=frame, time_s=frame / 20)
        self.participants.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.states.write_text("".join(json.dumps(row) + "\n" for row in states))

    def state(self, moving=True, following=True, parked=False, apparatus=True):
        return {"apparatus_moving": apparatus, "ego_moving": moving,
                "ego_following": following, "ego_parked": parked,
                "warning_lamp": True, "siren": True}

    def test_traveling_boundary_and_full_frame_history(self):
        self.write([499, 500, 501], [self.state() for _ in range(3)])
        result = module.measure_branch(self.participants, self.states, 3,
                                       "traveling_follow", self.context)
        self.assertEqual(result["below_500_frames"], [0])
        self.assertEqual(result["active_frame_count"], 3)
        self.assertAlmostEqual(result["min_gap_ft"], 499)
        self.assertAlmostEqual(result["max_gap_ft"], 501)
        self.assertTrue(result["at_500_requires_tolerance_review"])

    def test_stopped_drive_and_park_are_distinct(self):
        self.write([550, 450, 450], [self.state(apparatus=False, following=False),
                                     self.state(apparatus=False, following=False),
                                     self.state(moving=False, following=False, parked=True, apparatus=False)])
        driving = module.measure_branch(self.participants, self.states, 3,
                                        "stopped_drive_to", self.context)
        parked = module.measure_branch(self.participants, self.states, 3,
                                       "stopped_park", self.context)
        self.assertEqual(driving["active_frame_count"], 1)
        self.assertEqual(parked["active_frame_count"], 1)
        self.assertEqual(driving["boundary_measurement"], "centre_distance_ft")
        self.assertEqual(parked["boundary_measurement"], "centre_distance_ft")
        self.assertGreater(driving["min_boundary_distance_ft"], driving["min_gap_ft"])
        self.assertFalse(driving["observations"][0]["branch_active"])
        self.assertTrue(driving["observations"][1]["branch_active"])
        self.assertFalse(driving["observations"][2]["branch_active"])
        self.assertFalse(parked["observations"][0]["branch_active"])
        self.assertTrue(parked["observations"][2]["branch_active"])

    def test_source_join_and_context_rejection(self):
        self.write([450], [self.state()])
        altered = json.loads(self.states.read_text())
        altered["time_s"] = 1
        self.states.write_text(json.dumps(altered) + "\n")
        with self.assertRaisesRegex(ValueError, "join failed"):
            module.measure_branch(self.participants, self.states, 1,
                                  "traveling_follow", self.context)
        altered["time_s"] = 0
        del altered["ego_following"]
        self.states.write_text(json.dumps(altered) + "\n")
        with self.assertRaisesRegex(ValueError, "participant state"):
            module.measure_branch(self.participants, self.states, 1,
                                  "traveling_follow", self.context)
        with self.assertRaisesRegex(ValueError, "context"):
            module.measure_branch(self.participants, self.states, 1,
                                  "traveling_follow", {})

    def test_stationary_apparatus_with_nonclosing_ego_is_not_drive_to(self):
        self.write([450, 450], [self.state(apparatus=False, following=False),
                                self.state(apparatus=False, following=False)])
        with self.assertRaisesRegex(ValueError, "no measured active frames"):
            module.measure_branch(self.participants, self.states, 2,
                                  "stopped_drive_to", self.context)

    def test_stopped_boundary_uses_centre_not_body_gap(self):
        self.write([550, 490], [self.state(apparatus=False, following=False),
                                self.state(apparatus=False, following=False)])
        result = module.measure_branch(self.participants, self.states, 2,
                                       "stopped_drive_to", self.context)
        self.assertLess(result["min_gap_ft"], 500)
        self.assertGreater(result["min_boundary_distance_ft"], 500)
        self.assertEqual(result["below_500_frames"], [])
        self.assertEqual(result["above_500_frames"], [1])

    def test_exception_is_sourced_context_not_inferred_from_lamps(self):
        self.write([450], [self.state()])
        self.context["subject_authorized_emergency"] = True
        self.context["subject_official_business"] = True
        result = module.measure_branch(self.participants, self.states, 1,
                                       "traveling_follow", self.context)
        self.assertTrue(result["exception_context"]["authorized_emergency"])
        self.assertTrue(result["exception_context"]["official_business"])
        self.assertEqual(result["below_500_frames"], [0])


if __name__ == "__main__":
    unittest.main()
