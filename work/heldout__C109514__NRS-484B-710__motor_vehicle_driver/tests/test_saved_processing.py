"""Fresh raw-source saved-processing proof for C109514's first exact case."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

folder = Path(__file__).resolve().parents[1]
repo = folder.parents[1]
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(repo / '.runtime-work/adapter/c109514-saved')
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
sys.path.insert(1, str(repo / 'runtime/python'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources, run as process_saved

class SavedProcessingTests(unittest.TestCase):
    def test_selected_intersection_following_source_path(self):
        with tempfile.TemporaryDirectory(prefix='c109514-saved-', dir=repo / '.runtime-work') as temp:
            root = Path(temp)
            decoder = repo / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'
            for target in (499, 500, 501):
                case = folder.name + f'__traveling_follow_{target}ft'
                case_root = root / str(target)
                case_root.mkdir()
                fixture = case_root / 'fixture'
                recipe = (folder / 'diagnostic-recipe.json' if target == 500
                          else folder / 'cases' / f'traveling_follow_{target}ft' / 'diagnostic-recipe.json')
                make_fixture(repo, recipe, fixture)
                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                    with self.subTest(target=target, candidate=candidate):
                        attempt, output = (case_root / (candidate+suffix)
                                           for suffix in ('-attempt', '-processed'))
                        make_attempt(folder / 'execution-manifest.json', case, attempt,
                                     candidate=candidate)
                        copy_sources(fixture, attempt)
                        self.assertFalse((attempt / 'fire_gap_ft.jsonl').exists())
                        receipt = process_saved(folder / 'execution-manifest.json', case,
                                                attempt, output, repo / 'runtime/library', decoder)
                        self.assertTrue(receipt['passed'])
                        self.assertEqual(receipt['candidate_id'], candidate)
                        self.assertTrue(receipt['originals_preserved'])
                        self.assertTrue(receipt['final_video_checks']['passed'])
                        self.assertFalse((attempt / 'fire_gap_ft.jsonl').exists())
                        stage = Path(receipt['analysis_directory'])
                        rows = [json.loads(line) for line in (stage / 'fire_gap_ft.jsonl').read_text().splitlines()]
                        self.assertEqual(len(rows), 9)
                        self.assertTrue(all(abs(row['value'] - target) < 1e-6 for row in rows))
                        result = json.loads((stage / 'result.json').read_text())
                        self.assertFalse(result['physical_acceptance_claimed'])

if __name__ == '__main__': unittest.main()
