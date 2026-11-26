"""Source packet and exact bundle CPU checks."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from access_aisle import CASES
from site_review import OPTIONAL_SIGN, REQUIRED, reviewed_site
from test_access_aisle import site as site_fixture


class BundleTests(unittest.TestCase):
    def packet(self, root):
        data = site_fixture()
        data.update(format='c150072-reviewed-original-aisle-v1',
                    source_kind='original_reviewed', diagnostic_fixture=False,
                    reviewer='fixture-reviewer', case_id=ROOT.name + '__' + CASES[0].case_id)
        data['sources'] = {}
        for name in REQUIRED + OPTIONAL_SIGN:
            path = root / (name + '.json')
            path.write_text(json.dumps({'source_role': name}) + '\n')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            data['sources'][name] = {'path': path.name, 'sha256': digest}
        for name in ('jurisdiction', 'map', 'aisle_marking', 'adjacent_designated_space',
                     'accessible_route', 'ingress_egress_design', 'vehicle_blueprint',
                     'approach_route', *OPTIONAL_SIGN):
            data[name + '_source_sha256'] = data['sources'][name]['sha256']
        for name in ('aisle_full', 'aisle_partial', 'adjacent_space'):
            data['target_footprints'][name]['source_sha256'] = data['sources']['target_' + name]['sha256']
        packet = root / 'site.json'
        packet.write_text(json.dumps(data) + '\n')
        return packet, data

    def test_original_packet_and_hash_tamper(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path, data = self.packet(root)
            self.assertEqual(reviewed_site(path, data['case_id'])['reviewer'], 'fixture-reviewer')
            (root / 'aisle_marking.json').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                reviewed_site(path, data['case_id'])

    def test_reject_diagnostic_or_wrong_case(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path, data = self.packet(root)
            data['diagnostic_fixture'] = True
            path.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original'):
                reviewed_site(path, data['case_id'])
            data['diagnostic_fixture'] = False
            path.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original'):
                reviewed_site(path, data['case_id'] + '__wrong')

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
