import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_narrow_road_probe import check_config


class NarrowProbeTests(unittest.TestCase):
    def test_exact_case_and_engineering_target(self):
        config=json.loads((ROOT/'narrow-probe-config.json').read_text())
        check_config(config)
        config['max_total_width_m']=5.0
        with self.assertRaisesRegex(ValueError,'target differs'):
            check_config(config)
        config['max_total_width_m']=4.5
        config['selected_case_id']+='-wrong'
        with self.assertRaisesRegex(ValueError,'Unknown'):
            check_config(config)


if __name__=='__main__':
    unittest.main()
