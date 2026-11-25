import json
import tempfile
import unittest
from pathlib import Path

from test_native_site_measurement import site
from reviewed_site import FIELDS, sha, verify


class ReviewedSiteTests(unittest.TestCase):
    def packet(self, root):
        scene = site()
        bindings = {}
        for field in FIELDS:
            source = root / (field + '.txt')
            source.write_text('reviewed ' + field + '\n', encoding='utf-8')
            digest = sha(source)
            scene[field + '_source_sha256'] = digest
            bindings[field] = {'path': source.name, 'sha256': digest,
                               'citation': 'local reviewed ' + field,
                               'reviewer': 'test reviewer'}
        packet = {'format': 'c143687-reviewed-site-v1', 'review_status': 'reviewed',
                  'reviewer': 'test reviewer', 'diagnostic_fixture': False,
                  'site': scene, 'source_bindings': bindings}
        path = root / 'reviewed-site.json'
        path.write_text(json.dumps(packet), encoding='utf-8')
        return path

    def test_reopens_all_original_source_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.packet(Path(tmp))
            self.assertEqual(len(verify(path)['source_hashes']), len(FIELDS))
            (Path(tmp) / 'sign_wording.txt').write_text('changed', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'bytes absent or changed'):
                verify(path)

    def test_rejects_diagnostic_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.packet(Path(tmp))
            packet = json.loads(path.read_text())
            packet['diagnostic_fixture'] = True
            path.write_text(json.dumps(packet), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'status missing'):
                verify(path)
            packet['diagnostic_fixture'] = False
            packet['source_bindings']['route']['path'] = '../outside.txt'
            path.write_text(json.dumps(packet), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'path invalid'):
                verify(path)
