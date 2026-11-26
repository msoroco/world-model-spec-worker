"""Source-shaped fake Native packet tests; no original evidence claim."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import analysis
from build_draft import rows_for, site_for
from original_runner import REQUIRED


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OriginalAnalysisTests(unittest.TestCase):
    def test_source_shaped_native_history_branch_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'reviewed-site').mkdir()
            sources = {}
            for name in REQUIRED:
                path = root / 'reviewed-site' / name
                path.write_text('fake reviewed-source protocol ' + name + '\n')
                sources[name] = {'path': name, 'sha256': sha(path)}
            adapter = root / 'reviewed-site/native-adapter.py'
            adapter.write_text('fake adapter source\n')
            site = site_for('cross_yield', sources['road.xodr']['sha256'])
            site.update(source_kind='reviewed_original_site', accepted_original_source=True)
            for name, field in (('municipal_jurisdiction', 'municipal_jurisdiction_source'),
                                ('through_highway_designation', 'through_highway_designation_source'),
                                ('intersection_geometry', 'intersection_geometry_source'),
                                ('entrance_control', 'entrance_control_source'),
                                ('antecedent_review', 'antecedent_review_source')):
                site[field] = sources[name]['sha256']
            site_path = root / 'reviewed-site/site-context.json'
            site_path.write_text(json.dumps(site) + '\n')
            manifest_path = root / 'reviewed-site/source-manifest.json'
            manifest_path.write_text(json.dumps({
                'format': 'reviewed-through-highway-site-v1', 'case_id': site['case_id'],
                'site_sha256': sha(site_path), 'reviewer': 'fake protocol test',
                'citation': 'synthetic unit fixture', 'source_kind': 'reviewed_original_site',
                'native_adapter_sha256': sha(adapter), 'sources': sources}) + '\n')
            for name in ('config.json', 'runner.py', 'construction.json'):
                (root / name).write_bytes((HERE / name).read_bytes())
            rows = rows_for('cross_yield', site)
            (root / 'history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            (root / 'camera-frame-map.jsonl').write_text('fake frame map\n')
            (root / 'video_frames.jsonl').write_text('fake video map\n')
            for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
                (root / (name + '.mkv')).write_bytes(b'fake diagnostic video')
            (root / 'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'native', 'diagnostic_fixture': False}) + '\n')
            sealed = [str(path.relative_to(root)) for path in (root / 'reviewed-site').iterdir() if path.is_file()]
            sealed += ['history.jsonl', 'camera-frame-map.jsonl', 'video_frames.jsonl']
            sealed += [name + '.mkv' for name in
                       ('overview', 'approach', 'reference_corner', 'driver_reference')]
            seal = {'case_id': site['case_id'], 'provenance_kind': 'native',
                    'diagnostic_fixture': False, 'frames': 900,
                    'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                    'restoration': {'restored': True},
                    'native_revision': {'construction_sha256': sha(root / 'construction.json'),
                                        'runner_sha256': sha(root / 'runner.py')},
                    'reviewed_manifest_sha256': sha(manifest_path),
                    'reviewed_site_sha256': sha(site_path),
                    'sources': {name: sha(root / name) for name in sealed}}
            (root / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
            report = analysis.analyze(root)
            self.assertFalse(report['diagnostic_fixture'])
            self.assertEqual(report['measurements']['through_highway_interaction']['value']['original_frame_count'], 900)
            self.assertFalse(report['legal_verdict_claimed'])
            (root / 'history.jsonl').write_text('tampered fake history\n')
            with self.assertRaisesRegex(ValueError, 'sealed original Native source changed'):
                analysis.analyze(root)


if __name__ == '__main__':
    unittest.main()
