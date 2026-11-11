import json
from pathlib import Path
import sys
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path: sys.path.insert(0, str(root))
from signal_finalizer import analyze, build_result
from signal_comparison_audit import audit
from flashing_yellow import CASES


def fixture(path, branch='east_cautious_approach'):
    prefix = 'heldout__C111273__NRS-484B-310-2__motor_vehicle_driver__'
    config = {'selected_case_id': prefix+branch, 'case_branch': branch,
              'law_id': 'NRS-484B-310-2', 'cell_id': 'C111273', 'actor': 'motor_vehicle_driver',
              'target_speed_mps': CASES[branch].approach_target_mps,
              'rate_hz': 20, 'frames': 160, 'duration_s': 8,
              'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference']}
    context = {'official_control_source': 'source-backed control premise',
               'selected_direction': 'west' if branch.startswith('west') else 'east',
               'opendrive_id': 'road-1', 'junction_id': 42, 'flash_period_s': .5}
    (path/'config.json').write_text(json.dumps(config))
    (path/'signal_context.json').write_text(json.dumps(context))
    streams = {'signal_state.jsonl': [], 'participant_state.jsonl': [],
               'video_frames.jsonl': [], 'trace.jsonl': []}
    for i in range(20):
        frame, time_s = 100+i, round(i*.05, 3)
        on = i < 5 or 10 <= i < 15
        ego = {'actor_id': 7, 'center_xy': [float(i), 0.], 'speed_mps': 4.}
        crossing = None if branch == 'east_clear_approach' else {'actor_id': 8, 'center_xy': [0., float(i)], 'speed_mps': 6.}
        streams['signal_state.jsonl'].append({'frame': frame, 'time_s': time_s,
            'light_actor_id': 2, 'opendrive_id': 'road-1', 'yellow_commanded': on,
            'native_light_state': 'Yellow' if on else 'Off', 'lens_pixel_visible': None})
        streams['participant_state.jsonl'].append({'frame': frame, 'time_s': time_s,
                                                    'ego': ego, 'crossing': crossing})
        streams['video_frames.jsonl'].append({'video_frame': i, 'carla_frame': frame, 'time_s': time_s})
        streams['trace.jsonl'].append({'frame': frame, 'time_s': time_s})
    for name, rows in streams.items():
        (path/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))


class TestSignalFinalizer(unittest.TestCase):
    def test_native_result_shape_keeps_pixel_and_legal_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); fixture(path)
            config = json.loads((path/'config.json').read_text())
            config['case'] = {'recording_description': {'channels': [
                {'name': name, 'unit': 'source value'} for name in (
                    'native_yellow_on', 'ego_speed_mps', 'ego_center_xy',
                    'crossing_center_xy', 'lens_pixel_visible')]}}
            (path/'config.json').write_text(json.dumps(config))
            result = build_result(path, analyze(path))
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['maneuver_completed'])
            self.assertFalse(result['target_checks'][0]['physical_cause_confirmed'])
            self.assertEqual(len(result['recording_evidence']), 5)

    def test_all_exact_branches_and_retained_sources(self):
        for branch in ('east_cautious_approach', 'east_faster_approach',
                       'east_clear_approach', 'west_cautious_approach'):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp); fixture(path, branch)
                report = analyze(path)
                measured = report['measurements']['flashing_yellow']
                self.assertEqual(measured['native_transitions'], 3)
                self.assertEqual(measured['lens_pixel_visibility'], 'unverified')
                self.assertEqual(measured['legal_caution_judgment'], 'unresolved')
                self.assertEqual(len((path/'native_yellow_on.jsonl').read_text().splitlines()), 20)
                with self.assertRaisesRegex(ValueError, 'Retain prior'):
                    analyze(path)

    def test_reject_missing_changed_and_unjoined_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp); fixture(path)
            rows = [json.loads(line) for line in (path/'signal_state.jsonl').read_text().splitlines()]
            rows[3]['native_light_state'] = 'Off'
            (path/'signal_state.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'readback differs'):
                analyze(path, write_channels=False)
            fixture(path)
            rows = [json.loads(line) for line in (path/'participant_state.jsonl').read_text().splitlines()]
            rows[3]['frame'] += 1
            (path/'participant_state.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'join failed'):
                analyze(path, write_channels=False)
            (path/'signal_context.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(path, write_channels=False)

    def test_carla_enum_string_spelling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp); fixture(path)
            rows = [json.loads(line) for line in (path/'signal_state.jsonl').read_text().splitlines()]
            for row in rows:
                row['native_light_state'] = 'TrafficLightState.' + row['native_light_state']
            (path/'signal_state.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            self.assertEqual(analyze(path, write_channels=False)['measurements']['flashing_yellow']['native_transitions'], 3)

    def test_comparisons_check_fixed_conditions_and_sources(self):
        pairs = {'approach_speed_sample': 'east_faster_approach',
                 'crossing_traffic_context': 'east_clear_approach',
                 'approach_direction': 'west_cautious_approach'}
        for comparison, other in pairs.items():
            with self.subTest(comparison=comparison), tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
                first, second = Path(a), Path(b)
                fixture(first); fixture(second, other)
                receipt = audit(comparison, first, second)
                self.assertTrue(receipt['fixed_conditions_checked'])
                self.assertEqual(receipt['legal_caution_judgment'], 'unresolved')
                context = json.loads((second/'signal_context.json').read_text())
                context['junction_id'] = 99
                (second/'signal_context.json').write_text(json.dumps(context))
                with self.assertRaisesRegex(ValueError, 'Fixed condition differs'):
                    audit(comparison, first, second)


if __name__ == '__main__': unittest.main()
