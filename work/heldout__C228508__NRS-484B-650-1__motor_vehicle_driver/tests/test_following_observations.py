from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from following_observations import sample, write_samples


def vehicle(actor_id, x):
    transform = NS(location=NS(x=x, y=0, z=0), rotation=NS(yaw=0))
    body = NS(get_world_vertices=lambda _: [NS(x=x + i, y=0, z=0)
                                            for i in range(8)])
    return NS(id=actor_id, get_transform=lambda: transform,
              get_velocity=lambda: NS(x=12, y=0, z=0), bounding_box=body)


class ObservationTests(unittest.TestCase):
    def test_original_body_source_and_20hz_rejection(self):
        ego, lead = vehicle(1, 0), vehicle(2, 15)
        rows = [sample(100 + i, i * .05, ego, lead,
                       requested_phase='first_closing_request',
                       map_speed_limit_kmh=50) for i in range(3)]
        self.assertEqual(len(rows[0]['lead']['body_corners_m']), 8)
        self.assertEqual(rows[0]['ego']['speed_mps'], 12)
        self.assertFalse(rows[0]['speed_limit_sign_physically_verified'])
        self.assertIsNone(rows[0]['too_close_legal_judgment'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'following_sources.jsonl'
            write_samples(path, rows)
            self.assertEqual(len(path.read_text().splitlines()), 3)
            with self.assertRaisesRegex(ValueError, 'Retain prior'):
                write_samples(path, rows)
            path.unlink()
            rows[2]['frame'] = 104
            with self.assertRaisesRegex(ValueError, 'not continuous'):
                write_samples(path, rows)


if __name__ == '__main__':
    unittest.main()
