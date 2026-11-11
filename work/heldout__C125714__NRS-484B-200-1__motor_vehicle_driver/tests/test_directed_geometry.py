import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'directed_geometry.py'
SPEC = importlib.util.spec_from_file_location('directed_geometry', MODULE)
geometry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geometry)


def lane(lane_id, x, y, direction, width=3):
    return NS(road_id=7, lane_id=lane_id, lane_width=width,
              transform=NS(location=NS(x=x, y=y),
                           get_forward_vector=lambda: NS(x=direction, y=0)))


class DirectedGeometryTests(unittest.TestCase):
    def test_east_and_west_directed_edges(self):
        east = geometry.directed_road_section(lane(-1, 0, 1.5, 1),
                                               lane(1, 0, -1.5, -1))
        self.assertEqual(east['roadway_center_point_xy'], [0, 0])
        self.assertEqual(east['right_road_edge_xy'], [0, 3])
        self.assertEqual(east['left_road_edge_xy'], [0, -3])
        west = geometry.directed_road_section(lane(1, 0, -1.5, -1),
                                               lane(-1, 0, 1.5, 1))
        self.assertEqual(west['right_road_edge_xy'], [0, -3])
        self.assertEqual(west['left_road_edge_xy'], [0, 3])

    def test_rejects_unjoined_or_wrong_direction_lanes(self):
        subject = lane(-1, 0, 1.5, 1)
        with self.assertRaisesRegex(ValueError, 'share a center boundary'):
            geometry.directed_road_section(subject, lane(1, 0, -3, -1))
        with self.assertRaisesRegex(ValueError, 'travel direction'):
            geometry.directed_road_section(subject, lane(1, 0, -1.5, 1))
        with self.assertRaisesRegex(ValueError, 'opposite signs'):
            geometry.directed_road_section(subject, lane(-2, 0, -1.5, -1))

    def test_reads_native_body_vertices_and_actor_identity(self):
        vertices = [NS(x=i % 2, y=(i // 2) % 2, z=i // 4) for i in range(8)]
        ego = NS(id=19, get_transform=lambda: object(),
                 bounding_box=NS(get_world_vertices=lambda _: vertices))
        result = geometry.footprint_row(ego, lane(-1, 0, 1.5, 1),
                                        lane(1, 0, -1.5, -1), 42, 2.1)
        self.assertEqual(result['ego_id'], '19')
        self.assertEqual(result['frame'], 42)
        self.assertEqual(len(result['ego_corners']), 4)
        self.assertEqual(result['ego_corners'], [[0, 0], [1, 0], [0, 1], [1, 1]])

    def test_opposite_lane_selection_rejects_median_gap(self):
        subject = lane(-1, 0, 1.5, 1)
        opposite = lane(1, 0, -1.5, -1)
        subject.get_left_lane = lambda: opposite
        self.assertIs(geometry.adjacent_opposing_lane(subject), opposite)
        subject.get_left_lane = lambda: None
        with self.assertRaisesRegex(ValueError, 'No adjacent'):
            geometry.adjacent_opposing_lane(subject)
        subject.get_left_lane = lambda: lane(1, 0, -3, -1)
        with self.assertRaisesRegex(ValueError, 'share a center'):
            geometry.adjacent_opposing_lane(subject)


if __name__ == '__main__':
    unittest.main()
