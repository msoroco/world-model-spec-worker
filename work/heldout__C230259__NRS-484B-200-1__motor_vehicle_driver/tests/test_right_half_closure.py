"""Closure construction and original source continuity checks."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace as N

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from right_half_closure import ClosureSourceRecorder, closure_transforms


class FakeCarla:
    @staticmethod
    def Location(**kwargs):
        return N(**kwargs)

    @staticmethod
    def Transform(location, rotation):
        return N(location=location, rotation=rotation)


class ClosureTest(unittest.TestCase):
    def test_three_lane_interior_positions(self):
        waypoint = N(lane_width=4., transform=N(
            location=N(x=10., y=2., z=0.), rotation=N(),
            get_forward_vector=lambda: N(x=1., y=0.)))
        positions = closure_transforms(FakeCarla, waypoint)
        self.assertEqual([round(p.location.y, 2) for p in positions], [.6, 2., 3.4])
        waypoint.lane_width = 0.
        with self.assertRaisesRegex(ValueError, 'width unavailable'):
            closure_transforms(FakeCarla, waypoint)

    def test_original_actor_ids_and_continuous_frames(self):
        actors = [N(id=i, type_id='static.prop.trafficcone01',
                    get_transform=lambda i=i: N(location=N(x=float(i), y=0., z=0.)))
                  for i in (1, 2, 3)]
        with TemporaryDirectory() as temp:
            recorder = ClosureSourceRecorder(temp, actors)
            recorder.append(10, 0.)
            recorder.append(11, .05)
            with self.assertRaisesRegex(ValueError, 'not continuous'):
                recorder.append(13, .15)
            recorder.close()
            rows = [json.loads(row) for row in (Path(temp) / 'closure_devices.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual([item['actor_id'] for item in rows[0]['devices']], ['1', '2', '3'])
            self.assertFalse(rows[0]['authority_verified'])
