import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assemble_execution_manifest import SOURCES, assemble


class AssemblyTests(unittest.TestCase):
    def test_all_nine_current_constructions_and_stale_source_rejection(self):
        combined = assemble(ROOT)
        self.assertEqual(len(combined['cases']), 9)
        self.assertEqual(len({case['case_id'] for case in combined['cases']}), 9)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'case-plan.json').write_bytes((ROOT / 'case-plan.json').read_bytes())
            for name in SOURCES:
                manifest = json.loads((ROOT / name).read_text())
                (target / name).write_text(json.dumps(manifest))
                for case in manifest['cases']:
                    source = case['construction']
                    (target / source).write_bytes((ROOT / source).read_bytes())
            first = json.loads((target / SOURCES[0]).read_text())
            source = target / first['cases'][0]['construction']
            source.write_text(source.read_text() + '\n')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                assemble(target)
            first['cases'][0]['construction'] = '../outside.json'
            (target / SOURCES[0]).write_text(json.dumps(first))
            with self.assertRaisesRegex(ValueError, 'escapes assignment'):
                assemble(target)


if __name__ == '__main__':
    unittest.main()
