import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

construct = module('construct')
native = module('native_device')
CASE = 'testing__C111748__NRS-484B-403-2__motor_vehicle_driver__prohibited_obey'


def site():
    return {'case_id': CASE, 'map_name': 'Town01', 'map_sha256': 'map',
            'highway_status': {'source_sha256': 'highway'}, 'ego_blueprint': 'vehicle.test',
            'ego_spawn': [1, 2], 'device_blueprint': 'static.prop.sign',
            'u_turn_route': [{'road_id': 1, 'lane_id': 1}, {'road_id': 1, 'lane_id': 1, 'junction_id': 1}, {'road_id': 1, 'lane_id': -1}],
            'device': {'authority_source_sha256': 'authority', 'legal_consistency_source_sha256': 'legal',
                       'display_source_sha256': 'display', 'governed_approach': 'A',
                       'position_xy_m': [1, 2], 'prohibits_u_turn': True}}


def packet(turn=False):
    d = site()['device'].copy()
    d['device_id'] = 77
    return {'case_id': CASE, 'actor': 'motor_vehicle_driver', 'map_sha256': 'map', 'route_sha256': 'route',
            'highway_status': {'source_sha256': 'highway'}, 'device': d, 'ego_id': 42,
            'frames': [{'frame': i, 'time_s': i / 20, 'ego': {'id': 42, 'road_id': 1, 'lane_id': -1 if turn and i == 3 else 1, 'x': i, 'y': 0, 'yaw_deg': 180 if turn and i == 3 else 0,
                       'approach_id': 'A', 'u_turn_in_progress': turn and i == 2},
                       'device_readback': {'device_id': 77, 'prohibits_u_turn': True, 'visible_to_ego': i >= 1}}
                      for i in range(4)]}


class Tests(unittest.TestCase):
    def dump(self, obj):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        p = Path(tmp.name) / 'source.json'
        raw = json.dumps(obj).encode()
        p.write_bytes(raw)
        return p, hashlib.sha256(raw).hexdigest()

    def test_site_valid_and_hash_guard(self):
        p, h = self.dump(site())
        self.assertEqual(construct.load_site(p, h, CASE)['map_name'], 'Town01')
        with self.assertRaisesRegex(construct.ConstructionError, 'hash'):
            construct.load_site(p, 'wrong', CASE)

    def test_site_rejects_non_official_and_wrong_lane(self):
        s = site(); del s['device']['authority_source_sha256']
        p, h = self.dump(s)
        with self.assertRaises(construct.ConstructionError):
            construct.load_site(p, h, CASE)
        s = site(); s['u_turn_route'][-1]['lane_id'] = 1
        p, h = self.dump(s)
        with self.assertRaisesRegex(construct.ConstructionError, 'opposite'):
            construct.load_site(p, h, CASE)

    def test_native_obey_and_turn(self):
        for turning in (False, True):
            p, h = self.dump(packet(turning))
            self.assertEqual(native.analyze(p, case_id=CASE, sha256=h)['turn_observed'], turning)

    def test_native_rejects_stale_display_and_frame_gap(self):
        s = packet(); s['frames'][2]['device_readback']['prohibits_u_turn'] = False
        p, h = self.dump(s)
        with self.assertRaisesRegex(native.SourceError, 'display'):
            native.analyze(p, case_id=CASE, sha256=h)
        s = packet(); s['frames'][2]['frame'] = 9
        p, h = self.dump(s)
        with self.assertRaisesRegex(native.SourceError, 'noncontiguous'):
            native.analyze(p, case_id=CASE, sha256=h)

    def test_native_rejects_missing_visibility_and_wrong_hash(self):
        s = packet();
        for f in s['frames']:
            f['device_readback']['visible_to_ego'] = False
        p, h = self.dump(s)
        with self.assertRaisesRegex(native.SourceError, 'visibility'):
            native.analyze(p, case_id=CASE, sha256=h)
        with self.assertRaisesRegex(native.SourceError, 'hash'):
            native.analyze(p, case_id=CASE, sha256='wrong')

    def test_native_rejects_visibility_after_turn(self):
        s = packet(True)
        for i, f in enumerate(s['frames']):
            f['device_readback']['visible_to_ego'] = i == 3
        p, h = self.dump(s)
        with self.assertRaisesRegex(native.SourceError, 'before turn'):
            native.analyze(p, case_id=CASE, sha256=h)

    def test_native_rejects_turn_claim_without_reversal(self):
        s = packet(True); s['frames'][-1]['ego']['yaw_deg'] = 0
        p, h = self.dump(s)
        with self.assertRaisesRegex(native.SourceError, 'reversal'):
            native.analyze(p, case_id=CASE, sha256=h)
        s = packet(True); s['frames'][-1]['ego']['lane_id'] = 1
        p, h = self.dump(s)
        with self.assertRaisesRegex(native.SourceError, 'opposite'):
            native.analyze(p, case_id=CASE, sha256=h)
