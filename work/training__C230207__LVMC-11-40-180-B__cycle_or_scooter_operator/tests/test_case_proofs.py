import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class CaseProofTests(unittest.TestCase):
    def test_comparison_rejects_changed_held_interval(self):
        comparison = module('comparison_audit', ROOT / 'native/comparison_audit.py')
        self.assertEqual(comparison.audit()['signed_roadway_riding_frames'],
                         {'witness_1': 0, 'witness_2': 400})
        with self.assertRaisesRegex(ValueError, 'held condition'):
            comparison.audit(True)

    def test_selected_diagnostic_measurements_are_source_bound(self):
        for index, expected in ((1, 0), (2, 9)):
            with self.subTest(index=index):
                receipt = json.loads((ROOT / f'compat-witness_{index}.json').read_text())
                measurement = receipt['measurement_examples']['signed_roadway_riding']
                self.assertEqual(measurement['value'], expected)
                self.assertEqual(set(measurement['sources']),
                                 {'setup.json', 'raw-frames.json', 'video_frames.jsonl'})
                self.assertEqual(receipt['negative_removed'], 'setup.json')
                self.assertIn('Missing required source: setup.json',
                              (ROOT / f'negative-witness_{index}.log').read_text())


if __name__ == '__main__':
    unittest.main()
