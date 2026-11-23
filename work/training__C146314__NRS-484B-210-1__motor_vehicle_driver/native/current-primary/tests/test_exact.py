import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from check import check


class CurrentPrimary(unittest.TestCase):
    def test_exact_request(self):
        result = check(Path.cwd())
        self.assertEqual((result['frames'], result['cameras']), (600, 4))
        self.assertFalse(result['original_native_observed'])
        self.assertFalse(result['delivery_ready'])

    def test_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            dst = Path(folder)
            for name in ('config.json', 'assignment-source.json', 'case-plan.json',
                         'one-way-pass.xodr', 'requested-tracks.jsonl'):
                (dst / name).write_bytes(Path(name).read_bytes())
            with (dst / 'requested-tracks.jsonl').open('a') as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, 'Changed or missing source'):
                check(dst)

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            dst = Path(folder)
            for name in ('config.json', 'assignment-source.json', 'case-plan.json',
                         'one-way-pass.xodr', 'requested-tracks.jsonl'):
                if name != 'one-way-pass.xodr':
                    (dst / name).write_bytes(Path(name).read_bytes())
            with self.assertRaises(FileNotFoundError):
                check(dst)

    def test_rehashed_wrong_assignment_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            dst = Path(folder)
            for name in ('config.json', 'assignment-source.json', 'case-plan.json',
                         'one-way-pass.xodr', 'requested-tracks.jsonl'):
                (dst / name).write_bytes(Path(name).read_bytes())
            assignment = json.loads((dst / 'assignment-source.json').read_text())
            assignment['assignment_id'] = 'different_assignment'
            source = dst / 'assignment-source.json'
            source.write_text(json.dumps(assignment) + '\n')
            config_path = dst / 'config.json'
            config = json.loads(config_path.read_text())
            config['assignment_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            config_path.write_text(json.dumps(config) + '\n')
            with self.assertRaisesRegex(ValueError, 'Assignment identity differs'):
                check(dst)
