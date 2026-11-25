import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

AUDIT_PATH = Path(__file__).resolve().parents[2] / 'audit_branch_comparison.py'
spec = importlib.util.spec_from_file_location('audit_branch_comparison', AUDIT_PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class BranchComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.base = self.make('base', 'stopped', 'none')

    def make(self, name, activity, exception, traffic=False):
        folder = self.root / name
        folder.mkdir()
        (folder / 'road.xodr').write_text('<OpenDRIVE/>\n')
        (folder / 'acquisition-provenance.json').write_text('{"source_kind":"synthetic_diagnostic"}\n')
        (folder / 'video_frames.jsonl').write_text(''.join(
            json.dumps({'native_frame': i, 'video_frame': i, 'time_s': i / 20}) + '\n'
            for i in range(600)))
        context = {'source_kind': 'synthetic_diagnostic', 'cell_id': 'C229410',
                   'entrance': {'x_min_m': -3, 'x_max_m': 3, 'road_side': 'south'},
                   'fire_station_identity_reviewed': False,
                   'driveway_entrance_reviewed': False,
                   'highway_side_reviewed': False,
                   'initial_activity': activity, 'exception_context': exception,
                   'applicable_law_source_reviewed': exception == 'law',
                   'police_direction_source_observed': exception == 'police_officer',
                   'official_device_source_observed': exception == 'official_device'}
        (folder / 'entrance-context.json').write_text(json.dumps(context) + '\n')
        other = {'actor_id': 2, 'body_xy_m': [[1, 1]] * 4} if traffic else None
        rows = ({'native_frame': i, 'video_frame': i, 'time_s': i / 20,
                 'actor_id': 1, 'blueprint_id': 'vehicle.test',
                 'center_xy_m': [3, -2], 'body_xy_m': [[2, -3]] * 4,
                 'speed_mps': 0, 'traffic_conflict_vehicle': other} for i in range(600))
        (folder / 'native-vehicle.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        return folder

    def test_activity_and_traffic_contrasts(self):
        standing = self.make('standing', 'standing', 'none')
        traffic = self.make('traffic', 'stopped', 'traffic_conflict', traffic=True)
        self.assertTrue(audit.compare(self.base, standing, 'activity')['passed'])
        self.assertTrue(audit.compare(self.base, traffic, 'traffic_conflict')['passed'])

    def test_direction_contexts_are_only_synthetic_proofs(self):
        for name, exception in (('law', 'law'), ('police', 'police_officer'),
                                ('device', 'official_device')):
            with self.subTest(name=name):
                variant = self.make(name, 'stopped', exception)
                result = audit.compare(self.base, variant, exception)
                self.assertEqual(result['source_kind'], 'synthetic_diagnostic')
                self.assertFalse(result['physical_or_legal_result_claimed'])

    def test_changed_motion_rejected(self):
        standing = self.make('standing', 'standing', 'none')
        rows = (standing / 'native-vehicle.jsonl').read_text().splitlines()
        changed = json.loads(rows[200])
        changed['center_xy_m'] = [4, -2]
        rows[200] = json.dumps(changed)
        (standing / 'native-vehicle.jsonl').write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'Ego motion'):
            audit.compare(self.base, standing, 'activity')

    def test_missing_traffic_actor_rejected(self):
        variant = self.make('traffic', 'stopped', 'traffic_conflict')
        with self.assertRaisesRegex(ValueError, 'Independent traffic actor'):
            audit.compare(self.base, variant, 'traffic_conflict')

    def test_missing_direction_source_rejected(self):
        variant = self.make('police', 'stopped', 'police_officer')
        context_path = variant / 'entrance-context.json'
        context = json.loads(context_path.read_text())
        context['police_direction_source_observed'] = False
        context_path.write_text(json.dumps(context) + '\n')
        with self.assertRaisesRegex(ValueError, 'Police direction source'):
            audit.compare(self.base, variant, 'police_officer')

    def test_original_direction_source_and_actor_time_join(self):
        variant = self.make('original', 'stopped', 'police_officer')
        authority = variant / 'authority'
        authority.mkdir()
        sources = {}
        for name in ('station_identity', 'driveway_entrance', 'highway_boundary'):
            path = authority / (name + '.source')
            path.write_text(name + '\n')
            sources[name] = {'sha256': audit.sha(path)}
        command = {'police_officer': {'source_id': 'order-1', 'issued_by': 'officer-3',
                   'directed_action': 'stop', 'actor_id': 3,
                   'valid_time': {'start_s': 24, 'end_s': 30}}}
        path = authority / 'activity_and_directions.source'
        path.write_text(json.dumps(command) + '\n')
        sources['activity_and_directions'] = {'sha256': audit.sha(path)}
        manifest = authority / 'manifest.json'
        manifest.write_text(json.dumps({'sources': sources}) + '\n')
        context = json.loads((variant / 'entrance-context.json').read_text())
        context.update({'authority_manifest_sha256': audit.sha(manifest),
                        'authority_source_sha256': {key: item['sha256']
                        for key, item in sources.items()}})
        rows = audit.load_rows(variant / 'native-vehicle.jsonl')
        for row in rows[-100:]:
            row['direction_source_actor_ids'] = [3]
        self.assertEqual(audit.original_direction_record(variant, context,
                         'police_officer', rows)['source_id'], 'order-1')
        rows[-1]['direction_source_actor_ids'] = []
        with self.assertRaisesRegex(ValueError, 'not joined'):
            audit.original_direction_record(variant, context, 'police_officer', rows)
        rows[-1]['direction_source_actor_ids'] = [3]
        command['police_officer']['valid_time']['end_s'] = 25
        path.write_text(json.dumps(command) + '\n')
        with self.assertRaisesRegex(ValueError, 'source missing or changed'):
            audit.original_direction_record(variant, context, 'police_officer', rows)


if __name__ == '__main__':
    unittest.main()
