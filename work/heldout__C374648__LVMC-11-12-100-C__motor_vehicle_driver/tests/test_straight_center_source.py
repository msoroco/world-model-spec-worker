"""Center-origin straight saved analysis on retained original rows."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from straight_center_finalizer import CASE, analyze
from straight_center_runner import check_config
from test_straight_use_measurement import straight_source


class StraightCenterSourceTests(unittest.TestCase):
    def _source(self, root):
        root = Path(root)
        straight_source(root)
        config = json.loads((HERE/'config.json').read_text())
        config['selected_case_id'] = CASE
        config['case']['case_id'] = CASE
        (root/'config.json').write_text(json.dumps(config)+'\n')
        context = json.loads((root/'case_context.json').read_text())
        context['case_id'] = CASE
        context['requested_maneuver'] = 'straight'
        (root/'case_context.json').write_text(json.dumps(context)+'\n')
        return config

    def test_center_straight_originals_bind(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(check_config(self._source(directory)), CASE)
            report = analyze(directory, write_channels=False)
            value = report['measurements']['straight_use_observation']['value']
            self.assertTrue(value['origin_matches_center_lane'])
            self.assertTrue(value['straight_motion_observed'])
            self.assertFalse(report['physical_acceptance_claimed'])

    def test_wrong_straight_context_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            self._source(directory)
            context_path = Path(directory)/'case_context.json'
            context = json.loads(context_path.read_text())
            context['requested_maneuver'] = 'left turn'
            context_path.write_text(json.dumps(context)+'\n')
            with self.assertRaisesRegex(ValueError, 'source/intent binding'):
                analyze(directory, write_channels=False)
