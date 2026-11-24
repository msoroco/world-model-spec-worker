import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosswalk_measurements import ASSIGNMENT_ID
from native_crosswalk_world import run_sourced_world


class FakeWorld:
    def __init__(self, map_text, map_name="synthetic-map"):
        self.map_text = map_text
        self.map_name = map_name
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=.1)
        self.applied = []

    def get_map(self):
        return SimpleNamespace(name=self.map_name, to_opendrive=lambda: self.map_text)

    def get_settings(self):
        return copy.copy(self.settings)

    def apply_settings(self, value):
        self.settings = copy.copy(value)
        self.applied.append(copy.copy(value))


class NativeCrosswalkWorldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.root = Path(self.temp.name)
        self.map_text = "<OpenDRIVE><header name='synthetic'/></OpenDRIVE>"
        (self.root / "map.xodr").write_text(self.map_text)
        (self.root / "site.json").write_text(json.dumps({"site": "synthetic"}) + "\n")
        self.proposal = {"assignment_id": ASSIGNMENT_ID,
                         "case_id": ASSIGNMENT_ID + "__unmarked_pass",
                         "map_id": "synthetic-map",
                         "source": {"path": str(self.root / "site.json"),
                                    "sha256": hashlib.sha256((self.root / "site.json").read_bytes()).hexdigest()},
                         "source_inventory": {"map": {"path": "map.xodr",
                                                      "sha256": hashlib.sha256((self.root / "map.xodr").read_bytes()).hexdigest()}}}

    def tearDown(self):
        self.temp.cleanup()

    def test_matching_map_sets_and_restores_world_clock(self):
        world = FakeWorld(self.map_text)
        def capture(active):
            self.assertTrue(active.get_settings().synchronous_mode)
            self.assertEqual(active.get_settings().fixed_delta_seconds, .05)
            return {"tick_count": 900}
        result = run_sourced_world(world=world, proposal=self.proposal, capture=capture)
        self.assertEqual(result["capture_result"], {"tick_count": 900})
        self.assertEqual(result["map_sha256"], self.proposal["source_inventory"]["map"]["sha256"])
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertFalse(world.get_settings().synchronous_mode)
        self.assertEqual(world.get_settings().fixed_delta_seconds, .1)

    def test_capture_failure_still_restores_world(self):
        world = FakeWorld(self.map_text)
        def fail(_):
            raise RuntimeError("actor capture failed")
        with self.assertRaisesRegex(RuntimeError, "actor capture failed"):
            run_sourced_world(world=world, proposal=self.proposal, capture=fail)
        self.assertFalse(world.get_settings().synchronous_mode)

    def test_mismatched_loaded_map_or_changed_source_rejected_before_capture(self):
        called = []
        def capture(_):
            called.append(True)
        with self.assertRaisesRegex(ValueError, "loaded Native map"):
            run_sourced_world(world=FakeWorld("<different/>"), proposal=self.proposal, capture=capture)
        (self.root / "map.xodr").write_text("changed source")
        with self.assertRaisesRegex(ValueError, "original map source changed"):
            run_sourced_world(world=FakeWorld(self.map_text), proposal=self.proposal, capture=capture)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
