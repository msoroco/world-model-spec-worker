import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S


ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

sources = load('opposing_turn_sources')
measurement = load('opposing_turn_measurement')


class Actor:
    def __init__(self, actor_id, x, y, yaw):
        self.id, self.x, self.y, self.yaw = actor_id, x, y, yaw
        self.bounding_box = self

    def get_transform(self):
        return S(location=S(x=self.x, y=self.y), rotation=S(yaw=self.yaw))

    def get_world_vertices(self, transform):
        return [S(x=self.x+dx, y=self.y+dy, z=z)
                for z in (0, 2) for dx, dy in ((-.3,-.2),(.3,-.2),(.3,.2),(-.3,.2))]


class OriginalRecorderTests(unittest.TestCase):
    def test_native_sources_feed_saved_geometry_and_preserve_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            recorder = sources.OpposingTurnRecorder(root,
                {'source_map': 'Native test map', 'both_highways_two_directional': True,
                 'same_intersection': True, 'opposing_approaches': True},
                {'governing_device': 'none', 'source': 'Native landmark inventory'})
            a, b = Actor(1, 0, 0, 0), Actor(2, 4, 1, 180)
            for frame in range(4):
                a.x = frame
                b.x = 4-frame
                recorder.append(frame, frame*.05, a, b,
                    subject_in_intersection=True, opposing_in_intersection=True,
                    subject_turning_left=True, opposing_turning_left=True)
            with self.assertRaisesRegex(ValueError, 'increase together'):
                recorder.append(3, .2, a, b,
                    subject_in_intersection=True, opposing_in_intersection=True,
                    subject_turning_left=True, opposing_turning_left=True)
            recorder.close()
            result = measurement.measure(root/'subject_original.jsonl',
                root/'opposing_original.jsonl', root/'topology_original.json',
                root/'devices_original.json')
            self.assertEqual(result['simultaneous_frames'], 4)
            self.assertGreater(result['closest']['ground_body_clearance_m'], 0)
            with self.assertRaises(FileExistsError):
                sources.OpposingTurnRecorder(root, {'source_map':'other'},
                                             {'governing_device':'none'})

    def test_missing_map_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'source inventory'):
                sources.OpposingTurnRecorder(temp, {}, {'governing_device':'none'})


if __name__ == '__main__':
    unittest.main()
