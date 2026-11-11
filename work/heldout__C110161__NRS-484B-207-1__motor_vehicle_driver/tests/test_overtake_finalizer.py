import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_finalizer import analyze, build_result
from test_overtake_measurement import box


CASE = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__left_pass_wide'


def sources(root):
    (root / 'config.json').write_text(json.dumps({
        'selected_case_id': CASE, 'law_id': 'NRS-484B-207-1',
        'cell_id': 'C110161', 'actor': 'motor_vehicle_driver',
        'target_left_gap_m': 2, 'requested_return_clearance_m': 3,
        'case': {'recording_description': {'channels': [], 'context_inputs': [],
                                           'limitations': ['CPU fixture only']}}}))
    mapping, trace, bodies = [], [], []
    for i, (ego_x, ego_y) in enumerate(((0, 4), (5, 4), (10, 4), (12, 2))):
        frame, time_s = 100 + i, i * .05
        mapping.append({'video_frame': i, 'carla_frame': frame, 'time_s': time_s})
        trace.append({'frame': frame, 'time_s': time_s})
        bodies.append({'frame': frame, 'time_s': time_s,
                       'ego_id': 'ego', 'other_id': 'other',
                       'road_tangent_xy': [1, 0], 'ego_heading_xy': [1, 0],
                       'other_heading_xy': [1, 0],
                       'ego_corners': box(ego_x, ego_x + 4, ego_y, ego_y + 2),
                       'other_corners': box(5, 9, 0, 2)})
    for name, rows in (('video_frames.jsonl', mapping), ('trace.jsonl', trace),
                       ('participant_footprints.jsonl', bodies)):
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))


class SavedOvertakeTests(unittest.TestCase):
    def test_selected_requirement_contract_joins_original_sources(self):
        folder = Path(__file__).resolve().parents[1]
        contract = json.loads((folder / 'first-measurement-contract.json').read_text())
        plan = json.loads((folder / 'case-plan.json').read_text())
        sys.path.insert(0, str(folder.parents[1] / 'runtime' / 'scenario_pipeline'))
        from worker_exchange.measurement_contract import validate, verify_report
        validate(contract, plan['requirement_dispositions'],
                 (folder / 'overtake_finalizer.py').read_text(), CASE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            report = analyze(root)
            self.assertIn('overtake_observation', verify_report(contract, report, root))
            (root / 'participant_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)

    def test_original_join_and_canonical_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            report = analyze(root)
            native = build_result(root, report)
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'scenario_pipeline'))
            from worker_exchange.native_output import validate_result
            validate_result(native)
            self.assertEqual(native['realized_observables']['return_clearance_m']['value'], 3)
            self.assertFalse(native['physical_acceptance_claimed'])
            self.assertEqual({item['name'] for item in native['recording_evidence']},
                             {'left_pass_clearance_m', 'return_clearance_m'})
            (root / 'participant_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(root)

    def test_stale_trace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            rows = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
            rows[1]['frame'] = 17
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'join failed'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
