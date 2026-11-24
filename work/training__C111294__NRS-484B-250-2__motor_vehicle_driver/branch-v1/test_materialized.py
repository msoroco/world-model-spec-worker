"""Tests run from one materialized exact branch construction."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path.cwd()
NATIVE=ROOT/'work/training__C111294__NRS-484B-250-2__motor_vehicle_driver/native'
sys.path.insert(0,str(NATIVE))
from check import check


class ExactExclusionBranch(unittest.TestCase):
    def test_source_bound_native_request(self):
        result=check(ROOT)
        self.assertEqual(result['frames'],600)
        self.assertFalse(result['original_native_observed'])

    def test_missing_actor_request_rejected(self):
        scratch=ROOT/'.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            copy=Path(tmp)
            for name in ('config.json','assignment-source.json','case-plan.json',
                         'crossroads.xodr'):
                shutil.copyfile(ROOT/name,copy/name)
            with self.assertRaises(FileNotFoundError):
                check(copy)

    def test_law_source_mutation_rejected(self):
        scratch=ROOT/'.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            copy=Path(tmp)
            for name in ('config.json','assignment-source.json','case-plan.json',
                         'crossroads.xodr','requested-tracks.jsonl'):
                shutil.copyfile(ROOT/name,copy/name)
            source=json.loads((copy/'assignment-source.json').read_text())
            source['law']['text']='altered'
            (copy/'assignment-source.json').write_text(json.dumps(source))
            with self.assertRaises(ValueError):
                check(copy)


if __name__=='__main__':
    unittest.main()
