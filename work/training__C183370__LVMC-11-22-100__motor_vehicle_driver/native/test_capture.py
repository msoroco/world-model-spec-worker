import sys
import hashlib
import json
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import CAMERAS, prepare_attempt, sample
from build_exact import build
from pathing import repository_root


def xyz(x, y, z=0):
    return types.SimpleNamespace(x=x, y=y, z=z)


class Ego:
    id = 10
    type_id = 'vehicle.example'

    def __init__(self):
        self.bounding_box = types.SimpleNamespace(
            get_world_vertices=lambda _: [xyz(i, 0) for i in range(8)])

    def get_transform(self):
        return types.SimpleNamespace(location=xyz(1, 2),
                                     rotation=types.SimpleNamespace(yaw=0))

    def get_velocity(self):
        return xyz(3, 4)


class Person:
    id = 12
    type_id = 'walker.pedestrian.0001'

    def get_transform(self):
        return types.SimpleNamespace(location=xyz(2, 0))


class World:
    def get_map(self):
        return types.SimpleNamespace(get_waypoint=lambda *args, **kwargs:
            types.SimpleNamespace(road_id=8, lane_id=1, lane_type='Driving'))


CARLA = types.SimpleNamespace(LaneType=types.SimpleNamespace(
    Any='Any', Driving='Driving', Shoulder='Shoulder'))


class CaptureTest(unittest.TestCase):
    def test_source_sample_keeps_raw_motion_and_person(self):
        row = sample(World(), CARLA, Ego(), Person(), {'steer': 0.2})
        self.assertEqual(row['ego_velocity_xyz_mps'], [3, 4, 0])
        self.assertEqual(row['ego_speed_mps'], 5)
        self.assertEqual(len(row['ego_body_vertices_xyz_m']), 8)
        self.assertEqual(row['warning_person_actor_id'], 12)
        self.assertFalse(row['warning_act_verified'])

    def test_four_distinct_source_cameras(self):
        self.assertEqual([camera[0] for camera in CAMERAS],
                         ['overview', 'approach', 'reference_corner',
                          'driver_reference'])
        self.assertTrue(all(camera[1] > 0 and camera[2] > 0 for camera in CAMERAS))

    def test_materialized_attempt_preserves_exact_bundle(self):
        repo=repository_root(__file__)
        (repo/'.runtime-work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=repo/'.runtime-work') as directory:
            attempt=Path(directory)
            construction=json.dumps(build('reference'),sort_keys=True)+'\n'
            (attempt/'construction.json').write_text(construction)
            config=next(item['content'] for item in build('reference')['files']
                        if item['path']=='config.json')
            (attempt/'config.json').write_text(config)
            (attempt/'candidate-selection.json').write_text(json.dumps({
                'case_id':json.loads(config)['case_id'],
                'construction_sha256':hashlib.sha256(construction.encode()).hexdigest()}))
            self.assertEqual(prepare_attempt(attempt,repo,'reference',600,
                                             materialized=True),attempt)
            self.assertEqual((attempt/'config.json').read_text(),config)
            (attempt/'trace.jsonl').write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'Preserve prior Native capture'):
                prepare_attempt(attempt,repo,'reference',600,materialized=True)


if __name__ == '__main__':
    unittest.main()
