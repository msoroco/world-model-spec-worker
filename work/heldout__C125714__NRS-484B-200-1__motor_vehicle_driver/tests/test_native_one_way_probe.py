import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_one_way_probe import check_config


class OneWayProbeConfigTests(unittest.TestCase):
    def test_exact_case_and_leftward_controller(self):
        config=json.loads((ROOT/'one-way-probe-config.json').read_text())
        check_config(config)
        config['requested_lane_fraction']=.4
        with self.assertRaisesRegex(ValueError,'fraction differs'):
            check_config(config)
        config['requested_lane_fraction']=.75
        config['selected_case_id']+='-wrong'
        with self.assertRaisesRegex(ValueError,'Unknown one-way'):
            check_config(config)


if __name__=='__main__':
    unittest.main()
