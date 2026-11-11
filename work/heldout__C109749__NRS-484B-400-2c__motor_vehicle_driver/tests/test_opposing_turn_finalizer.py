import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('opposing_turn_finalizer', ROOT / 'opposing_turn_finalizer.py')
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


class Actor:
    def __init__(self, actor_id, x, y, yaw):
        self.id, self.x, self.y, self.yaw = actor_id, x, y, yaw
        self.bounding_box = self

    def get_transform(self):
        return S(location=S(x=self.x, y=self.y), rotation=S(yaw=self.yaw))

    def get_world_vertices(self, transform):
        return [S(x=self.x+dx, y=self.y+dy, z=z)
                for z in (0, 2) for dx, dy in ((-.3,-.2),(.3,-.2),(.3,.2),(-.3,.2))]


class SavedFinalizerTests(unittest.TestCase):
    def build_originals(self, root):
        from opposing_turn_sources import OpposingTurnRecorder
        (root / 'config.json').write_bytes((ROOT / 'config.json').read_bytes())
        recorder = OpposingTurnRecorder(root,
            {'source_map': 'Native test map', 'both_highways_two_directional': True,
             'same_intersection': True, 'opposing_approaches': True},
            {'governing_device': 'none', 'source': 'Native device inventory'})
        a, b = Actor(1, 0, 0, 0), Actor(2, 4, 1, 180)
        mapping, trace = [], []
        for frame in range(4):
            a.x = frame
            b.x = 4-frame
            recorder.append(frame, frame*.05, a, b,
                subject_in_intersection=True, opposing_in_intersection=True,
                subject_turning_left=True, opposing_turning_left=True)
            mapping.append({'video_frame': frame, 'carla_frame': frame, 'time_s': frame*.05})
            trace.append({'frame': frame, 'time_s': frame*.05})
        recorder.close()
        for name, rows in (('video_frames.jsonl', mapping), ('trace.jsonl', trace)):
            (root / name).write_text(''.join(json.dumps(row)+'\n' for row in rows))

    def test_saved_originals_produce_joined_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build_originals(root)
            report = finalizer.analyze(root)
            result = finalizer.result(root, report)
            self.assertEqual(report['measurements']['opposing_turn_geometry']['value']['simultaneous_frames'], 4)
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertEqual(len(result['recording_evidence']), 4)
            self.assertEqual(result['realized_observables']['simultaneous_left_turn_frames']['value'], 4)

    def test_missing_and_stale_originals_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build_originals(root)
            (root / 'devices_original.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                finalizer.analyze(root)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build_originals(root)
            rows = [json.loads(x) for x in (root/'video_frames.jsonl').read_text().splitlines()]
            rows[2]['carla_frame'] = 999
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'frame/time join'):
                finalizer.analyze(root)


if __name__ == '__main__':
    unittest.main()
