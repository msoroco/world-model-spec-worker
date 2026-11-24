"""Source-gate and delegation tests for the local Native CLI."""
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from live_entrypoint import run_native
from test_carla_scene_factory import API, World, packet
from saved_left_turn import ASSIGNMENT_ID


class LiveEntrypoint(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c109749-live-entrypoint-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.world = World()
        self.packet = packet(self.world)
        self.config = {
            "law_id": "NRS-484B-253", "cell_id": "C109749",
            "actor": "motor_vehicle_driver",
            "selected_case_id": ASSIGNMENT_ID + "__inside_yield",
            "rate_hz": 20, "duration_s": 45,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "controller": {"wait_for_initial_opponent": True, "signal_left": True,
                           "wait_for_later_opponent": None, "target_speed_mps": 5.0},
        }
        self.config_path = self.root / "config.json"
        self.map_path = self.root / "map.json"
        self.output = self.root / "attempt"

    def invoke(self):
        self.config_path.write_text(json.dumps(self.config) + "\n")
        self.map_path.write_text(json.dumps(self.packet) + "\n")
        client = types.SimpleNamespace(get_world=lambda: self.world)
        with mock.patch("live_capture.run", return_value={"physical_acceptance": "unverified"}) as run:
            result = run_native(self.config_path, self.map_path, self.output,
                                api=API, client=client)
        return result, run

    def test_delegates_exact_reviewed_case_to_live_orchestrator(self):
        result, runner = self.invoke()
        self.assertEqual(result["physical_acceptance"], "unverified")
        self.assertEqual(runner.call_count, 1)
        args = runner.call_args.kwargs
        self.assertEqual(args["map_path"], self.map_path)
        self.assertEqual(args["output"], self.output)
        self.assertTrue(callable(args["scene_factory"]))
        self.assertEqual(args["left_blinker_mask"], 1)

    def test_rejects_diagnostic_before_car_connection(self):
        self.packet["diagnostic_fixture"] = True
        with self.assertRaisesRegex(ValueError, "reviewed original"):
            self.invoke()

    def test_rejects_nonempty_attempt_before_car_connection(self):
        self.output.mkdir()
        (self.output / "old.txt").write_text("previous\n")
        with self.assertRaisesRegex(ValueError, "must be empty"):
            self.invoke()

    def test_rejects_reciprocal_before_car_connection(self):
        self.config["selected_case_id"] = ASSIGNMENT_ID + "__reciprocal_yield"
        self.config["controller"]["wait_for_later_opponent"] = True
        self.packet["later_opposing_route"] = list(self.packet["opposing_route"])
        with self.assertRaisesRegex(ValueError, "separately spawned later opponent"):
            self.invoke()


if __name__ == "__main__":
    unittest.main()
