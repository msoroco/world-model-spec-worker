import hashlib
import json
import sys
import unittest
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_crossing import validate_source_packet, controller_request, construct_native
from saved_signal_audit import audit

MAP = b'<OpenDRIVE>reviewed test map</OpenDRIVE>'
REVIEW = b'operator-reviewed highway and device inventory'
SHA = hashlib.sha256


def packet():
    return {'schema': 'median-signal-review-v1', 'map_sha256': SHA(MAP).hexdigest(),
            'review_sha256': SHA(REVIEW).hexdigest(), 'cell_id': 'C125751',
            'law_id': 'NRS-484B-250-1', 'driver_scope_reviewed': True,
            'crossing_id': 'median-1', 'official_device_inventory': [{'id': 'light-1'}],
            'ego_highway': 'A', 'other_highway': 'B', 'crossing_bounds_xy_m': [-2, -2, 2, 2],
            'ego_road_id': 1, 'other_road_id': 2,
            'ego_route_xy_m': [[-8, 0], [0, 0], [8, 0]],
            'other_route_xy_m': [[0, -8], [0, 0], [0, 8]]}


def sealed_history():
    rows = []
    # Other enters at 1 and clears at 3; ego enters at 3 and clears at 5.
    ego = [[-8, 0], [-6, 0], [-4, 0], [0, 0], [1, 0], [6, 0]]
    other = [[0, -6], [0, 0], [0, 1], [0, 6], [0, 8], [0, 10]]
    for i in range(6):
        rows.append({'frame': i, 'time_s': i/20, 'ego_light_readback': 'Green',
                     'ego': {'actor_id': 11, 'alive': True, 'xy_m': ego[i]},
                     'other': {'actor_id': 12, 'alive': True, 'xy_m': other[i]}})
    payload = json.dumps({'map_sha256': SHA(MAP).hexdigest(),
                          'crossing_bounds_xy_m': [-2, -2, 2, 2],
                          'ego_actor_id': 11, 'other_actor_id': 12,
                          'frames': rows}).encode()
    seal = {'payload_sha256': SHA(payload).hexdigest(), 'case_id': 'case-1',
            'review_sha256': SHA(REVIEW).hexdigest(), 'map_sha256': SHA(MAP).hexdigest(),
            'expected_frames': 6, 'crossing_id': 'median-1',
            'ego_route_sha256': 'ego-route', 'other_route_sha256': 'other-route',
            'camera_plan_sha256': 'camera-plan', 'duration_frames': 6,
            'ego_blueprint': 'vehicle.a', 'other_blueprint': 'vehicle.b'}
    return seal, payload


