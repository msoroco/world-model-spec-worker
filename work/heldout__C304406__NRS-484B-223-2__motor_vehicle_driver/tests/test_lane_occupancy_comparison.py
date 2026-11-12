import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_lane_occupancy_comparison import audit
from three_lane_finalizer import PREFIX, analyze, build_result
from three_lane_source_capture import ThreeLaneSourceRecorder
from test_three_lane_route import corridor
from test_three_lane_source_capture import Ego


def case(root, suffix, y):
    root.mkdir()
    _, route = corridor()
    recorder = ThreeLaneSourceRecorder(root, route[0], Ego(y))
    trace, mapping = [], []
    for index in range(3):
        frame, time_s = 10 + index, index * .05
        recorder.append(frame, time_s)
        trace.append({'frame': frame, 'time_s': time_s,
                      'position_m': [index, y, 0]})
        mapping.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
    for name, rows in (('trace.jsonl', trace), ('video_frames.jsonl', mapping)):
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (root / 'config.json').write_text(json.dumps({
        'selected_case_id': PREFIX + suffix, 'law_id': 'NRS-484B-223-2',
        'cell_id': 'C304406', 'actor': 'motor_vehicle_driver',
        'rate_hz': 20, 'frames': 3, 'duration_s': .15,
        'travel_direction': 'east', 'cameras': [], 'required_atoms': [],
        'source_packets': [], 'lane_role': 'right' if suffix == 'right_baseline' else 'center',
        'case': {'recording_description': {'channels': [{'name': 'three_lane_observation'}]}}}) + '\n')
    report = analyze(root)
    result = build_result(root, report)
    saved = root.parent / (suffix + '-saved')
    analysis = saved / 'analysis'
    analysis.mkdir(parents=True)
    (analysis / 'analysis-report.json').write_text(json.dumps(report) + '\n')
    (analysis / 'result.json').write_text(json.dumps(result) + '\n')
    processing = saved / 'processing.json'
    processing.write_text(json.dumps({'case_id': PREFIX + suffix, 'passed': True,
        'recorded_only': True, 'originals_preserved': True,
        'missing_evidence': False}) + '\n')
    return processing


class LaneOccupancyComparisonTests(unittest.TestCase):
    def test_fixed_map_and_changed_body_lane(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            right, center = root / 'right', root / 'center'
            a = case(right, 'right_baseline', 0)
            b = case(center, 'center_default', 3.5)
            self.assertTrue(audit(right, a, center, b)['deliberate_difference_passed'])
            map_path = center / 'three_lane_map_readback.json'
            changed = json.loads(map_path.read_text())
            changed['road_id'] = 99
            map_path.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'original source differs'):
                audit(right, a, center, b)

    def test_missing_occupancy_change_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            right, center = root / 'right', root / 'center'
            a = case(right, 'right_baseline', 0)
            b = case(center, 'center_default', 0)
            with self.assertRaisesRegex(ValueError, 'contrast missing'):
                audit(right, a, center, b)


if __name__ == '__main__':
    unittest.main()
