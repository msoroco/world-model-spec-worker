from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from delivery_audit import verify_native_alley_sources


CASE = 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__person_3mps'


class NativeDeliverySourceTests(unittest.TestCase):
    def make_attempt(self, root):
        source = {'format': 'worker-native-alley-survey-v1',
                  'verified_alley': True, 'reviewer': 'test reviewer',
                  'evidence_reference': 'reviewed map asset',
                  'map_name': 'TestMap', 'opendrive_sha256': 'a' * 64,
                  'polygon_xy': [[0, -3], [40, -3], [40, 3], [0, 3]],
                  'alley_width_m': 6,
                  'routes': {'east': {'road_id': 5, 'lane_id': 1, 'start_s': 2.0}}}
        raw = (json.dumps(source, indent=2) + '\n').encode()
        (root / 'alley-survey-original.json').write_bytes(raw)
        verified = {'format': 'worker-native-alley-verification-v1',
                    'verified': True, 'map_name': source['map_name'],
                    'opendrive_sha256': source['opendrive_sha256'],
                    'operator_manifest_sha256': sha256(raw).hexdigest(),
                    'polygon_xy': source['polygon_xy'],
                    'alley_width_m': source['alley_width_m'],
                    'selected_direction': 'east',
                    'selected_route': source['routes']['east']}
        (root / 'alley-survey-verification.json').write_text(json.dumps(verified))
        probe = {'case_id': CASE, 'native_survey': verified,
                 'route': {'map_name': 'TestMap', 'road_id': 5,
                           'lane_id': 1, 'start_s': 2.0,
                           'polygon_source_sha256': sha256(raw).hexdigest()}}
        (root / 'construction-probe.json').write_text(json.dumps(probe))
        return source, verified, probe

    def test_exact_source_and_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, verified, _ = self.make_attempt(root)
            self.assertEqual(verify_native_alley_sources(
                root, {'alley_direction': 'east'}, CASE), verified)

    def test_tampered_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_attempt(root)
            (root / 'alley-survey-original.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'survey is absent or differs'):
                verify_native_alley_sources(root, {'alley_direction': 'east'}, CASE)

    def test_changed_route_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, probe = self.make_attempt(root)
            probe['route']['lane_id'] = 2
            (root / 'construction-probe.json').write_text(json.dumps(probe))
            with self.assertRaisesRegex(ValueError, 'route differs'):
                verify_native_alley_sources(root, {'alley_direction': 'east'}, CASE)


if __name__ == '__main__':
    unittest.main()
