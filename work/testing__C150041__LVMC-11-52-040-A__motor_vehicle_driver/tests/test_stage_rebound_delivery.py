"""Canonical staging uses synthetic retained packets only as protocol fixtures."""
import json
import hashlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rebind_reviewed_execution import rebind
import stage_rebound_delivery
from stage_rebound_delivery import install, reviewed_fixture_spec, stage
from test_bind_reviewed_site import pair


class CanonicalStageTests(unittest.TestCase):
    def test_fixture_telemetry_rebases_to_reviewed_scene(self):
        path = ROOT / 'diagnostic/park_parallel_lawful/saved-fixture-spec.json'
        original = json.loads(path.read_text())
        scene = {'target_pose': {'target_body_vertices_xy_m': [
            [10.0, 4.0], [14.0, 4.0], [14.0, 6.0], [10.0, 6.0]],
            'target_forward_xy': [0.0, 1.0]}}
        spec = reviewed_fixture_spec(original, scene, '<OpenDRIVE><road id="9"/></OpenDRIVE>')
        history = [json.loads(line) for line in spec['files']['parking-history.jsonl'].splitlines()]
        trace = [json.loads(line) for line in spec['files']['trace.jsonl'].splitlines()]
        evidence = [json.loads(line) for line in spec['files']['capture/evidence.jsonl'].splitlines()]
        self.assertTrue(all(row['body_vertices_xy_m'] == scene['target_pose']['target_body_vertices_xy_m']
                            for row in history))
        self.assertTrue(all(row['position_m'] == [12.0, 5.0, 0.0] for row in trace))
        self.assertTrue(all(row['ego']['position_m'] == [12.0, 5.0, 0.0]
                            for row in evidence))
        self.assertIn('road id="9"', spec['files']['road.xodr'])

    def test_twelve_bundles_and_no_stale_proof_claims(self):
        with TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as name:
            root = Path(name)
            packets = pair(root)
            rebound = root / 'rebound'
            rebind(packets['park'], packets['stand'], rebound)
            staged = root / 'staged'
            receipt_path = stage(rebound, staged)
            receipt = json.loads(receipt_path.read_text())
            manifest = json.loads((staged / 'execution-manifest.json').read_text())
            self.assertEqual(len(receipt['constructions']), 32)
            self.assertFalse(receipt['original_review_claimed'])
            self.assertFalse(receipt['delivery_ready_claimed'])
            self.assertEqual(len(manifest['cases']), 16)
            for entry in manifest['cases']:
                self.assertNotIn('offline', entry)
                self.assertNotIn('compatibility', entry)
                expected = {
                    'body_vertices_xy_m', 'vehicle_forward_xy', 'speed_m_s',
                    'control', 'camera_frame_map'}
                if 'orientation_sweep-' in entry['case_id']:
                    expected.add('parallel_deviation_deg')
                self.assertEqual(set(entry['acquisition']), expected)
                self.assertEqual(entry['acquisition']['body_vertices_xy_m']['method'],
                                 'capture_frame')
                self.assertEqual(entry['acquisition']['camera_frame_map']['method'],
                                 'capture_ticks')
                for selected in (entry, entry['candidates'][0]):
                    path = staged / selected['construction']
                    self.assertTrue(path.is_file())
                    names = {item['path'] for item in json.loads(path.read_text())['files']}
                    self.assertNotIn('reviewed-context.json', names)
                    self.assertFalse(any(name.startswith('reviewed_sources/') for name in names))
                recipe = json.loads((staged / entry['fixture_recipe'].removeprefix(
                    'work/' + ROOT.name + '/')).read_text())
                self.assertIn('reviewed-context.json', {item['path'] for item in recipe['sources']})
            with self.assertRaisesRegex(ValueError, 'fresh staging output'):
                stage(rebound, staged)
            mirror = root / 'mirror' / 'work' / ROOT.name
            mirror.mkdir(parents=True)
            original_temp = stage_rebound_delivery.tempfile.NamedTemporaryFile
            temporary_dirs = []
            def scratch_temp(*args, **kwargs):
                temporary_dirs.append(Path(kwargs['dir']).resolve())
                return original_temp(*args, **kwargs)
            with patch.object(stage_rebound_delivery.tempfile,
                              'NamedTemporaryFile', side_effect=scratch_temp):
                installed = install(staged, packets['park'], packets['stand'], mirror)
            self.assertTrue(temporary_dirs)
            self.assertEqual(set(temporary_dirs), {ROOT.parents[1] / '.runtime-work'})
            self.assertEqual(installed, mirror / 'execution-manifest.json')
            self.assertEqual(len(list((mirror / 'diagnostic' / 'reviewed').rglob('primary.json'))), 16)
            self.assertEqual(len(list((mirror / 'diagnostic' / 'reviewed').rglob('fallback1.json'))), 16)
            self.assertEqual(len(list((mirror / 'diagnostic' / 'reviewed').rglob('fixture-recipe.json'))), 16)
            self.assertEqual(installed.parents[2], root / 'mirror')
            changed = root / 'changed-packet.json'
            changed.write_text('{}\n')
            with self.assertRaises(ValueError):
                install(staged, changed, packets['stand'], mirror)

    def test_changed_rebound_construction_is_rejected(self):
        with TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as name:
            root = Path(name)
            packets = pair(root)
            rebound = root / 'rebound'
            rebind(packets['park'], packets['stand'], rebound)
            receipt = json.loads((rebound / 'rebound-manifest.json').read_text())
            target = rebound / receipt['cases'][0]['variants'][0]['construction']
            target.write_text(target.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'construction or packet seal differs'):
                stage(rebound, root / 'staged')
            self.assertFalse((root / 'staged').exists())

    def test_late_staged_artifact_rejected_before_any_publication(self):
        with TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as name:
            root = Path(name)
            packets = pair(root)
            rebound = root / 'rebound'
            rebind(packets['park'], packets['stand'], rebound)
            staged = root / 'staged'
            receipt = json.loads(stage(rebound, staged).read_text())
            late = staged / receipt['artifacts'][-1]['path']
            late.write_text(late.read_text() + '\n')
            mirror = root / 'mirror' / 'work' / ROOT.name
            mirror.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'staged artifact changed'):
                install(staged, packets['park'], packets['stand'], mirror)
            self.assertEqual(list(mirror.rglob('*')), [])

    def test_stale_runtime_manifest_rejected_before_publication(self):
        with TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as name:
            root = Path(name)
            packets = pair(root)
            rebound = root / 'rebound'
            rebind(packets['park'], packets['stand'], rebound)
            staged = root / 'staged'
            receipt_path = stage(rebound, staged)
            manifest_path = staged / 'execution-manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['runtime_manifest_sha256'] = '0' * 64
            manifest_path.write_text(json.dumps(manifest) + '\n')
            receipt = json.loads(receipt_path.read_text())
            receipt['manifest_sha256'] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            receipt_path.write_text(json.dumps(receipt) + '\n')
            mirror = root / 'mirror' / 'work' / ROOT.name
            mirror.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, 'inventory differs'):
                install(staged, packets['park'], packets['stand'], mirror)
            self.assertEqual(list(mirror.rglob('*')), [])


if __name__ == '__main__':
    unittest.main()
