"""Check one uniform engineering fallback across all controlled comparisons."""
import copy
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


class FallbackIsolationTests(unittest.TestCase):
    def test_only_passenger_anchor_moves_toward_curb(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        self.assertEqual(len(manifest['cases']), 7)
        shifts = []
        for entry in manifest['cases']:
            primary = json.loads((HERE / entry['construction']).read_text())
            alternate = json.loads((HERE / entry['candidates'][0]['construction']).read_text())
            pf = {item['path']: item['content'] for item in primary['files']}
            af = {item['path']: item['content'] for item in alternate['files']}
            self.assertEqual(set(pf), set(af))
            for key in pf.keys() - {'scene.json'}:
                self.assertEqual(pf[key], af[key])
            before, after = json.loads(pf['scene.json']), json.loads(af['scene.json'])
            start = before['zone']['passenger_anchor'][:]
            moved = after['zone']['passenger_anchor'][:]
            shifts.append(tuple(b - a for a, b in zip(start, moved)))
            restored = copy.deepcopy(after)
            restored['zone']['passenger_anchor'] = start
            self.assertEqual(before, restored)
        self.assertEqual(set(shifts), {(0, -0.5, 0)})


if __name__ == '__main__':
    unittest.main()
