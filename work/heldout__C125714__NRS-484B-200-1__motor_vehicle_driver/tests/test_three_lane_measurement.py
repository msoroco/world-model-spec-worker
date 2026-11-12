import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from three_lane_measurement import measure_three_lane


class ThreeLaneMeasurementTests(unittest.TestCase):
    def test_original_topology_and_rule_claim_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=json.loads((ROOT/'three-lane-diagnostic.json').read_text())
            for name in ('three_lane_roadway.jsonl','video_frames.jsonl','trace.jsonl'):
                (root/name).write_text(source['files'][name])
            self.assertAlmostEqual(measure_three_lane(root)['minimum_roadway_width_m'],10.5)
            path=root/'three_lane_roadway.jsonl'
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['applicable_lane_rule_verified']=True
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'unsupported'):
                measure_three_lane(root)
            rows[0]['applicable_lane_rule_verified']=False
            rows[0]['far_left_lane_tangent_xy']=[1,0]
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'direction pattern'):
                measure_three_lane(root)


if __name__=='__main__':
    unittest.main()
