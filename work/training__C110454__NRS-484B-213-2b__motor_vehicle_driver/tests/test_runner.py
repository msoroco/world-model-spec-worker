import json
from pathlib import Path
import unittest
from types import SimpleNamespace

from runner import check, frame_map_row, observed_speed_mps


class RunnerCheck(unittest.TestCase):
    def test_exact_bundle(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        outcome = check(config)
        self.assertTrue(outcome['offline_geometry']['passed'])
        self.assertEqual(outcome['candidate_id'], config['candidate_id'])
        self.assertFalse(outcome['physical_success_claimed'])

    def test_join_rejects_invalid_identity(self):
        with self.assertRaises(ValueError):
            frame_map_row(1, -1, .05)

    def test_observed_speed_uses_current_velocity_and_rejects_nonfinite(self):
        class Actor:
            velocity = SimpleNamespace(x=3, y=4, z=0)
            def get_velocity(self):
                return self.velocity

        actor = Actor()
        self.assertEqual(observed_speed_mps(actor), 5)
        actor.velocity = SimpleNamespace(x=0, y=0, z=2)
        self.assertEqual(observed_speed_mps(actor), 2)
        actor.velocity = SimpleNamespace(x=float('nan'), y=0, z=0)
        with self.assertRaisesRegex(ValueError, 'Nonfinite observed Native velocity'):
            observed_speed_mps(actor)


if __name__ == '__main__':
    unittest.main()
