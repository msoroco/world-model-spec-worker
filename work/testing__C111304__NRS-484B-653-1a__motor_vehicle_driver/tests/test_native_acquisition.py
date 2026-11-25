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
    def __init__(self, *, bad_camera=None, bad_frame=None, bad_occupancy=False,
                 case=None, bad_release=False):
        self.frame = 100
        self.destroyed = []
        self.braked = False
        self.bad_camera = bad_camera
        self.bad_frame = bad_frame
        self.bad_occupancy = bad_occupancy
        self.case = case or encounter.CASES[0]
        self.bad_release = bad_release

    def tick(self):
        frame = self.frame
        self.frame += 1
        return frame, (frame - 100) / 20

    def read_actor(self, actor):
        role = actor
        packet = {'original_frame': self.frame - 1, 'id': actor,
                  'xy': [float(self.frame - 100), float(len(actor))],
                  'z': 0.0, 'heading_deg': 0.0,
                  'speed_mps': 2.0, 'blueprint': role + '-blueprint'}
        if role == 'occupant':
            packet['vehicle_id'] = 'wrong' if self.bad_occupancy else 'crossing_vehicle'
        if self.bad_frame == role:
            packet['original_frame'] += 1
        return packet

    def read_control(self, ego, crossing):
        return {'original_frame': self.frame - 1, 'ego_command': 'drive',
                'crossing_command': 'drive',
                'ego_target_speed_mps': self.case.ego_speed_mps,
                'crossing_target_speed_mps': self.case.crossing_speed_mps,
                'crossing_release_s': self.case.crossing_release_s + (1 if self.bad_release else 0)}

    def read_camera(self, name):
        frame = self.frame - 1
        if self.bad_camera == name:
            frame += 1
        return frame, f'{name}-{frame}'.encode()

    def brake(self, ego):
        self.braked = True

    def destroy(self, actor):
        self.destroyed.append(actor)


class TimingAdapter(Adapter):
    def read_actor(self, actor):
        packet = super().read_actor(actor)
        if actor == 'occupant':
            packet['xy'][1] += self.case.crossing_release_s
        return packet


class PropertyAdapter(Adapter):
    def read_actor(self, actor):
        packet = super().read_actor(actor)
        if actor == 'property':
            packet['xy'][1] += 0.0 if self.case.case_id == 'property_near' else 8.0
        return packet


class DirectionAdapter(Adapter):
    def read_actor(self, actor):
        packet = super().read_actor(actor)
        if actor == 'ego' and self.case.approach == 'southbound':
            packet['xy'][0] = -packet['xy'][0]
        return packet


def site():
    return {'site_sha256': 'a' * 64, 'map_sha256': 'b' * 64,
            'camera_plan_sha256': 'c' * 64, 'public_access_basis': 'highway'}


def actors(case):
    return {'case_id': case.case_id, 'ego': 'ego', 'crossing_vehicle': 'crossing_vehicle',
            'occupant': 'occupant', 'property': 'property',
            'owned': ('ego', 'crossing_vehicle', 'property')}


