import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from center_turn_cameras import CAMERAS
from outer_finalizer import CASE, analyze, build_result
from outer_runner import check_config
from test_turn_origin_finalizer import sources


class OuterCaseTests(unittest.TestCase):
    def test_outer_origin_source_and_exact_runner_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            config = json.loads((root/'config.json').read_text())
            config['selected_case_id'] = CASE
            config['case']['case_id'] = CASE
            config.update({'rate_hz': 20, 'frames': 80, 'duration_s': 4,
                           'cameras': [{'name': name, 'width': item[2][0],
                                        'height': item[2][1], 'fov_deg': item[3]}
                                       for name, item in CAMERAS.items()]})
            (root/'config.json').write_text(json.dumps(config))
            context = json.loads((root/'case_context.json').read_text())
            context['case_id'] = CASE
            (root/'case_context.json').write_text(json.dumps(context))
            rows = [json.loads(line) for line in (root/'turn_origin_native.jsonl').read_text().splitlines()]
            for row in rows:
                row['lane_id'] = 2
            (root/'turn_origin_native.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            self.assertEqual(check_config(config), CASE)
            report = analyze(root)
            result = build_result(root, report)
            self.assertFalse(report['measurements']['turn_origin_observation']['value']['origin_matches_center_lane'])
            self.assertTrue(result['target_checks'][0]['measured'])
            self.assertEqual(result['realized_observables']['origin_matches_center_lane']['value'], 0)
            self.assertFalse(result['physical_acceptance_claimed'])


if __name__ == '__main__':
    unittest.main()
