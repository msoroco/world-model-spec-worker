"""Focused construction checks for the exact flagger response pair."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from check_requests import check_pair, read_case


HERE = Path(__file__).resolve().parent


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        scratch = Path('.runtime-work/c183370-construction-tests').resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.base = Path(self.temp.name)
        for suffix in ('probe_a', 'probe_b'):
            shutil.copytree(HERE / suffix, self.base / suffix)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_pair(self):
        proof = check_pair(base=self.base)
        self.assertTrue(proof['passed'])
        self.assertEqual(proof['crossing_frames'], [1350, 1200])

    def test_reject_changed_case_scope(self):
        path = self.base / 'probe_b' / 'config.json'
        original = path.read_text()
        try:
            changed = json.loads(original)
            changed['controller_policy'] = 'hold_until_release'
            path.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'Exact flagger config'):
                read_case('probe_b', base=self.base)
        finally:
            path.write_text(original)

    def test_reject_changed_track_source(self):
        path = self.base / 'probe_a' / 'requested-tracks.jsonl'
        original = path.read_text()
        try:
            rows = original.splitlines()
            changed = json.loads(rows[120])
            changed['signal'] = 'release'
            rows[120] = json.dumps(changed)
            path.write_text('\n'.join(rows) + '\n')
            with self.assertRaisesRegex(ValueError, 'construction source'):
                read_case('probe_a', base=self.base)
        finally:
            path.write_text(original)

    def test_reject_changed_frozen_source(self):
        path = self.base / 'probe_a' / 'config.json'
        original = path.read_text()
        try:
            changed = json.loads(original)
            changed['assignment_sha256'] = '0' * 64
            path.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'Frozen assignment source'):
                read_case('probe_a', base=self.base)
        finally:
            path.write_text(original)


if __name__ == '__main__':
    unittest.main()
