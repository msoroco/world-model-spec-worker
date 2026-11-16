import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('marked_native_runner', ROOT / 'native_runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeRunnerTests(unittest.TestCase):
    def source(self, directory):
        path = Path(directory) / 'site.json'
        path.write_text(json.dumps({
            'authority_document': 'CPU fixture claim only',
            'municipal_jurisdiction_source': 'CPU fixture only',
            'intersection_source': 'CPU fixture only',
            'authorization_source': 'CPU fixture only',
            'intersection_id': 'fixture-junction',
            'map_name': 'fixture-map',
            'median_opening_with_intersecting_road': True,
            'indicated_course_xy_m': [[-2, 5], [3, 5], [7, 7], [12, 7]],
            'divergent_course_xy_m': [[-2, 5], [3, 6], [7, 8], [12, 7]],
            'markers': [{'x': 3, 'y': 5, 'z': 0, 'yaw': 0,
                         'blueprint_id': 'static.prop.trafficcone01'}]}))
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_prepare_both_exact_variants_and_reject_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest = self.source(directory)
            for variant in module.VARIANTS:
                plan = module.prepare(module.ASSIGNMENT + '__' + variant, path, digest)
                self.assertEqual(plan['variant'], variant)
                self.assertEqual(plan['approach_heading_deg'], 0)
                self.assertFalse(plan['authority_verified'])
            numeric = module.prepare(module.ASSIGNMENT + '__marker_course_blend_050',
                                     path, digest)
            self.assertEqual((numeric['variant'], numeric['course_blend']),
                             ('indicated_course', .5))
            for suffix, expected in (('c126064_course_blend-0000', 0.),
                                     ('c126064_course_blend-0001', 1.),
                                     ('c126064_course_blend-0002', .5)):
                sweep = module.prepare(module.ASSIGNMENT + '__' + suffix, path, digest)
                self.assertEqual((sweep['indication_form'], sweep['variant'],
                                  sweep['course_blend']),
                                 ('marker', 'indicated_course', expected))
            with self.assertRaisesRegex(ValueError, 'Unknown exact'):
                module.prepare(module.ASSIGNMENT + '__unplanned', path, digest)
            path.write_text(path.read_text() + ' ')
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                module.prepare(module.ASSIGNMENT + '__indicated_course', path, digest)

    def test_prepare_button_and_other_indication_require_matching_original_form(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.source(directory)
            source = json.loads(path.read_text())
            source.pop('markers')
            for form in ('button', 'other_indication'):
                source['indication_form'] = form
                source['indications'] = [{'form': form, 'x': 3, 'y': 5,
                                          'blueprint_id': 'static.prop.trafficcone01'}]
                path.write_text(json.dumps(source))
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                for variant in module.VARIANTS:
                    plan = module.prepare(module.ASSIGNMENT + '__' + form + '_' + variant,
                                          path, digest)
                    self.assertEqual((plan['indication_form'], plan['variant']),
                                     (form, variant))
                if form == 'button':
                    for suffix, expected in module.NUMERIC_INDICATION_CASES.items():
                        if expected:
                            with self.assertRaisesRegex(ValueError, 'placement axis'):
                                module.prepare(module.ASSIGNMENT + '__' + suffix,
                                               path, digest)
                    source['placement_axis_xy'] = [1, 0]
                    path.write_text(json.dumps(source))
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    for suffix, expected in module.NUMERIC_INDICATION_CASES.items():
                        sweep = module.prepare(module.ASSIGNMENT + '__' + suffix,
                                               path, digest)
                        self.assertEqual((sweep['indication_form'], sweep['variant'],
                                          sweep['placement_offset_m']),
                                         ('button', 'indicated_course', expected))
                other = 'button' if form == 'other_indication' else 'other_indication'
                with self.assertRaisesRegex(ValueError, 'exact indication form'):
                    module.prepare(module.ASSIGNMENT + '__' + other + '_indicated_course',
                                   path, digest)

    def test_native_wiring_passes_same_source_and_restores_owned_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest = self.source(directory)
            plan = module.prepare(module.ASSIGNMENT + '__divergent_course', path, digest)
            settings = types.SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
            restored = []
            ego = types.SimpleNamespace(id=7, destroy=lambda: restored.append('ego'))
            waypoint = types.SimpleNamespace(transform=types.SimpleNamespace(
                location=types.SimpleNamespace(z=0.)))
            world = types.SimpleNamespace(
                get_settings=lambda: settings,
                apply_settings=lambda value: restored.append('settings'),
                get_map=lambda: types.SimpleNamespace(name='fixture-map',
                                                      get_waypoint=lambda location: waypoint),
                get_blueprint_library=lambda: types.SimpleNamespace(find=lambda name: name),
                try_spawn_actor=lambda blueprint, transform: ego)
            client = types.SimpleNamespace(set_timeout=lambda seconds: None,
                                           get_world=lambda: world)
            fake_carla = types.SimpleNamespace(
                Client=lambda host, port: client,
                Location=lambda **values: types.SimpleNamespace(**values),
                Rotation=lambda **values: types.SimpleNamespace(**values),
                Transform=lambda location, rotation: types.SimpleNamespace(
                    location=location, rotation=rotation))
            recorder = types.SimpleNamespace(close=lambda: restored.append('recorder'))
            seen = []

            def execute(world_arg, carla_arg, ego_arg, case, source, source_hash,
                        variant, make_transform, recorder_arg):
                seen.append((case, source, source_hash, variant, recorder_arg))
                self.assertEqual(make_transform(1, 2, 3, 4).location.x, 1)
                return {'authority_verified': False, 'motion': {'actual_turn_observed': False}}

            with patch.dict(sys.modules, {'carla': fake_carla}), \
                    patch.object(module, 'SourceRecorder', return_value=recorder), \
                    patch.object(module, 'execute_marked_turn', side_effect=execute):
                result = module.run(plan, Path(directory) / 'attempt')
            self.assertEqual(seen[0][:4], (plan['case_id'], str(path), digest, 'divergent_course'))
            self.assertFalse(result['authority_verified'])
            self.assertEqual(restored[-2:], ['ego', 'settings'])
            self.assertFalse(settings.synchronous_mode)
            self.assertIsNone(settings.fixed_delta_seconds)
            self.assertTrue((Path(directory) / 'attempt/native-turn-result.json').is_file())
            numeric = module.prepare(module.ASSIGNMENT + '__marker_course_blend_050',
                                     path, digest)
            numeric_seen = []
            def numeric_execute(*args, **kwargs):
                numeric_seen.append(kwargs['course_blend'])
                return {'authority_verified': False,
                        'motion': {'actual_turn_observed': False}}
            with patch.dict(sys.modules, {'carla': fake_carla}), \
                    patch.object(module, 'SourceRecorder', return_value=recorder), \
                    patch.object(module, 'execute_marked_turn', side_effect=numeric_execute):
                module.run(numeric, Path(directory) / 'numeric-attempt')
            self.assertEqual(numeric_seen, [.5])
            button_source = json.loads(path.read_text())
            button_source.pop('markers')
            button_source['indication_form'] = 'button'
            button_source['indications'] = [{'form': 'button', 'x': 3, 'y': 5,
                                             'blueprint_id': 'static.prop.road_button'}]
            button_source['placement_axis_xy'] = [1, 0]
            path.write_text(json.dumps(button_source))
            button_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            offset_plan = module.prepare(module.ASSIGNMENT + '__c126064_indication_offset-0002',
                                         path, button_digest)
            offsets = []
            def indication_execute(*args, **kwargs):
                offsets.append(kwargs['placement_offset_m'])
                return {'authority_verified': False,
                        'motion': {'actual_turn_observed': False}}
            with patch.dict(sys.modules, {'carla': fake_carla}), \
                    patch.object(module, 'SourceRecorder', return_value=recorder), \
                    patch.object(module, 'execute_indication_turn', side_effect=indication_execute):
                module.run(offset_plan, Path(directory) / 'offset-attempt')
            self.assertEqual(offsets, [.5])
            with patch.dict(sys.modules, {'carla': fake_carla}):
                with self.assertRaisesRegex(ValueError, 'does not match Native map'):
                    module.run(dict(plan, map_name='different-map'), Path(directory) / 'wrong-map')
            restored.clear()
            with patch.dict(sys.modules, {'carla': fake_carla}), \
                    patch.object(module, 'SourceRecorder', return_value=recorder), \
                    patch.object(module, 'execute_marked_turn', side_effect=ValueError('turn failed')):
                with self.assertRaisesRegex(ValueError, 'turn failed'):
                    module.run(plan, Path(directory) / 'failed-attempt')
            self.assertEqual(restored[-2:], ['ego', 'settings'])
            self.assertFalse(settings.synchronous_mode)


if __name__ == '__main__':
    unittest.main()
