"""Verify construction isolation and source failures for the traffic sweep."""
import copy
import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from build_traffic_effect_sweep import GAPS, SOURCE, construct  # noqa: E402


class TrafficEffectSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = [json.loads(line) for line in
                      (SOURCE / "native-actors.jsonl").read_text().splitlines()]

    def test_setting_changes_only_follower_history(self):
        histories = [construct(self.source, gap) for gap in GAPS]
        self.assertEqual([len(rows) for rows in histories], [600] * 3)
        changed = {"following_x_m", "following_speed_mps",
                   "following_velocity_xyz_mps", "following_gap_m",
                   "sweep_source_kind", "follower_brake_gap_setting_m"}
        for index, source in enumerate(self.source):
            for rows in histories:
                self.assertEqual({k: v for k, v in rows[index].items() if k not in changed},
                                 {k: v for k, v in source.items() if k not in changed})
        self.assertEqual(len({rows[599]["following_x_m"] for rows in histories}), 3)

    def test_rejects_unreviewed_setting_and_bad_source(self):
        with self.assertRaisesRegex(ValueError, "Unreviewed engineering gap"):
            construct(self.source, 4.0)
        damaged = copy.deepcopy(self.source)
        damaged[1]["source_kind"] = "original_carla_actor_and_map_readback"
        with self.assertRaisesRegex(ValueError, "source-labeled"):
            construct(damaged, GAPS[0])
        damaged = copy.deepcopy(self.source)
        damaged[20]["ego_x_m"] = damaged[19]["ego_x_m"] - 1
        with self.assertRaisesRegex(ValueError, "Ego route reverses"):
            construct(damaged, GAPS[0])


if __name__ == "__main__":
    unittest.main()