class NativeAcquisitionTests(unittest.TestCase):
    def test_saved_approach_pair_reopens_opposed_original_motion(self):
        north, south = encounter.CASES[0], encounter.CASES[2]
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'north', Path(tmp) / 'south'
            left.mkdir(); right.mkdir()
            native.capture(DirectionAdapter(case=north), actors(north), north, site(), left)
            native.capture(DirectionAdapter(case=south), actors(south), south, site(), right)
            result = saved_audit.audit_saved_approach_pair(left, right)
            self.assertEqual(result['comparison_id'], 'highway_person_approach_direction')
            self.assertAlmostEqual(result['direction_cosine'], -1.0)
            self.assertFalse(result['physical_completion'])
            with self.assertRaisesRegex(ValueError, 'exact case mismatch'):
                saved_audit.audit_saved_approach_pair(right, left)
            packet = right / 'original-packets.jsonl'
            packet.write_bytes(packet.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                saved_audit.audit_saved_approach_pair(left, right)

    def test_saved_approach_pair_rejects_same_motion_and_changed_site(self):
        north, south = encounter.CASES[0], encounter.CASES[2]
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'north', Path(tmp) / 'south'
            left.mkdir(); right.mkdir()
            native.capture(Adapter(case=north), actors(north), north, site(), left)
            native.capture(Adapter(case=south), actors(south), south, site(), right)
            with self.assertRaisesRegex(ValueError, 'directions not opposed'):
                saved_audit.audit_saved_approach_pair(left, right)
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'north', Path(tmp) / 'south'
            left.mkdir(); right.mkdir()
            native.capture(DirectionAdapter(case=north), actors(north), north, site(), left)
            changed = site(); changed['map_sha256'] = 'd' * 64
            native.capture(DirectionAdapter(case=south), actors(south), south, changed, right)
            with self.assertRaisesRegex(ValueError, 'fixed condition changed: map_sha256'):
                saved_audit.audit_saved_approach_pair(left, right)

    def test_saved_property_pair_reopens_sources_and_measures_position(self):
        near, far = encounter.CASES[4:6]
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'near', Path(tmp) / 'far'
            left.mkdir(); right.mkdir()
            native.capture(PropertyAdapter(case=near), actors(near), near, site(), left)
            native.capture(PropertyAdapter(case=far), actors(far), far, site(), right)
            result = saved_audit.audit_saved_property_pair(left, right)
            self.assertEqual(result['comparison_id'], 'highway_property_position')
            self.assertLess(*result['min_ego_property_center_distance_m'])
            self.assertNotEqual(*result['first_property_xy'])
            self.assertFalse(result['physical_completion'])
            with self.assertRaisesRegex(ValueError, 'exact case mismatch'):
                saved_audit.audit_saved_property_pair(right, left)
            packet = right / 'original-packets.jsonl'
            packet.write_bytes(packet.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                saved_audit.audit_saved_property_pair(left, right)

    def test_saved_property_pair_rejects_unchanged_property_and_site(self):
        near, far = encounter.CASES[4:6]
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'near', Path(tmp) / 'far'
            left.mkdir(); right.mkdir()
            native.capture(Adapter(case=near), actors(near), near, site(), left)
            native.capture(Adapter(case=far), actors(far), far, site(), right)
            with self.assertRaisesRegex(ValueError, 'position difference missing'):
                saved_audit.audit_saved_property_pair(left, right)
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'near', Path(tmp) / 'far'
            left.mkdir(); right.mkdir()
            native.capture(PropertyAdapter(case=near), actors(near), near, site(), left)
            changed = site(); changed['map_sha256'] = 'd' * 64
            native.capture(PropertyAdapter(case=far), actors(far), far, changed, right)
            with self.assertRaisesRegex(ValueError, 'fixed condition changed: map_sha256'):
                saved_audit.audit_saved_property_pair(left, right)

    def test_saved_timing_pair_reopens_both_original_attempts(self):
        early, late = encounter.CASES[0:2]
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'early', Path(tmp) / 'late'
            left.mkdir(); right.mkdir()
            native.capture(TimingAdapter(case=early), actors(early), early, site(), left)
            native.capture(TimingAdapter(case=late), actors(late), late, site(), right)
            result = saved_audit.audit_saved_timing_pair(
                left, right, 'highway_person_north_timing')
            self.assertEqual(result['crossing_release_s'], [1.0, 4.0])
            self.assertNotEqual(*result['min_ego_occupant_center_distance_m'])
            self.assertFalse(result['actual_pixels'])
            with self.assertRaisesRegex(ValueError, 'exact case mismatch'):
                saved_audit.audit_saved_timing_pair(
                    right, left, 'highway_person_north_timing')
            with self.assertRaisesRegex(ValueError, 'unsupported exact timing comparison'):
                saved_audit.audit_saved_timing_pair(left, right, 'approach_direction')
            source = right / 'original-packets.jsonl'
            source.write_bytes(source.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                saved_audit.audit_saved_timing_pair(
                    left, right, 'highway_person_north_timing')

    def test_saved_timing_pair_rejects_unchanged_encounter(self):
        early, late = encounter.CASES[0:2]
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'early', Path(tmp) / 'late'
            left.mkdir(); right.mkdir()
            native.capture(Adapter(case=early), actors(early), early, site(), left)
            native.capture(Adapter(case=late), actors(late), late, site(), right)
            with self.assertRaisesRegex(ValueError, 'measured encounter difference missing'):
                saved_audit.audit_saved_timing_pair(
                    left, right, 'highway_person_north_timing')

    def test_saved_timing_pair_rejects_changed_fixed_site(self):
        early, late = encounter.CASES[0:2]
        with TemporaryDirectory() as tmp:
            left, right = Path(tmp) / 'early', Path(tmp) / 'late'
            left.mkdir(); right.mkdir()
            native.capture(TimingAdapter(case=early), actors(early), early, site(), left)
            changed_site = site(); changed_site['map_sha256'] = 'd' * 64
            native.capture(TimingAdapter(case=late), actors(late), late,
                           changed_site, right)
            with self.assertRaisesRegex(ValueError, 'fixed condition changed: map_sha256'):
                saved_audit.audit_saved_timing_pair(
                    left, right, 'highway_person_north_timing')

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
                        {'bad_occupancy': True}, {'bad_release': True}):
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

    def test_sealed_trace_and_frame_map_reject_tamper(self):
        case = encounter.CASES[0]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = native.capture(Adapter(), actors(case), case, site(), root)
            for name in ('trace.jsonl', 'video_frames.jsonl'):
                source = root / name
                original = source.read_bytes()
                source.write_bytes(original + b'\n')
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    saved_audit.audit_native_acquisition(root, receipt)
                source.write_bytes(original)

    def test_rejects_unsourced_site_and_premises_mismatch(self):
        case = encounter.CASES[6]
        adapter = Adapter()
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'public access basis mismatch'):
                native.capture(adapter, actors(case), case, site(), Path(tmp))
            invalid = site(); invalid['site_sha256'] = ''
            with self.assertRaisesRegex(ValueError, 'site/map/camera source missing'):
                native.capture(adapter, actors(encounter.CASES[0]), encounter.CASES[0], invalid, Path(tmp))

    def test_saved_measurement_finalizer_rejoins_sealed_sources(self):
        case = encounter.CASES[0]
        with TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            native.capture(Adapter(), actors(case), case, site(), attempt)
            result = saved_audit.finalize_saved_measurements(attempt, case)
            self.assertEqual(result['measurements']['frame_count'], 900)
            self.assertEqual(result['measurements']['min_ego_occupant_center_distance_m'], 5.0)
            self.assertFalse(result['physical_completion'])
            self.assertIsNone(result['legal_judgment'])
            with self.assertRaisesRegex(ValueError, 'exact case mismatch'):
                saved_audit.finalize_saved_measurements(attempt, encounter.CASES[1])
            source = attempt / 'original-history.jsonl'
            source.write_bytes(source.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                saved_audit.finalize_saved_measurements(attempt, case)

    def test_late_case_control_packet_is_exact(self):
        case = encounter.CASES[1]
        with TemporaryDirectory() as tmp:
            attempt = Path(tmp)
            receipt = native.capture(Adapter(case=case), actors(case), case, site(), attempt)
            self.assertEqual(receipt['crossing_release_s'], 4.0)
            self.assertEqual(saved_audit.audit_native_acquisition(attempt, receipt)['frame_count'], 900)
            receipt['crossing_release_s'] = 1.0
            with self.assertRaisesRegex(ValueError, 'differs from exact case'):
                saved_audit.audit_native_acquisition(attempt, receipt)


if __name__ == '__main__':
    unittest.main()
