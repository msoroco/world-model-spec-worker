import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

FOLDER = Path(__file__).resolve().parents[2]
SOURCE = FOLDER / "native/compare_preparing.py"
SPEC = importlib.util.spec_from_file_location("compare_preparing", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
compare = MODULE.compare
SCRATCH = FOLDER.parents[1] / ".runtime-work" / "c405647-tests"
MOVEMENT = FOLDER / "preparing-fixture-sources/visible_vehicle_movement/preparing_observations.jsonl"
HAND = FOLDER / "preparing-fixture-sources/visible_driver_hand_signal/preparing_observations.jsonl"
MOVING = FOLDER / "selected-fixture-sources/a/emergency_observations.jsonl"


class PreparingComparisonTest(unittest.TestCase):
    def test_both_pairs_fix_context_and_start_geometry(self):
        for pair, left, right in (
                ("moving_vs_visible_movement", MOVING, MOVEMENT),
                ("movement_vs_hand_signal", MOVEMENT, HAND)):
            receipt = compare(pair, left, right)
            self.assertEqual(receipt["joined_frames"], 600)
            self.assertTrue(receipt["fixed_geometry_verified"])
            self.assertTrue(receipt["fixture_only"])
            self.assertFalse(receipt["physical_completion_claimed"])

    def test_changed_original_context_is_rejected(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            rows = [json.loads(line) for line in HAND.read_text().splitlines()]
            rows[200]["weather_context_source_id"] = "changed"
            path = Path(temporary) / "changed.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "fixed road/weather/officer"):
                compare("movement_vs_hand_signal", MOVEMENT, path)


if __name__ == "__main__":
    unittest.main()
