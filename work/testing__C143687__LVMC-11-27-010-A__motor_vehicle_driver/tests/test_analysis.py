"""Positive and missing-source checks of selected saved trail measurements."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import sys

from analysis import report, saved_result
from test_saved_source_finalizer import make_attempt, SCRATCH
from test_trail_capture import CASES


REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report


class AnalysisTests(unittest.TestCase):
    def test_all_six_selected_measurements_and_canonical_results(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            assignment = Path(__file__).resolve().parents[1]
            plan = json.loads((assignment / 'case-plan.json').read_text())
            for case in CASES:
                with self.subTest(case=case.name):
                    root = Path(temporary) / case.name
                    root.mkdir()
                    bundle = assignment / 'cases' / case.name
                    shutil.copy2(bundle / 'config.json', root / 'config.json')
                    shutil.copy2(bundle / 'construction.json', root / 'construction.json')
                    make_attempt(root, case)
                    packets = [json.loads(line) for line in
                               (root / 'original-history-packets.jsonl').read_text().splitlines()]
                    with (root / 'trace.jsonl').open('x') as trace, (root / 'video_frames.jsonl').open('x') as frames:
                        for index, packet in enumerate(packets):
                            trace.write(json.dumps({'frame': packet['frame'],
                                                    'time_s': packet['time_s'],
                                                    'position_m': [*packet['location_xy'], 0.0],
                                                    'position': {'x': packet['location_xy'][0],
                                                                 'y': packet['location_xy'][1], 'z': 0.0},
                                                    'heading_deg': 0.0,
                                                    'speed_mps': 1.0}) + '\n')
                            frames.write(json.dumps({'video_frame': index,
                                                     'carla_frame': packet['frame'],
                                                     'native_frame': packet['frame'],
                                                     'time_s': packet['time_s']}) + '\n')
                    value = report(root)
                    contract = json.loads((bundle / 'measurement-contract.json').read_text())
                    validate(contract, plan['requirement_dispositions'],
                             (bundle / 'analysis.py').read_text(),
                             json.loads((bundle / 'config.json').read_text())['selected_case_id'])
                    self.assertEqual(len(verify_report(contract, value, root)), 7)
                    self.assertTrue(value['diagnostic_fixture'])
                    canonical = saved_result(root, value)
                    self.assertEqual(len(canonical['recording_evidence']), 5)
                    self.assertFalse(canonical['target_checks'][0]['physical_cause_confirmed'])
                    (root / 'acquisition.json').unlink()
                    with self.assertRaisesRegex(ValueError, 'Missing required source: acquisition.json'):
                        report(root)

    def test_missing_case_source_rejected_before_measurement(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            with self.assertRaisesRegex(ValueError, 'Missing required source: acquisition.json'):
                report(Path(temporary))


if __name__ == '__main__':
    unittest.main()
