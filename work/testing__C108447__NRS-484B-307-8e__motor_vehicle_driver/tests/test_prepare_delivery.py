import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

BASE = Path(__file__).resolve().parents[1]
for name in ('map_binding', 'property_route', 'case_observation', 'saved_delivery',
             'physical_completion', 'delivery_audit', 'prepare_delivery'):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
binding = sys.modules['map_binding']
preparer = sys.modules['prepare_delivery']
delivery = sys.modules['delivery_audit']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrepareDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempt = self.root / 'attempt'
        self.attempt.mkdir()
        self.case = 'testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__private_bypass'
        road = self.root / 'source.xodr'
        road.write_text('<OpenDRIVE><header name="source"/></OpenDRIVE>\n')
        routes = {'lot': [[-3, 5], [5, 5], [13, 5]]}
        authority = self.root / 'parcel-source.json'
        authority.write_text(json.dumps({
            'format': 'original-parcel-authority-v1', 'opendrive_sha256': sha(road),
            'coordinate_frame': 'native-map', 'map_name': 'source',
            'intersecting_street_id': 'street-B', 'connector_routes': routes,
            'roadway_route': [[-3, -2], [5, -2], [13, -2]],
            'properties': [{'id': 'lot', 'status': 'private', 'authority': 'fixture reviewed source',
                            'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}],
        }, sort_keys=True) + '\n')
        self.packet = binding.bind(road, authority, property_id='lot',
                                   intersecting_street_id='street-B', connector_routes=routes,
                                   review={'reviewer': 'fixture reviewer', 'source': 'fixture register',
                                           'decision': 'reviewed'},
                                   roadway_route=[[ -3, -2], [5, -2], [13, -2]])
        self.packet_path = self.root / 'map-packet.input.json'
        self.packet_path.write_text(json.dumps(self.packet, sort_keys=True) + '\n')
        frames = list(range(100, 120))
        ego = [{'frame': frame, 'time_s': i / 20, 'x': -3 if i == 0 else 5 if i == 1 else 13,
                'y': 5} for i, frame in enumerate(frames)]
        approach = [{'frame': frame, 'device_id': 'A', 'source': 'original signal',
                     'facing_ego': True, 'state': 'red_alone'} for frame in frames]
        destination = [{'frame': frame, 'device_id': 'B', 'source': 'original signal',
                        'facing_ego': False, 'state': 'yellow'} for frame in frames]
        trace = {'format': 'original-native-property-route-v1', 'case_id': self.case,
                 'status': 'recorded_unreviewed', 'coordinate_frame': 'native-map',
                 'actor_class': 'vehicle', 'actor_source': {'source': 'original actor registry'},
                 'ego': ego, 'approach_signal': approach[0], 'destination_signal': destination[2],
                 'approach_signal_history': approach, 'destination_signal_history': destination,
                 'destination_street_id': 'street-B', 'destination_entry_frame': 102,
                 'purpose': {'source': 'original intent record', 'value': 'avoid_red'}}
        (self.attempt / 'trace.json').write_text(json.dumps(trace, sort_keys=True) + '\n')
        sink = io.BytesIO()
        Image.new('RGB', (2, 2), (12, 22, 32)).save(sink, format='PNG')
        pixels = sink.getvalue()
        pixel_sha = hashlib.sha256(pixels).hexdigest()
        rows = []
        for i, frame in enumerate(frames):
            cameras = {}
            for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
                cameras[name] = {'member': f'{frame}.png', 'sha256': pixel_sha}
            rows.append({'frame': frame, 'time_s': i / 20, 'cameras': cameras})
        (self.attempt / 'frame-map.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        for name in rows[0]['cameras']:
            with ZipFile(self.attempt / f'{name}.zip', 'w') as archive:
                for frame in frames:
                    archive.writestr(f'{frame}.png', pixels)

    def test_self_contained_bundle_passes_original_audit(self):
        result = preparer.prepare(self.attempt, self.packet_path, self.case, 'lot', expected_frames=20)
        bundle = json.loads(Path(result['bundle_path']).read_text())
        self.assertFalse(Path(bundle['map']['path']).is_absolute())
        self.assertFalse(Path(json.loads((self.attempt / 'map-packet.json').read_text())['source']['path']).is_absolute())
        audited = delivery.audit(self.attempt, bundle, expected_frames=20)
        self.assertEqual(audited['physical_completion']['status'], 'met')
        self.assertFalse(audited['physical_acceptance_claimed'])

    def test_rejects_resealed_packet_not_equal_reviewed_binding(self):
        packet = json.loads(self.packet_path.read_text())
        packet['properties'][0]['status'] = 'public'
        self.packet_path.write_text(json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'differs from reviewed original binding'):
            preparer.prepare(self.attempt, self.packet_path, self.case, 'lot', expected_frames=20)


if __name__ == '__main__':
    unittest.main()
