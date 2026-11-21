import json
import unittest
from pathlib import Path
import native_runner
from traffic_spec_adapter.geometry import painted_map_objects, static_map

class PrimaryPlan(unittest.TestCase):
    def test_exact_primary_plan_and_paint(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'config.json').read_text())
        receipt=native_runner.validate_capture_plan(config,root)
        self.assertEqual(receipt['selected_boundary'],'stop_line')
        self.assertFalse(receipt['native_site_verified'])
        path=root/'inoperative-stop-line.xodr'
        rows=painted_map_objects(path)
        self.assertEqual([r['region']['kind'] for r in rows],['stop_line','stop_line'])
        self.assertEqual([r['source']['road_id'] for r in rows],[158190,158194])
        _,_,lanes=static_map(path,junctions=True)
        self.assertIn((158190,0,-1),lanes)
        self.assertIn((158194,0,-1),lanes)

if __name__=='__main__':unittest.main()
