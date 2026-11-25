"""CPU-only route configuration and survey tests."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('selected_runner', ROOT/'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BundleTests(unittest.TestCase):
    def test_config(self):
        self.assertEqual(runner.config_check()['case_id'], runner.CASE)

    def test_survey_rejects_missing_sources(self):
        with self.assertRaisesRegex(ValueError, 'Missing reviewed Native survey source'):
            runner.survey_check({})


if __name__ == '__main__':
    unittest.main()
