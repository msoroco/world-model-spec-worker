import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / '.runtime-work'
sys.path.insert(0, str(ROOT))
import runner
from saved_crest_audit import ASSIGNMENT


class RunnerSiteTests(unittest.TestCase):
    def fixture(self, root):
        case_id = ASSIGNMENT + '__early_decrease'
        map_path = root / 'crest.xodr'
        map_path.write_text('<OpenDRIVE/>\n', encoding='utf-8')
        limit_path = root / 'limit.json'
        limit_path.write_text(json.dumps({'road_id': 603,
            'source_kind': 'reviewed_original_limit',
            'prescribed_limit_mps': 15.0}) + '\n', encoding='utf-8')
        site = {'format': 'c104084-reviewed-crest-site-v1',
                'case_id': case_id, 'review_status': 'reviewed_original_source',
                'prescribed_limit_mps': 15.0,
                'map': {'path': map_path.name, 'sha256': hashlib.sha256(map_path.read_bytes()).hexdigest(),
                        'origin': 'reviewed_original'},
                'limit': {'path': limit_path.name,
                          'sha256': hashlib.sha256(limit_path.read_bytes()).hexdigest(),
                          'origin': 'reviewed_original'}}
        site_path = root / 'site.json'
        site_path.write_text(json.dumps(site) + '\n', encoding='utf-8')
        return site_path, case_id

    def test_exact_reviewed_site_cli_preflight_without_carla(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            site, case = self.fixture(Path(temp))
            selected = runner.reviewed_site(site, case)
            self.assertEqual(selected['limit_mps'], 15.0)
            self.assertEqual(selected['map_sha256'], hashlib.sha256((Path(temp) / 'crest.xodr').read_bytes()).hexdigest())
            self.assertEqual(runner.main(['--case', case, '--site', str(site),
                '--attempt', str(Path(temp) / 'attempt'),
                '--scratch-root', str(Path(temp)), '--capture-ref', 'native-001',
                '--check']), 0)

    def test_rejects_wrong_case_and_changed_original_sources(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            site, case = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'exact reviewed'):
                runner.reviewed_site(site, ASSIGNMENT + '__late_decrease')
            (root / 'crest.xodr').write_text('changed\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runner.reviewed_site(site, case)
            site, case = self.fixture(root)
            (root / 'limit.json').write_text('changed\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runner.reviewed_site(site, case)

    def test_rejects_unreviewed_and_inapplicable_limit(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            site, case = self.fixture(root)
            packet = json.loads(site.read_text())
            packet['review_status'] = 'draft'
            site.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'independent original source review'):
                runner.reviewed_site(site, case)
            site, case = self.fixture(root)
            limit = root / 'limit.json'
            limit.write_text(json.dumps({'road_id': 999,
                'source_kind': 'reviewed_original_limit',
                'prescribed_limit_mps': 15.0}) + '\n')
            packet = json.loads(site.read_text())
            packet['limit']['sha256'] = hashlib.sha256(limit.read_bytes()).hexdigest()
            site.write_text(json.dumps(packet) + '\n')
            with self.assertRaisesRegex(ValueError, 'does not bind'):
                runner.reviewed_site(site, case)


if __name__ == '__main__':
    unittest.main()
