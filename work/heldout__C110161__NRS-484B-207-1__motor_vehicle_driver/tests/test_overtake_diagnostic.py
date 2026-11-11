"""Source-shaped diagnostic proof for the first overtaking case."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(FOLDER))
sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))

from overtake_finalizer import analyze, build_result
from worker_exchange.fixture_generator import generate
from worker_exchange.measurement_contract import verify_report


class DiagnosticIntegrationTests(unittest.TestCase):
    def test_first_case_original_sources_and_missing_source_rejection(self):
        spec = json.loads((FOLDER / 'diagnostic.json').read_text())
        contract = json.loads((FOLDER / 'first-measurement-contract.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / 'attempt'
            attempt.mkdir()
            generate(spec, attempt)
            shutil.copyfile(FOLDER / 'probe-config.json', attempt / 'config.json')
            self.assertFalse((attempt / 'left_pass_clearance_m.jsonl').exists())
            report = analyze(attempt)
            values = verify_report(contract, report, attempt)
            observed = values['overtake_observation']['value']
            self.assertEqual(observed['frame_count'], 9)
            self.assertTrue(observed['all_abreast_left'])
            self.assertEqual(observed['min_abreast_lateral_gap_m'], 2)
            self.assertGreater(observed['clearance_at_first_return_m'], 0)
            native = build_result(attempt, report)
            self.assertFalse(native['physical_acceptance_claimed'])
            self.assertEqual(len((attempt / 'left_pass_clearance_m.jsonl').read_text().splitlines()), 9)
            self.assertEqual(len((attempt / 'return_clearance_m.jsonl').read_text().splitlines()), 9)
            (attempt / 'participant_footprints.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, contract['negative']['error_contains']):
                analyze(attempt)


if __name__ == '__main__':
    unittest.main()
