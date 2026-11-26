"""Reviewed scene packet and five exact rear-signal bundles."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rear_signal import CASES
from scene_review import TOP, REAR, reviewed_scene
from test_rear_signal import scene as scene_fixture


class BundleTests(unittest.TestCase):
    def packet(self, root):
        data = scene_fixture(CASES[0])
        data.update(format='c150640-reviewed-original-rear-signal-v1',
                    source_kind='original_reviewed', diagnostic_fixture=False,
                    reviewer='fixture-reviewer', case_id=ROOT.name + '__' + CASES[0].case_id,
                    map_id='fixture-map', ego_blueprint_id='vehicle.fixture.ego',
                    rear_blueprint_id='vehicle.fixture.rear',
                    rear_driver_blueprint_id='walker.fixture.driver')
        data['sources'] = {}
        for name in (*TOP, *('rear_' + key for key in REAR), 'map'):
            path = root / (name + '.json')
            path.write_text(json.dumps({'source_role': name}) + '\n')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            data['sources'][name] = {'path': path.name, 'sha256': digest}
        for name in TOP:
            data[name + '_source_sha256'] = data['sources'][name]['sha256']
        for name in REAR:
            data['rear_vehicle'][name + '_source_sha256'] = data['sources']['rear_' + name]['sha256']
        data['map_source_sha256'] = data['sources']['map']['sha256']
        packet = root / 'scene.json'
        packet.write_text(json.dumps(data) + '\n')
        return packet, data

    def test_original_packet_and_hash_tamper(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path, data = self.packet(root)
            self.assertEqual(reviewed_scene(path, data['case_id'])['reviewer'], 'fixture-reviewer')
            (root / 'signal_device.json').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                reviewed_scene(path, data['case_id'])

    def test_reject_diagnostic_or_wrong_case(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path, data = self.packet(root)
            data['diagnostic_fixture'] = True
            path.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original'):
                reviewed_scene(path, data['case_id'])
            data['diagnostic_fixture'] = False
            path.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original'):
                reviewed_scene(path, data['case_id'] + '__wrong')

    def test_five_exact_configs_and_inline_sources(self):
        import author_bundles
        for i, case in enumerate(CASES):
            folder = ROOT if i == 0 else ROOT / 'cases' / case.case_id
            config = json.loads((folder / 'config.json').read_text())
            construction = json.loads((folder / 'construction.json').read_text())
            self.assertEqual(config['selected_case_id'], ROOT.name + '__' + case.case_id)
            self.assertEqual(construction['case_id'], config['selected_case_id'])
            for item in construction['files']:
                if item.get('source'):
                    self.assertEqual(item['content'], (ROOT / item['path']).read_text())
            self.assertEqual(config['cameras'], author_bundles.CAMERAS)


if __name__ == '__main__':
    unittest.main()
