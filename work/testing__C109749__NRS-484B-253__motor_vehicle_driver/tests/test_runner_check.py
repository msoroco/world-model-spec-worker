import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class RunnerCheckTests(unittest.TestCase):
    def test_cpu_check_is_lazy_and_exact(self):
        run=subprocess.run([sys.executable,str(ROOT/'runner.py'),'--check'],
                           capture_output=True,text=True,check=True)
        report=json.loads(run.stdout)
        self.assertTrue(report['cpu_check_passed'])
        self.assertFalse(report['carla_started'])
        self.assertEqual(report['case_id'],
          'testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_yield_after_turn')
