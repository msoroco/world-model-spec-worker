import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from v2_runner import check

class Route(unittest.TestCase):
    def test_600_source_bound_route(self):
        result = check(Path.cwd())
        self.assertEqual(result['checked_frames'], 600)
        self.assertFalse(result['actual_exit_observed'])

    def copy(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for name in ('config.json', 'authored-route.jsonl', 'road.xodr',
                     'assignment-source.json', 'case-plan.json'):
            shutil.copy2(name, root / name)
        return temporary, root

    def test_changed_track_hash_rejected(self):
        temporary, root = self.copy()
        with temporary:
            (root / 'authored-route.jsonl').write_text((root / 'authored-route.jsonl').read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                check(root)

    def test_changed_assignment_rejected(self):
        temporary, root = self.copy()
        with temporary:
            (root / 'assignment-source.json').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'Frozen assignment source differs'):
                check(root)

    def test_rebound_route_change_rejected(self):
        temporary, root = self.copy()
        with temporary:
            path = root / 'authored-route.jsonl'
            lines = path.read_text().splitlines()
            item = json.loads(lines[300]); item['lane_id'] = -99
            lines[300] = json.dumps(item)
            path.write_text('\n'.join(lines) + '\n')
            config = json.loads((root / 'config.json').read_text())
            config['track_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / 'config.json').write_text(json.dumps(config) + '\n')
            with self.assertRaisesRegex(ValueError, 'route source differs'):
                check(root)
