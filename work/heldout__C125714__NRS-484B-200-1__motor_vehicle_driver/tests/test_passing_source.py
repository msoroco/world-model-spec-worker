import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from passing_source import PassingSourceRecorder
from passing_source_audit import audit


def actor(actor_id, x, speed):
    return SimpleNamespace(id=actor_id, type_id='vehicle.test',
        get_transform=lambda: SimpleNamespace(location=SimpleNamespace(x=x, y=0, z=0)),
        get_velocity=lambda: SimpleNamespace(x=speed, y=0, z=0))


class PassingSourceTests(unittest.TestCase):
    def test_recorder_retains_original_readback_and_continuity(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = PassingSourceRecorder(directory, actor(1, 0, 12), actor(2, 1, 8))
            row = recorder.append(10, .5)
            self.assertEqual(row['subject']['position_m'], [0.0, 0.0, 0.0])
            self.assertFalse(row['passing_law_verified'])
            with self.assertRaisesRegex(ValueError, 'continuous'):
                recorder.append(12, .6)
            recorder.close()

    def test_audit_positive_and_negative_original_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            passing, roadway = [], []
            for i, x in enumerate((-2, -1, 1, 2)):
                passing.append({'frame': i, 'time_s': i*.05,
                    'subject': {'actor_id': '1', 'blueprint_id': 'vehicle.test',
                        'position_m': [x, 0, 0], 'velocity_mps': [12, 0, 0]},
                    'lead': {'actor_id': '2', 'blueprint_id': 'vehicle.test',
                        'position_m': [0, 0, 0], 'velocity_mps': [8, 0, 0]},
                    'passing_law_verified': False})
                roadway.append({'frame': i, 'time_s': i*.05, 'travel_tangent_xy': [1, 0],
                    'ego_id': '1', 'ego_corners': [[x-.5,-.5],[x-.5,.5],[x+.5,-.5],[x+.5,.5]]})
            def write():
                (root/'passing_actors.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in passing))
                (root/'directed_roadway_footprints.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in roadway))
            write()
            self.assertEqual(audit(root)['actor_ids'], ['1', '2'])
            passing[2]['lead']['velocity_mps'] = [-1, 0, 0]
            write()
            with self.assertRaisesRegex(ValueError, 'selected direction'):
                audit(root)
            passing[2]['lead']['velocity_mps'] = [8, 0, 0]
            passing[0]['subject']['position_m'] = [1, 0, 0]
            roadway[0]['ego_corners'] = [[.5,-.5],[.5,.5],[1.5,-.5],[1.5,.5]]
            write()
            with self.assertRaisesRegex(ValueError, 'order change'):
                audit(root)
            (root/'passing_actors.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original source'):
                audit(root)


if __name__ == '__main__':
    unittest.main()
