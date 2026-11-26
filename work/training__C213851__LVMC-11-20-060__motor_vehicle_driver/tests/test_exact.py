import json
import subprocess
import sys
import unittest
from pathlib import Path

class ExactBundle(unittest.TestCase):
    def test_selected_and_source_shape(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'config.json').read_text())
        selected = json.loads((root / 'native/selected-case.json').read_text())
        self.assertEqual(config['selected_case_id'], selected['case_id'])
        result = subprocess.run([sys.executable, str(root / 'runner.py'), '--check'],
                                capture_output=True, text=True, check=True)
        proof = json.loads(result.stdout)
        self.assertTrue(proof['requests']['passed'])
        self.assertTrue(proof['road']['passed'])
        self.assertFalse(proof['carla_started'])

    def test_missing_source_rejected(self):
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / 'native'))
        from measure_sidewalk import measure
        with self.assertRaises(FileNotFoundError):
            measure(root, json.loads((root / 'config.json').read_text())['case_id'])
