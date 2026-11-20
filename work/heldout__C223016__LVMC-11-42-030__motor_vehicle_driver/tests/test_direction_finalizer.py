"""Source-join and negative controls for C223016 saved direction analysis."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'scenario_pipeline'))
from direction_finalizer import analyze, build_result
from runner import check_config
from batch_pipeline.validation import recording_evidence


PREFIX = 'heldout__C223016__LVMC-11-42-030__motor_vehicle_driver__'


def fixture(root, *, suffix='morning_east_with', velocity=(5, 0)):
    config = {'selected_case_id': PREFIX + suffix, 'cell_id': 'C223016',
              'law_id': 'LVMC-11-42-030', 'actor': 'motor_vehicle_driver',
              'governed_lane_id': -1,
              'case': {'recording_description': {'channels': [
                  {'name': 'observed_direction', 'unit': 'category'}]}}}
    (root / 'config.json').write_text(json.dumps(config))
    rows, mapping, trace = [], [], []
    base_time = datetime(2026, 11, 19, 8, 0, tzinfo=timezone(timedelta(hours=-8)))
    for index in range(4):
        frame, stamp = 100 + index, index * .05
        rows.append({'frame': frame, 'time_s': stamp, 'lane_id': -1,
                     'civil_time': {'source': 'Native capture clock',
                                    'iso8601': (base_time + timedelta(seconds=stamp)).isoformat()},
                     'device': {'kind': 'barrier', 'governs_lane_id': -1,
                                'source_id': 'native-device-7',
                                'period_id': 'morning', 'effective': True,
                                'direction_xy': [1, 0]},
                     'subject_velocity_xy': list(velocity)})
        mapping.append({'video_frame': index, 'carla_frame': frame, 'time_s': stamp})
        trace.append({'frame': frame, 'time_s': stamp})
    for name, data in (('direction_state.jsonl', rows),
                       ('video_frames.jsonl', mapping), ('trace.jsonl', trace)):
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in data))
    return rows, mapping


class DirectionFinalizerTests(unittest.TestCase):
    def test_first_case_runner_rejects_wrong_period_and_identity(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        self.assertTrue(check_config(config))
        config['period_id'] = 'evening'
        with self.assertRaisesRegex(ValueError, 'first exact case'):
            check_config(config)
        config['period_id'] = 'morning'
        config['selected_case_id'] = PREFIX + 'morning_west_against'
        with self.assertRaisesRegex(ValueError, 'first exact C223016'):
            check_config(config)

    def test_fallback_knob_bounds(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        for knob, invalid in [('spawn_candidate_index', -1),
                              ('device_forward_m', 3), ('speed_kp', .8)]:
            changed = dict(config, **{knob: invalid})
            with self.assertRaises(ValueError):
                check_config(changed)
        for knob, value in [('spawn_candidate_index', 1),
                            ('device_forward_m', 6), ('speed_kp', .12)]:
            self.assertTrue(check_config(dict(config, **{knob: value})))

    def test_positive_saved_join_stays_legally_unresolved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root)
            report = analyze(root, write_channels=True)
            result = build_result(root, report)
            self.assertEqual(report['measurements']['reversible_direction']['value']['direction'],
                             'with_designation')
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertFalse(result['legal_acceptance_claimed'])
            self.assertEqual(len(result['video_references']), 4)
            with self.assertRaisesRegex(ValueError, 'Retain prior'):
                analyze(root, write_channels=True)

    def test_full_planned_channel_evidence_validates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root)
            source = Path(__file__).resolve().parents[1] / 'config.json'
            root.joinpath('config.json').write_bytes(source.read_bytes())
            report = analyze(root, write_channels=True)
            result = build_result(root, report)
            planned = json.loads(source.read_text())['case']['recording_description']
            recording_evidence(result, planned, lambda reference: root / reference)
            self.assertEqual(len(result['recording_evidence']), 5)

    def test_opposed_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture(root, suffix='morning_west_against', velocity=(-5, 0))
            self.assertEqual(analyze(root)['measurements']['reversible_direction']['value']['direction'],
                             'against_designation')

    def test_changed_period_and_missing_civil_offset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows, _ = fixture(root)
            rows[2]['device']['period_id'] = 'evening'
            (root / 'direction_state.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'Effective designation changed'):
                analyze(root)
            rows[2]['device']['period_id'] = 'morning'
            rows[2]['civil_time']['iso8601'] = '2026-11-19T08:00:00'
            (root / 'direction_state.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'Civil-time offset required'):
                analyze(root)

    def test_video_map_and_lane_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows, mapping = fixture(root)
            mapping[2]['carla_frame'] += 1
            (root / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in mapping))
            with self.assertRaisesRegex(ValueError, 'video frame mapping differs'):
                analyze(root)
            mapping[2]['carla_frame'] -= 1
            (root / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in mapping))
            rows[2]['lane_id'] = 2
            (root / 'direction_state.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'Subject left'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
