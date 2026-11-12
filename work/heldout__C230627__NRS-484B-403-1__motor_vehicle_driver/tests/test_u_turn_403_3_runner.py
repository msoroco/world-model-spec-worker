"""CARLA-lazy configuration path for the planned 403(3) candidate."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from runner import PREFIX, check_config


class DistrictRunnerTests(unittest.TestCase):
    def test_403_3_case_identity_is_accepted_without_native_import(self):
        config=copy.deepcopy(json.loads((ROOT/'config.json').read_text()))
        case_id=PREFIX+'prohibition_403_3'
        config['selected_case_id']=case_id
        config['case']['case_id']=case_id
        self.assertEqual(check_config(config),case_id)
        config['case']['case_id']=PREFIX+'safety_clear'
        with self.assertRaisesRegex(ValueError,'Unknown'):
            check_config(config)


if __name__=='__main__':
    unittest.main()
