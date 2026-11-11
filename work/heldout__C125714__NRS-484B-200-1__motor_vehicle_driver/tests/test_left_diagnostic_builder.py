from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from left_diagnostic_builder import build, LEFT_CASE


class LeftDiagnosticBuilderTests(unittest.TestCase):
    def test_original_ego_pose_and_crossing_are_consistent(self):
        left = build(json.loads((ROOT/'diagnostic.json').read_text()))
        files = left['files']
        trace = json.loads(files['trace.jsonl'].splitlines()[0])
        evidence = json.loads(files['capture/evidence.jsonl'].splitlines()[0])
        road = json.loads(files['directed_roadway_footprints.jsonl'].splitlines()[0])
        graph = left['graphs'][9]
        ego = next(node['attributes'] for node in graph['nodes'] if node['id']=='ego')
        manifest = json.loads(files['capture/manifest.json'])
        self.assertEqual(manifest['case_id'], LEFT_CASE)
        self.assertEqual(trace['position_m'], evidence['ego']['position_m'])
        self.assertEqual(trace['position_m'], ego['original_observation']['position_m'])
        self.assertEqual(road['subject_lane_id'], -1)
        self.assertEqual(road['travel_tangent_xy'], [1, 0])
        self.assertLess(min(point[1] for point in road['ego_corners']), 0)
        self.assertEqual(manifest['sources']['trace.jsonl'],
                         sha256(files['trace.jsonl'].encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
