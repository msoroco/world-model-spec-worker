import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import original_capture
import saved_measurement
import signal_exception


def source(root, name, body):
    path = root / name
    path.write_text(json.dumps(body), encoding='utf-8')
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class Adapter:
    def __init__(self, rows):
        self.rows = iter(rows)

    def tick(self):
        return next(self.rows)


class OriginalCaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        refs = {key: source(self.root, key + '.json', {'source': key}) for key in
                ('map_ref', 'route_ref', 'signal_ref', 'stop_ref', 'crosswalk_ref')}
        refs['cause_ref'] = source(self.root, 'cause.json', {
            'official_head_id': 'head-17', 'actor_type_id': 'vehicle.motorcycle',
            'classification': 'failed_detection', 'source_method': 'native_detector_readback',
            'original_frame_start': 0, 'original_frame_end': 900})
        self.site = {
            'cell_id': 'C111125', 'actor': 'motorcycle_or_moped_operator',
            'maneuver': 'straight', 'control': 'traffic_light',
            'original_sources': refs, 'map_ref': 'map_ref', 'route_ref': 'route_ref',
            'signal_ref': 'signal_ref', 'stop_ref': 'stop_ref', 'crosswalk_ref': 'crosswalk_ref',
            'cause_source_ref': 'cause_ref', 'unchanged_signal_cause': 'failed_detection',
            'ego_approach_id': 'approach-west', 'official_head_id': 'head-17',
            'facing_relation': True, 'route_xy': [[-20, 0], [-5, 0], [5, 0], [20, 0]],
            'straight_tolerance_m': 0.5, 'stop_reference_kind': 'marked_stop_line',
            'stop_reference_station_m': -5, 'intersection_entry_station_m': 0,
            'ego_blueprint_id': 'vehicle.motorcycle', 'ego_classification_source': 'source-17',
        }

    def rows(self):
        rows = []
        for frame in range(900):
            if frame < 100:
                phase = ['steady_red', 'green_turn_arrow']
            elif frame < 200:
                phase = ['steady_red']
            elif frame < 300:
                phase = ['steady_red', 'green_turn_arrow']
            elif frame < 400:
                phase = ['steady_red']
            else:
                phase = ['steady_red', 'green_turn_arrow']
            rows.append({
                'frame': frame, 'time_s': frame * 0.05,
                'source_kind': 'native_world_snapshot',
                'official_head_id': 'head-17', 'facing_approach_id': 'approach-west',
                'actor_id': 'ego-1', 'actor_type_id': 'vehicle.motorcycle',
                'lit_aspects': phase, 'ego_front_station_m': -6 if frame < 600 else 1,
                'speed_mps': 0 if frame < 600 else 3, 'other_users': [],
            })
        return rows

    def test_full_capture_seals_original_trace_for_existing_measurement(self):
        receipt = original_capture.capture_original(self.site, self.root, Adapter(self.rows()),
                                                    self.root / 'original-events.json', diagnostic_fixture=True)
        self.assertEqual(receipt['frame_count'], 900)
        self.assertTrue(receipt['diagnostic_fixture'])
        self.assertFalse(receipt['physical_acceptance_claimed'])
        measurement = signal_exception.measure_attempt(self.site, self.root, receipt['event_ref'])
        self.assertEqual(measurement['full_cycles_after_stop'], 2)
        self.assertEqual(measurement['entry_frame'], 600)
        (self.root / 'original-events.json').write_text('[]', encoding='utf-8')
        with self.assertRaisesRegex(signal_exception.SourceError, 'source hash mismatch'):
            signal_exception.measure_attempt(self.site, self.root, receipt['event_ref'])

    def test_rejects_gap_before_writing(self):
        rows = self.rows()
        rows[101]['frame'] = 103
        out = self.root / 'failed.json'
        with self.assertRaisesRegex(signal_exception.SourceError, 'Native frame gap'):
            original_capture.capture_original(self.site, self.root, Adapter(rows), out)
        self.assertFalse(out.exists())

    def test_rejects_non_native_or_missing_participant_inventory(self):
        rows = self.rows()
        rows[0]['source_kind'] = 'authored_target'
        with self.assertRaisesRegex(signal_exception.SourceError, 'non-Native'):
            original_capture.capture_original(self.site, self.root, Adapter(rows), self.root / 'a.json')
        rows = self.rows()
        rows[50].pop('other_users')
        with self.assertRaisesRegex(signal_exception.SourceError, 'other-user'):
            original_capture.capture_original(self.site, self.root, Adapter(rows), self.root / 'b.json')

    def test_rejects_rate_drift_and_substituted_actor(self):
        rows = self.rows()
        rows[40]['time_s'] += 0.02
        with self.assertRaisesRegex(signal_exception.SourceError, '20 Hz'):
            original_capture.capture_original(self.site, self.root, Adapter(rows), self.root / 'a.json')
        rows = self.rows()
        rows[40]['actor_id'] = 'ego-2'
        with self.assertRaisesRegex(signal_exception.SourceError, 'ego actor changed'):
            original_capture.capture_original(self.site, self.root, Adapter(rows), self.root / 'b.json')

    def test_saved_join_uses_same_sealed_events_and_site(self):
        rows = self.rows()
        rows[510]['other_users'] = [{'actor_id': 'ped-1', 'region': 'adjacent_crosswalk',
                                   'source_kind': 'native_world_snapshot'}]
        receipt = original_capture.capture_original(self.site, self.root, Adapter(rows),
                                                    self.root / 'original-events.json', diagnostic_fixture=True)
        refs = self.site['original_sources']
        sources = {'original_events': receipt['event_ref'], 'map': refs['map_ref'],
                   'route': refs['route_ref'], 'signal': refs['signal_ref'],
                   'stop_reference': refs['stop_ref'], 'crosswalk': refs['crosswalk_ref'],
                   'cause': refs['cause_ref']}
        views = {}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            views[name] = {'source': source(self.root, name + '.txt', 'diagnostic camera inventory'),
                           'decoded_frames': 900, 'fps': 20, 'width': 64, 'height': 64,
                           'first_original_frame': 0, 'last_original_frame': 899}
        manifest = {'assignment_id': saved_measurement.ASSIGNMENT_ID,
                    'case_id': saved_measurement.ASSIGNMENT_ID + '__pedestrian_crosswalk',
                    'law_id': 'NRS-484B-307-9b', 'actor': 'motorcycle_or_moped_operator',
                    'fps': 20, 'duration_frames': 900, 'sources': sources,
                    'official_head_id': 'head-17', 'actor_id': 'ego-1',
                    'camera_views': views, 'pixel_review_status': 'pending'}
        out = self.root / 'measurement.json'
        result = saved_measurement.process_saved(self.site, self.root, manifest, out)
        self.assertEqual(result['measurement']['full_cycles_after_stop'], 2)
        self.assertEqual(result['other_user_region'], 'adjacent_crosswalk')
        self.assertEqual(result['lawful_participant_status'], 'unresolved')
        self.assertFalse(result['physical_acceptance'])
        self.assertTrue(out.is_file())
        out.unlink()
        bad = dict(manifest, sources=dict(sources, map=refs['route_ref']))
        with self.assertRaisesRegex(signal_exception.SourceError, 'site/acquisition source mismatch'):
            saved_measurement.process_saved(self.site, self.root, bad, out)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
