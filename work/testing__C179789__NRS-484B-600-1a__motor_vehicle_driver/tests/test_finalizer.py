import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('speed_conditions_finalizer', ROOT / 'finalizer.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_fixture(root):
    config = json.loads((ROOT / 'config.json').read_text())
    config['condition_target'] = {'surface': 'dry', 'lane_width_m': [3, 4],
                                  'longitudinal_body_gap_m': [10, 35],
                                  'sight_distance_m': [10, 120],
                                  'precipitation_percent': [0, 5]}
    (root / 'config.json').write_text(json.dumps(config) + '\n')
    surface = 'Observed dry pavement in source review.\n'
    (root / 'surface.txt').write_text(surface)
    source = {'path': 'surface.txt', 'sha256': hashlib.sha256(surface.encode()).hexdigest()}
    context = {'native_map_id': 'TestMap', 'ego_actor_id': 10, 'road_id': 7,
               'lane_id': -1, 'road_surface_source': source,
               'lane_width_source': 'original Native waypoint',
               'traffic_source': 'original Native actor',
               'weather_source': 'original Native weather',
               'sight_source': 'original Native ray',
               'curvature_source': 'original Native waypoint',
               'braking_model_source': 'declared engineering model',
               'diagnostic_reaction_time_s': 1.0,
               'diagnostic_braking_deceleration_mps2': 5.0}
    (root / 'road_context.json').write_text(json.dumps(context) + '\n')
    rows = []
    frames = []
    traces = []
    for index in range(3):
        frame, time = 100 + index, index * .05
        rows.append({'frame': frame, 'time_s': time, 'ego_actor_id': 10,
                     'ego_position_m': [index * .4, 0, 0],
                     'road_id': 7, 'lane_id': -1,
                     'ego_velocity_source': 'actor.get_velocity',
                     'ego_velocity_mps': [8, 0, 0], 'lane_width_m': 3.5,
                     'surface': 'dry', 'surface_source': source,
                     'physical_surface_verified': False,
                     'precipitation_percent': 0,
                     'fog_density_percent': 0, 'fog_distance_m': 100,
                     'weather_source': 'world.get_weather',
                     'sight_distance_m': 80,
                     'sight_ray_source': 'original Native cast_ray',
                     'curvature_per_m': 0,
                     'curvature_source': 'native-waypoint.next(5.0)',
                     'surrounding_traffic': [{'actor_id': 20,
                                             'velocity_source': 'actor.get_velocity',
                                             'velocity_mps': [7, 0, 0],
                                             'longitudinal_body_gap_m': 20}]})
        frames.append({'video_frame': index, 'carla_frame': frame,
                       'native_frame': frame, 'time_s': time})
        traces.append({'frame': frame, 'time_s': time,
                       'position_m': [index * .4, 0, 0]})
    for name, data in [('condition_history.jsonl', rows),
                       ('video_frames.jsonl', frames), ('trace.jsonl', traces)]:
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in data))
    (root / 'capture').mkdir()
    (root / 'capture/evidence.jsonl').write_text('{}\n')
    for name in MODULE.CAMERAS:
        (root / name).write_text('test camera placeholder\n')


class SavedFinalizerTests(unittest.TestCase):
    def test_unknown_case_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root)
            config = json.loads((root / 'config.json').read_text())
            config['selected_case_id'] = MODULE.ASSIGNMENT + '__unplanned'
            (root / 'config.json').write_text(json.dumps(config) + '\n')
            with self.assertRaisesRegex(ValueError, 'Wrong exact speed/conditions case'):
                MODULE.finalize(root, root / 'analysis.json')

    def test_source_bound_saved_result_and_no_legal_conclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root)
            analysis = MODULE.finalize(root, root / 'analysis.json')
            result = json.loads((root / 'result.json').read_text())
            self.assertEqual(analysis['measurements']['sampled_peak_speed_mps']['value'], 8)
            self.assertEqual(result['measured_values']['reasonable_or_proper_judgment'], 'unresolved')
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertFalse(result['target_checks'][0]['physical_cause_confirmed'])
            self.assertEqual(result['source_hashes']['surface.txt'],
                             hashlib.sha256((root / 'surface.txt').read_bytes()).hexdigest())
            self.assertTrue((root / 'speed-channel.jsonl').is_file())
            with self.assertRaisesRegex(ValueError, 'Retain prior finalization'):
                MODULE.finalize(root, root / 'analysis.json')

    def test_missing_or_changed_original_surface_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root)
            (root / 'surface.txt').unlink()
            with self.assertRaisesRegex(ValueError, 'Original surface document missing'):
                MODULE.finalize(root, root / 'analysis.json')
            self.assertFalse((root / 'result.json').exists())
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_fixture(root)
            (root / 'surface.txt').write_text('tampered\n')
            with self.assertRaisesRegex(ValueError, 'Original surface document hash changed'):
                MODULE.finalize(root, root / 'analysis.json')
            self.assertFalse((root / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
