import hashlib
import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


scene = module('emergency_scene')
audit = module('warning_audit')


class EmergencyConstructionTests(unittest.TestCase):
    def test_both_approaches_have_recipient_ahead_outside_lane(self):
        for direction in ('eastbound', 'westbound'):
            value = scene.scene_geometry(direction)
            self.assertGreater(value['pedestrian_distance_at_spawn_m'], 20)
            self.assertGreater(abs(value['pedestrian_spawn_xy_m'][1] - value['ego_spawn_xy_m'][1]), 2)
            self.assertEqual((value['pedestrian_spawn_xy_m'][0] - value['ego_spawn_xy_m'][0]) > 0, direction == 'eastbound')

    def test_case_controls_preserve_duration_and_separate_devices(self):
        self.assertEqual(len(scene.CASE_KNOBS), 7)
        for suffix in scene.CASE_KNOBS:
            control = scene.control_plan(suffix)
            self.assertEqual(control['capture_duration_s'] * control['capture_rate_hz'], 900)
            self.assertEqual(bool(control['siren_command_window_s']), scene.CASE_KNOBS[suffix]['siren'])
            self.assertEqual(bool(control['warning_lamp_command_window_s']), scene.CASE_KNOBS[suffix]['lamps'])


class OriginalAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.contents = {
            'device_trace': ''.join(json.dumps({'frame': i, 'elapsed_s': i / 20,
                'siren_active': 160 <= i <= 440, 'warning_lamp_active': False}) + '\n' for i in range(900)),
            'dispatch_context': json.dumps({'source_status': 'documented', 'event': 'emergency_call', 'event_interval_frames': [100, 500]}),
            'equipment_record': json.dumps({'authorization_source': 'test-document', 'device_installation_source': 'test-document', 'audibility_500ft_status': 'unknown'}),
        }
        self.manifest = {'source_kind': 'original_capture', 'sources': {}}
        for key, content in self.contents.items():
            path = key + '.jsonl' if key == 'device_trace' else key + '.json'
            (self.folder / path).write_text(content)
            self.manifest['sources'][key] = {'path': path, 'sha256': hashlib.sha256(content.encode()).hexdigest()}

    def tearDown(self):
        self.temp.cleanup()

    def test_positive_source_join_and_temporal_observation(self):
        result = audit.audit(self.folder, self.manifest)
        self.assertEqual(result['observed_siren_frames'], 281)
        self.assertTrue(result['all_siren_frames_within_documented_event'])
        self.assertEqual(result['recipient_hearing'], 'unknown')
        self.assertEqual(result['audibility_500ft_documentation_status'], 'unknown')

    def test_tampered_original_source_rejected(self):
        (self.folder / 'dispatch_context.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit.audit(self.folder, self.manifest)

    def test_missing_source_rejected(self):
        self.manifest['sources'].pop('equipment_record')
        with self.assertRaisesRegex(ValueError, 'inventory incomplete'):
            audit.audit(self.folder, self.manifest)

    def test_device_frames_missing_rejected(self):
        self.contents['device_trace'] = ''.join(self.contents['device_trace'].splitlines(keepends=True)[:-1])
        (self.folder / 'device_trace.jsonl').write_text(self.contents['device_trace'])
        self.manifest['sources']['device_trace']['sha256'] = hashlib.sha256(self.contents['device_trace'].encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'frame sequence incomplete'):
            audit.audit(self.folder, self.manifest)

    def test_unqualified_siren_is_observed_not_labeled(self):
        context = {'source_status': 'documented', 'event': 'none', 'event_interval_frames': [0, 899]}
        text = json.dumps(context)
        (self.folder / 'dispatch_context.json').write_text(text)
        self.manifest['sources']['dispatch_context']['sha256'] = hashlib.sha256(text.encode()).hexdigest()
        result = audit.audit(self.folder, self.manifest)
        self.assertEqual(result['event'], 'none')
        self.assertEqual(result['warning_purpose'], 'requires_independent_review')


if __name__ == '__main__':
    unittest.main()

comparison = module('comparison_audit')


class ComparisonTests(unittest.TestCase):
    def _record(self, case, event, siren, lamps):
        value = {key: 'hash-' + key for key in comparison.FIXED}
        value.update({'cell_id': 'C109035', 'actor': 'emergency_vehicle_driver',
            'case_id': case, 'event_context': event, 'requested_siren': siren,
            'requested_warning_lamps': lamps})
        return value

    def test_response_device_comparison(self):
        a = self._record('response_siren', 'emergency_call', True, False)
        b = self._record('response_lamps', 'emergency_call', False, True)
        self.assertEqual(comparison.compare('response_device_choice', [a, b])['physical_status'], 'source_join_only')

    def test_changed_site_rejected(self):
        a = self._record('response_siren', 'emergency_call', True, False)
        b = self._record('response_lamps', 'emergency_call', False, True)
        b['site_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'Fixed condition'):
            comparison.compare('response_device_choice', [a, b])

    def test_undeclared_device_change_rejected(self):
        a = self._record('response', 'emergency_call', True, False)
        b = self._record('pursuit', 'immediate_pursuit_actual', False, False)
        with self.assertRaisesRegex(ValueError, 'Undeclared change'):
            comparison.compare('qualifying_event_for_siren', [a, b])

native_scene = module('native_scene')


class NativeSceneTests(unittest.TestCase):
    def _packet(self, folder, direction):
        geometry = scene.scene_geometry(direction)
        data = {'case_id': 'case-1', 'cell_id': 'C109035', 'actor': 'emergency_vehicle_driver',
            'reviewer': 'cpu-fixture-only', 'source_citation': 'synthetic-test-packet',
            'opendrive_sha256': hashlib.sha256(b'fixture-map').hexdigest(),
            'approach': direction, 'pedestrian_role': 'approach_warning_recipient',
            'ego_blueprint_id': 'vehicle.test.emergency', 'pedestrian_blueprint_id': 'walker.pedestrian.test',
            'ego_transform': {'location': [*geometry['ego_spawn_xy_m'], 0.5], 'rotation': [0, geometry['ego_heading_deg'], 0]},
            'pedestrian_transform': {'location': [*geometry['pedestrian_spawn_xy_m'], 0.5], 'rotation': [0, 0, 0]}}
        p = folder / 'site.json'; p.write_text(json.dumps(data)); return p

    def test_packet_accepts_both_approach_directions(self):
        with tempfile.TemporaryDirectory() as temp:
            for direction in ('eastbound', 'westbound'):
                p = self._packet(Path(temp), direction)
                self.assertEqual(native_scene.validate_site(p, case_id='case-1', map_opendrive='fixture-map')['approach'], direction)

    def test_unreviewed_or_wrong_map_packet_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self._packet(Path(temp), 'eastbound')
            with self.assertRaisesRegex(ValueError, 'map hash mismatch'):
                native_scene.validate_site(p, case_id='case-1', map_opendrive='other-map')
            d = json.loads(p.read_text()); d.pop('reviewer'); p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError, 'citation missing'):
                native_scene.validate_site(p, case_id='case-1', map_opendrive='fixture-map')
