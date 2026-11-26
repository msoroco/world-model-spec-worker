"""Offline construction tests for passenger and cargo door-duration schedules."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from door_actuation import apply_door_command, command, validate_setup
from runner import check


class DoorNativeOfflineTest(unittest.TestCase):
    def test_exact_configuration_and_full_schedule(self):
        config = json.loads(Path("config.json").read_text())
        self.assertEqual(check(config)["frames"], 600)
        schedule = config["schedule"]
        commands = [command(schedule, frame) for frame in range(600)]
        self.assertEqual(sum(row["door_command"] == "open" for row in commands),
                         112 if schedule.endswith("closes_after_transfer") else 300)
        self.assertTrue(all(row["observed_door_open"] is None for row in commands))

    def test_missing_original_observation_remains_missing(self):
        config = json.loads(Path("config.json").read_text())
        config["door_state_observed_by_command"] = True
        with self.assertRaisesRegex(ValueError, "Command cannot establish"):
            check(config)

    def test_actuator_calls_only_at_exact_transitions(self):
        class Vehicle:
            def __init__(self):
                self.calls = []

            def open_door(self, door):
                self.calls.append(("open", door))

            def close_door(self, door):
                self.calls.append(("closed", door))

        config = json.loads(Path("config.json").read_text())
        vehicle = Vehicle()
        for frame in range(600):
            apply_door_command(vehicle, "FL", config["schedule"], frame)
        self.assertEqual(vehicle.calls, [("closed", "FL"),
                                         ("open", "FL"), ("closed", "FL")])

    def test_source_bound_setup_rejects_wrong_side(self):
        config = json.loads(Path("config.json").read_text())
        root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
        self.assertTrue(root and ".runtime-work" in root)
        Path(root).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temporary:
            folder = Path(temporary)
            def ref(name, value):
                path = folder / name
                path.write_text(json.dumps(value) + "\n")
                return {"path": str(path),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            source = {"source_kind": "source_bound_native_setup",
                      "sources": {
                          "map": ref("map.json", {"map_name": "Town03"}),
                          "road": ref("road.json", {"map_name": "Town03",
                              "frozen_cell": config["frozen_cell"],
                              "door_side": "left", "passing_side": "left"}),
                          "transfer": ref("transfer.json", {"kind": config.get("transfer_kind", "passenger"),
                              "frame": 200, "cargo_actor_id": "cargo-4"})},
                      "native_setup": {"ego_spawn_index": 0,
                                       "passing_spawn_index": 1,
                                       "walker_spawn_index": 2, "door": "FL"}}
            self.assertEqual(validate_setup(source, config["schedule"])["door_side"],
                             "left")
            source["native_setup"]["door"] = "FR"
            with self.assertRaisesRegex(ValueError, "Native door differs"):
                validate_setup(source, config["schedule"])


if __name__ == "__main__":
    unittest.main()
