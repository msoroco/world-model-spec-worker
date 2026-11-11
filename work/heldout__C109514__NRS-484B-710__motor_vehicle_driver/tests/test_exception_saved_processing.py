import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


folder = Path(__file__).resolve().parents[1]
repo = folder.parents[1]
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(repo / '.runtime-work/adapter/c109514-exception')
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources, run as process_saved


class ExceptionSavedTests(unittest.TestCase):
    def test_both_exception_cases_and_all_variants_process_saved_sources(self):
        with tempfile.TemporaryDirectory(prefix='c109514-exception-', dir=repo / '.runtime-work') as temp:
            base = Path(temp)
            decoder = repo / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'
            for suffix, expected in (('ordinary_police_at499', False),
                                     ('authorized_police_at499', True)):
                case = folder.name + '__' + suffix
                case_root = base / suffix
                case_root.mkdir()
                fixture = case_root / 'fixture'
                make_fixture(repo, folder / 'cases' / suffix / 'diagnostic-recipe.json', fixture)
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                    with self.subTest(suffix=suffix, candidate=candidate):
                        attempt = case_root / (candidate + '-attempt')
                        processed = case_root / (candidate + '-processed')
                        make_attempt(folder / 'execution-manifest.json', case, attempt,
                                     candidate=candidate)
                        copy_sources(fixture, attempt)
                        receipt = process_saved(folder / 'execution-manifest.json', case,
                                                attempt, processed, repo / 'runtime/library', decoder)
                        self.assertTrue(receipt['passed'])
                        self.assertTrue(receipt['originals_preserved'])
                        self.assertTrue(receipt['final_video_checks']['passed'])
                        report = json.loads((Path(receipt['analysis_directory']) / 'analysis-report.json').read_text())
                        self.assertIs(report['measurements']['exception_context']['value']
                                      ['subject_authorized_emergency'], expected)
                        self.assertIs(report['measurements']['exception_context']['value']
                                      ['subject_official_business'], expected)


if __name__ == '__main__':
    unittest.main()
