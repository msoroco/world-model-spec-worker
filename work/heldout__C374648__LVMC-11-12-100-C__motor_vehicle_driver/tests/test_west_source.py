"""Portable westbound source-path checks; no CARLA or physical claim."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from west_finalizer import CASE, analyze
from west_runner import check_config
from test_turn_origin_finalizer import sources


class WestSourceTests(unittest.TestCase):
    def _source(self, root):
        root = Path(root)
        sources(root)
        config = json.loads((HERE/'config.json').read_text())
        config['selected_case_id'] = CASE
        config['case']['case_id'] = CASE
        (root/'config.json').write_text(json.dumps(config)+'\n')
        rows = [json.loads(line) for line in
                (root/'turn_origin_native.jsonl').read_text().splitlines()]
        for row in rows:
            row['ego_forward_xy'] = [-v for v in row['ego_forward_xy']]
            row['lane_id'] = -row['lane_id']
            row['center_turn_lane_id'] = -row['center_turn_lane_id']
            row['center_marking_source_ids'] = [
                source.replace('lane:1:', 'lane:-1:')
                for source in row['center_marking_source_ids']]
        (root/'turn_origin_native.jsonl').write_text(''.join(
            json.dumps(row)+'\n' for row in rows))
        context = json.loads((root/'case_context.json').read_text())
        context['case_id'] = CASE
        context['target_exit_lane_id'] = -1
        (root/'case_context.json').write_text(json.dumps(context)+'\n')
        return config

    def test_west_config_and_source_bound_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._source(tmp)
            self.assertEqual(check_config(config), CASE)
            report = analyze(tmp)
            value = report['measurements']['turn_origin_observation']['value']
            self.assertTrue(value['origin_matches_center_lane'])
            self.assertEqual(value['maximum_left_deflection_deg'], 90)
            self.assertFalse(value['designation_authority_verified'])
            self.assertFalse(report['physical_acceptance_claimed'])

    def test_missing_original_west_source_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._source(tmp)
            (Path(tmp)/'turn_origin_native.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                analyze(tmp)


if __name__ == '__main__':
    unittest.main()
