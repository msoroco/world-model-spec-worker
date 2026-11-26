"""Source-bound synthetic checks for the saved taxi measurement."""
import json
import tempfile
import unittest
from pathlib import Path

from selected_finalize import finalize, taxi_loading_measurement


def write_lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


class SavedTaxiMeasurement(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        reviews = ('taxi-license-review.json', 'participant-activity-review.json',
                   'stand-designation-review.json', 'other-regulations-review.json')
        for name in reviews:
            review = {
                'source_basis': 'synthetic source-shaped diagnostic',
                'synthetic_cpu_fixture': True, 'legal_verdict': None}
            if name == 'stand-designation-review.json':
                review['observed_sign_content'] = 'synthetic diagnostic stand sign'
            (self.root / name).write_text(json.dumps(review) + '\n')
        native, mapping, trace, capture, activity = [], [], [], [], []
        for i in range(600):
            frame, time_s = i + 100, (i + 1) / 20
            cameras = {name: frame for name in (
                'overview', 'approach', 'reference_corner', 'driver_reference')}
            native.append({'video_frame': i, 'native_frame': frame,
                           'time_s': time_s, 'taxi_actor_id': 42,
                           'source_cameras': cameras})
            mapping.append({'video_frame': i, 'carla_frame': frame,
                            'time_s': time_s, 'camera_native_frames': cameras})
            trace.append({'frame': frame, 'time_s': time_s, 'taxi_actor_id': 42})
            capture.append({'original_frame': frame, 'recording_time_s': time_s,
                            'actor_id': 42})
            active = 160 <= i < 400
            activity.append({'video_frame': i, 'native_frame': frame,
                'time_s': time_s, 'observed_taxi_identity': True,
                'observed_stand_location': 'outside_designated_stand',
                'observed_speed_mps': 0, 'observed_door_open': active,
                'observed_occupant_count': 2 if i < 400 else 3,
                'observed_activity': 'passenger_loading' if active else 'no_activity'})
        for name, values in (('native-rows.jsonl', native),
                             ('video_frames.jsonl', mapping), ('trace.jsonl', trace),
                             ('capture/evidence.jsonl', capture),
                             ('observed-activity.jsonl', activity)):
            write_lines(self.root / name, values)

    def test_passenger_measurement_and_provenance(self):
        measurement = taxi_loading_measurement(self.root)
        self.assertEqual(measurement['requested_activity'], 'passenger_loading')
        self.assertEqual(measurement['active_frames'], 240)
        self.assertEqual(measurement['source_kind'], 'synthetic_cpu_fixture')
        self.assertNotIn('legal_verdict', measurement)

    def test_missing_activity_source_rejected(self):
        (self.root / 'observed-activity.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source: observed-activity.jsonl'):
            taxi_loading_measurement(self.root)

    def test_changed_frame_identity_rejected(self):
        path = self.root / 'trace.jsonl'
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        entries[200]['frame'] += 1
        write_lines(path, entries)
        with self.assertRaisesRegex(ValueError, 'frame join differs'):
            taxi_loading_measurement(self.root)

    def test_saved_analysis_and_native_result_are_derived(self):
        assignment = 'training__C394327__LVMC-11-60-040__taxi_driver'
        case = assignment + '__probe_a'
        (self.root / 'config.json').write_text(json.dumps({
            'assignment_id': assignment, 'selected_case_id': case}) + '\n')
        channels = [{'name': name, 'unit': 'source observation'} for name in (
            'ru.taxicab', 'st.curb_zone', 'dev.regulatory_sign',
            'drv.standing_or_parked', 'rel.occupies', 'drv.stopped',
            'sig.door_open', 'ru.occupant_count', 'kin.time')]
        contexts = [{'name': name, 'unit': 'source review'} for name in (
            'taxi_license_review', 'stand_designation_review',
            'other_regulations_review')]
        (self.root / 'construction.json').write_text(json.dumps({
            'case_id': case,
            'recording_description': {'channels': channels,
                                      'context_inputs': contexts}}) + '\n')
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            (self.root / (name + '.mkv')).write_bytes(b'synthetic video placeholder')
        report = finalize(self.root, self.root / 'analysis-report.json')
        result = json.loads((self.root / 'result.json').read_text())
        self.assertEqual(report['measurements']['taxi_loading_measurement']['value'][
            'requested_activity'], 'passenger_loading')
        self.assertEqual(result['provenance_kind'], 'synthetic_local_diagnostic')
        self.assertFalse(result['accepted'])
        sign = json.loads((self.root / 'channels/dev.regulatory_sign.jsonl').read_text().splitlines()[0])
        self.assertEqual(sign['value'], 'synthetic diagnostic stand sign')
        self.assertEqual(len(result['recording_evidence']), 9)
        with self.assertRaisesRegex(ValueError, 'fresh saved attempt'):
            finalize(self.root, self.root / 'analysis-report.json')


if __name__ == '__main__':
    unittest.main()
