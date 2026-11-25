import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_site import verify
from test_native_acquisition import site as diagnostic_site


class ReviewedSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.site = diagnostic_site()
        self.site.update(cell_id='C111329', actor='pedestrian')
        original_map = {'diagnostic': False, 'cell_id': 'C111329',
                        'map_name': self.site['map_name'],
                        'map_sha256': self.site['map_sha256'],
                        'corners': self.site['corners'],
                        'intersection_polygon': self.site['intersection_polygon']}
        devices = {'diagnostic': False, 'cell_id': 'C111329',
                   'map_sha256': self.site['map_sha256'],
                   'devices': self.site['devices']}
        for device in devices['devices']:
            device['diagonal_instruction_reviewed'] = True
        self.site['devices'] = devices['devices']
        self.site['original_sources'] = {
            'map': self.write('original-map.json', original_map),
            'devices': self.write('original-devices.json', devices)}

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        raw = (json.dumps(value, sort_keys=True) + '\n').encode()
        (self.root / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def test_source_bound_authorized_and_unauthed(self):
        self.assertEqual(verify(self.root, self.site, 'opposite', True)['route_kind'], 'opposite')
        self.assertEqual(verify(self.root, self.site, 'adjacent', False)['exception_484B_290'], 'unresolved')

    def test_changed_original_map_rejected(self):
        (self.root / 'original-map.json').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify(self.root, self.site, 'opposite', True)

    def test_rehashed_wrong_corner_rejected(self):
        changed = json.loads((self.root / 'original-map.json').read_text())
        changed['corners'][1][0] += 5
        self.site['original_sources']['map'] = self.write('original-map.json', changed)
        with self.assertRaisesRegex(ValueError, 'corner survey differs'):
            verify(self.root, self.site, 'opposite', True)

    def test_rehashed_unreviewed_instruction_rejected(self):
        changed = json.loads((self.root / 'original-devices.json').read_text())
        for device in changed['devices']:
            device['diagonal_instruction_reviewed'] = False
        self.site['devices'] = changed['devices']
        self.site['original_sources']['devices'] = self.write('original-devices.json', changed)
        with self.assertRaisesRegex(ValueError, 'instruction absent'):
            verify(self.root, self.site, 'opposite', True)

    def test_diagnostic_survey_rejected(self):
        changed = json.loads((self.root / 'original-map.json').read_text())
        changed['diagnostic'] = True
        self.site['original_sources']['map'] = self.write('original-map.json', changed)
        with self.assertRaisesRegex(ValueError, 'independently reviewed'):
            verify(self.root, self.site, 'opposite', True)


if __name__ == '__main__':
    unittest.main()
