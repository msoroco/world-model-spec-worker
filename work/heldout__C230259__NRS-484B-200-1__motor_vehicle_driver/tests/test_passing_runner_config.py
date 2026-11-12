"""Exact passing case identity and fixed 80-frame baseline capture contract."""
import json
import sys
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parents[1]
CASE='heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__passing_left'
sys.path.insert(0,str(HERE))
from passing_runner import check_config

class PassingConfigTest(unittest.TestCase):
    def test_passing_exact_identity_and_duration(self):
        config=json.loads((HERE/'config.json').read_text())
        config['selected_case_id']=CASE
        config['case']['case_id']=config['selected_case_id']
        config['frames']=80;config['duration_s']=4
        self.assertEqual(check_config(config),'passing_left')
        config['frames']=160
        with self.assertRaisesRegex(ValueError,'80 original frames'):
            check_config(config)
        config['frames']=80;config['selected_case_id']=CASE.replace('passing_left','baseline_left')
        with self.assertRaisesRegex(ValueError,'only exact passing'):
            check_config(config)

if __name__=='__main__':unittest.main()
