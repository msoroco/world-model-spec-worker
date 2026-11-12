import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('exception_comparison_audit', HERE / 'exception_comparison_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
BASE = Path('.runtime-work/c230259-baseline-left-saved-3/v0001/analysis')
TARGETS = {
    'three_lane_left': Path('.runtime-work/c230259-three-lane-left-saved-1/v0001/analysis'),
    'one_way_left': Path('.runtime-work/c230259-one-way-left-saved-1/v0001/analysis'),
    'narrow_left': Path('.runtime-work/c230259-narrow-left-saved-1/v0001/analysis'),
}


class ExceptionComparisonTests(unittest.TestCase):
    def copy_sources(self, source, target):
        target.mkdir()
        for name in ('config.json', 'ego_road_frames.jsonl', 'road_exception_context.json',
                     'video_frames.jsonl', 'trace.jsonl', 'one_way_sign.jsonl'):
            if (source / name).exists():
                shutil.copy2(source / name, target / name)

    def test_all_three_source_comparisons_and_changed_width_rejection(self):
        for suffix, source in TARGETS.items():
            if not source.exists():
                self.skipTest('Saved diagnostic source directory unavailable')
            self.assertTrue(module.audit(BASE, source, suffix)['passed'])
            with tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / 'source'
                self.copy_sources(source, target)
                path = target / 'ego_road_frames.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                rows[0]['road_width_m'] = 1.0 if suffix == 'three_lane_left' else 99.0
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                with self.assertRaisesRegex(ValueError, 'lane inventory|width contrast'):
                    module.audit(BASE, target, suffix)

    def test_missing_one_way_sign_rejected(self):
        source = TARGETS['one_way_left']
        if not source.exists():
            self.skipTest('Saved diagnostic source directory unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'source'
            self.copy_sources(source, target)
            (target / 'one_way_sign.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original comparison source'):
                module.audit(BASE, target, 'one_way_left')


if __name__ == '__main__':
    unittest.main()
