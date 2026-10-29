import tempfile,unittest
from pathlib import Path
from analyze import body_gap,truck_width_and_lanes
class TestTruckSources(unittest.TestCase):
 def test_missing_case_specific_source(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: truck_history.jsonl'):body_gap(Path(d))
 def test_qualifying_width_context(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'truck_context.json';p.write_text('{"trucks":[{"measured_bbox_width_m":2.6},{"measured_bbox_width_m":2.6}],"same_direction_lane_count":1,"source":"test"}')
   self.assertEqual(truck_width_and_lanes(Path(d))['same_direction_lane_count'],1)
