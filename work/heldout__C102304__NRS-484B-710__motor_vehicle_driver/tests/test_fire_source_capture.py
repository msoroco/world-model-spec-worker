import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fire_source_capture", root / "fire_source_capture.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def vector(x, y, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


class Actor:
    def __init__(self, actor_id, x, direction, speed, parked=False):
        self.id, self.x, self.direction, self.speed, self.parked = actor_id, x, direction, speed, parked
        self.bounding_box = SimpleNamespace(get_world_vertices=self.vertices)

    def vertices(self, _):
        return [vector(self.x + dx, dy, z) for dx in (-2, 2)
                for dy in (-1, 1) for z in (0, 1)]

    def get_transform(self):
        return SimpleNamespace(location=vector(self.x, 0),
                               get_forward_vector=lambda: vector(self.direction, 0))

    def get_velocity(self):
        return vector(self.direction * self.speed, 0)

    def get_control(self):
        return SimpleNamespace(hand_brake=self.parked)


class SourceCaptureTests(unittest.TestCase):
    def test_original_sources_feed_existing_measurers_in_both_directions(self):
        branch_spec = importlib.util.spec_from_file_location("fire_branch", root / "fire_branch.py")
        branch = importlib.util.module_from_spec(branch_spec)
        branch_spec.loader.exec_module(branch)
        context = {"alarm_response_source": "test-sourced-alarm-context",
                   "apparatus_answered_alarm": True,
                   "subject_authorized_emergency": False,
                   "subject_official_business": False}
        for direction in (1, -1):
            with self.subTest(direction=direction), tempfile.TemporaryDirectory() as temp:
                ego, apparatus = Actor(1, 0, direction, 6), Actor(2, direction * 150, direction, 0)
                with module.FireSourceRecorder(temp, ego, apparatus) as recorder:
                    for frame in (10, 11):
                        recorder.append(frame, frame / 20, warning_lamp_readback=True,
                                        siren_readback=True)
                        ego.x += direction
                result = branch.measure_branch(Path(temp) / "participant_footprints.jsonl",
                                               Path(temp) / "participant_state.jsonl", 2,
                                               "stopped_drive_to", context)
                self.assertEqual(result["active_frame_count"], 1)
                self.assertEqual(result["boundary_measurement"], "centre_distance_ft")
                self.assertEqual(len(json.loads((Path(temp) / "participant_footprints.jsonl").read_text().splitlines()[0])["ego_corners"]), 4)

    def test_rejects_missing_readback_and_frame_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            ego, apparatus = Actor(1, 0, 1, 6), Actor(2, 150, 1, 0)
            with module.FireSourceRecorder(temp, ego, apparatus) as recorder:
                with self.assertRaisesRegex(ValueError, "explicit readbacks"):
                    recorder.append(10, .5, warning_lamp_readback=None, siren_readback=True)
                recorder.append(10, .5, warning_lamp_readback=True, siren_readback=True)
                with self.assertRaisesRegex(ValueError, "frame/time"):
                    recorder.append(12, .6, warning_lamp_readback=True, siren_readback=True)


if __name__ == "__main__":
    unittest.main()
