import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import encounter
import native_acquisition as native
import saved_audit


class Adapter:
    def __init__(self, *, bad_camera=None, bad_frame=None, bad_occupancy=False):
        self.frame = 100
        self.destroyed = []
        self.braked = False
        self.bad_camera = bad_camera
        self.bad_frame = bad_frame
        self.bad_occupancy = bad_occupancy

    def tick(self):
        frame = self.frame
        self.frame += 1
        return frame, (frame - 100) / 20

    def read_actor(self, actor):
        role = actor
        packet = {'original_frame': self.frame - 1, 'id': actor,
                  'xy': [float(self.frame - 100), float(len(actor))],
                  'speed_mps': 2.0, 'blueprint': role + '-blueprint'}
        if role == 'occupant':
            packet['vehicle_id'] = 'wrong' if self.bad_occupancy else 'crossing_vehicle'
        if self.bad_frame == role:
            packet['original_frame'] += 1
        return packet

    def read_control(self, ego, crossing):
        return {'original_frame': self.frame - 1, 'ego_command': 'drive',
                'crossing_command': 'drive'}

    def read_camera(self, name):
        frame = self.frame - 1
        if self.bad_camera == name:
            frame += 1
        return frame, f'{name}-{frame}'.encode()

    def brake(self, ego):
        self.braked = True

    def destroy(self, actor):
        self.destroyed.append(actor)


def site():
    return {'site_sha256': 'a' * 64, 'map_sha256': 'b' * 64,
            'camera_plan_sha256': 'c' * 64, 'public_access_basis': 'highway'}


def actors(case):
    return {'case_id': case.case_id, 'ego': 'ego', 'crossing_vehicle': 'crossing_vehicle',
            'occupant': 'occupant', 'property': 'property',
            'owned': ('ego', 'crossing_vehicle', 'property')}


class NativeAcquisitionTests(unittest.TestCase):
    def test_900_frame_original_sources_and_saved_rejoin(self):
        case = encounter.CASES[0]
        adapter = Adapter()
        with TemporaryDirectory() as tmp:
            receipt = native.capture(adapter, actors(case), case, site(), Path(tmp))
            self.assertEqual(receipt['frame_count'], 900)
            self.assertEqual(receipt['last_original_frame'], 999)
            evidence = saved_audit.audit_native_acquisition(Path(tmp), receipt)
            self.assertFalse(evidence['physical_completion'])
            self.assertEqual(evidence['frame_count'], 900)
            self.assertTrue(adapter.braked)
            self.assertEqual(adapter.destroyed, ['property', 'crossing_vehicle', 'ego'])
            row = json.loads((Path(tmp) / 'original-history.jsonl').read_text().splitlines()[0])
            self.assertEqual(row['occupant_vehicle_id'], 'crossing_vehicle')
            self.assertEqual(row['case_id'], receipt['case_id'])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                native.capture(Adapter(), actors(case), case, site(), Path(tmp))

    def test_missing_camera_and_actor_frame_fail_with_cleanup(self):
        case = encounter.CASES[0]
        for variant in ({'bad_camera': 'rear'}, {'bad_frame': 'occupant'},
                        {'bad_occupancy': True}):
            adapter = Adapter(**variant)
            with TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    native.capture(adapter, actors(case), case, site(), Path(tmp))
                self.assertTrue(adapter.braked)
                self.assertEqual(adapter.destroyed, ['property', 'crossing_vehicle', 'ego'])
                self.assertFalse((Path(tmp) / 'native-receipt.json').exists())

    def test_saved_rejoin_rejects_tamper_and_missing_sources(self):
        case = encounter.CASES[0]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = native.capture(Adapter(), actors(case), case, site(), root)
            camera = root / 'original-cameras.jsonl'
            camera.write_bytes(camera.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                saved_audit.audit_native_acquisition(root, receipt)
            camera.unlink()
            with self.assertRaisesRegex(ValueError, 'missing or redirected'):
                saved_audit.audit_native_acquisition(root, receipt)

    def test_rejects_unsourced_site_and_premises_mismatch(self):
        case = encounter.CASES[6]
        adapter = Adapter()
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'public access basis mismatch'):
                native.capture(adapter, actors(case), case, site(), Path(tmp))
            invalid = site(); invalid['site_sha256'] = ''
            with self.assertRaisesRegex(ValueError, 'site/map/camera source missing'):
                native.capture(adapter, actors(encounter.CASES[0]), encounter.CASES[0], invalid, Path(tmp))


if __name__ == '__main__':
    unittest.main()
