"""Exercise the actor interface and original trace contract without CARLA."""
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from native_runner import run, run_carla
from red_left_turn_controller import Observation
from tests.test_source_bound_scene import fixture
from tests.test_native_frame import Actor as FrameActor, World


class Actor:
    def __init__(self):
        self.controls = []

    def apply_control(self, control):
        self.controls.append(control)


class NativeRunnerTests(unittest.TestCase):
    def test_control_calls_and_source_join(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "site.json"
            packet.write_text(json.dumps(fixture(root)))
            actor = Actor()
            obs = [Observation(0, 4, 2, "steady_red_alone", False, False),
                   Observation(1, 1, 0, "steady_red_alone", True, False),
                   Observation(1.5, 1, 0, "steady_red_alone", True, False),
                   Observation(2, 1, 0, "steady_red_alone", False, False)]
            trace = root / "trace.jsonl"
            result = run(actor, obs, packet_path=packet,
                         case_suffix="stopped_leftmost_pedestrian_yield",
                         control_factory=lambda **kw: kw, output_path=trace)
            rows = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual(result["samples"], 4)
            self.assertEqual([row["requested_phase"] for row in rows],
                             ["approach", "stopping", "yielding", "turning"])
            self.assertEqual(len(actor.controls), 4)
            self.assertTrue(all(not row["physical_realization_claimed"] for row in rows))
            with self.assertRaisesRegex(ValueError, "retain the previous"):
                run(actor, obs, packet_path=packet,
                    case_suffix="stopped_leftmost_pedestrian_yield",
                    control_factory=lambda **kw: kw, output_path=trace)

    def test_empty_stream_and_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "site.json"
            packet.write_text(json.dumps(fixture(root)))
            trace = root / "trace.jsonl"
            with self.assertRaisesRegex(ValueError, "empty"):
                run(Actor(), [], packet_path=packet, case_suffix="stopped_leftmost_clear",
                    control_factory=lambda **kw: kw, output_path=trace)
            self.assertFalse(trace.exists())
            (root / "opendrive.txt").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "retained source missing or changed"):
                run(Actor(), [Observation(0, 1, 0, "steady_red_alone", False, False)],
                    packet_path=packet, case_suffix="stopped_leftmost_clear",
                    control_factory=lambda **kw: kw, output_path=trace)

    def test_native_world_frames_joined_to_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = fixture(root)
            packet["signal"]["native_actor_id"] = "9"
            path = root / "site.json"
            path.write_text(json.dumps(packet))
            class Ego(FrameActor):
                def __init__(self):
                    super().__init__(1)
                    self.controls = []
                def apply_control(self, control):
                    self.controls.append(control)
            ego = Ego()
            result = run_carla(World(), ego, FrameActor(9), [FrameActor(2)],
                               [FrameActor(3)], packet_path=path,
                               case_suffix="stopped_leftmost_clear", count=2,
                               observation_from_frame=lambda frame, scene:
                                   Observation(frame["time_s"], 1, 0, "steady_red_alone", False, False),
                               control_factory=lambda **kw: kw,
                               output_path=root / "native-trace.jsonl")
            rows = [json.loads(line) for line in (root / "native-trace.jsonl").read_text().splitlines()]
            self.assertEqual(result["samples"], 2)
            self.assertEqual(len(ego.controls), 2)
            self.assertTrue(all(row["original_sample_claim"] for row in rows))
            self.assertEqual(rows[0]["native_frame"]["pedestrians"][0]["actor_id"], "2")
            class GreenSignal(FrameActor):
                def get_state(self):
                    return "Green"
            with self.assertRaisesRegex(ValueError, "controller signal observation differs"):
                run_carla(World(), Ego(), GreenSignal(9), [], [], packet_path=path,
                          case_suffix="stopped_leftmost_clear", count=1,
                          observation_from_frame=lambda frame, scene:
                              Observation(frame["time_s"], 1, 0, "steady_red_alone", False, False),
                          control_factory=lambda **kw: kw,
                          output_path=root / "wrong-signal.jsonl")


if __name__ == "__main__":
    unittest.main()
