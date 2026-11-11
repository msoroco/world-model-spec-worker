import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('sweep_probe', ROOT / 'sweep_probe.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SweepProbeTests(unittest.TestCase):
    def test_grid_changes_controller_feedback_without_claiming_physical_feasibility(self):
        result = module.probe(json.loads((ROOT / 'config.json').read_text()))
        self.assertEqual([point['requested_engineering_gap_m'] for point in result['points']],
                         [7.0, 8.5, 10.0])
        self.assertFalse(result['physical_feasibility_proven'])
        self.assertFalse(result['legal_threshold_asserted'])
        self.assertEqual([point['target_center_spacing_m'] for point in result['points']],
                         [11.0, 12.5, 14.0])

    def test_unreviewed_base_config_is_rejected(self):
        config = json.loads((ROOT / 'config.json').read_text())
        config['requested_engineering_gap_m'] = 9.0
        with self.assertRaisesRegex(ValueError, 'reviewed base'):
            module.probe(config)
