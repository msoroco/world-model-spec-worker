from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from closure_finalizer import analyze, build_result
from test_right_half_finalizer import FinalizerTests


class ClosureFinalizerTests(unittest.TestCase):
    def make_sources(self, root):
        FinalizerTests().sources(root)
        config_path = root / 'config.json'
        config = json.loads(config_path.read_text())
        config['selected_case_id'] = config['selected_case_id'].replace(
            'baseline_right_east', 'right_half_closed')
        config_path.write_text(json.dumps(config))
        roadway_path = root / 'directed_roadway_footprints.jsonl'
        roadway = [json.loads(x) for x in roadway_path.read_text().splitlines()]
        for row in roadway:
            row['subject_lane_width_m'] = 3.0
        roadway_path.write_text(''.join(json.dumps(r) + '\n' for r in roadway))
        closure = []
        for frame in range(2):
            closure.append({'frame': frame, 'time_s': frame * .05,
                            'authority_verified': False,
                            'devices': [{'actor_id': str(i),
                                         'blueprint_id': 'static.prop.trafficcone01',
                                         'position_m': [0, y, .05]}
                                        for i, y in [(1,.3),(2,1.5),(3,2.7)]]})
        (root / 'closure_devices.jsonl').write_text(
            ''.join(json.dumps(r) + '\n' for r in closure))

    def test_saved_join_and_missing_original_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_sources(root)
            report = analyze(root)
            self.assertEqual(report['measurements']['closure_construction'][
                'value']['cone_count'], 3)
            result = build_result(root, report)
            self.assertEqual(result['realized_observables']['closure_cone_count']['value'], 3)
            self.assertFalse(result['legal_acceptance_claimed'])
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'scenario_pipeline'))
            from worker_exchange.native_output import validate_result
            validate_result(result)
            (root / 'closure_devices.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: closure_devices.jsonl'):
                analyze(root)


if __name__ == '__main__':
    unittest.main()
