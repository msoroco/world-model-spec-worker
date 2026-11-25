"""Independent comparison proof from original diagnostic event packets."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import original_capture
import prove_comparison
import test_original_capture as capture_fixture


class SourceComparisonTest(unittest.TestCase):
    def attempt(self, suffix):
        fixture = capture_fixture.OriginalCaptureTest('test_full_capture_seals_original_trace_for_existing_measurement')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root, site = fixture.root, fixture.site
        site['case_id'] = ROOT.name + '__' + suffix
        rows = fixture.rows()
        if suffix == 'one_cycle_entry':
            for row in rows[300:400]:
                row['lit_aspects'] = ['steady_red', 'green_turn_arrow']
        if suffix == 'three_cycles_clear':
            for row in rows[500:600]:
                row['lit_aspects'] = ['steady_red']
            for row in rows[600:700]:
                row['ego_front_station_m'], row['speed_mps'] = -6, 0
        if suffix == 'rolling_entry':
            for row in rows[:600]:
                row['speed_mps'] = 1
        if suffix == 'no_causal_record':
            site['original_sources'].pop('cause_ref')
            site['cause_source_ref'] = None
            site['unchanged_signal_cause'] = 'not_established'
        if suffix == 'pedestrian_crosswalk':
            rows[700]['other_users'] = [{'actor_id': 'ped-1', 'region': 'adjacent_crosswalk',
                                        'source_kind': 'native_world_snapshot'}]
        if suffix == 'lawful_traffic':
            rows[700]['other_users'] = [{'actor_id': 'car-1', 'region': 'intersection',
                                        'source_kind': 'native_world_snapshot'}]
        (root / 'native-site.json').write_text(json.dumps(site) + '\n', encoding='utf-8')
        receipt = original_capture.capture_original(site, root, capture_fixture.Adapter(rows),
                                                     root / 'original-events.json', diagnostic_fixture=True)
        refs = site['original_sources']
        sources = {'original_events': receipt['event_ref'], 'map': refs['map_ref'],
                   'route': refs['route_ref'], 'signal': refs['signal_ref'],
                   'stop_reference': refs['stop_ref'], 'crosswalk': refs['crosswalk_ref']}
        if suffix != 'no_causal_record':
            sources['cause'] = refs['cause_ref']
        views = {}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            views[name] = {'source': capture_fixture.source(root, name + '.txt', {'view': name}),
                           'decoded_frames': 900, 'fps': 20, 'width': 64, 'height': 64,
                           'first_original_frame': 0, 'last_original_frame': 899}
        manifest = {'assignment_id': ROOT.name, 'case_id': site['case_id'],
                    'law_id': 'NRS-484B-307-9b', 'actor': 'motorcycle_or_moped_operator',
                    'fps': 20, 'duration_frames': 900, 'sources': sources,
                    'official_head_id': 'head-17', 'actor_id': 'ego-1',
                    'camera_views': views, 'pixel_review_status': 'pending'}
        if suffix == 'no_causal_record':
            manifest['cause_status'] = 'not_established'
        (root / 'saved-manifest.json').write_text(json.dumps(manifest) + '\n', encoding='utf-8')
        return root

    def test_every_declared_pair_uses_original_attempts(self):
        baseline = self.attempt('two_cycles_clear')
        for suffix, name in (('one_cycle_entry', 'complete_cycle_count'),
                             ('three_cycles_clear', 'complete_cycle_count_above'),
                             ('rolling_entry', 'stopping_event'),
                             ('no_causal_record', 'causal_record'),
                             ('pedestrian_crosswalk', 'crosswalk_yield'),
                             ('lawful_traffic', 'intersection_yield')):
            with self.subTest(name=name):
                right = self.attempt(suffix)
                proof = prove_comparison.prove(name, baseline, right)
                self.assertTrue(proof['passed'])
                self.assertFalse(proof['physical_acceptance'])
                self.assertIsNone(proof['legal_verdict'])

    def test_missing_and_changed_original_sources_rejected(self):
        baseline = self.attempt('two_cycles_clear')
        other = self.attempt('one_cycle_entry')
        (other / 'signal_ref.json').write_text('{"tampered":true}\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            prove_comparison.prove('complete_cycle_count', baseline, other)


if __name__ == '__main__':
    unittest.main()
