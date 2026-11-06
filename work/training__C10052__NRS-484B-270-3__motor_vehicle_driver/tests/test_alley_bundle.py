"""Portable CPU checks for the exact alley-entry bundle."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from alley_engineering import parameters, TRIGGERS
from alley_geometry import check as geometry_check, route
from runner import check as runner_check
from measure_alley_triggers import evaluate as evaluate_triggers, sha as trigger_sha


class AlleyBundleTests(unittest.TestCase):
    def test_exact_runner_preflight(self):
        config = json.loads((ROOT/'config.json').read_text())
        result = runner_check(config)
        self.assertEqual(result['candidate'], config['candidate_id'])
        self.assertEqual(result['camera_count'], 4)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['physical_success_claimed'])

    def test_candidate_changes_are_distinct(self):
        primary = parameters('primary')
        changes = []
        for name in ('fallback1', 'fallback2', 'fallback3'):
            candidate = parameters(name)
            changes.append(frozenset(k for k in primary if candidate[k] != primary[k]))
            self.assertTrue(all(TRIGGERS[name][key] for key in
                                ('source', 'metric', 'failure_condition', 'changed_knobs')))
        self.assertEqual(len(set(changes)), 3)

    def test_authored_turn_and_routes(self):
        self.assertTrue(geometry_check())
        self.assertGreater(len(route(-55.0)), len(route(-45.0)))
        self.assertNotEqual(route(-55.0)[0], route(-45.0)[0])

    def test_source_hashed_trigger_path_and_tamper_negative(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            poses = []
            views = []
            for i in range(480):
                frame = 100+i
                time_s = (i+1)/20
                poses.append({'native_frame': frame, 'time_s': time_s,
                    'phase': 'turn' if 200 <= i < 280 else 'approach',
                    'speed_mps': 2.5, 'native_center_xy_m': [-40.0, -1.5],
                    'synthetic_diagnostic': True})
                views.append({'native_frame': frame, 'time_s': time_s,
                    'visible': True, 'synthetic_diagnostic': True})
            (folder/'turn_samples.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in poses))
            (folder/'turn_visibility.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in views))
            (folder/'turn_geometry.json').write_text(json.dumps({
                'turn_radius_m': 5.0, 'turn_start_x_m': 0.0}))
            names = ('turn_samples.jsonl','turn_geometry.json','turn_visibility.jsonl')
            (folder/'alley-trigger-sources.json').write_text(json.dumps({
                'format': 'c10052-alley-trigger-sources-v1',
                'source_kind': 'synthetic_cpu_fixture',
                'sha256': {name: trigger_sha(folder/name) for name in names}}))
            result = evaluate_triggers(folder)
            self.assertEqual(result['approach_runway_m'], 40.0)
            self.assertEqual(result['peak_lateral_accel_proxy_mps2'], 1.25)
            self.assertEqual(result['turn_visibility_fraction'], 1.0)
            self.assertFalse(any(result[f'fallback{i}_trigger_measured'] for i in (1,2,3)))
            (folder/'turn_visibility.jsonl').write_text(
                (folder/'turn_visibility.jsonl').read_text()+' ')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                evaluate_triggers(folder)


if __name__ == '__main__':
    unittest.main()
