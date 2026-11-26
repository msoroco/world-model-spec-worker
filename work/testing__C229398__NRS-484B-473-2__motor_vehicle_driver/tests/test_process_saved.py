import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from parked_lamps import CASES
from process_saved import process_saved
from test_capture_seal import make_stage


class SavedTests(unittest.TestCase):
    def test_all_cases_render_without_changing_original_sources(self):
        scratch = ROOT / '.runtime-work' / 'c229398-saved-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp)
            for case in CASES:
                with self.subTest(case=case.name):
                    stage = root / case.name
                    stage.mkdir()
                    make_stage(stage, case)
                    source = stage / 'original-ticks.jsonl'
                    before = hashlib.sha256(source.read_bytes()).hexdigest()
                    output = root / (case.name + '-derived')
                    report = process_saved(stage, output, diagnostic_fixture=True)
                    self.assertEqual(len(report['videos']), 4)
                    self.assertTrue(all(video['decoded_frames'] == 3
                                        for video in report['videos'].values()))
                    self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())
                    self.assertFalse(report['physical_acceptance_claimed'])
                    with self.assertRaisesRegex(ValueError, 'already exists'):
                        process_saved(stage, output, diagnostic_fixture=True)


if __name__ == '__main__':
    unittest.main()
