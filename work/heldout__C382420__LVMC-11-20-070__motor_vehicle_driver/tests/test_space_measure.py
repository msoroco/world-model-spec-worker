import sys
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from space_measure import analyze
from space_finalizer import analyze as finalize
from space_construction import crosswalk_polygons, choose_region, connected_entry_route
from space_native_runner import check_config, PREFIX
from types import SimpleNamespace


def rectangle(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def fixture(kind='marked_crosswalk', blocked=False):
    scene = {'region_kind': kind, 'entry_region': rectangle(0, -2, 4, 2),
             'other_side_origin': [4, 0], 'receiving_path_end': [14, 0],
             'receiving_corridor': rectangle(4, -2, 14, 2),
             'vehicle_length_m': 3.5}
    occupants = [{'id': 'standing_queue', 'footprint': rectangle(5, -.8, 7, .8)}] if blocked else []
    rows = []
    for frame, x in enumerate((-4.0, -1.0, 1.0, 5.0)):
        rows.append({'frame': frame, 'time_s': frame / 20.0,
                     'signal_state': 'proceed', 'ego_footprint': rectangle(x, -.8, x + 2.0, .8),
                     'downstream_occupants': occupants,
                     'passage_participants': [{'id': 'walker', 'kind': 'pedestrian',
                                               'passage_polygon': rectangle(1, -3, 2, 3)}]})
    return scene, rows


class SpaceMeasurementTest(unittest.TestCase):
    def test_crosswalk_clear_and_blocked_entry(self):
        clear = analyze(*fixture())
        blocked = analyze(*fixture(blocked=True))
        self.assertEqual(clear['entry']['frame'], 1)
        self.assertEqual(clear['entry']['downstream_available_length_m'], 10)
        self.assertEqual(blocked['entry']['downstream_available_length_m'], 1)
        self.assertEqual(blocked['entry']['first_downstream_occupant'], 'standing_queue')
        self.assertEqual(blocked['entry']['signal_state'], 'proceed')
        self.assertTrue(blocked['any_passage_overlap'])
        self.assertFalse(blocked['legal_sufficiency_decided'])

    def test_intersection_alternative(self):
        scene, rows = fixture(kind='intersection', blocked=True)
        self.assertEqual(analyze(scene, rows)['entry']['region_kind'], 'intersection')

    def test_missing_and_changed_sources_rejected(self):
        scene, rows = fixture()
        rows[1]['signal_state'] = None
        with self.assertRaisesRegex(ValueError, 'Signal readback missing'):
            analyze(scene, rows)
        scene, rows = fixture()
        rows[2]['time_s'] = 9
        with self.assertRaisesRegex(ValueError, 'frame/time join'):
            analyze(scene, rows)
        scene, rows = fixture()
        rows[1]['ego_footprint'] = rectangle(0, 0, 0, 0)
        with self.assertRaisesRegex(ValueError, 'Invalid ego body'):
            analyze(scene, rows)

    def test_saved_finalizer_joins_original_sources(self):
        scene, rows = fixture(blocked=True)
        case = 'heldout__C382420__LVMC-11-20-070__motor_vehicle_driver__crosswalk_blocked_downstream'
        scene['case_id'] = case
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.json').write_text(json.dumps({'selected_case_id': case}))
            (root / 'space_scene.json').write_text(json.dumps(scene))
            for index, row in enumerate(rows):
                row['carla_frame'] = 200 + index
            (root / 'space_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            (root / 'trace.jsonl').write_text(''.join(json.dumps(
                {'frame': row['carla_frame'], 'time_s': row['time_s']}) + '\n' for row in rows))
            (root / 'video_frames.jsonl').write_text(''.join(json.dumps(
                {'video_frame': index, 'carla_frame': row['carla_frame'], 'time_s': row['time_s']}) + '\n'
                for index, row in enumerate(rows)))
            report = finalize(root)
            self.assertEqual(report['case_id'], case)
            self.assertEqual(report['measurements']['space_at_entry']['value']['entry']['downstream_available_length_m'], 1)
            self.assertEqual(len((root / 'signal_indication.jsonl').read_text().splitlines()), 4)
            (root / 'trace.jsonl').write_text('tampered\n')
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                finalize(root)

    def test_native_crosswalk_split_and_connected_route(self):
        def point(x, y):
            return SimpleNamespace(x=x, y=y)
        vertices = [point(x, y) for x, y in [(-1,-2), (1,-2), (1,2), (-1,2), (-1,-2),
                                             (20,-2), (22,-2), (22,2), (20,2), (20,-2)]]
        self.assertEqual(len(crosswalk_polygons(vertices)), 2)
        with self.assertRaisesRegex(ValueError, 'Unclosed'):
            crosswalk_polygons(vertices[:-1])
        class Lane:
            pass
        Lane.Driving = Lane()
        class Waypoint:
            lane_type = Lane.Driving
            lane_id = 1
            def __init__(self, x, junction=False):
                self.s = x
                self.road_id = 1 if x < 4 else 2
                self.is_junction = junction
                self.transform = SimpleNamespace(location=point(x, 0))
                self.next_waypoint = None
            def next(self, step):
                return [self.next_waypoint] if self.next_waypoint else []
            def get_junction(self):
                box = SimpleNamespace(location=point(2, 0), extent=point(2, 2))
                return SimpleNamespace(id=11, bounding_box=box)
        route = [Waypoint(x, junction=1 <= x <= 3) for x in (-4,-2,0,1,2,3,4,6)]
        for left, right in zip(route, route[1:]):
            left.next_waypoint = right
        world_map = SimpleNamespace(get_spawn_points=lambda: [SimpleNamespace(location=point(-4,0))],
                                    get_waypoint=lambda location: route[0],
                                    get_crosswalks=lambda: vertices)
        selected = connected_entry_route(world_map)
        self.assertEqual([w.s for w in selected], [w.s for w in route[:-1]])
        self.assertEqual(len(choose_region(world_map, selected, 'marked_crosswalk')), 4)
        self.assertEqual(len(choose_region(world_map, selected, 'intersection')), 4)

    def test_exact_native_case_mechanisms(self):
        base = {'law_id': 'LVMC-11-20-070', 'cell_id': 'C382420',
                'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                'frames': 160, 'cameras': [{}, {}, {}, {}]}
        for suffix, expected in [('crosswalk_clear_downstream', ('marked_crosswalk', False)),
                                 ('crosswalk_blocked_downstream', ('marked_crosswalk', True)),
                                 ('intersection_clear_downstream', ('intersection', False)),
                                 ('intersection_blocked_downstream', ('intersection', True))]:
            config = {**base, 'selected_case_id': PREFIX + suffix,
                      'case': {'case_id': PREFIX + suffix}}
            self.assertEqual(check_config(config), expected)
        config['case']['case_id'] = PREFIX + 'crosswalk_clear_downstream'
        with self.assertRaisesRegex(ValueError, 'Unknown exact'):
            check_config(config)


if __name__ == '__main__':
    unittest.main()
