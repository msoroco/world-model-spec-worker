"""Source binding checks for a reviewed speed-zone site packet."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_speed_zone import site as site_fixture
from speed_site import FIELD, REQUIRED, validate_packet


class SpeedSiteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = site_fixture()
        sources = {}
        for name in REQUIRED:
            source = self.root / (name + '.txt')
            source.write_text('diagnostic ' + name + '\n')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            sources[name] = {'path': source.name, 'sha256': digest}
        for name, field in FIELD.items():
            self.site[field] = sources[name]['sha256']
        for direction in ('eastbound', 'westbound'):
            self.site['lanes'][direction]['source_sha256'] = sources[direction + '_lane']['sha256']
            self.site['signs'][direction]['source_sha256'] = sources[direction + '_sign']['sha256']
        self.site['vehicle_class_source_sha256'] = sources['vehicle_classification']['sha256']
        self.case_id = ROOT.name + '__signed_below'
        self.packet = {'format': 'c136559-reviewed-speed-site-v1',
                       'cell_id': 'C136559', 'law_id': 'NRS-484B-620-2',
                       'actor': 'motor_vehicle_driver', 'case_id': self.case_id,
                       'site': self.site, 'sources': sources}
        self.path = self.root / 'site.json'
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.packet) + '\n')

    def test_positive_packet_and_all_direction_sources(self):
        _, site, case = validate_packet(self.path, self.case_id)
        self.assertEqual(case.case_id, 'signed_below')
        self.assertNotEqual(site['lanes']['eastbound']['source_sha256'],
                            site['lanes']['westbound']['source_sha256'])

    def test_changed_source_and_false_binding_rejected(self):
        (self.root / 'zone_establishment.txt').write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'source absent or changed'):
            validate_packet(self.path, self.case_id)
        (self.root / 'zone_establishment.txt').write_text('diagnostic zone_establishment\n')
        self.packet['site']['signs']['westbound']['source_sha256'] = 'wrong'
        self.save()
        with self.assertRaisesRegex(ValueError, 'directional sign source binding'):
            validate_packet(self.path, self.case_id)

    def test_missing_role_and_wrong_case_rejected(self):
        self.packet['sources'].pop('public_access')
        self.save()
        with self.assertRaisesRegex(ValueError, 'inventory incomplete'):
            validate_packet(self.path, self.case_id)
        self.packet['sources']['public_access'] = {
            'path': 'public_access.txt',
            'sha256': hashlib.sha256((self.root / 'public_access.txt').read_bytes()).hexdigest()}
        self.save()
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            validate_packet(self.path, ROOT.name + '__signed_above')

    def test_native_capture_seals_full_original_shape_after_cleanup(self):
        from native_capture import capture
        config = {'selected_case_id': self.case_id, 'frame_count': 900,
                  'cameras': [{'name': name} for name in (
                      'overview', 'approach', 'reference_corner', 'driver_reference')]}
        output = self.root / 'attempt'
        output.mkdir()
        (output / 'construction.json').write_text('{}\n')
        (output / 'runner.py').write_text('pass\n')

        class Adapter:
            closed = False
            destroyed = []

            def spawn_vehicle(self, point, **kwargs):
                return 'ego'

            def install_sign(self, spec, **kwargs):
                return 'sign'

            def read_sign(self, sign):
                return {'source_sha256': 'original-sign-readback',
                        'direction': 'eastbound', 'installed': True}

            def set_route(self, *args, **kwargs):
                pass

            def attach_cameras(self, ego, cameras):
                return {item['name']: object() for item in cameras}

            def request_speed(self, *args):
                pass

            def tick_and_read(self, built, cameras):
                index = getattr(self, 'index', 0)
                self.index = index + 1
                return {'original_frame': index, 'original_time_s': index / 20,
                        'camera_png': {name: b'\x89PNG\r\n\x1a\nfixture' for name in cameras},
                        'state': {'ego_id': 'ego', 'inside_zone': True,
                                  'sign_installed': True, 'actual_speed_mps': 9.0},
                        'trace': {'original_frame': index},
                        'video_frame': {'original_frame': index, 'video_frame': index}}

            def finalize_media(self, output, views, mapping):
                result = {}
                for name in (*views, 'raw'):
                    path = output / (name + '.mkv')
                    path.write_bytes(b'diagnostic media placeholder')
                    result[name] = path
                return result

            def ego_blueprint_id(self, ego):
                return 'vehicle.diagnostic'

            def destroy(self, actor):
                self.destroyed.append(actor)

            def close(self):
                self.closed = True
                return True

        adapter = Adapter()
        receipt = capture(adapter, config, self.path, output)
        self.assertEqual(receipt['frame_count'], 900)
        self.assertTrue(adapter.closed)
        self.assertEqual(adapter.destroyed, ['sign', 'ego'])
        seal = json.loads((output / 'capture-seal.json').read_text())
        self.assertEqual(seal['events'][-1], 'restoration_verified')
        self.assertEqual(len([name for name in seal['sources'] if 'source-review/' in name]), 11)
