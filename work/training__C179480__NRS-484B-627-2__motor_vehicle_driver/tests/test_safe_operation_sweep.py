"""Check physical geometry isolation for the hazard-gap CPU sweep."""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from build_safe_operation_sweep import GAPS, SOURCE, construct  # noqa: E402


class SafeOperationSweepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = [json.loads(line) for line in
                      (SOURCE/'native-actors.jsonl').read_text().splitlines()]

    def test_only_hazard_geometry_changes(self):
        histories = [construct(self.source, gap) for gap in GAPS]
        self.assertEqual(len(histories), 3)
        for original, sampled in zip(self.source, zip(*histories)):
            for row, gap in zip(sampled, GAPS):
                self.assertEqual({key:value for key,value in row.items() if key!='hazard_state'},
                                 {key:value for key,value in original.items() if key!='hazard_state'})
                self.assertEqual(row['hazard_state']['ego_center_gap_m'], gap)
                self.assertAlmostEqual(row['hazard_state']['position_xyz_m'][0]-row['ego_x_m'], gap)
                self.assertEqual(row['hazard_state']['velocity_xyz_mps'],
                                 original['hazard_state']['velocity_xyz_mps'])

    def test_invalid_setting_and_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            construct(self.source, 3.0)
        bad = copy.deepcopy(self.source)
        bad[10]['hazard_state']['source_kind'] = 'original_carla_actor_and_map_readback'
        with self.assertRaisesRegex(ValueError, 'Source hazard'):
            construct(bad, GAPS[0])
        bad = copy.deepcopy(self.source)
        bad[10]['hazard_state']['ego_center_gap_m'] = -1
        with self.assertRaisesRegex(ValueError, 'invalid'):
            construct(bad, GAPS[0])


if __name__ == '__main__':
    unittest.main()
