import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

folder = Path(__file__).resolve().parents[1]
repo = folder.parents[1]
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(repo / '.runtime-work/adapter/c109514-park')
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
sys.path.insert(1, str(repo / 'runtime/python'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources, run as process_saved


class ParkSavedTests(unittest.TestCase):
    def test_park_primary_and_fallback_saved_sources(self):
        with tempfile.TemporaryDirectory(prefix='c109514-park-', dir=repo / '.runtime-work') as temp:
            root = Path(temp)
            decoder = repo / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'
            for target in (499, 500, 501):
                case = folder.name + f'__stopped_park_{target}ft'
                case_root = root / str(target)
                case_root.mkdir()
                fixture = case_root / 'fixture'
                make_fixture(repo, folder / 'cases' / f'stopped_park_{target}ft' /
                            'diagnostic-recipe.json', fixture)
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                  with self.subTest(target=target, candidate=candidate):
                    attempt, output = case_root / (candidate + '-attempt'), case_root / (candidate + '-processed')
                    make_attempt(folder / 'execution-manifest.json', case, attempt,
                                 candidate=candidate)
                    copy_sources(fixture, attempt)
                    self.assertFalse((attempt / 'fire_gap_ft.jsonl').exists())
                    receipt = process_saved(folder / 'execution-manifest.json', case, attempt,
                                            output, repo / 'runtime/library', decoder)
                    self.assertTrue(receipt['passed'])
                    self.assertEqual(receipt['candidate_id'], candidate)
                    self.assertTrue(receipt['originals_preserved'])
                    self.assertTrue(receipt['final_video_checks']['passed'])
                    measured = json.loads((Path(receipt['analysis_directory']) /
                                           'analysis-report.json').read_text())['measurements']['fire_boundary_observation']['value']
                    self.assertEqual(measured['branch'], 'stopped_park')
                    self.assertEqual(measured['active_frame_count'], 5)
                    key = {499: 'below_500_frames', 500: 'at_500_frames',
                           501: 'above_500_frames'}[target]
                    self.assertEqual(measured[key], list(range(38037, 38042)))
                    self.assertFalse((attempt / 'fire_gap_ft.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
