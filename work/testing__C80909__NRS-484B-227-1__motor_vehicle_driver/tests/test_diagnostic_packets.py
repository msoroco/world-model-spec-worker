import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('c80909_diagnostic_builder', ROOT / 'build_diagnostic_packets.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
from runner import load_plan


class DiagnosticPacketTests(unittest.TestCase):
    def test_all_four_exact_cpu_packets_and_physical_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builder.build(root)
            packets = sorted((root / 'cases').glob('*/site-plan.json'))
            self.assertEqual(len(packets), 4)
            ids = set()
            for packet in packets:
                plan = load_plan(packet)
                ids.add(plan['selected_case_id'])
                self.assertEqual(plan['source_review_status'], 'authored_cpu_diagnostic')
                self.assertEqual(plan['frames'], 600)
            self.assertEqual(ids, {builder.ASSIGNMENT + '__' + suffix for suffix in builder.ROUTES})
            result = subprocess.run([sys.executable, str(ROOT / 'runner.py'),
                                     '--site-plan', str(packets[0]),
                                     '--config', str(root / 'absent-config.json'),
                                     '--output-dir', str(root)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Reviewed original Native map and cameras required for physical capture',
                          result.stderr)


if __name__ == '__main__': unittest.main()