class SignalCrossingTest(unittest.TestCase):
    def test_saved_cli_uses_sealed_payload(self):
        seal, payload = sealed_history()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'packet.json').write_text(json.dumps(seal))
            (root/'frames.json').write_bytes(payload)
            cmd = [sys.executable, str(Path(__file__).resolve().parents[1]/'saved_signal_audit.py'),
                   '--packet', str(root/'packet.json'), '--payload', str(root/'frames.json'),
                   '--case', 'case-1', '--source-sha256', SHA(REVIEW).hexdigest(),
                   '--output', str(root/'result.json')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads((root/'result.json').read_text())['other_entered_first'])
            (root/'frames.json').write_bytes(payload+b' ')
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)

    def test_native_construction_checks_both_routes_and_device_before_spawn(self):
        class Point:
            def __init__(self, x, y):
                self.x, self.y = x, y

        class Waypoint:
            def __init__(self, x, y, road_id, junction):
                self.transform = type('Transform', (), {'location': Point(x, y)})()
                self.road_id, self.lane_id, self.is_junction = road_id, -1, junction
                self.successor = []

            def next(self, distance):
                return self.successor

        class Map:
            def __init__(self):
                self.ego = [Waypoint(-8, 0, 1, False), Waypoint(0, 0, 3, True),
                            Waypoint(8, 0, 4, False)]
                self.other = [Waypoint(0, -8, 2, False), Waypoint(1, 0, 5, True),
                              Waypoint(0, 8, 6, False)]
                for chain in (self.ego, self.other):
                    for a, b in zip(chain, chain[1:]):
                        a.successor = [b]

            def to_opendrive(self):
                return MAP.decode()

            def get_waypoint(self, location, project_to_road):
                assert project_to_road is False
                for wp in self.ego + self.other:
                    p = wp.transform.location
                    if (p.x, p.y) == (location.x, location.y):
                        return wp
                return None

        class World:
            def __init__(self, world_map):
                self.world_map = world_map

            def get_map(self):
                return self.world_map

        created = []
        spawn = lambda party, transform: created.append(party) or object()
        resolve = lambda world, item: type('Device', (), {'get_state': lambda self: 'TrafficLightState.Green'})() if item['id'] == 'light-1' else None
        m = Map()
        p = packet(); p['other_route_xy_m'][1] = [1, 0]
        result = construct_native(World(m), p, MAP, REVIEW,
                                  lambda x, y: Point(x, y), resolve, spawn)
        self.assertEqual(created, ['ego', 'other'])
        self.assertEqual(result['initial_light_readback'], 'Green')
        created.clear()
        with self.assertRaises(ValueError):
            construct_native(World(m), p, MAP, REVIEW,
                             lambda x, y: Point(x, y), lambda world, item: None, spawn)
        self.assertEqual(created, [])
        m.other[0].successor = []
        with self.assertRaises(ValueError):
            construct_native(World(m), p, MAP, REVIEW,
                             lambda x, y: Point(x, y), resolve, spawn)
        self.assertEqual(created, [])

    def test_source_and_geometry(self):
        self.assertEqual(validate_source_packet(packet(), MAP, REVIEW)['crossing_id'], 'median-1')
        for key, value in [('map_sha256', '0'*64), ('review_sha256', '0'*64),
                           ('driver_scope_reviewed', False), ('official_device_inventory', []),
                           ('other_highway', 'A')]:
            p = packet(); p[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_source_packet(p, MAP, REVIEW)

    def test_route_crossing_and_signal_controller(self):
        p = packet(); p['other_route_xy_m'] = [[0, -8], [0, -4], [0, -3]]
        with self.assertRaises(ValueError):
            validate_source_packet(p, MAP, REVIEW)
        self.assertEqual(controller_request(True, True, False, 'Green', True), 'brake')
        self.assertEqual(controller_request(True, True, True, 'Green', True), 'proceed')
        self.assertEqual(controller_request(True, True, True, 'Red', True), 'brake')
        self.assertEqual(controller_request(True, True, True, None, True), 'brake')

    def test_sealed_original_frame_audit(self):
        seal, payload = sealed_history()
        report = audit(seal, payload, 'case-1', SHA(REVIEW).hexdigest())
        self.assertTrue(report['other_entered_first'])
        self.assertEqual(report['other_entry_frame'], 1)
        with self.assertRaises(ValueError):
            audit(seal, payload+b' ', 'case-1', SHA(REVIEW).hexdigest())
        with self.assertRaises(ValueError):
            audit(seal, payload, 'wrong-case', SHA(REVIEW).hexdigest())
        with self.assertRaises(ValueError):
            audit(seal, payload, 'case-1', '0'*64)

    def test_missing_readback_and_actor(self):
        seal, payload = sealed_history()
        history = json.loads(payload)
        for mutation in ('light', 'actor', 'frame', 'position'):
            h = json.loads(payload)
            if mutation == 'light':
                h['frames'][2].pop('ego_light_readback')
            elif mutation == 'actor':
                h['frames'][2]['other']['actor_id'] = 99
            elif mutation == 'frame':
                h['frames'][2]['frame'] = 8
            else:
                h['frames'][2]['ego']['xy_m'] = None
            changed = json.dumps(h).encode()
            s = dict(seal, payload_sha256=SHA(changed).hexdigest())
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit(s, changed, 'case-1', SHA(REVIEW).hexdigest())
        seal['expected_frames'] = 900
        with self.assertRaises(ValueError):
            audit(seal, payload, 'case-1', SHA(REVIEW).hexdigest())


if __name__ == '__main__':
    unittest.main()
