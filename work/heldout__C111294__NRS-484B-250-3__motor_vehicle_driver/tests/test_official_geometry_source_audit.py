import json
from hashlib import sha256
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from official_geometry_binding import bind_geometry, _digest
from official_geometry_source_audit import audit
from test_official_geometry_binding import sources


def opendrive(include_road=True, include_signal=True):
    roads = [(1, '-1'), (2, '-1'), (3, '-1'), (5, '42'), (6, '42')]
    if not include_road:
        roads.remove((3, '-1'))
    rows = []
    for road_id, junction in roads:
        signal = ('<signals><signal id="signal-7"><validity fromLane="-1" '
                  'toLane="-1"/></signal></signals>') if road_id == 1 and include_signal else ''
        rows.append(f'<road id="{road_id}" junction="{junction}"><lanes><laneSection>'
                    f'<right><lane id="-1"/></right></laneSection></lanes>{signal}</road>')
    return '<OpenDRIVE>' + ''.join(rows) + '<junction id="42"/></OpenDRIVE>'


class OfficialGeometrySourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        world, routes, device = sources()
        world.to_opendrive = opendrive
        binding = bind_geometry(world, routes, device)
        self.write('official_geometry_binding.json', binding)
        self.write('road.xodr', world.to_opendrive())
        lanes = {}
        for role, path in (('subject', routes['subject']), ('other', routes['other'])):
            for index, point in enumerate(path):
                key = f'{role}-{index}'
                lanes[key] = {'road_id': point.road_id, 'lane_id': point.lane_id,
                              'junction_id': '42' if point.is_junction else None,
                              'successors': [f'{role}-{index+1}'] if index+1 < len(path) else []}
        self.write('intersection_topology.json', {
            'junction_id': '42', 'lanes': lanes,
            'subject_approach_lane': 'subject-0', 'other_approach_lane': 'other-0'})
        self.write('official_device_context.json', {
            'junction_id': '42', 'opendrive_signal_id': 'signal-7',
            'affected_road_id': 1, 'affected_lane_id': -1})

    def test_rebound_but_incomplete_map_rejected(self):
        for map_text, error in ((opendrive(False), 'route road'),
                                (opendrive(include_signal=False), 'governing signal')):
            with self.subTest(error=error):
                binding = json.loads((self.root / 'official_geometry_binding.json').read_text())
                binding['opendrive_sha256'] = sha256(map_text.encode()).hexdigest()
                binding['geometry_sha256'] = _digest(binding)
                self.write('official_geometry_binding.json', binding)
                self.write('road.xodr', map_text)
                with self.assertRaisesRegex(ValueError, error):
                    audit(self.root)

    def write(self, name, value):
        (self.root / name).write_text(value if isinstance(value, str) else json.dumps(value))

    def test_current_originals_join(self):
        result = audit(self.root)
        self.assertEqual(result['signal_id'], 'signal-7')
        self.assertFalse(result['physical_realization_claimed'])

    def test_capture_exit_extension_preserves_bound_selection(self):
        path = self.root / 'intersection_topology.json'
        topology = json.loads(path.read_text())
        topology['lanes']['subject-2']['successors'] = ['subject-3']
        topology['lanes']['subject-3'] = {
            'road_id': 3, 'lane_id': -1, 'junction_id': None, 'successors': []}
        self.write(path.name, topology)
        self.assertEqual(audit(self.root)['junction_id'], '42')

    def test_changed_originals_rejected(self):
        for name, change, error in (
            ('road.xodr', lambda _: '<OpenDRIVE changed="yes"/>', 'OpenDRIVE'),
            ('official_device_context.json', lambda d: {**d, 'opendrive_signal_id': 'other'}, 'signal'),
            ('intersection_topology.json', lambda d: {**d, 'junction_id': '99'}, 'junction'),
        ):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_text()
                value = original if name == 'road.xodr' else json.loads(original)
                self.write(name, change(value))
                with self.assertRaisesRegex(ValueError, error):
                    audit(self.root)
                path.write_text(original)

    def test_changed_route_and_missing_binding_rejected(self):
        path = self.root / 'intersection_topology.json'
        original = path.read_text()
        data = json.loads(original)
        data['lanes']['other-1']['road_id'] = 999
        self.write(path.name, data)
        with self.assertRaisesRegex(ValueError, 'route differs'):
            audit(self.root)
        path.write_text(original)
        (self.root / 'official_geometry_binding.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing official original source'):
            audit(self.root)


if __name__ == '__main__':
    unittest.main()
