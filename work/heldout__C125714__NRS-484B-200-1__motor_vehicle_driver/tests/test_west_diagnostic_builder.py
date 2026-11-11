import json
from hashlib import sha256
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from west_diagnostic_builder import build, WEST_CASE


ROOT = Path(__file__).resolve().parents[1]


class WestDiagnosticBuilderTests(unittest.TestCase):
    def test_opposite_lane_originals_and_graph_ego_agree(self):
        east = json.loads((ROOT / 'diagnostic.json').read_text())
        west = build(east)
        files = west['files']
        trace = json.loads(files['trace.jsonl'].splitlines()[0])
        road = json.loads(files['directed_roadway_footprints.jsonl'].splitlines()[0])
        evidence = json.loads(files['capture/evidence.jsonl'].splitlines()[0])
        graph = west['graphs'][9]
        ego = next(node['attributes'] for node in graph['nodes'] if node['id'] == 'ego')
        manifest = json.loads(files['capture/manifest.json'])
        self.assertEqual(manifest['case_id'], WEST_CASE)
        self.assertEqual(trace['position_m'], evidence['ego']['position_m'])
        self.assertEqual(trace['position_m'], ego['original_observation']['position_m'])
        self.assertEqual(evidence['world']['road_projection']['lane_id'], 1)
        self.assertEqual(road['subject_lane_id'], 1)
        self.assertEqual(road['travel_tangent_xy'], [-1, 0])
        self.assertEqual(trace['heading_deg'], 180)
        self.assertLess(trace['position_m'][1], 0)
        east_road = json.loads(east['files']['directed_roadway_footprints.jsonl'].splitlines()[0])
        self.assertAlmostEqual(road['ego_corners'][0][1], east_road['ego_corners'][0][1] - 3.5)
        self.assertEqual(manifest['sources']['trace.jsonl'],
                         sha256(files['trace.jsonl'].encode()).hexdigest())


if __name__ == '__main__':
    unittest.main()
