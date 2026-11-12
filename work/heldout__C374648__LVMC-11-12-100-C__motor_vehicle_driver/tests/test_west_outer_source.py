"""Portable westbound outer-origin source checks."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from test_turn_origin_finalizer import sources
from west_outer_finalizer import CASE, analyze
from west_outer_runner import check_config


class WestOuterSourceTests(unittest.TestCase):
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
            row['lane_id'] = -2
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

    def test_outer_west_origin_is_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._source(tmp)
            self.assertEqual(check_config(config), CASE)
            value = analyze(tmp)['measurements']['turn_origin_observation']['value']
            self.assertFalse(value['origin_matches_center_lane'])
            self.assertEqual(value['maximum_left_deflection_deg'], 90)

    def test_wrong_original_context_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._source(tmp)
            context = json.loads((Path(tmp)/'case_context.json').read_text())
            context['case_id'] = 'wrong'
            (Path(tmp)/'case_context.json').write_text(json.dumps(context)+'\n')
            with self.assertRaisesRegex(ValueError, 'source/intent binding'):
                analyze(tmp)
