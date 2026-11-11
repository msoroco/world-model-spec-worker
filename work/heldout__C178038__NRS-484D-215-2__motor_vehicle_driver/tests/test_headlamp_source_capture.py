import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headlamp_source_capture import HeadlampSourceRecorder
from headlamp_follow_measurement import measure


def actor(identity, x, light):
    vertices = [NS(x=x + dx, y=dy, z=z) for z in (0, 1)
                for dx, dy in ((-.5, -.5), (.5, .5), (.5, -.5), (-.5, .5))]
    transform = NS(get_forward_vector=lambda: NS(x=1, y=0))
    return NS(id=identity, bounding_box=NS(get_world_vertices=lambda _: vertices),
              get_transform=lambda: transform, get_light_state=lambda: light)


class HeadlampSourceTests(unittest.TestCase):
    def test_native_readback_feeds_saved_measurement(self):
        carla = NS(VehicleLightState=NS(HighBeam=2, LowBeam=4))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = HeadlampSourceRecorder(root, actor(1, 0, 4),
                                              actor(2, 299 * .3048 + 1, 0))
            recorder.append(10, .5, carla)
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                recorder.append(12, .55, carla)
            recorder.append(11, .55, carla)
            recorder.close()
            (root / 'lighting_context.json').write_text(json.dumps({
                'lighting_time_applies': True,
                'time_source': 'original civil-time clock plus cited NRS 484D.100(1) premise'}))
            report = measure(root / 'following_footprints.jsonl',
                             root / 'headlamp_readbacks.jsonl',
                             root / 'lighting_context.json')
            self.assertAlmostEqual(report['minimum_surface_gap_ft'], 299)
            self.assertTrue(report['observations'][0]['low_beam_readback'])
            self.assertFalse(report['observations'][0]['uppermost_distribution_readback'])
            with self.assertRaises(FileExistsError):
                HeadlampSourceRecorder(root, actor(1, 0, 4), actor(2, 100, 0))


if __name__ == '__main__':
    unittest.main()
