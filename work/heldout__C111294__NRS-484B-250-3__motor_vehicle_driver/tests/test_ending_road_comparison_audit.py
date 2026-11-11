import json
from pathlib import Path
import sys
import tempfile
import unittest


folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
from ending_road_comparison_audit import audit


def box(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class EndingRoadComparisonTests(unittest.TestCase):
    def test_changed_entry_order_with_fixed_topology_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            topology = {
                'highway_identity_source': 'retained Native lane graph and reviewed highway identity',
                'junction_id': 'J', 'subject_approach_lane': 'S',
                'other_approach_lane': 'T', 'subject_id': 'ending', 'other_id': 'through',
                'conflict_polygon_xy': box(0, 4, 0, 4),
                'lanes': {
                    'S': {'junction_id': 'J', 'highway_id': 'ending', 'successors': ['C']},
                    'C': {'junction_id': None, 'highway_id': 'through', 'successors': []},
                    'T': {'junction_id': 'J', 'highway_id': 'through', 'successors': ['U']},
                    'U': {'junction_id': None, 'highway_id': 'through', 'successors': []},
                },
            }
            sources = {}
            for label, subject_x in (('yield', [-3, -3, 1, 5]),
                                     ('proceed', [-3, 1, 5, 6])):
                path = root / label
                path.mkdir()
                (path / 'intersection_topology.json').write_text(json.dumps(topology))
                rows = []
                for i, (sx, oy) in enumerate(zip(subject_x, [-3, 1, 5, 6])):
                    rows.append({'frame': 70 + i, 'time_s': i / 20,
                                 'subject_id': 'ending', 'other_id': 'through',
                                 'subject_corners': box(sx, sx + 1, 1, 2),
                                 'other_corners': box(1, 2, oy, oy + 1)})
                (path / 'intersection_participants.jsonl').write_text(
                    ''.join(json.dumps(row) + '\n' for row in rows))
                sources[label] = path
            self.assertTrue(audit(sources['yield'], sources['proceed'])['passed'])
            topology['lanes']['C']['highway_id'] = 'ending'
            (sources['proceed'] / 'intersection_topology.json').write_text(json.dumps(topology))
            with self.assertRaisesRegex(ValueError, 'changed fixed lane topology'):
                audit(sources['yield'], sources['proceed'])
            (sources['proceed'] / 'intersection_topology.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing exact comparison original'):
                audit(sources['yield'], sources['proceed'])


if __name__ == '__main__':
    unittest.main()
