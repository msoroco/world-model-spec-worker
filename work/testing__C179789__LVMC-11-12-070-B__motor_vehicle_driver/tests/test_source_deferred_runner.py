"""Focused checks for original Native source gating and exact preflight."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import source_deferred_runner as runner
from original_runner import REQUIRED, load_reviewed_site


class RunnerTests(unittest.TestCase):
    def test_root_selected_preflight(self):
        case_id, name = runner.check(HERE)
        self.assertEqual(case_id, HERE.name + '__' + name)
        self.assertEqual(name, 'cross_yield')

    def test_missing_reviewed_packet_fails_before_native_use(self):
        class Adapter:
            def provenance(self):
                raise AssertionError('Native adapter reached before reviewed source gate')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('construction.json', 'runner.py', 'config.json'):
                (root / name).write_text(name + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original site packet missing'):
                runner.capture_original(Adapter(), root / 'missing-manifest.json',
                                        root / 'missing-site.json', root, HERE)

    def test_synthetic_packet_rejected_for_original_capture(self):
        class Adapter:
            def provenance(self):
                raise AssertionError('Native adapter reached with synthetic source')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('construction.json', 'runner.py', 'config.json'):
                (root / name).write_text(name + '\n')
            site = json.loads((HERE / 'scene.json').read_text())
            (root / 'site.json').write_text(json.dumps(site) + '\n')
            (root / 'manifest.json').write_text(json.dumps({
                'format': 'reviewed-through-highway-site-v1',
                'case_id': HERE.name + '__cross_yield',
                'source_kind': 'synthetic_diagnostic_fixture'}) + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original site identity/provenance missing'):
                runner.capture_original(Adapter(), root / 'manifest.json',
                                        root / 'site.json', root, HERE)

    def test_reviewed_packet_is_source_hashed_and_case_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {}
            for name in REQUIRED:
                path = root / name
                path.write_text('reviewed source ' + name + '\n')
                sources[name] = {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            site = json.loads((HERE / 'scene.json').read_text())
            site.update(source_kind='reviewed_original_site', accepted_original_source=True,
                        map_sha256=sources['road.xodr']['sha256'])
            for name, field in (('municipal_jurisdiction', 'municipal_jurisdiction_source'),
                                ('through_highway_designation', 'through_highway_designation_source'),
                                ('intersection_geometry', 'intersection_geometry_source'),
                                ('entrance_control', 'entrance_control_source'),
                                ('antecedent_review', 'antecedent_review_source')):
                site[field] = sources[name]['sha256']
            site_path = root / 'site.json'
            site_path.write_text(json.dumps(site) + '\n')
            manifest = {'format': 'reviewed-through-highway-site-v1',
                        'case_id': HERE.name + '__cross_yield', 'reviewer': 'fixture reviewer',
                        'citation': 'synthetic protocol test only', 'source_kind': 'reviewed_original_site',
                        'site_sha256': hashlib.sha256(site_path.read_bytes()).hexdigest(),
                        'sources': sources}
            manifest_path = root / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest) + '\n')
            self.assertEqual(load_reviewed_site(manifest_path, site_path, manifest['case_id'])['case_id'], manifest['case_id'])
            (root / 'antecedent_review').write_text('changed source\n')
            with self.assertRaisesRegex(ValueError, 'source seal changed'):
                load_reviewed_site(manifest_path, site_path, manifest['case_id'])


if __name__ == '__main__':
    unittest.main()
