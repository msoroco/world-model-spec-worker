import json
from pathlib import Path
import unittest
from unittest.mock import patch

import layout
import runner
from branch_cases import CASES


class SchoolTurnDraftTests(unittest.TestCase):
    def test_geometry(self):
        value=layout.check()
        self.assertEqual(value['road_lane_ids'],[1,-1])
        self.assertFalse(value['zone_designation_reviewed'])

    def test_capture(self):
        config={'cell_id':'C263073','law_id':'NRS-484B-363-3',
            'case_suffix':'controlled_2','duration_s':30,'rate_hz':20,
            'cameras':[{'name':name,'width':width,'height':height} for name,width,height,*_ in runner.CAMERAS],
            'vehicle_blueprint':'vehicle.tesla.model3',
            'branch_context':CASES['controlled_2']}
        with patch.object(Path,'read_text',return_value=json.dumps(config)):
            value=runner.check()
        self.assertEqual(value['frame_count'],600)
        self.assertFalse(value['kinematic_path_only'])
        self.assertEqual(len(config['cameras']),4)
