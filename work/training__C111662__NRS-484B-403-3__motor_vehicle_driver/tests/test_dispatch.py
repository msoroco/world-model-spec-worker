"""Exercise the root exact-case dispatcher against the selected CPU bundle."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
PYTHON = ROOT / '.venv-cpu/bin/python'


class ExactDispatch(unittest.TestCase):
    def test_reference_offline_and_unknown_case_rejection(self):
        case = HERE.name + '__reference'
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c111662-root-dispatch-') as temporary:
            output = Path(temporary) / 'offline'
            command = [str(PYTHON), str(HERE / 'runner.py'), '--mode', 'offline',
                       '--case', case, '--candidate', 'primary', '--output', str(output)]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)['offline_passed'])
            unknown = subprocess.run([str(PYTHON), str(HERE / 'runner.py'), '--mode', 'offline',
                                      '--case', HERE.name + '__unknown', '--output', str(output)],
                                     cwd=ROOT, text=True, capture_output=True, timeout=30)
            self.assertNotEqual(unknown.returncode, 0)
            self.assertIn('outside exact selected assignment', unknown.stderr)


if __name__ == '__main__':
    unittest.main()
