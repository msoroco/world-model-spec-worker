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
for name in ('property_route', 'case_observation', 'saved_delivery', 'physical_completion', 'delivery_audit'):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
audit = sys.modules['saved_delivery']
original_delivery = sys.modules['delivery_audit']


class SavedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = 'testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__private_bypass'
        original = self.root / 'original-map.json'
        xodr = self.root / 'original.xodr'
        xodr.write_text('<OpenDRIVE><header name="source"/></OpenDRIVE>\n')
        connector = {'lot': [[-3, 5], [5, 5], [13, 5]]}
        original.write_text(json.dumps({'opendrive_sha256': audit.sha(xodr.read_bytes()),
                                        'connector_routes': connector}) + '\n')
        map_packet = {
            'source': {'kind': 'original_native_map_and_property_authority', 'path': str(original), 'sha256': audit.sha(original.read_bytes())},
            'native_map': {'path': str(xodr), 'sha256': audit.sha(xodr.read_bytes()), 'map_name': 'source'},
            'authority_review': {'decision': 'reviewed', 'reviewer': 'fixture reviewer', 'source': 'fixture register'},
            'coordinate_frame': 'native-map', 'intersecting_street_id': 'street-B',
            'connector_routes': connector,
            'properties': [{'id': 'lot', 'status': 'private', 'authority': 'original parcel authority',
                            'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}],
        }
        original.write_text(json.dumps({
            'format': 'original-parcel-authority-v1',
            'opendrive_sha256': audit.sha(xodr.read_bytes()),
            'map_name': 'source', 'coordinate_frame': 'native-map',
            'intersecting_street_id': 'street-B', 'connector_routes': connector,
            'roadway_route': None, 'properties': map_packet['properties'],
        }) + '\n')
        map_packet['source']['sha256'] = audit.sha(original.read_bytes())
        frames = list(range(100, 120))
        self.trace = {'case_id': self.case, 'coordinate_frame': 'native-map', 'actor_class': 'vehicle',
                      'actor_source': {'source': 'original registry'},
                      'ego': [{'frame': f, 'time_s': i / 20, 'x': -3 if i == 0 else 13 if i >= 2 else 5,
                               'y': 5} for i, f in enumerate(frames)],
                      'approach_signal_history': [], 'destination_signal_history': [],
                      'destination_street_id': 'street-B', 'destination_entry_frame': 102,
                      'purpose': {'source': 'original intent record', 'value': 'avoid_red'}}
        for f in frames:
            self.trace['approach_signal_history'].append({'frame': f, 'device_id': 'A', 'source': 'original device', 'facing_ego': True, 'state': 'red_alone'})
            self.trace['destination_signal_history'].append({'frame': f, 'device_id': 'B', 'source': 'original device', 'facing_ego': False, 'state': 'yellow'})
        self.trace['approach_signal'] = self.trace['approach_signal_history'][0]
        self.trace['destination_signal'] = self.trace['destination_signal_history'][2]
        self.bundle = {'format': 'original-native-property-delivery-v1', 'case_id': self.case,
                       'diagnostic_fixture': False, 'cameras': {}}
        for name, content in [('map', map_packet), ('trace', self.trace), ('case', {'case_id': self.case})]:
            self.bundle[name] = self.write(name + '.json', json.dumps(content) + '\n')
        image = Image.new('RGB', (2, 2), (12, 22, 32))
        sink = io.BytesIO()
        image.save(sink, format='PNG')
        pixels = sink.getvalue()
        for camera in audit.CAMERAS:
            path = self.root / (camera + '.zip')
            members = []
            with ZipFile(path, 'w') as archive:
                for f in frames:
                    member = f'{f}.png'
                    archive.writestr(member, pixels)
                    members.append({'frame': f, 'member': member, 'sha256': audit.sha(pixels)})
            self.bundle['cameras'][camera] = {'path': path.name, 'sha256': audit.sha(path.read_bytes()), 'frames': members}
        frame_rows = []
        for i, f in enumerate(frames):
            frame_rows.append({'frame': f, 'time_s': i / 20,
                               'cameras': {camera: {'member': f'{f}.png', 'sha256': self.bundle['cameras'][camera]['frames'][i]['sha256']}
                                           for camera in audit.CAMERAS}})
        self.bundle['frame_map'] = self.write('frames.jsonl', ''.join(json.dumps(row) + '\n' for row in frame_rows))

    def write(self, name, content):
        path = self.root / name
        path.write_text(content)
        return {'path': name, 'sha256': audit.sha(path.read_bytes())}

    def test_positive_full_pixel_decode_and_observation(self):
        result = audit.audit(self.root, self.bundle, expected_frames=20)
        self.assertEqual(result['decoded_original_images'], {c: 20 for c in audit.CAMERAS})
        self.assertTrue(result['observations']['all_observation_conditions_present'])
        self.assertEqual(result['case_observation_audit']['planned_case'], 'private_bypass')
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_independent_original_route_completion(self):
        result = original_delivery.audit(self.root, self.bundle, expected_frames=20)
        self.assertEqual(result['physical_completion']['status'], 'met')
        self.assertEqual(result['physical_completion']['observed']['endpoint_error_m'], 0)

    def test_independent_audit_rejects_sealed_false_entry(self):
        trace = json.loads((self.root / 'trace.json').read_text())
        trace['ego'][2]['x'] = 5
        self.bundle['trace'] = self.write('trace.json', json.dumps(trace) + '\n')
        with self.assertRaisesRegex(ValueError, 'Original physical route completion required'):
            original_delivery.audit(self.root, self.bundle, expected_frames=20)

    def test_diagnostic_rejected(self):
        self.bundle['diagnostic_fixture'] = True
        with self.assertRaisesRegex(ValueError, 'diagnostic source'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_missing_camera_rejected(self):
        del self.bundle['cameras']['driver_reference']
        with self.assertRaisesRegex(ValueError, 'four original camera'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_trace_tamper_rejected(self):
        (self.root / 'trace.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'trace source hash'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_byte_identical_source_alias_and_traversal_rejected(self):
        trace = self.root / 'trace.json'
        original = trace.read_bytes()
        alias = self.root / 'trace-copy.json'
        alias.write_bytes(original)
        trace.unlink()
        trace.symlink_to(alias)
        with self.assertRaisesRegex(ValueError, 'symlink alias'):
            audit.audit(self.root, self.bundle, expected_frames=20)
        trace.unlink()
        trace.write_bytes(original)
        self.bundle['trace']['path'] = 'nested/../trace.json'
        with self.assertRaisesRegex(ValueError, 'path traversal'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_sealed_wrong_case_observation_rejected(self):
        trace = json.loads((self.root / 'trace.json').read_text())
        for row in trace['approach_signal_history']:
            row['state'] = 'green'
        trace['approach_signal']['state'] = 'green'
        self.bundle['trace'] = self.write('trace.json', json.dumps(trace) + '\n')
        with self.assertRaisesRegex(ValueError, 'steady red alone approach'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_original_map_tamper_rejected(self):
        (self.root / 'original.xodr').write_text('<OpenDRIVE/>\n')
        with self.assertRaisesRegex(ValueError, 'original OpenDRIVE source hash'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_sealed_route_override_rejected(self):
        packet = json.loads((self.root / 'map.json').read_text())
        packet['connector_routes']['lot'][1][1] = 6
        self.bundle['map'] = self.write('map.json', json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'saved connector route differs'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_resealed_parcel_classification_override_rejected(self):
        packet = json.loads((self.root / 'map.json').read_text())
        packet['properties'][0]['status'] = 'public'
        self.bundle['map'] = self.write('map.json', json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'saved parcel classification or boundaries differ'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_missing_connector_route_rejected_even_when_both_packets_omit_it(self):
        packet = json.loads((self.root / 'map.json').read_text())
        authority = json.loads((self.root / 'original-map.json').read_text())
        del packet['connector_routes']
        del authority['connector_routes']
        (self.root / 'original-map.json').write_text(json.dumps(authority) + '\n')
        packet['source']['sha256'] = audit.sha((self.root / 'original-map.json').read_bytes())
        self.bundle['map'] = self.write('map.json', json.dumps(packet) + '\n')
        with self.assertRaisesRegex(ValueError, 'saved connector route differs'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_frame_gap_rejected(self):
        rows = (self.root / 'frames.jsonl').read_text().splitlines()
        row = json.loads(rows[5])
        row['frame'] += 2
        rows[5] = json.dumps(row)
        self.bundle['frame_map'] = self.write('frames.jsonl', '\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'contiguous original frame'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_original_media_tamper_rejected(self):
        path = self.root / 'reference_corner.zip'
        with ZipFile(path, 'a') as archive:
            archive.writestr('extra.txt', 'different')
        self.bundle['cameras']['reference_corner']['sha256'] = audit.sha(path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'image inventory differs'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_resealed_duplicate_image_member_rejected(self):
        path = self.root / 'reference_corner.zip'
        with ZipFile(path, 'a') as archive:
            archive.writestr('100.png', archive.read('100.png'))
        self.bundle['cameras']['reference_corner']['sha256'] = audit.sha(path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'duplicate entries'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_production_image_profile_rejected_when_wrong(self):
        image = Image.new('RGB', (2, 2), (1, 2, 3))
        sink = io.BytesIO()
        image.save(sink, format='PNG')
        with Image.open(io.BytesIO(sink.getvalue())) as decoded:
            audit.validate_original_image(decoded, 'overview', 20)
            with self.assertRaisesRegex(ValueError, 'profile required'):
                audit.validate_original_image(decoded, 'overview', 900)

    def test_case_rebind_rejected(self):
        self.bundle['case_id'] = 'wrong-case'
        with self.assertRaisesRegex(ValueError, 'case identity differs'):
            audit.audit(self.root, self.bundle, expected_frames=20)

    def test_camera_frame_map_rebind_rejected(self):
        rows = (self.root / 'frames.jsonl').read_text().splitlines()
        row = json.loads(rows[5])
        row['cameras']['reference_corner']['member'] = 'other.png'
        rows[5] = json.dumps(row)
        self.bundle['frame_map'] = self.write('frames.jsonl', '\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'original frame map image join'):
            audit.audit(self.root, self.bundle, expected_frames=20)


if __name__ == '__main__':
    unittest.main()
