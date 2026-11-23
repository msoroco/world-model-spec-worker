import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from saved_conditions import measure, seal


def rows():
    return [{"frame": 200 + index, "time_s": index * .05,
             "source_frame": 200 + index,
             "ego_speed_mps": 8 + index,
             "leader_gap_m": 30 - index,
             "highway_width_m": 8.0,
             "roadway_driving_width_m": 7.0,
             "shoulder_width_m": 1.0,
             "mapped_width_scope": "OpenDRIVE lane cross section; statutory highway boundary unverified",
             "surface_wetness": .2,
             "precipitation_strength": 20,
             "fog_density": 10,
             "tire_friction": 1.0,
             "source_ids": {"ego_actor_id": 1, "leader_actor_id": 2,
                            "road_id": 42, "lane_id": -1,
                            "opendrive_sha256": "a" * 64}}
            for index in range(4)]


class SavedConditionsTests(unittest.TestCase):
    def test_sealed_original_history_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            seal(attempt, "exact-case", rows())
            result = measure(attempt, "exact-case")
            self.assertEqual(result["summary"]["ego_speed_mps"]["mean"], 9.5)
            self.assertEqual(result["summary"]["leader_gap_m"]["minimum"], 27)
            self.assertEqual(len(result["full_history"]), 4)
            self.assertEqual(result["legal_judgment"], "unresolved")

    def test_changed_original_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            seal(attempt, "exact-case", rows())
            with (attempt / "original-conditions.jsonl").open("a") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                measure(attempt, "exact-case")

    def test_stale_case_and_broken_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            sample = rows()
            sample[2]["source_frame"] = 999
            seal(attempt, "exact-case", sample)
            with self.assertRaisesRegex(ValueError, "identity differs"):
                measure(attempt, "other-case")
            with self.assertRaisesRegex(ValueError, "source frame join"):
                measure(attempt, "exact-case")

    def test_noncontiguous_time_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            sample = rows()
            sample[2]["time_s"] = .2
            seal(attempt, "exact-case", sample)
            with self.assertRaisesRegex(ValueError, "contiguous at 20 Hz"):
                measure(attempt, "exact-case")

    def test_changed_map_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            sample = rows()
            sample[-1]["source_ids"] = {**sample[-1]["source_ids"], "opendrive_sha256": "b" * 64}
            seal(attempt, "exact-case", sample)
            with self.assertRaisesRegex(ValueError, "source changed"):
                measure(attempt, "exact-case")

    def test_mapped_width_cannot_omit_driving_or_shoulder(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            sample = rows()
            sample[1]["shoulder_width_m"] = 2.0
            seal(attempt, "exact-case", sample)
            with self.assertRaisesRegex(ValueError, "mapped width components"):
                measure(attempt, "exact-case")


if __name__ == "__main__":
    unittest.main()
